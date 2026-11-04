-- Build sites (0.1-mi segments + intersections) from tasc.road.
-- Run (three corridors, College Station only):
--   psql "$DATABASE_URL" -v network_version=v0_2019 -v as_of=2019-12-31 \
--        -v routes=BS0006R,FM0060,FM2154 -v city_code=9050 -f sql/02_build_network.sql
-- Use routes=ALL and/or city_code=ALL to drop either filter.
-- Run (whole city: TxDOT 2019 centerlines plus the streets OSM adds, inside the city limits):
--   psql "$DATABASE_URL" -v network_version=v1_2022 -v as_of=2022-12-31 -v routes=ALL -v city_code=ALL \
--        -v road_source=roadway_inventory_2019 -v osm_source=osm_roads_2022-12-31 \
--        -v boundary='College Station' -v stub_m=15 -v merge_m=15 -f sql/02_build_network.sql
-- road_source, osm_source, boundary, stub_m and merge_m are optional (default: any TxDOT source,
-- no OSM roads, no boundary, no clean-up), so the v0_2019 command above builds what it always did.
--
-- Only centerline roadbeds (KG) are used. TxDOT also draws each direction of a divided road
-- (LG / RG) on top of the centerline, which would double the network. OSM roads come from
-- `ingest.py osm-roads`, which already left out divided-road duplicates.
-- Known limits are listed in the README.

\if :{?road_source}
\else
    \set road_source ALL
\endif
\if :{?osm_source}
\else
    \set osm_source NONE
\endif
\if :{?boundary}
\else
    \set boundary NONE
\endif
\if :{?stub_m}
\else
    \set stub_m 0
\endif
\if :{?merge_m}
\else
    \set merge_m 0
\endif

SET search_path = tasc, public;
-- Databases created before site.interchange was added to sql/init/01_schema.sql.
ALTER TABLE site ADD COLUMN IF NOT EXISTS interchange boolean;
BEGIN;

-- Rebuilding a version replaces it (crash_match rows for it cascade away).
DELETE FROM site WHERE network_version = :'network_version';

-- 0. Source roads for this build: TxDOT centerlines, plus the OSM streets if asked for,
--    keeping only roads that touch the boundary if one is given.
CREATE TEMP TABLE src ON COMMIT DROP AS
SELECT road.*
FROM road
WHERE ((roadbed = 'KG'
        AND (:'road_source' = 'ALL' OR source = :'road_source')
        AND (:'routes' = 'ALL' OR route_name = ANY (string_to_array(:'routes', ',')))
        AND (:'city_code' = 'ALL' OR city_code::text = :'city_code'))   -- text: 'ALL'::integer would fail
       OR source = :'osm_source')
  AND (:'boundary' = 'NONE'
       OR ST_Intersects(geom, (SELECT geom FROM boundary WHERE name = :'boundary')));

-- 0b. ingest.py osm-roads ends each OSM street exactly on a TxDOT centerline, but between two
--     of its points. ST_Snap puts that end in as a new point of the TxDOT line, so step 1 can
--     split the line there and the meeting becomes an intersection. Only OSM street ends are
--     used, so a build without osm_source (v0_2019) is unchanged.
UPDATE src
SET geom = ST_Snap(src.geom, e.pts, 0.5)
FROM (
    SELECT s.road_id, ST_Collect(p.pt) AS pts
    FROM src s
    JOIN (SELECT road_id, ST_StartPoint(geom) AS pt FROM src WHERE source = :'osm_source'
          UNION ALL
          SELECT road_id, ST_EndPoint(geom) FROM src WHERE source = :'osm_source') p
      ON p.road_id <> s.road_id AND ST_DWithin(p.pt, s.geom, 0.5)
    GROUP BY s.road_id
) e
WHERE src.road_id = e.road_id;

-- 1. Links: union all linework so lines are split wherever they cross, then merge.
--    ST_LineMerge joins lines end to end but stops wherever 3+ lines meet,
--    so each link runs from one intersection (or dead end) to the next.
--    Snapping to a 0.5 m grid closes tiny gaps between lines that should touch.
CREATE TEMP TABLE link ON COMMIT DROP AS
SELECT row_number() OVER () AS link_id, geom
FROM (
    SELECT (ST_Dump(ST_LineMerge(ST_UnaryUnion(ST_Collect(ST_SnapToGrid(geom, 0.5)))))).geom AS geom
    FROM src
) d
WHERE ST_Length(geom) > 0;

