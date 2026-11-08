import os
from datetime import date

import pytest

from database import NOT_RECORDED_SOURCE, _fill_absent_features, _json_value, relation


def test_snapshot_dates_are_iso():
    assert _json_value({"d": date(2022,12,31)}) == {"d": "2022-12-31"}


def test_database_identifiers_reject_injection():
    pytest.importorskip("psycopg")
    for name in ("site;DROP TABLE site", "tasc.site;drop", "site", "tasc.site.extra"):
        with pytest.raises(ValueError):
            relation(name)


def test_absent_intersection_features_become_explicit_nulls():
    sites = [{"site_id": "1", "as_of_date": "2019-12-31"}, {"site_id": "2", "as_of_date": "2019-12-31"}]
    features = [{"site_id": "1", "feature_name": "speed_limit", "value": 45,
                 "as_of_date": "2019-12-31", "source": "roadway_inventory_2019"}]
    added = _fill_absent_features(sites, features, ["speed_limit"], "v0", {"as_of_date": "2022-12-31"})
    assert features[1] == {"site_id": "2", "feature_name": "speed_limit", "value": None,
                           "as_of_date": "2019-12-31", "source": NOT_RECORDED_SOURCE}
    assert added == [{"source": NOT_RECORDED_SOURCE, "version": "v0", "as_of_date": "2022-12-31",
                      "available_as_of": "2022-12-31", "role": "predictor"}]


def test_nothing_added_when_every_feature_is_present():
    sites = [{"site_id": "1", "as_of_date": "2019-12-31"}]
    features = [{"site_id": "1", "feature_name": "speed_limit", "value": 45}]
    assert _fill_absent_features(sites, features, ["speed_limit"], "v0", {}) == []
    assert len(features) == 1


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


class _FakeConnection:
    """Answers load_snapshot's queries in the order it issues them."""
    def __init__(self, results):
        self.results = list(results)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params=None):
        return _Result(self.results.pop(0))


def _fake_database(hin_rows):
    site = lambda sid: {"site_id": sid, "site_type": "segment", "as_of_date": "2019-12-31",
                        "risk_length_mi": .1, "network_length_mi": .1, "road_name": "Texas Ave"}
    test = [{"crash_id": "9", "crash_date": "2024-01-01", "severity": "A", "in_analysis_area": True, "site_id": "1"}]
    found = [{"relation": "view"}]
    return [[], found, found, found, [site("1"), site("2")], [], [], test, [{"n": len(test)}], [], hin_rows]


def test_partial_hin_view_blocks_loading(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    from database import load_snapshot
    config = {"network_version": "v0", "feature_set": "backtest_2022", "site_scope_view": "tasc.a",
              "crash_scope_view": "tasc.b", "source_registry_view": "tasc.c", "hin_view": "tasc.d",
              "metadata": {"hin_version": "v1", "as_of_date": "2022-12-31"}}
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    for hin_rows in ([{"site_id": "1", "in_hin": True}],
                     [{"site_id": "1", "in_hin": True}, {"site_id": "1", "in_hin": False}, {"site_id": "2", "in_hin": False}]):
        monkeypatch.setattr(psycopg, "connect", lambda *a, rows=hin_rows, **k: _FakeConnection(_fake_database(rows)))
        with pytest.raises(ValueError, match="duplicates or misses sites"):
            load_snapshot(config, ["speed_limit"])


def test_hin_example_config_is_blocked_until_real_values_exist():
    import copy
    import json
    from pathlib import Path
    from leakage import validate_snapshot
    from make_demo import demo_snapshot
    config = json.loads((Path(__file__).resolve().parents[1]/"config/corridor_diagnostic_hin.example.json").read_text())
    snapshot = demo_snapshot(n_sites=10)
    metadata = copy.deepcopy(config["database"]["metadata"])
    snapshot["metadata"].update({**metadata, "sources": snapshot["metadata"]["sources"]})
    with pytest.raises(ValueError):
        validate_snapshot(snapshot, config["features"])


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set: no live S1 database")
def test_live_s1_database_meets_the_snapshot_contract():
    import json
    from pathlib import Path
    import psycopg
    from database import load_snapshot
    from leakage import validate_snapshot
    config = json.loads((Path(__file__).resolve().parents[1]/"config/corridor_diagnostic.example.json").read_text())
    snapshot = load_snapshot(config["database"], config["features"])
    result = validate_snapshot(snapshot, config["features"])
    assert result["analysis_scope"] == "corridor_diagnostic" and not result["full_network"]
    assert not result["hin_available"]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        n_sites = conn.execute("SELECT count(*) FROM tasc.s2_site_scope WHERE network_version=%s AND in_analysis_area",
                               (config["database"]["network_version"],)).fetchone()[0]
        writable = conn.execute("SELECT has_table_privilege(current_user, 'tasc.crash', 'INSERT')").fetchone()[0]
    assert result["sites"] == n_sites
    assert not writable, "S2 must connect with a read-only role"
