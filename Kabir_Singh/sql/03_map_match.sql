-- Match every crash to a site, and log every miss.
-- Run:  psql "$DATABASE_URL" -v network_version=v0_2019 -v tol_m=45.72 -f sql/03_map_match.sql
-- Needs tasc.corridor_street filled first:  python ingest.py corridors
--
-- Rule, in order:
--   1. street_name not a study-corridor spelling -> unmatched, reason 'off_corridor'
--   2. no coordinates                            -> unmatched, reason 'no_coordinates'
--   3. within 250 ft (76.2 m) of an intersection -> that intersection (nearest one)
--   4. else nearest segment ON THE CRASH'S OWN CORRIDOR within tol_m -> that segment
--   5. else                                      -> unmatched, reason 'outside_tolerance'
-- Rule 1 means a crash CRIS records on a cross street is never pulled onto a corridor, and
-- rule 4 means a Texas Ave crash near University Dr still goes to Texas Ave.
-- tol_m is your call: 45.72 m = 150 ft is a placeholder. distance_m is stored for every
-- corridor crash, so you can see what any other tolerance would do without re-running.

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
       CASE WHEN cs.route_name IS NULL THEN 'off_corridor'
            WHEN c.geom IS NULL       THEN 'no_coordinates'
            WHEN i.site_id IS NULL AND (s.dist IS NULL OR s.dist > :tol_m) THEN 'outside_tolerance'
       END
FROM crash c
LEFT JOIN corridor_street cs ON cs.street_name = upper(trim(c.street_name))
LEFT JOIN LATERAL (
    SELECT site_id, ST_Distance(site.geom, c.geom) AS dist
    FROM site
    WHERE site_type = 'intersection'
      AND network_version = :'network_version'
      AND ST_DWithin(site.geom, c.geom, 76.2)
    ORDER BY site.geom <-> c.geom
    LIMIT 1
) i ON cs.route_name IS NOT NULL AND c.geom IS NOT NULL
LEFT JOIN LATERAL (
    SELECT site.site_id, ST_Distance(site.geom, c.geom) AS dist
    FROM site
    JOIN road USING (road_id)
    WHERE site.site_type = 'segment'
      AND site.network_version = :'network_version'
      AND road.route_name = cs.route_name
    ORDER BY site.geom <-> c.geom
    LIMIT 1
) s ON cs.route_name IS NOT NULL AND c.geom IS NOT NULL AND i.site_id IS NULL;

COMMIT;

SELECT * FROM match_rate WHERE network_version = :'network_version';
