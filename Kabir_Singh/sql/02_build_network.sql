-- Build sites (0.1-mi segments + intersections) from tasc.road.
-- Run (three corridors, College Station only):
--   psql "$DATABASE_URL" -v network_version=v0_2019 -v as_of=2019-12-31 \
--        -v routes=BS0006R,FM0060,FM2154 -v city_code=9050 -f sql/02_build_network.sql
-- Use routes=ALL and/or city_code=ALL to drop either filter.
--
-- Only centerline roadbeds (KG) are used. TxDOT also draws each direction of a divided road
-- (LG / RG) on top of the centerline, which would double the network.
-- Known limits are listed in the README.

SET search_path = tasc, public;
BEGIN;

-- Rebuilding a version replaces it (crash_match rows for it cascade away).
DELETE FROM site WHERE network_version = :'network_version';

-- 0. Source roads for this build.
CREATE TEMP TABLE src ON COMMIT DROP AS
SELECT *
FROM road
WHERE roadbed = 'KG'
  AND (:'routes' = 'ALL' OR route_name = ANY (string_to_array(:'routes', ',')))
  AND (:'city_code' = 'ALL' OR city_code = :'city_code'::integer);

-- 1. Links: union all linework so lines are split wherever they cross, then merge.
--    ST_LineMerge joins lines end to end but stops wherever 3+ lines meet,
--    so each link runs from one intersection (or dead end) to the next.
--    Snapping to a 0.5 m grid closes tiny gaps between lines that should touch.
CREATE TEMP TABLE link ON COMMIT DROP AS
SELECT geom
FROM (
    SELECT (ST_Dump(ST_LineMerge(ST_UnaryUnion(ST_Collect(ST_SnapToGrid(geom, 0.5)))))).geom AS geom
    FROM src
) d
WHERE ST_Length(geom) > 0;

-- 2. Intersections: link endpoints shared by 3 or more link ends.
INSERT INTO site (site_type, geom, legs, network_version, as_of_date)
SELECT 'intersection', pt, count(*), :'network_version', :'as_of'::date
FROM (
    SELECT ST_StartPoint(geom) AS pt FROM link
    UNION ALL
    SELECT ST_EndPoint(geom) FROM link
) ends
GROUP BY pt
HAVING count(*) >= 3;

-- 3. Segments: cut each link into equal pieces no longer than 0.1 mi (160.934 m).
--    Each piece takes its attributes from the source road nearest its midpoint.
INSERT INTO site (site_type, geom, length_m, road_id, network_version, as_of_date)
SELECT 'segment', s.geom, ST_Length(s.geom), r.road_id, :'network_version', :'as_of'::date
FROM (
    SELECT ST_LineSubstring(l.geom, (i - 1)::float8 / l.n, i::float8 / l.n) AS geom
    FROM (SELECT geom, ceil(ST_Length(geom) / 160.934)::int AS n FROM link) l,
         generate_series(1, l.n) AS i
) s
LEFT JOIN LATERAL (
    SELECT road_id
    FROM src
    ORDER BY src.geom <-> ST_LineInterpolatePoint(s.geom, 0.5)
    LIMIT 1
) r ON true;

COMMIT;

SELECT site_type, count(*) AS sites, round(sum(length_m)::numeric / 1609.344, 1) AS miles
FROM site
WHERE network_version = :'network_version'
GROUP BY site_type;
