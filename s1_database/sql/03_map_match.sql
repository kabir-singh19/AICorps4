-- Match every crash to a site, and log every miss.
-- Run:  psql "$DATABASE_URL" -v network_version=v0 -v tol_m=45.72 -f sql/03_map_match.sql
--
-- Rule:
--   1. no coordinates                          -> unmatched, reason 'no_coordinates'
--   2. within 250 ft (76.2 m) of an intersection -> that intersection (nearest one)
--   3. else nearest segment within tol_m        -> that segment
--   4. else                                     -> unmatched, reason 'outside_tolerance'
-- tol_m is your call: 45.72 m = 150 ft is a placeholder. distance_m is stored for every
-- crash, so you can see what any other tolerance would do without re-running.
--
-- FIRST DRAFT: not yet run against real data.

SET search_path = tasc, public;
BEGIN;

DELETE FROM crash_match WHERE network_version = :'network_version';

INSERT INTO crash_match (crash_id, network_version, site_id, nearest_site_id, distance_m, tolerance_m, status, reason)
SELECT c.crash_id,
       :'network_version',
       CASE WHEN i.site_id IS NOT NULL THEN i.site_id
            WHEN s.dist <= :tol_m     THEN s.site_id
       END,
       COALESCE(i.site_id, s.site_id),
       COALESCE(i.dist, s.dist),
       :tol_m,
       CASE WHEN i.site_id IS NOT NULL OR s.dist <= :tol_m THEN 'matched' ELSE 'unmatched' END,
       CASE WHEN c.geom IS NULL THEN 'no_coordinates'
            WHEN i.site_id IS NULL AND (s.dist IS NULL OR s.dist > :tol_m) THEN 'outside_tolerance'
       END
FROM crash c
LEFT JOIN LATERAL (
    SELECT site_id, ST_Distance(site.geom, c.geom) AS dist
    FROM site
    WHERE site_type = 'intersection'
      AND network_version = :'network_version'
      AND ST_DWithin(site.geom, c.geom, 76.2)
    ORDER BY site.geom <-> c.geom
    LIMIT 1
) i ON c.geom IS NOT NULL
LEFT JOIN LATERAL (
    SELECT site_id, ST_Distance(site.geom, c.geom) AS dist
    FROM site
    WHERE site_type = 'segment'
      AND network_version = :'network_version'
    ORDER BY site.geom <-> c.geom
    LIMIT 1
) s ON c.geom IS NOT NULL AND i.site_id IS NULL;

COMMIT;

SELECT * FROM match_rate WHERE network_version = :'network_version';
