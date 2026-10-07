-- Fill site_feature from the road attributes behind each site.
-- Run:  psql "$DATABASE_URL" -v network_version=v0_2019 -v feature_set=backtest_2022 -f sql/04_features.sql
--
-- Every value carries the date it describes (as_of_date). The site_feature trigger rejects the
-- whole run if any value is dated after the feature set's cutoff (backtest_2022: 2022-12-31),
-- so a too-new source cannot slip into the backtest.
--
-- Segments: speed_limit, num_lanes, aadt, func_class, median_type from the source road nearest
--           the segment midpoint (site.road_id). AADT is dated Dec 31 of its own count year.
-- Intersections: legs.
-- func_class and median_type are stored as TxDOT codes in value_text.

SET search_path = tasc, public;
BEGIN;

-- Rebuilding replaces this version's features in this set.
DELETE FROM site_feature f
USING site s
WHERE f.site_id = s.site_id
  AND s.network_version = :'network_version'
  AND f.feature_set = :'feature_set';

INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, value_text, as_of_date, source)
SELECT s.site_id, :'feature_set', v.feature_name, v.value_num, v.value_text, v.as_of_date, r.source
FROM site s
JOIN road r USING (road_id)
CROSS JOIN LATERAL (VALUES
    ('speed_limit', r.speed_limit::float8, NULL::text,   r.as_of_date),
    ('num_lanes',   r.num_lanes::float8,   NULL,         r.as_of_date),
    ('aadt',        r.aadt::float8,        NULL,         make_date(r.aadt_year, 12, 31)),
    ('func_class',  NULL,                  r.func_class, r.as_of_date),
    ('median_type', NULL,                  r.median_type, r.as_of_date)
) AS v(feature_name, value_num, value_text, as_of_date)
WHERE s.network_version = :'network_version'
  AND s.site_type = 'segment'
  AND (v.value_num IS NOT NULL OR v.value_text IS NOT NULL)
  AND v.as_of_date IS NOT NULL;

INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
SELECT site_id, :'feature_set', 'legs', legs, as_of_date, 'network ' || network_version
FROM site
WHERE network_version = :'network_version'
  AND site_type = 'intersection';

COMMIT;

-- Coverage: every site should have every feature for its type.
SELECT s.site_type, f.feature_name, count(*) AS sites,
       min(f.as_of_date) AS oldest, max(f.as_of_date) AS newest
FROM site_feature f
JOIN site s USING (site_id)
WHERE s.network_version = :'network_version'
  AND f.feature_set = :'feature_set'
GROUP BY 1, 2
ORDER BY 1, 2;
