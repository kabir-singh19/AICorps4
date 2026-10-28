-- OSM site features (IF-03) from tasc.osm_feature into site_feature.
-- Run after `ingest.py osm` has loaded the snapshot:
--   psql "$DATABASE_URL" -v network_version=v0_2019 -v feature_set=backtest_2022 \
--        -v osm_source=osm_2022-12-31 -f sql/06_osm_features.sql
--   (live ranking: -v feature_set=current -v osm_source=osm_latest)
--
-- Every value is dated with the snapshot date, so the site_feature trigger refuses a snapshot
-- newer than the feature set's cutoff (e.g. osm_latest into backtest_2022).
-- Counts apply to segments and intersections (distance to the line or point); sidewalk share
-- applies to segments only. A count of 0 means "none mapped in OSM at that date", which in 2022
-- often means "not mapped yet", not "not there": OSM was far less complete then.
-- Not built: lighting from `lit` tags (no corridor road had one in the 2022 snapshot) and
-- street-lamp counts (one mapped lamp within 50 m of any of the 187 sites in 2022).

SET search_path = tasc, public;
BEGIN;

DELETE FROM site_feature f
USING site s
WHERE f.site_id = s.site_id
  AND s.network_version = :'network_version'
  AND f.feature_set = :'feature_set'
  AND f.source = :'osm_source';

-- Point-like counts within a distance of each site. Polygons (schools, some restaurants) count
-- if any part is within the distance.
INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
SELECT s.site_id, :'feature_set', d.feature_name,
       (SELECT count(*) FROM osm_feature o
        WHERE o.source = :'osm_source' AND o.grp = d.grp AND ST_DWithin(o.geom, s.geom, d.radius_m)),
       (SELECT max(snapshot_date) FROM osm_feature WHERE source = :'osm_source'),
       :'osm_source'
FROM site s
CROSS JOIN (VALUES
    ('osm_bus_stops_200m',    'bus_stop',        200),   -- stops sit on side streets, not the corridors
    ('osm_schools_400m',      'school',          400),
    ('osm_bars_200m',         'bar',             200),
    ('osm_restaurants_100m',  'restaurant',      100),
    ('osm_crossings_30m',     'crossing',         30)
) AS d(feature_name, grp, radius_m)
WHERE s.network_version = :'network_version';

-- Signalized intersections. OSM often has one traffic_signals point per approach (up to 4 at one
-- intersection), so points within 50 m of each other are merged into one intersection first.
-- 50 m is stable: merging at 75 m changes the 2022 count only from 58 to 57.
CREATE TEMP TABLE signal_cluster ON COMMIT DROP AS
SELECT ST_Collect(geom) AS geom
FROM (SELECT geom, ST_ClusterDBSCAN(geom, 50, 1) OVER () AS cid
      FROM osm_feature WHERE source = :'osm_source' AND grp = 'traffic_signals') t
GROUP BY cid;

INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
SELECT s.site_id, :'feature_set', 'osm_signalized_intersections_30m',
       (SELECT count(*) FROM signal_cluster c WHERE ST_DWithin(c.geom, s.geom, 30)),
       (SELECT max(snapshot_date) FROM osm_feature WHERE source = :'osm_source'),
       :'osm_source'
FROM site s
WHERE s.network_version = :'network_version';

-- Sidewalk share: the fraction of each segment's length lying within 30 m of a mapped sidewalk.
INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
SELECT s.site_id, :'feature_set', 'osm_sidewalk_share',
       COALESCE(ST_Length(ST_Intersection(s.geom, sw.zone)) / NULLIF(ST_Length(s.geom), 0), 0),
       (SELECT max(snapshot_date) FROM osm_feature WHERE source = :'osm_source'),
       :'osm_source'
FROM site s
LEFT JOIN LATERAL (
    SELECT ST_Union(ST_Buffer(o.geom, 30)) AS zone
    FROM osm_feature o
    WHERE o.source = :'osm_source' AND o.grp = 'sidewalk' AND ST_DWithin(o.geom, s.geom, 30)
) sw ON true
WHERE s.network_version = :'network_version' AND s.site_type = 'segment';

-- A feature with the same value at every site carries no information (in 2022 no bus stop was
-- mapped within 50 m of any corridor, since stops sit on side streets), so it is dropped and reported.
CREATE TEMP TABLE constant_feature ON COMMIT DROP AS
SELECT f.feature_name, min(f.value_num) AS value
FROM site_feature f JOIN site s USING (site_id)
WHERE s.network_version = :'network_version' AND f.feature_set = :'feature_set' AND f.source = :'osm_source'
GROUP BY f.feature_name
HAVING min(f.value_num) = max(f.value_num);

DELETE FROM site_feature f
USING site s, constant_feature c
WHERE f.site_id = s.site_id AND s.network_version = :'network_version'
  AND f.feature_set = :'feature_set' AND f.source = :'osm_source' AND f.feature_name = c.feature_name;

SELECT feature_name AS dropped_no_variation, value AS value_at_every_site FROM constant_feature;

COMMIT;

-- Summary: how often each feature is nonzero, and its range.
SELECT f.feature_name, count(*) AS sites, count(*) FILTER (WHERE f.value_num > 0) AS nonzero,
       round(min(f.value_num)::numeric, 2) AS min, round(avg(f.value_num)::numeric, 2) AS mean,
       round(max(f.value_num)::numeric, 2) AS max, min(f.as_of_date) AS as_of
FROM site_feature f JOIN site s USING (site_id)
WHERE s.network_version = :'network_version' AND f.feature_set = :'feature_set' AND f.source = :'osm_source'
GROUP BY f.feature_name ORDER BY f.feature_name;
