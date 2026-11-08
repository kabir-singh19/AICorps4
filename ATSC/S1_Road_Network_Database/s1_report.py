"""S1 data report: map-matching rate (FSR 3.2.1.4), input validation (3.2.3.1.2), HIN and
streetlight status, source as-of dates. Reads the database only; writes one JSON file.

    python s1_report.py --network v1_2022 --hin-version <v> --out ../integration/artifacts/s1_data_report.json
"""
import argparse
import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest  # noqa: E402


def rows(cur, sql, params=()):
    cur.execute(sql, params)
    cols = [d.name for d in cur.description]
    return [{c: (v.isoformat() if isinstance(v, (date, datetime)) else float(v) if hasattr(v, "as_integer_ratio") and not isinstance(v, (int, float)) else v)
             for c, v in zip(cols, r)} for r in cur.fetchall()]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--network", default="v1_2022")
    p.add_argument("--hin-version", required=True)
    p.add_argument("--streetlight-file", help="City streetlight GIS layer, if one was delivered")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    with ingest.connect() as conn, conn.cursor() as cur:
        match = rows(cur, "SELECT * FROM tasc.match_rate WHERE network_version = %s", (a.network,))
        unmatched_fsi = rows(cur, """
            SELECT c.crash_id::text, c.crash_date, c.severity, c.street_name, m.reason,
                   round(m.distance_m::numeric, 1) AS distance_m
            FROM tasc.crash c JOIN tasc.crash_match m USING (crash_id)
            WHERE m.network_version = %s AND m.status = 'unmatched' AND c.severity IN ('K','A')
              AND m.reason NOT IN ('no_coordinates', 'outside_city')
            ORDER BY c.crash_date""", (a.network,))
        reasons = rows(cur, """SELECT status, coalesce(reason, '') AS reason, count(*) AS crashes,
                                      count(*) FILTER (WHERE c.severity IN ('K','A')) AS fsi
                               FROM tasc.crash_match m JOIN tasc.crash c USING (crash_id)
                               WHERE network_version = %s GROUP BY 1, 2 ORDER BY 3 DESC""", (a.network,))
        ingest_runs = rows(cur, """SELECT run_id, source, file_name, rows_total, rows_bad, bad_pct, status
                                   FROM tasc.ingest_run ORDER BY run_id""")
        severity = rows(cur, "SELECT severity, count(*) FROM tasc.crash GROUP BY 1 ORDER BY 1")
        years = rows(cur, "SELECT crash_year, count(*) AS crashes, count(*) FILTER (WHERE is_fsi) AS fsi FROM tasc.crash GROUP BY 1 ORDER BY 1")
        sources = rows(cur, "SELECT source, version, role, as_of_date, available_as_of FROM tasc.s2_source_availability ORDER BY role, source")
        hin = rows(cur, """
            SELECT s.site_type, count(*) AS sites, count(*) FILTER (WHERE h.in_hin) AS in_hin,
                   sum(v.network_length_mi) AS network_mi,
                   sum(v.network_length_mi) FILTER (WHERE h.in_hin) AS hin_mi
            FROM tasc.s2_hin_site h JOIN tasc.site s USING (site_id, network_version)
            JOIN tasc.s2_site_scope v USING (site_id, network_version)
            WHERE h.network_version = %s AND h.hin_version = %s AND v.in_analysis_area
            GROUP BY 1 ORDER BY 1""", (a.network, a.hin_version))
        lamps = rows(cur, """SELECT source, count(*) AS street_lamps FROM tasc.osm_feature
                             WHERE grp = 'street_lamp' GROUP BY 1 ORDER BY 1""")
        lighting = rows(cur, """SELECT feature_set, osm_source, lamp_points, lit_tagged_roads, sites_with_lamp,
                                       dropped_constant FROM tasc.lighting_gap WHERE network_version = %s
                                ORDER BY feature_set""", (a.network,))
        segs = rows(cur, """SELECT count(*) AS segments,
                                   count(*) FILTER (WHERE length_m BETWEEN 80.4672 AND 241.4016) AS in_range,
                                   round(min(length_m)::numeric / 1609.344, 4) AS min_mi,
                                   round(max(length_m)::numeric / 1609.344, 4) AS max_mi
                            FROM tasc.site WHERE network_version = %s AND site_type = 'segment'""", (a.network,))
        folds = rows(cur, """SELECT action, count(*) AS pieces, round(sum(length_m)::numeric / 1609.344, 2) AS miles
                             FROM tasc.site_fold WHERE network_version = %s GROUP BY 1 ORDER BY 2 DESC""", (a.network,))
    m = match[0] if match else {}
    total_mi = sum(float(r["network_mi"] or 0) for r in hin)
    hin_mi = sum(float(r["hin_mi"] or 0) for r in hin)
    loaded_crash_files = [r for r in ingest_runs if r["source"] in ("cris", "cris_details")]
    report = {
        "network_version": a.network,
        "map_matching_fsr_3_2_1_4": {
            "fsi_geocoded_in_city": m.get("fsi_geocoded"), "fsi_matched": m.get("fsi_matched"),
            "fsi_match_pct": float(m["fsi_match_pct"]) if m else None, "threshold_pct": 95.0,
            "result": "PASS" if m and float(m["fsi_match_pct"]) >= 95 else "FAIL",
            "unmatched_geocoded_fsi": unmatched_fsi, "all_crash_match_status": reasons,
            "note": "Every crash has a crash_match row with status and reason (tasc.crash_match)."},
        "input_validation_fsr_3_2_3_1_2": {
            "rule": "ingest.py rejects a whole file when more than 2% of records fail count, required-field, "
                    "coordinate-bounds, date-range or severity checks",
            "files_loaded": len(loaded_crash_files),
            "max_bad_pct": max((float(r["bad_pct"]) for r in loaded_crash_files), default=None),
            "ingest_runs": ingest_runs,
            "stop_test": "tests/test_validate.py: test_over_two_percent_bad_stops (3% bad file stops) and "
                         "test_exactly_two_percent_loads"},
        "crashes_by_severity": severity, "crashes_by_year": years,
        "hin_method_a": {"hin_version": a.hin_version, "rule": "segment: >=50% of length within 30 m; "
                         "intersection: center within 30 m", "by_site_type": hin,
                         "hin_share_of_network_length": hin_mi / total_mi if total_mi else None},
        "streetlights_if_04": (
            {"status": "delivered", "file": a.streetlight_file} if a.streetlight_file else
            {"status": "city GIS not delivered; ICD fallback applied",
             "detail": "Per ICD IF-04 the fallback is OSM lighting (sql/11_lighting.sql): osm_street_lamps_50m and "
             "osm_lit_share are built as dated site features; a feature that is constant everywhere is dropped "
             "and the gap is logged in tasc.lighting_gap.",
             "osm_street_lamp_points": lamps, "lighting_gap": lighting}),
        "site_definition_fsr_3_2_1_2": {
            "rule": "segments 0.1 mi +/- 0.05 mi; links under 0.05 mi folded into the adjacent intersection "
                    "(inside its 250 ft zone) or joined to the next segment (sql/10_short_links.sql)",
            "segments": segs[0] if segs else None, "folded": folds,
            "result": "PASS" if segs and segs[0]["segments"] == segs[0]["in_range"] else "FAIL"},
        "sources": sources,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(report, f, indent=2, default=str)
        f.write("\n")
    print(json.dumps({"event": "s1_report", "fsi_match_pct": report["map_matching_fsr_3_2_1_4"]["fsi_match_pct"],
                      "hin_share": report["hin_method_a"]["hin_share_of_network_length"], "out": a.out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
