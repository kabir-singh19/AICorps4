-- Fill site_feature from the road attributes behind each site.
-- Run:  psql "$DATABASE_URL" -v network_version=v0_2019 -v feature_set=backtest_2022 -f sql/04_features.sql
--
-- Every value carries the date it describes (as_of_date). The site_feature trigger rejects the
-- whole run if any value is dated after the feature set's cutoff (backtest_2022: 2022-12-31),
-- so a too-new source cannot slip into the backtest.
--
-- Segments: speed_limit, num_lanes, aadt, func_class, median_type from the source road nearest
--           the segment midpoint (site.road_id). AADT is dated Dec 31 of its own count year.
--           From road.attrs (ingest.py road-attrs; TxDOT roads only): lane_width_ft,
--           shoulder_inside_ft, shoulder_outside_ft, median_width_ft, surface_width_ft, truck_pct,
--           access_control, curb_left, curb_right.
--           From the geometry: curvature_deg_per_mi (total change of direction along the segment,
--           per mile) and dist_to_intersection_m (midpoint to the nearest intersection).
-- Intersections: legs, and interchange (1 = touches a freeway, so the roads may cross on a bridge).
-- func_class, median_type, access_control and curbs are stored as TxDOT codes in value_text.

SET search_path = tasc, public;
BEGIN;

-- Rebuilding replaces the features this script writes (road and network sources) for this
-- version and set. OSM features from 06_osm_features.sql are left alone.
DELETE FROM site_feature f
USING site s
WHERE f.site_id = s.site_id
  AND s.network_version = :'network_version'
  AND f.feature_set = :'feature_set'
  AND (f.source = 'network ' || s.network_version OR f.source IN (SELECT DISTINCT source FROM road));

INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, value_text, as_of_date, source)
SELECT s.site_id, :'feature_set', v.feature_name, v.value_num, v.value_text, v.as_of_date, r.source
FROM site s
JOIN road r USING (road_id)
CROSS JOIN LATERAL (VALUES
    ('speed_limit', r.speed_limit::float8, NULL::text,   r.as_of_date),
    ('num_lanes',   r.num_lanes::float8,   NULL,         r.as_of_date),
    ('aadt',        r.aadt::float8,        NULL,         make_date(r.aadt_year, 12, 31)),
    ('func_class',  NULL,                  r.func_class, r.as_of_date),
    ('median_type', NULL,                  r.median_type, r.as_of_date),
    ('lane_width_ft',       (r.attrs ->> 'lane_width_ft')::float8,       NULL, r.as_of_date),
    ('shoulder_inside_ft',  (r.attrs ->> 'shoulder_inside_ft')::float8,  NULL, r.as_of_date),
    ('shoulder_outside_ft', (r.attrs ->> 'shoulder_outside_ft')::float8, NULL, r.as_of_date),
    ('median_width_ft',     (r.attrs ->> 'median_width_ft')::float8,     NULL, r.as_of_date),
    ('surface_width_ft',    (r.attrs ->> 'surface_width_ft')::float8,    NULL, r.as_of_date),
    ('truck_pct',           (r.attrs ->> 'truck_pct')::float8,           NULL, r.as_of_date),
    ('access_control',      NULL, r.attrs ->> 'access_control', r.as_of_date),
    ('curb_left',           NULL, r.attrs ->> 'curb_left',      r.as_of_date),
    ('curb_right',          NULL, r.attrs ->> 'curb_right',     r.as_of_date)
) AS v(feature_name, value_num, value_text, as_of_date)
WHERE s.network_version = :'network_version'
  AND s.site_type = 'segment'
  AND (v.value_num IS NOT NULL OR v.value_text IS NOT NULL)
  AND v.as_of_date IS NOT NULL;

INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
SELECT site_id, :'feature_set', v.feature_name, v.value_num, as_of_date, 'network ' || network_version
FROM site
CROSS JOIN LATERAL (VALUES ('legs', legs::float8), ('interchange', interchange::int::float8)) AS v(feature_name, value_num)
WHERE network_version = :'network_version'
  AND site_type = 'intersection'
  AND v.value_num IS NOT NULL;

-- Segment geometry. Curvature: the change of direction between consecutive line pieces,
-- folded into 0-180 degrees, summed along the segment and divided by its length in miles.
INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
WITH pt AS (
    SELECT s.site_id, (d).path[1] AS i, (d).geom AS g
    FROM site s, ST_DumpPoints(s.geom) d
    WHERE s.network_version = :'network_version' AND s.site_type = 'segment'),
az AS (
    SELECT site_id, i, ST_Azimuth(g, lead(g) OVER (PARTITION BY site_id ORDER BY i)) AS a FROM pt),
turn AS (
    SELECT site_id,
           abs(mod((degrees(lead(a) OVER (PARTITION BY site_id ORDER BY i) - a) + 540)::numeric, 360) - 180) AS deg
    FROM az WHERE a IS NOT NULL)
SELECT s.site_id, :'feature_set', 'curvature_deg_per_mi',
       COALESCE((SELECT sum(deg) FROM turn t WHERE t.site_id = s.site_id), 0) / (s.length_m / 1609.344),
       s.as_of_date, 'network ' || s.network_version
FROM site s
WHERE s.network_version = :'network_version' AND s.site_type = 'segment' AND s.length_m > 0;

INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
SELECT s.site_id, :'feature_set', 'dist_to_intersection_m',
       (SELECT ST_Distance(i.geom, ST_LineInterpolatePoint(s.geom, 0.5)) FROM site i
        WHERE i.network_version = s.network_version AND i.site_type = 'intersection'
        ORDER BY i.geom <-> ST_LineInterpolatePoint(s.geom, 0.5) LIMIT 1),
       s.as_of_date, 'network ' || s.network_version
FROM site s
WHERE s.network_version = :'network_version' AND s.site_type = 'segment'
  AND EXISTS (SELECT FROM site i WHERE i.network_version = s.network_version AND i.site_type = 'intersection');

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
