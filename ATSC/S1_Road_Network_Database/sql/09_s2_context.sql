-- S2/S3/S4 read-only context views (IF-09), added 8 Nov 2026.
--   s2_site_context  site geometry (EPSG:4326 GeoJSON), centroid, route, jurisdiction and, for
--                    intersections, the largest and smallest AADT of the segments that meet there
--   s2_crash_detail  one row per crash with its match and the crash-type flags S2 and S3 use
--
--   psql "$DATABASE_URL" -v feature_set=backtest_2022 -f sql/09_s2_context.sql
--
-- Jurisdiction: TxDOT for state routes (SH, US, IH, FM, BS, SL, SS, PR route codes), TAMU for
-- campus streets, City otherwise. An intersection is "City/TxDOT" when it joins both.
-- AADT at intersections comes from segment features of the given feature set (TxDOT 2019 in
-- backtest_2022), so it carries the same as-of date as those features.

\set ON_ERROR_STOP on
\if :{?feature_set}
\else
  \echo 'feature_set is required' \quit
\endif

SET search_path = tasc, public;
BEGIN;

DROP VIEW IF EXISTS s2_site_context;
DROP TABLE IF EXISTS site_context;
CREATE TABLE site_context AS
WITH seg AS (
    SELECT s.site_id, s.network_version, s.geom, r.route_name, r.maintainer,
           CASE WHEN r.maintainer = 'TAMU' THEN 'TAMU'
                WHEN substr(coalesce(r.route_name, ''), 1, 2) IN ('SH','US','IH','FM','BS','SL','SS','PR') THEN 'TxDOT'
                ELSE 'City' END AS jurisdiction,
           f.value_num AS aadt
    FROM site s LEFT JOIN road r USING (road_id)
    LEFT JOIN site_feature f ON f.site_id = s.site_id AND f.feature_set = :'feature_set' AND f.feature_name = 'aadt'
    WHERE s.site_type = 'segment'
), legs AS (
    SELECT i.site_id, i.network_version,
           max(seg.aadt) AS aadt_major, min(seg.aadt) AS aadt_minor, count(*) AS approach_segments,
           CASE WHEN bool_and(seg.jurisdiction = 'TxDOT') THEN 'TxDOT'
                WHEN bool_or(seg.jurisdiction = 'TxDOT') THEN 'City/TxDOT'
                WHEN bool_and(seg.jurisdiction = 'TAMU') THEN 'TAMU'
                ELSE 'City' END AS jurisdiction,
           string_agg(DISTINCT seg.route_name, ',') FILTER (WHERE seg.jurisdiction = 'TxDOT') AS route_name
    FROM site i JOIN seg ON seg.network_version = i.network_version AND ST_DWithin(seg.geom, i.geom, 15)
    WHERE i.site_type = 'intersection'
    GROUP BY i.site_id, i.network_version
)
SELECT s.site_id, s.network_version, s.site_type,
       coalesce(seg.route_name, legs.route_name) AS route_name,
       coalesce(seg.jurisdiction, legs.jurisdiction, 'City') AS jurisdiction,
       legs.aadt_major, legs.aadt_minor, coalesce(legs.approach_segments, 0) AS approach_segments,
       ST_X(c.p) AS x_m, ST_Y(c.p) AS y_m,
       ST_X(ST_Transform(c.p, 4326)) AS lon, ST_Y(ST_Transform(c.p, 4326)) AS lat,
       ST_AsGeoJSON(ST_Transform(s.geom, 4326), 6) AS geojson
FROM site s
LEFT JOIN seg USING (site_id, network_version)
LEFT JOIN legs USING (site_id, network_version)
CROSS JOIN LATERAL (SELECT CASE WHEN s.site_type = 'segment' THEN ST_LineInterpolatePoint(s.geom, 0.5)
                                ELSE s.geom END AS p) c;
ALTER TABLE site_context ADD PRIMARY KEY (site_id, network_version);

CREATE VIEW s2_site_context AS SELECT * FROM site_context;

DROP VIEW IF EXISTS s2_crash_detail;
CREATE VIEW s2_crash_detail AS
SELECT c.crash_id::text AS crash_id, c.crash_date, c.crash_year, c.severity, m.network_version,
       m.status AS match_status, m.site_id, m.distance_m,
       c.crash_type, c.light_condition, c.surface_condition,
       c.crash_type LIKE 'ANGLE%'                                   AS angle,
       c.crash_type LIKE 'SAME DIRECTION%' AND (c.crash_type LIKE '%REAR END%' OR c.crash_type LIKE '%STOPPED%')
                                                                     AS rear_end,
       c.crash_type LIKE 'ONE MOTOR VEHICLE%'                       AS single_vehicle,
       c.crash_type LIKE 'OPPOSITE DIRECTION%'                      AS opposite_direction,
       c.crash_type LIKE '%SIDESWIPE%'                              AS sideswipe,
       split_part(c.light_condition, ' ', 1) IN ('2', '3', '4')     AS night,
       split_part(c.surface_condition, ' ', 1) IN ('2', '3')        AS wet
FROM crash c JOIN crash_match m USING (crash_id);

COMMIT;
GRANT SELECT ON tasc.s2_site_context, tasc.site_context, tasc.s2_crash_detail TO s2_reader;

SELECT network_version, site_type, jurisdiction, count(*), count(aadt_major) AS with_aadt
FROM s2_site_context GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
