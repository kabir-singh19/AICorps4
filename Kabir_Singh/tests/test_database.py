"""Database tests: need the PostGIS container running and a built network. Skipped otherwise.

    docker compose up -d
    .venv/bin/python -m unittest discover -s tests -v

Every test runs inside a transaction that is rolled back, so the database is left unchanged.
"""
import os
import sys
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


if __name__ == "__main__":
    unittest.main()