-- 1b. Stubs (stub_m > 0): a road drawn a few meters past the street it meets leaves a short
--     dead-end link, which would add a fake leg and a near-zero-length segment. Delete dead-end
--     links shorter than stub_m, then merge again so the lines they split rejoin.
CREATE TEMP TABLE link_end ON COMMIT DROP AS
SELECT link_id, ST_StartPoint(geom) AS pt FROM link
UNION ALL
SELECT link_id, ST_EndPoint(geom) FROM link;

CREATE TEMP TABLE stub (geom geometry) ON COMMIT DROP;
WITH d AS (
    DELETE FROM link l
    WHERE ST_Length(l.geom) < :stub_m
      AND EXISTS (SELECT FROM link_end e
                  WHERE e.link_id = l.link_id
                    AND (SELECT count(*) FROM link_end o WHERE ST_Equals(o.pt, e.pt)) = 1)
    RETURNING l.geom
)
INSERT INTO stub SELECT geom FROM d;

-- Merge again only if a stub was removed, and then all links together: merging just the links
-- next to a stub would join two of them straight through a junction whose other legs were left
-- out, and the junction would vanish. With no stub removed (v0_2019) every link is kept exactly.
CREATE TEMP TABLE link2 ON COMMIT DROP AS
SELECT row_number() OVER () AS link_id, geom
FROM (SELECT geom FROM link WHERE NOT EXISTS (SELECT FROM stub)
      UNION ALL
      SELECT (ST_Dump(ST_LineMerge(ST_Collect(geom)))).geom FROM link WHERE EXISTS (SELECT FROM stub)) d
WHERE geom IS NOT NULL;
DROP TABLE link;
ALTER TABLE link2 RENAME TO link;
CREATE INDEX ON link_end USING gist (pt);
TRUNCATE link_end;
INSERT INTO link_end
SELECT link_id, ST_StartPoint(geom) FROM link
UNION ALL
SELECT link_id, ST_EndPoint(geom) FROM link;

-- 2. Intersections: link endpoints shared by 3 or more link ends. With merge_m > 0, nodes
--    closer than merge_m are one junction drawn as several: they become one intersection at
--    their center, the short links between them are dropped, and legs are counted once.
--    An intersection touching a freeway (TxDOT functional class 1 or 2) is flagged as an
--    interchange: those lines usually cross on a bridge, so it is not an ordinary junction.
CREATE TEMP TABLE node ON COMMIT DROP AS
SELECT pt, count(*) AS ends,
       ST_ClusterDBSCAN(pt, eps := :merge_m, minpoints := 1) OVER () AS cluster
FROM link_end
GROUP BY pt
HAVING count(*) >= 3;
CREATE INDEX ON node USING gist (pt);

CREATE TEMP TABLE inner_link ON COMMIT DROP AS
SELECT l.link_id, a.cluster
FROM link l
JOIN node a ON ST_Equals(a.pt, ST_StartPoint(l.geom))
JOIN node b ON ST_Equals(b.pt, ST_EndPoint(l.geom)) AND b.cluster = a.cluster
WHERE NOT ST_Equals(a.pt, b.pt)                -- a loop back to the same node is a real street
  AND ST_Length(l.geom) <= 2 * :merge_m;       -- a long road between two close nodes stays
DELETE FROM link WHERE link_id IN (SELECT link_id FROM inner_link);

INSERT INTO site (site_type, geom, legs, interchange, network_version, as_of_date)
SELECT 'intersection', c.pt, c.ends - 2 * (SELECT count(*) FROM inner_link i WHERE i.cluster = c.cluster),
       EXISTS (SELECT FROM src WHERE src.func_class IN ('1', '2') AND ST_DWithin(src.geom, c.pt, :merge_m + 1)),
       :'network_version', :'as_of'::date
FROM (SELECT cluster, ST_Centroid(ST_Collect(pt)) AS pt, sum(ends) AS ends FROM node GROUP BY cluster) c;

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

-- 4. With a boundary, step 0 kept whole roads that cross it. Keep only the sites inside:
--    segments by their midpoint, intersections by their point.
DELETE FROM site
WHERE network_version = :'network_version'
  AND :'boundary' <> 'NONE'
  AND NOT ST_Within(CASE WHEN site_type = 'segment' THEN ST_LineInterpolatePoint(geom, 0.5) ELSE geom END,
                    (SELECT geom FROM boundary WHERE name = :'boundary'));

COMMIT;

SELECT site_type, count(*) AS sites, round(sum(length_m)::numeric / 1609.344, 1) AS miles
FROM site
WHERE network_version = :'network_version'
GROUP BY site_type;
