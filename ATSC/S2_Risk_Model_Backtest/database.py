"""IF-09 snapshot adapter. Read-only; never creates or modifies S1 tables.

S1 must first provide the agreed scope, HIN and provenance views described in
docs/interfaces.md (docs/s1_views_proposal.sql is a draft for S1 to review). Corridor-only data
runs only with analysis_scope "corridor_diagnostic", and every output says it is not the FSR
3.2.1.1 network.
"""
from __future__ import annotations

import os
from datetime import date, datetime

# Registered source for site/feature pairs S1 does not store, such as road attributes at
# intersections. Their values are null and training imputes them with missing indicators.
NOT_RECORDED_SOURCE = "s1_not_recorded"


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(v) for v in value]
    return value


def relation(name):
    from psycopg import sql
    pieces = name.split(".")
    if len(pieces) != 2 or not all(p.replace("_", "").isalnum() for p in pieces):
        raise ValueError("database relation must be schema.name")
    return sql.Identifier(*pieces)


def load_snapshot(db_config, feature_names, history_start=2016, history_end=2022):
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL environment variable is required")
    for field in ("network_version", "feature_set", "metadata", "site_scope_view", "crash_scope_view", "source_registry_view"):
        if field not in db_config:
            raise ValueError(f"database configuration missing {field}")
    version, feature_set = db_config["network_version"], db_config["feature_set"]
    scope = relation(db_config["site_scope_view"])
    area = relation(db_config["crash_scope_view"])
    registry = relation(db_config["source_registry_view"])
    with psycopg.connect(url, row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        for name in (db_config["site_scope_view"], db_config["crash_scope_view"], db_config["source_registry_view"]):
            if conn.execute("SELECT to_regclass(%s) AS relation", (name,)).fetchone()["relation"] is None:
                raise ValueError(f"missing S1 integration view: {name}; see docs/interfaces.md")
        sites = conn.execute(sql.SQL("""
            SELECT s.site_id::text AS site_id, s.site_type, s.as_of_date,
                   v.risk_length_mi, v.network_length_mi, v.road_name
            FROM tasc.site s JOIN {} v USING (site_id, network_version)
            WHERE s.network_version=%s AND v.in_analysis_area
            ORDER BY s.site_id
        """).format(scope), (version,)).fetchall()
        features = conn.execute(sql.SQL("""
            SELECT f.site_id::text AS site_id, f.feature_name, f.value_num, f.value_text, f.as_of_date, f.source
            FROM tasc.site_feature f JOIN tasc.site s USING (site_id)
            JOIN {} v USING (site_id, network_version)
            WHERE s.network_version=%s AND f.feature_set=%s AND v.in_analysis_area
              AND f.feature_name=ANY(%s)
            ORDER BY f.site_id, f.feature_name
        """).format(scope), (version, feature_set, feature_names)).fetchall()
        for feature in features:
            feature["value"] = feature.pop("value_num")
            text = feature.pop("value_text")
            if text is not None:
                if feature["value"] is not None:
                    raise ValueError("feature has both numeric and text values")
                feature["value"] = text
        history = conn.execute(sql.SQL("""
            SELECT m.site_id::text AS site_id, c.crash_year AS year, count(*)::integer AS crashes,
                   count(*) FILTER (WHERE c.severity!='U')::integer AS known_crashes,
                   count(*) FILTER (WHERE c.severity IN ('K','A'))::integer AS fsi_crashes
            FROM tasc.crash c JOIN tasc.crash_match m USING (crash_id)
            JOIN {} v ON v.site_id=m.site_id AND v.network_version=m.network_version
            WHERE m.network_version=%s AND m.status='matched' AND v.in_analysis_area
              AND c.crash_year BETWEEN %s AND %s
            GROUP BY m.site_id, c.crash_year ORDER BY m.site_id, c.crash_year
        """).format(scope), (version, history_start, history_end)).fetchall()
        test = conn.execute(sql.SQL("""
            SELECT c.crash_id::text AS crash_id, c.crash_date, c.severity, a.in_analysis_area,
                   CASE WHEN v.in_analysis_area AND m.status='matched' THEN m.site_id::text END AS site_id
            FROM tasc.crash c JOIN {} a USING (crash_id)
            LEFT JOIN tasc.crash_match m ON m.crash_id=c.crash_id AND m.network_version=%s
            LEFT JOIN {} v ON v.site_id=m.site_id AND v.network_version=m.network_version
            WHERE c.crash_year BETWEEN 2023 AND 2025 ORDER BY c.crash_id
        """).format(area, scope), (version,)).fetchall()
        total_test = conn.execute("SELECT count(*) AS n FROM tasc.crash WHERE crash_year BETWEEN 2023 AND 2025").fetchone()["n"]
        if len(test) != total_test:
            raise ValueError("crash-scope view must classify every test crash once, including unmatched/no-coordinate records")
        sources = conn.execute(sql.SQL("""
            SELECT source, version, as_of_date, available_as_of, role FROM {}
            WHERE network_version=%s AND feature_set=%s ORDER BY source
        """).format(registry), (version, feature_set)).fetchall()
        sources.extend(_fill_absent_features(sites, features, feature_names, version, db_config["metadata"]))
        hin_view = db_config.get("hin_view")
        if hin_view:
            hin = conn.execute(sql.SQL("""
                SELECT site_id::text AS site_id, in_hin FROM {}
                WHERE network_version=%s AND hin_version=%s
            """).format(relation(hin_view)), (version, db_config["metadata"]["hin_version"])).fetchall()
            mapping = {row["site_id"]: row["in_hin"] for row in hin}
            if len(mapping) != len(hin) or not {s["site_id"] for s in sites} <= mapping.keys():
                raise ValueError("HIN integration view contains duplicates or misses sites")
            for site in sites:
                site["in_hin"] = mapping[site["site_id"]]
        meta = {**db_config["metadata"], "network_version": version, "feature_set": feature_set, "sources": sources}
    return _json_value({"metadata": meta, "sites": sites, "features": features,
                        "history": history, "test_crashes": test})


def _fill_absent_features(sites, features, feature_names, network_version, metadata):
    """Add an explicit null record for every selected feature S1 does not store for a site.

    Returns the registry entry for those records (empty if nothing was absent), so they carry
    provenance like every other predictor.
    """
    present = {(f["site_id"], f["feature_name"]) for f in features}
    absent = [(site, name) for site in sites for name in feature_names
              if (site["site_id"], name) not in present]
    for site, name in absent:
        features.append({"site_id": site["site_id"], "feature_name": name, "value": None,
                         "as_of_date": site["as_of_date"], "source": NOT_RECORDED_SOURCE})
    if not absent:
        return []
    as_of = metadata.get("as_of_date", "2022-12-31")
    return [{"source": NOT_RECORDED_SOURCE, "version": network_version, "as_of_date": as_of,
             "available_as_of": as_of, "role": "predictor"}]


def result_payload(bundle):
    """Contract payload for S1's future transactional run-import service.

    Deliberately no implicit SQL writer to nonexistent result tables. S1 must
    ingest this atomically before S3/S4 read it through the shared database.
    """
    manifest = bundle["manifest"]
    run_id = manifest["run_id"]
    return {"schema_version": 1,
            "runs": [{key: manifest[key] for key in ("run_id", "created", "code_version", "data_versions", "as_of_date", "seed", "hyperparameters", "published")}],
            "predictions": [{"run_id": run_id, "method": method, **row}
                            for method, frame in bundle["predictions"].items() for row in frame.to_dict("records")],
            "explanations": [{"run_id": run_id, **row} for row in bundle["explanations"]],
            "backtest": [{"run_id": run_id, "method": m, **row}
                         for m, row in bundle["backtest"]["primary"]["methods"].items()],
            "evaluation": bundle["backtest"], "calibration": bundle["calibration"]}
