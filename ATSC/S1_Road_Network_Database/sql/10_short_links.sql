-- FSR 3.2.1.2 site definition: every segment 0.1 mi (+/- 0.05 mi).
-- 02_build_network.sql cuts each link into equal pieces of at most 0.1 mi, so a piece shorter than
-- 0.05 mi (80.47 m) only happens when the whole link between two nodes is that short. This step:
--   1. joins a short piece to the next segment of the same road when they meet at a plain node
--      (no intersection site there) and the result stays within 0.15 mi;
--   2. folds the remaining short pieces into the intersection at their end. A link under 0.05 mi
--      (264 ft) that ends at an intersection lies inside that intersection's 250 ft influence zone,
--      where crashes already belong to the intersection;
--   3. folds isolated short pieces (no intersection, nothing to join) into the nearest site.
-- Crash matches move with the piece. Every change is logged in tasc.site_fold.
-- Usage: psql -v network_version=v1_2022 < sql/10_short_links.sql
\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE IF NOT EXISTS tasc.site_fold (
  network_version text NOT NULL,
  site_id bigint NOT NULL,
  into_site_id bigint NOT NULL,
  action text NOT NULL,
  length_m double precision,
  folded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (network_version, site_id)
);
DELETE FROM tasc.site_fold WHERE network_version = :'network_version';

CREATE TEMP TABLE short_seg AS
SELECT s.site_id, s.road_id, ST_LineMerge(s.geom) AS g, s.length_m
FROM tasc.site s
WHERE s.network_version = :'network_version' AND s.site_type = 'segment' AND s.length_m < 80.4672;

-- 1. join at plain nodes, one piece at a time (a joined segment can take another piece while it stays <= 0.15 mi)
SELECT set_config('atsc.nv', :'network_version', true);
DO $$
DECLARE r record; nv text := current_setting('atsc.nv');
BEGIN
  LOOP
    SELECT ss.site_id, ss.g, ss.length_m, nb.site_id AS into_id INTO r
    FROM short_seg ss
    JOIN tasc.site nb ON nb.network_version = nv AND nb.site_type = 'segment' AND nb.site_id <> ss.site_id
     AND nb.road_id IS NOT DISTINCT FROM ss.road_id AND nb.length_m + ss.length_m <= 241.4016
     AND (ST_DWithin(nb.geom, ST_StartPoint(ss.g), 1) OR ST_DWithin(nb.geom, ST_EndPoint(ss.g), 1))
    WHERE NOT EXISTS (SELECT 1 FROM short_seg o WHERE o.site_id = nb.site_id)
      AND NOT EXISTS (SELECT 1 FROM tasc.site i WHERE i.network_version = nv AND i.site_type = 'intersection'
                        AND ST_DWithin(i.geom, ST_ClosestPoint(ss.g, nb.geom), 2))
    ORDER BY ss.site_id, nb.length_m
    LIMIT 1;
    EXIT WHEN NOT FOUND;
    UPDATE tasc.site SET geom = ST_LineMerge(ST_Union(geom, r.g)), length_m = length_m + r.length_m WHERE site_id = r.into_id;
    INSERT INTO tasc.site_fold (network_version, site_id, into_site_id, action, length_m)
    VALUES (nv, r.site_id, r.into_id, 'joined to the next segment of the same road', r.length_m);
    DELETE FROM short_seg WHERE site_id = r.site_id;
  END LOOP;
END $$;

-- 2. fold into the intersection at an end of the piece
INSERT INTO tasc.site_fold (network_version, site_id, into_site_id, action, length_m)
SELECT :'network_version', ss.site_id, i.site_id, 'inside the influence zone of this intersection', ss.length_m
FROM short_seg ss
CROSS JOIN LATERAL (
  SELECT i.site_id FROM tasc.site i
  WHERE i.network_version = :'network_version' AND i.site_type = 'intersection'
    AND (ST_DWithin(i.geom, ST_StartPoint(ss.g), 2) OR ST_DWithin(i.geom, ST_EndPoint(ss.g), 2))
  ORDER BY ST_Distance(i.geom, ST_LineInterpolatePoint(ss.g, 0.5)) LIMIT 1) i
ON CONFLICT DO NOTHING;
DELETE FROM short_seg WHERE site_id IN (SELECT site_id FROM tasc.site_fold WHERE network_version = :'network_version');

-- 3. isolated pieces: nearest remaining site
INSERT INTO tasc.site_fold (network_version, site_id, into_site_id, action, length_m)
SELECT :'network_version', ss.site_id, n.site_id, 'isolated short piece, folded into the nearest site', ss.length_m
FROM short_seg ss
CROSS JOIN LATERAL (
  SELECT s.site_id FROM tasc.site s
  WHERE s.network_version = :'network_version' AND s.site_id <> ss.site_id
    AND s.site_id NOT IN (SELECT site_id FROM tasc.site_fold WHERE network_version = :'network_version')
    AND s.site_id NOT IN (SELECT site_id FROM short_seg)
  ORDER BY s.geom <-> ss.g LIMIT 1) n
ON CONFLICT DO NOTHING;

-- move crash matches, then drop the folded pieces (features cascade)
UPDATE tasc.crash_match m SET site_id = f.into_site_id
FROM tasc.site_fold f WHERE f.network_version = :'network_version' AND m.network_version = f.network_version AND m.site_id = f.site_id;
UPDATE tasc.crash_match m SET nearest_site_id = f.into_site_id
FROM tasc.site_fold f WHERE f.network_version = :'network_version' AND m.network_version = f.network_version AND m.nearest_site_id = f.site_id;
DELETE FROM tasc.site s USING tasc.site_fold f
WHERE f.network_version = :'network_version' AND s.site_id = f.site_id;

SELECT action, count(*) AS pieces, round(sum(length_m)::numeric / 1609.344, 2) AS miles
FROM tasc.site_fold WHERE network_version = :'network_version' GROUP BY 1 ORDER BY 2 DESC;
SELECT count(*) AS segments,
       count(*) FILTER (WHERE length_m < 80.4672) AS under_0_05_mi,
       count(*) FILTER (WHERE length_m > 241.4016) AS over_0_15_mi
FROM tasc.site WHERE network_version = :'network_version' AND site_type = 'segment';
COMMIT;
