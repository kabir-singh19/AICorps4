"""Database tests: need the PostGIS container running and a built network. Skipped otherwise.

    docker compose up -d
    .venv/bin/python -m unittest discover -s tests -v

Every test runs inside a transaction that is rolled back, so the database is left unchanged.
"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ingest  # noqa: E402

try:
    import psycopg
    _conn = ingest.connect()
    _conn.close()
    DB_UP = True
except Exception:  # psycopg missing or database not running
    DB_UP = False


@unittest.skipUnless(DB_UP, "database not reachable")
class LeakageTests(unittest.TestCase):
    """FSR: the backtest refuses any feature dated after 31 Dec 2022."""

    def setUp(self):
        self.conn = ingest.connect()
        self.cur = self.conn.cursor()
        self.cur.execute("SELECT site_id FROM tasc.site WHERE site_type = 'segment' LIMIT 1")
        row = self.cur.fetchone()
        if row is None:
            self.skipTest("no sites built yet")
        self.site_id = row[0]

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert(self, feature_set, as_of):
        self.cur.execute(
            """INSERT INTO tasc.site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
               VALUES (%s, %s, 'seeded_test_feature', 1, %s, 'test')""",
            (self.site_id, feature_set, as_of),
        )

    def test_post_cutoff_feature_is_refused_from_backtest(self):
        with self.assertRaises(psycopg.errors.RaiseException) as ctx:
            self.insert("backtest_2022", "2024-06-30")
        self.assertIn("Leakage check", str(ctx.exception))

    def test_feature_dated_on_cutoff_is_accepted(self):
        self.insert("backtest_2022", "2022-12-31")

    def test_post_cutoff_feature_is_accepted_into_current(self):
        self.insert("current", "2024-06-30")

    def test_no_backtest_feature_is_dated_after_cutoff(self):
        self.cur.execute("""SELECT count(*) FROM tasc.site_feature
                            WHERE feature_set = 'backtest_2022' AND as_of_date > DATE '2022-12-31'""")
        self.assertEqual(self.cur.fetchone()[0], 0)


@unittest.skipUnless(DB_UP, "database not reachable")
class S2InterfaceTests(unittest.TestCase):
    """The views S2 reads (sql/05_s2_interface.sql) keep their contract."""

    def setUp(self):
        self.conn = ingest.connect()
        self.cur = self.conn.cursor()
        self.cur.execute("SELECT to_regclass('tasc.s2_site_scope')")
        if self.cur.fetchone()[0] is None:
            self.skipTest("S2 views not created yet (run sql/05_s2_interface.sql)")

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def one(self, sql):
        self.cur.execute(sql)
        return self.cur.fetchone()

    def test_every_site_once_with_positive_exposure(self):
        sites, scoped, distinct, bad = self.one("""
            SELECT (SELECT count(*) FROM tasc.site), count(*), count(DISTINCT (site_id, network_version)),
                   count(*) FILTER (WHERE risk_length_mi <= 0 OR network_length_mi < 0)
            FROM tasc.s2_site_scope""")
        self.assertEqual((scoped, distinct, bad), (sites, sites, 0))

    def test_intersections_add_no_flagging_length(self):
        self.assertEqual(self.one("""
            SELECT count(*) FROM tasc.s2_site_scope v JOIN tasc.site s USING (site_id, network_version)
            WHERE s.site_type = 'intersection' AND v.network_length_mi <> 0""")[0], 0)

    def test_every_crash_classified_once(self):
        crashes, scoped, distinct = self.one("""
            SELECT (SELECT count(*) FROM tasc.crash), count(*), count(DISTINCT crash_id) FROM tasc.s2_crash_scope""")
        self.assertEqual((scoped, distinct), (crashes, crashes))

    def test_corridor_crash_scope_classifies_every_crash_once(self):
        if self.one("SELECT to_regclass('tasc.s2_crash_scope_corridor')")[0] is None:
            self.skipTest("s2_crash_scope_corridor not created yet")
        crashes, scoped, distinct = self.one("""
            SELECT (SELECT count(*) FROM tasc.crash), count(*), count(DISTINCT crash_id)
            FROM tasc.s2_crash_scope_corridor""")
        self.assertEqual((scoped, distinct), (crashes, crashes))

    def test_crashes_matched_city_wide_are_in_the_analysis_area(self):
        # A crash placed on a site of the city network must count in the capture denominator.
        self.assertEqual(self.one("""
            SELECT count(*) FROM tasc.crash_match m JOIN tasc.s2_crash_scope a USING (crash_id)
            WHERE m.network_version = 'v1_2022' AND m.status = 'matched' AND NOT a.in_analysis_area""")[0], 0)

    def test_backtest_sources_available_by_cutoff(self):
        # Later sources (e.g. osm_latest for the live 'current' set) may exist, but the backtest
        # registry must list only predictor and history sources dated and available by the cutoff.
        self.assertEqual(self.one("""
            SELECT count(*) FROM tasc.s2_source_registry
            WHERE feature_set = 'backtest_2022' AND role IN ('predictor', 'history')
              AND (as_of_date > DATE '2022-12-31' OR available_as_of > DATE '2022-12-31')""")[0], 0)

    def test_every_feature_source_is_registered(self):
        self.assertEqual(self.one("""
            SELECT count(DISTINCT f.source) FROM tasc.site_feature f
            WHERE NOT EXISTS (SELECT FROM tasc.s2_source_availability a
                              WHERE a.source = f.source AND a.role = 'predictor')""")[0], 0)


@unittest.skipUnless(DB_UP, "database not reachable")
class GuardrailTests(unittest.TestCase):
    """Rerun and missing-step mistakes are stopped instead of silently corrupting data."""

    def tmp(self, suffix, text):
        f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, newline="", dir=tempfile.gettempdir(),
                                        prefix="tasc_guardrail_")
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def sql(self, statement, params=None):
        with ingest.connect() as conn, conn.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else None

    def test_reloading_roads_replaces_instead_of_duplicating(self):
        source = "test_guardrail_roads"
        geojson = json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"HWY": "TEST1"},
             "geometry": {"type": "LineString", "coordinates": [[-96.30, 30.60], [-96.31, 30.61]]}},
            {"type": "Feature", "properties": {"HWY": "TEST2"},
             "geometry": {"type": "LineString", "coordinates": [[-96.32, 30.62], [-96.33, 30.63]]}}]})
        path = self.tmp(".geojson", geojson)

        def cleanup():
            self.sql("DELETE FROM tasc.road WHERE source = %s", (source,))
            self.sql("DELETE FROM tasc.ingest_run WHERE source = %s", (source,))
        self.addCleanup(cleanup)
        for _ in range(2):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ingest.main(["roads", path, "--as-of", "2019-12-31", "--source", source]), 0)
        self.assertEqual(self.sql("SELECT count(*) FROM tasc.road WHERE source = %s", (source,))[0][0], 2)

    def test_reloading_roads_used_by_a_network_is_refused(self):
        used = self.sql("""SELECT r.source FROM tasc.road r JOIN tasc.site s USING (road_id) LIMIT 1""")
        if not used:
            self.skipTest("no network built")
        source = used[0][0]
        before = self.sql("SELECT count(*) FROM tasc.road WHERE source = %s", (source,))[0][0]
        path = self.tmp(".geojson", json.dumps({"type": "FeatureCollection", "features": []}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ingest.main(["roads", path, "--as-of", "2019-12-31", "--source", source]), 2)
        self.assertIn("STOPPED", out.getvalue())
        self.assertEqual(self.sql("SELECT count(*) FROM tasc.road WHERE source = %s", (source,))[0][0], before)

    def test_road_names_fill_in_place_and_refuse_the_wrong_file(self):
        source = "test_guardrail_road_names"

        def feature(name, x):
            return {"type": "Feature", "properties": {"HWY": "LS0000", "STE_NAM": name},
                    "geometry": {"type": "LineString", "coordinates": [[x, 30.60], [x - 0.01, 30.61]]}}
        path = self.tmp(".geojson", json.dumps({"type": "FeatureCollection",
                                                "features": [feature(" HOLLEMAN DR ", -96.30), feature(None, -96.32)]}))
        other = self.tmp(".geojson", json.dumps({"type": "FeatureCollection", "features": [feature("X ST", -96.50)]}))

        def cleanup():
            self.sql("DELETE FROM tasc.road WHERE source = %s", (source,))
            self.sql("DELETE FROM tasc.ingest_run WHERE source = %s", (source,))
        self.addCleanup(cleanup)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ingest.main(["roads", path, "--as-of", "2019-12-31", "--source", source]), 0)
        ids_before = self.sql("SELECT road_id FROM tasc.road WHERE source = %s ORDER BY road_id", (source,))
        self.sql("UPDATE tasc.road SET street_name = NULL WHERE source = %s", (source,))

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ingest.main(["road-names", other, "--source", source]), 2)
        self.assertIn("STOPPED", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ingest.main(["road-names", path, "--source", source]), 0)
        self.assertEqual(self.sql("SELECT road_id FROM tasc.road WHERE source = %s ORDER BY road_id", (source,)),
                         ids_before)                                   # same roads, not reloaded
        self.assertEqual([r[0] for r in self.sql("""SELECT street_name FROM tasc.road WHERE source = %s
                                                    ORDER BY street_name NULLS LAST""", (source,))],
                         ["HOLLEMAN DR", None])

    def test_boundary_reload_replaces_and_bad_file_is_refused(self):
        name = "test_guardrail_boundary"

        def square(x):
            return {"type": "Feature", "properties": {"NAME": "Test", "GEOID": "0", "vintage": "2022-01-01"},
                    "geometry": {"type": "Polygon", "coordinates": [[[x, 30.60], [x + 0.01, 30.60],
                                                                     [x + 0.01, 30.61], [x, 30.61], [x, 30.60]]]}}
        first = self.tmp(".geojson", json.dumps({"type": "FeatureCollection", "features": [square(-96.30)]}))
        second = self.tmp(".geojson", json.dumps({"type": "FeatureCollection", "features": [square(-96.40)]}))
        two = self.tmp(".geojson", json.dumps({"type": "FeatureCollection", "features": [square(-96.30), square(-96.40)]}))

        def cleanup():
            self.sql("DELETE FROM tasc.boundary WHERE name = %s", (name,))
            self.sql("DELETE FROM tasc.ingest_run WHERE source = 'boundary' AND file_name IN (%s, %s)",
                     (os.path.basename(first), os.path.basename(second)))
        self.addCleanup(cleanup)
        with contextlib.redirect_stdout(io.StringIO()):
            for path in (first, second):
                self.assertEqual(ingest.main(["boundary", path, "--name", name]), 0)
            self.assertEqual(ingest.main(["boundary", two, "--name", name]), 2)
        rows = self.sql("""SELECT round(ST_X(ST_Centroid(ST_Transform(geom, 4326)))::numeric, 3)
                           FROM tasc.boundary WHERE name = %s""", (name,))
        self.assertEqual([float(r[0]) for r in rows], [-96.395])        # one row, the second square

    def test_osm_roads_add_only_missing_named_streets_and_connect_them(self):
        # A made-up town: one TxDOT road running east-west along lat 30.61, inside a square boundary.
        # 0.0001 degree of latitude is about 11 m.
        txdot, osm, name = "test_guardrail_txdot", "test_guardrail_osm", "test_guardrail_town"

        def line(coords, **props):
            return {"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}}
        square = [[[-96.30, 30.60], [-96.28, 30.60], [-96.28, 30.62], [-96.30, 30.62], [-96.30, 30.60]]]
        boundary = self.tmp(".geojson", json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"NAME": "Town", "GEOID": "0", "vintage": "2022-01-01"},
             "geometry": {"type": "Polygon", "coordinates": square}}]}))
        roads = self.tmp(".geojson", json.dumps({"type": "FeatureCollection", "features": [
            line([[-96.30, 30.61], [-96.28, 30.61]], HWY="TEST", RDBD_ID="KG")]}))
        ways = [
            line([[-96.29, 30.605], [-96.29, 30.615]], name="Test Street", highway="residential"),   # crosses: kept
            line([[-96.30, 30.61004], [-96.28, 30.61004]], name="Dup Rd", highway="primary"),       # 4 m off TxDOT
            line([[-96.297, 30.613], [-96.295, 30.613]], highway="residential"),                    # no name
            line([[-96.287, 30.605], [-96.286, 30.609]], name="Ramp", highway="primary_link"),
            line([[-96.30, 30.610225], [-96.28, 30.610225]], name="Beside Blvd", highway="primary",
                 oneway="yes"),                                                                     # other half, 25 m
            line([[-96.297, 30.617], [-96.295, 30.617]], name="Lonely St", highway="tertiary",
                 oneway="yes", maxspeed="25 mph", lanes="2"),                                        # one-way, far: kept
        ]
        for i, w in enumerate(ways):
            w["properties"]["@osmId"] = f"way/{i}"
        snapshot = self.tmp(".json", json.dumps({"snapshot_time": "2022-12-31T23:59:59Z",
                                                 "groups": {"road": {"features": ways}}}))
        campus = self.tmp(".json", json.dumps({"groups": {"campus": {"features": [
            {"type": "Feature", "properties": {"name": "Texas A&M University"},
             "geometry": {"type": "Polygon", "coordinates": [[[-96.298, 30.616], [-96.294, 30.616], [-96.294, 30.618],
                                                              [-96.298, 30.618], [-96.298, 30.616]]]}}]}}}))

        def cleanup():
            self.sql("DELETE FROM tasc.road WHERE source IN (%s, %s)", (txdot, osm))
            self.sql("DELETE FROM tasc.ingest_run WHERE source IN (%s, %s)", (txdot, osm))
            self.sql("DELETE FROM tasc.boundary WHERE name = %s", (name,))
            self.sql("DELETE FROM tasc.ingest_run WHERE source = 'boundary' AND file_name = %s",
                     (os.path.basename(boundary),))
        self.addCleanup(cleanup)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ingest.main(["boundary", boundary, "--name", name]), 0)
            self.assertEqual(ingest.main(["roads", roads, "--as-of", "2019-12-31", "--source", txdot]), 0)
            for _ in range(2):                                             # a reload replaces
                self.assertEqual(ingest.main(["osm-roads", snapshot, "--against", txdot, "--boundary", name,
                                              "--campus", campus, "--source", osm]), 0)
        kept = self.sql("""SELECT o.street_name, o.maintainer, o.speed_limit, o.num_lanes, o.func_class,
                                  o.as_of_date::text, ST_Distance(ST_StartPoint(o.geom), t.geom) < 0.01
                                                      OR ST_Distance(ST_EndPoint(o.geom), t.geom) < 0.01
                           FROM tasc.road o, tasc.road t
                           WHERE t.source = %s AND o.source = %s ORDER BY o.street_name, ST_YMin(o.geom)""",
                        (txdot, osm))
        self.assertEqual([r[0] for r in kept], ["Lonely St", "Test Street", "Test Street"])
        self.assertEqual(kept[0][1:6], ("TAMU", 25, 2, "5", "2022-12-31"))
        self.assertEqual([r[1] for r in kept[1:]], [None, None])           # off campus
        self.assertEqual([r[6] for r in kept], [False, True, True])        # Test Street joined to TxDOT

    def test_crash_already_loaded_from_another_file_is_rejected(self):
        row = self.sql("SELECT crash_id, crash_date FROM tasc.crash LIMIT 1")
        if not row:
            self.skipTest("no crashes loaded")
        crash_id, crash_date = row[0]
        path = self.tmp(".csv", "Crash ID,Crash Date,Crash Severity,Latitude,Longitude\n"
                                f"{crash_id},{crash_date.isoformat()},N - NOT INJURED,30.6,-96.3\n")
        self.addCleanup(lambda: self.sql("DELETE FROM tasc.ingest_run WHERE file_name = %s",
                                         (os.path.basename(path),)))
        before = self.sql("SELECT run_id FROM tasc.crash WHERE crash_id = %s", (crash_id,))[0][0]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ingest.main(["crashes", path]), 2)       # 1 of 1 bad -> file rejected
        reasons = self.sql("""SELECT j.reason FROM tasc.ingest_reject j JOIN tasc.ingest_run r USING (run_id)
                              WHERE r.file_name = %s""", (os.path.basename(path),))
        self.assertTrue(reasons and reasons[0][0].startswith("crash_id already loaded from"))
        self.assertEqual(self.sql("SELECT run_id FROM tasc.crash WHERE crash_id = %s", (crash_id,))[0][0], before)

    def test_matching_stops_when_corridor_list_is_empty(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "sql", "03_map_match.sql")) as f:
            guard = re.search(r"DO \$\$.*?END \$\$;", f.read(), re.S).group(0)
        conn = ingest.connect()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM tasc.corridor_street")      # rolled back below
            with self.assertRaises(psycopg.errors.RaiseException) as ctx:
                cur.execute(guard)
            self.assertIn("ingest.py corridors", str(ctx.exception))
        finally:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    unittest.main()
