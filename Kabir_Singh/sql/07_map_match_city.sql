-- Match every crash to a site of a city-wide network (v1_2022), and log every miss.
-- Run:  psql "$DATABASE_URL" -v network_version=v1_2022 -v tol_m=45.72 -v boundary='College Station' \
--            -f sql/07_map_match_city.sql
-- Needs tasc.street_key filled first:  python ingest.py street-keys
-- 03_map_match.sql stays the rule for the corridor network v0_2019.
--
-- Rule, in order:
--   1. no coordinates                             -> unmatched, reason 'no_coordinates'
--   2. outside the city boundary                  -> unmatched, reason 'outside_city' (not in the
--                                                    analysis area, so not counted as a miss)
--   3. within 250 ft (76.2 m) of an intersection  -> that intersection (nearest one)
--   4. else the nearest segment WHOSE ROAD HAS THE CRASH'S STREET NAME within tol_m -> that segment.
--      Names are compared by street_key (street_names.py): equal key or equal base key.
--      A crash with no usable street name (blank, UNKNOWN) takes the nearest segment within tol_m.
--   5. else                                       -> unmatched:
--        'outside_tolerance'  a segment with its name exists, but farther than tol_m
--        'name_not_found'     no segment with its name within 500 m
-- Rule 4 is the corridor rule (a crash CRIS records on one street never goes to a cross street)
-- applied to every street. distance_m is stored for every crash with coordinates.

SET search_path = tasc, public;

-- Databases created before 'outside_city' was added to match_rate in sql/init/01_schema.sql.
CREATE OR REPLACE VIEW match_rate AS
SELECT m.network_version,
       count(*) FILTER (WHERE c.is_fsi AND c.geom IS NOT NULL)                          AS fsi_geocoded,
       count(*) FILTER (WHERE c.is_fsi AND c.geom IS NOT NULL AND m.status = 'matched') AS fsi_matched,
       round(100.0 * count(*) FILTER (WHERE c.is_fsi AND c.geom IS NOT NULL AND m.status = 'matched')
             / NULLIF(count(*) FILTER (WHERE c.is_fsi AND c.geom IS NOT NULL), 0), 2)    AS fsi_match_pct,
       count(*) FILTER (WHERE m.reason = 'no_coordinates')                              AS no_coordinates,
       count(*) FILTER (WHERE m.reason = 'outside_tolerance')                           AS outside_tolerance
FROM crash_match m
JOIN crash c USING (crash_id)
WHERE m.reason IS DISTINCT FROM 'off_corridor'          -- outside the analysis area: not a miss
  AND m.reason IS DISTINCT FROM 'outside_city'
GROUP BY m.network_version;

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM tasc.street_key) THEN
        RAISE EXCEPTION 'tasc.street_key is empty: run "python ingest.py street-keys" first. Nothing was matched.';
    END IF;
END $$;

DELETE FROM crash_match WHERE network_version = :'network_version';

-- Each segment with the name key of its road: the route code for state routes, else the street name.
CREATE TEMP TABLE seg ON COMMIT DROP AS
SELECT s.site_id, s.geom, k.name_key, k.name_base
FROM site s
JOIN road r USING (road_id)
LEFT JOIN street_key k
       ON k.street_name = upper(trim(CASE WHEN r.route_name IS NULL OR r.route_name = 'LS0000'
                                          THEN r.street_name ELSE r.route_name END))
WHERE s.network_version = :'network_version'
  AND s.site_type = 'segment';
CREATE INDEX ON seg USING gist (geom);

CREATE TEMP TABLE c ON COMMIT DROP AS
SELECT c.crash_id, c.geom, k.name_key, k.name_base,
       c.geom IS NOT NULL AND ST_Within(c.geom, (SELECT geom FROM boundary WHERE name = :'boundary')) AS in_city
FROM crash c
LEFT JOIN street_key k
       ON k.street_name = upper(trim(c.street_name)) AND k.name_key NOT IN ('UNKNOWN', 'NA');      -- placeholders, not names

INSERT INTO crash_match (crash_id, network_version, site_id, nearest_site_id, distance_m, tolerance_m, status, reason)
SELECT c.crash_id,
       :'network_version',
       CASE WHEN i.site_id IS NOT NULL THEN i.site_id
            WHEN s.dist <= :tol_m     THEN s.site_id
       END,
       COALESCE(i.site_id, s.site_id),
       COALESCE(i.dist, s.dist),
       :tol_m,
       CASE WHEN c.in_city AND (i.site_id IS NOT NULL OR s.dist <= :tol_m) THEN 'matched' ELSE 'unmatched' END,
       CASE WHEN c.geom IS NULL     THEN 'no_coordinates'
            WHEN NOT c.in_city      THEN 'outside_city'
            WHEN i.site_id IS NOT NULL OR s.dist <= :tol_m THEN NULL
            WHEN s.dist IS NOT NULL THEN 'outside_tolerance'
            ELSE 'name_not_found'
       END
FROM c
LEFT JOIN LATERAL (
    SELECT site_id, ST_Distance(site.geom, c.geom) AS dist
    FROM site
    WHERE site_type = 'intersection'
      AND network_version = :'network_version'
      AND ST_DWithin(site.geom, c.geom, 76.2)
    ORDER BY site.geom <-> c.geom
    LIMIT 1
) i ON c.in_city
LEFT JOIN LATERAL (
    SELECT seg.site_id, ST_Distance(seg.geom, c.geom) AS dist
    FROM seg
    WHERE ST_DWithin(seg.geom, c.geom, 500)
      AND (c.name_key IS NULL OR seg.name_key = c.name_key OR seg.name_base = c.name_base)
    ORDER BY seg.geom <-> c.geom
    LIMIT 1
) s ON c.in_city AND i.site_id IS NULL;

COMMIT;

SELECT * FROM match_rate WHERE network_version = :'network_version';
SELECT reason, count(*) AS crashes, count(*) FILTER (WHERE c.is_fsi) AS fsi
FROM crash_match m JOIN crash c USING (crash_id)
WHERE network_version = :'network_version'
GROUP BY reason ORDER BY reason NULLS FIRST;
