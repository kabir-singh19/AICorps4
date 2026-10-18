-- S1 -> S2 integration views (IF-09), adopted from Param_Shelar/docs/s1_views_proposal.sql.
-- Run after the network, matching and features exist. Safe to re-run.
--   psql "$DATABASE_URL" -v s2_password="$S2_PASSWORD" -f sql/05_s2_interface.sql
-- s2_password is optional; without it the read-only role is created but cannot log in.
--
-- These describe the CORRIDOR network (v0_2019) for the M2 diagnostic. A full-city network
-- needs a different in_analysis_area rule (the College Station boundary, not corridor names).

SET search_path = tasc, public;
BEGIN;

-- 1. Sites: analysis membership, the two lengths S2 needs, and a road name.
--    risk_length_mi    exposure and the per-mile rate denominator; > 0 for every site.
--    network_length_mi share of network length used for 11% flagging; no double counting.
--    Length policy, agreed with S2 on 18 Oct 2026: segments run all the way through each
--    intersection, so intersections add 0 flagging length; their exposure is the ICD Table 9
--    250 ft influence zone (250 / 5280 mi).
CREATE OR REPLACE VIEW s2_site_scope AS
WITH corridor AS (SELECT DISTINCT route_name, corridor FROM corridor_street),
     intersection_name AS (
         -- An intersection is named after the corridors whose segments end at it.
         SELECT i.site_id, string_agg(DISTINCT c.corridor, ' & ' ORDER BY c.corridor) AS road_name
         FROM site i
         JOIN site s ON s.network_version = i.network_version AND s.site_type = 'segment'
                    AND ST_DWithin(i.geom, s.geom, 1)
         JOIN road r ON r.road_id = s.road_id
         JOIN corridor c ON c.route_name = r.route_name
         WHERE i.site_type = 'intersection'
         GROUP BY i.site_id)
SELECT s.site_id,
       s.network_version,
       true AS in_analysis_area,
       CASE s.site_type WHEN 'segment' THEN s.length_m / 1609.344 ELSE 250 / 5280.0 END AS risk_length_mi,
       CASE s.site_type WHEN 'segment' THEN s.length_m / 1609.344 ELSE 0 END           AS network_length_mi,
       COALESCE(c.corridor, n.road_name, r.route_name, '') AS road_name
FROM site s
LEFT JOIN road r USING (road_id)
LEFT JOIN corridor c ON c.route_name = r.route_name
LEFT JOIN intersection_name n ON n.site_id = s.site_id;

-- 2. Crashes: every crash classified once, including ones without coordinates. For the corridor
--    network, "in the analysis area" means CRIS recorded the crash on a corridor street, the
--    same rule 03_map_match.sql uses, so unmatched and no-coordinate corridor crashes stay in
--    the capture denominator.
CREATE OR REPLACE VIEW s2_crash_scope AS
SELECT c.crash_id,
       COALESCE(upper(trim(c.street_name)) IN (SELECT street_name FROM corridor_street), false)
           AS in_analysis_area
FROM crash c;

-- 3. Source provenance: one row per source, with the evidence for its dates.
--    Predictor and history sources must be dated, and publicly available, by 2022-12-31.
--    `source` must equal site_feature.source for predictors.
CREATE TABLE IF NOT EXISTS s2_source_availability (
    source          text PRIMARY KEY,
    version         text NOT NULL,
    role            text NOT NULL CHECK (role IN ('predictor', 'history', 'evaluation', 'baseline')),
    as_of_date      date NOT NULL,      -- date the data describes
    available_as_of date NOT NULL,      -- date it was publicly available
    evidence        text NOT NULL       -- where the dates come from
);

INSERT INTO s2_source_availability (source, version, role, as_of_date, available_as_of, evidence) VALUES
  ('roadway_inventory_2019', 'TxDOT Roadway Inventory 2019 snapshot', 'predictor', '2019-12-31', '2021-08-06',
   'ArcGIS item 9466b4e7c8c94af08d508078ec9e1742 ("Roadway Inventory 2019", owner TPP_GIS) created 2021-08-06; '
   'layer services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services/TxDOT_Roadway_Inventory_2019/FeatureServer/0 '
   'editingInfo.dataLastEditDate 2021-08-06 (data unchanged since; item metadata edited 2025-02-25). '
   'Checked 2026-10-18. Downloaded 2026-10-07 by fetch_roads.py, Brazos County (CO=21); all AADT_YEAR = 2019.'),
  ('network v0_2019', 'v0_2019', 'predictor', '2019-12-31', '2021-08-06',
   'Derived only from roadway_inventory_2019 by 02_build_network.sql (routes BS0006R, FM0060, FM2154; '
   'city 9050; KG roadbed). Used for the intersection feature "legs". Built 2026-10-07; it uses no '
   'information beyond its source, so it carries the source''s availability date.'),
  ('cris_history', 'CRIS Query 2016-2022, College Station', 'history', '2022-12-31', '2022-12-31',
   'Crash facts for 2016-2022 (each crash dated on or before the cutoff). Exported from CRIS Query on '
   '2026-10-06/07; CRIS may revise or add late reports after the cutoff, which this export would include.'),
  ('cris_test', 'CRIS Query 2023-2025, College Station', 'evaluation', '2025-12-31', '2026-10-07',
   'CRIS Query exports downloaded 2026-10-07 (Brazos County, City of College Station, one file per year). '
   'Held out: never used for fitting.')
ON CONFLICT (source) DO UPDATE SET
    version = EXCLUDED.version, role = EXCLUDED.role, as_of_date = EXCLUDED.as_of_date,
    available_as_of = EXCLUDED.available_as_of, evidence = EXCLUDED.evidence;

CREATE OR REPLACE VIEW s2_source_registry AS
SELECT n.network_version, n.feature_set, a.source, a.version, a.as_of_date, a.available_as_of, a.role
FROM (SELECT DISTINCT s.network_version, f.feature_set
      FROM site s JOIN site_feature f USING (site_id)) n
CROSS JOIN s2_source_availability a;

-- 4. HIN membership (s2_hin_site) waits for the MPO layer. Until then S2 leaves hin_view out of
--    its config: methods B and C run, and method A is reported as unavailable.

COMMIT;

-- 5. Read-only role for S2: SELECT on the three views and the tables S2 reads, nothing else.
SELECT 'CREATE ROLE s2_reader LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 's2_reader') \gexec
GRANT CONNECT ON DATABASE tasc TO s2_reader;
GRANT USAGE ON SCHEMA tasc TO s2_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA tasc FROM s2_reader;
GRANT SELECT ON tasc.s2_site_scope, tasc.s2_crash_scope, tasc.s2_source_registry,
                tasc.site, tasc.site_feature, tasc.crash, tasc.crash_match TO s2_reader;
\if :{?s2_password}
ALTER ROLE s2_reader PASSWORD :'s2_password';
\else
\echo 'Note: s2_password not given, so s2_reader has no password and cannot log in yet.'
\endif

-- Checks: one scope row per site, lengths, and which sources are registered.
SELECT v.network_version,
       count(*) FILTER (WHERE s.site_type = 'segment')      AS segments,
       count(*) FILTER (WHERE s.site_type = 'intersection') AS intersections,
       count(*) FILTER (WHERE v.risk_length_mi <= 0)       AS nonpositive_risk_length,
       round(sum(v.network_length_mi)::numeric, 2)          AS total_network_mi
FROM s2_site_scope v JOIN site s USING (site_id, network_version)
GROUP BY v.network_version;
SELECT source, role, as_of_date, available_as_of FROM s2_source_availability ORDER BY role, source;
