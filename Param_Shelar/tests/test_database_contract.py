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
