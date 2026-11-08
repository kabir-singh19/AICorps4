-- IF-04 streetlights. No City streetlight GIS layer was delivered, so per the ICD the fallback is
-- OSM lighting: street_lamp points and lit=* tags on the roads, dated with the snapshot.
--   psql -v network_version=v1_2022 -v feature_set=backtest_2022 -v osm_source=osm_city_2022-12-31 < sql/11_lighting.sql
--   (live ranking: -v feature_set=current -v osm_source=osm_city_latest)
-- osm_street_lamps_50m: mapped street lamps within 50 m of the site.
-- osm_lit_share: share of a segment's length within 20 m of an OSM road tagged lit=yes.
-- A feature with the same value at every site carries no information; it is removed and the gap is
-- logged in tasc.lighting_gap (College Station tags no public street lit=yes in OSM, 2022 or now).
\set ON_ERROR_STOP on
SET search_path = tasc, public;
BEGIN;

CREATE TABLE IF NOT EXISTS lighting_gap (
  network_version text NOT NULL,
  feature_set text NOT NULL,
  osm_source text NOT NULL,
  city_gis_delivered boolean NOT NULL,
  lamp_points integer NOT NULL,
  lit_tagged_roads integer NOT NULL,
  sites_with_lamp integer NOT NULL,
  dropped_constant text[] NOT NULL,
  logged_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (network_version, feature_set, osm_source)
);

DELETE FROM site_feature f USING site s
WHERE f.site_id = s.site_id AND s.network_version = :'network_version' AND f.feature_set = :'feature_set'
  AND f.feature_name IN ('osm_street_lamps_50m', 'osm_lit_share');

INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
SELECT s.site_id, :'feature_set', 'osm_street_lamps_50m',
       (SELECT count(*) FROM osm_feature o WHERE o.source = :'osm_source' AND o.grp = 'street_lamp' AND ST_DWithin(o.geom, s.geom, 50)),
       (SELECT max(snapshot_date) FROM osm_feature WHERE source = :'osm_source'),
       :'osm_source'
FROM site s WHERE s.network_version = :'network_version';

INSERT INTO site_feature (site_id, feature_set, feature_name, value_num, as_of_date, source)
SELECT s.site_id, :'feature_set', 'osm_lit_share',
       COALESCE(ST_Length(ST_Intersection(s.geom, lz.zone)) / NULLIF(ST_Length(s.geom), 0), 0),
       (SELECT max(snapshot_date) FROM osm_feature WHERE source = :'osm_source'),
       :'osm_source'
FROM site s
LEFT JOIN LATERAL (
  SELECT ST_Union(ST_Buffer(o.geom, 20)) AS zone FROM osm_feature o
  WHERE o.source = :'osm_source' AND o.grp IN ('major_road', 'road') AND o.tags->>'lit' = 'yes'
    AND ST_DWithin(o.geom, s.geom, 20)) lz ON true
WHERE s.network_version = :'network_version' AND s.site_type = 'segment';

CREATE TEMP TABLE lit_constant ON COMMIT DROP AS
SELECT f.feature_name FROM site_feature f JOIN site s USING (site_id)
WHERE s.network_version = :'network_version' AND f.feature_set = :'feature_set'
  AND f.feature_name IN ('osm_street_lamps_50m', 'osm_lit_share')
GROUP BY f.feature_name HAVING min(f.value_num) = max(f.value_num);

DELETE FROM site_feature f USING site s
WHERE f.site_id = s.site_id AND s.network_version = :'network_version' AND f.feature_set = :'feature_set'
  AND f.feature_name IN (SELECT feature_name FROM lit_constant);

INSERT INTO lighting_gap (network_version, feature_set, osm_source, city_gis_delivered, lamp_points, lit_tagged_roads, sites_with_lamp, dropped_constant)
SELECT :'network_version', :'feature_set', :'osm_source', false,
       (SELECT count(*) FROM osm_feature WHERE source = :'osm_source' AND grp = 'street_lamp'),
       (SELECT count(*) FROM osm_feature WHERE source = :'osm_source' AND grp IN ('major_road', 'road') AND tags->>'lit' = 'yes'),
       (SELECT count(*) FROM site_feature f JOIN site s USING (site_id) WHERE s.network_version = :'network_version'
          AND f.feature_set = :'feature_set' AND f.feature_name = 'osm_street_lamps_50m' AND f.value_num > 0),
       COALESCE((SELECT array_agg(feature_name ORDER BY feature_name) FROM lit_constant), '{}')
ON CONFLICT (network_version, feature_set, osm_source) DO UPDATE SET
  lamp_points = EXCLUDED.lamp_points, lit_tagged_roads = EXCLUDED.lit_tagged_roads,
  sites_with_lamp = EXCLUDED.sites_with_lamp, dropped_constant = EXCLUDED.dropped_constant, logged_at = now();

SELECT feature_set, osm_source, lamp_points, lit_tagged_roads, sites_with_lamp, dropped_constant
FROM lighting_gap WHERE network_version = :'network_version' AND feature_set = :'feature_set';
COMMIT;
