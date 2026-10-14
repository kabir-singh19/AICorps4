-- PROPOSAL from S2 for S1 (Kabir) to review. Not run, and not part of the S1 schema until S1
-- adopts it. These are the read-only views S2's database.py reads (see docs/interfaces.md),
-- written against Kabir_Singh/sql/init/01_schema.sql as of 14 Oct 2026.
--
-- They describe the CORRIDOR network (v0_2019) for an M2 diagnostic run. A full-city network
-- needs a different in_analysis_area rule (the College Station boundary, not corridor names).

SET search_path = tasc, public;

-- 1. Sites: analysis membership and the two lengths S2 needs.
--    risk_length_mi    exposure and the per-mile rate denominator; must be > 0 for every site.
--    network_length_mi share of network length used for 11% flagging; must not double count.
--    PROPOSED length policy (needs S1/S2 agreement): segments run all the way through each
--    intersection, so intersections add 0 flagging length; their exposure is the ICD Table 9
--    "250 ft influence zone" (250 / 5280 mi).
CREATE OR REPLACE VIEW s2_site_scope AS
SELECT s.site_id,
       s.network_version,
       true AS in_analysis_area,
       CASE s.site_type WHEN 'segment' THEN s.length_m / 1609.344 ELSE 250 / 5280.0 END AS risk_length_mi,
       CASE s.site_type WHEN 'segment' THEN s.length_m / 1609.344 ELSE 0 END AS network_length_mi,
       COALESCE(cs.corridor, r.route_name, '') AS road_name
FROM site s
LEFT JOIN road r USING (road_id)
LEFT JOIN (SELECT DISTINCT route_name, corridor FROM corridor_street) cs ON cs.route_name = r.route_name;

-- 2. Crashes: every crash classified once, including ones without coordinates. For the corridor
--    run, "in the analysis area" means CRIS recorded the crash on a corridor street, the same rule
--    03_map_match.sql uses. Unmatched corridor crashes stay in the capture denominator.
CREATE OR REPLACE VIEW s2_crash_scope AS
SELECT c.crash_id,
       COALESCE(upper(trim(c.street_name)) IN (SELECT street_name FROM corridor_street), false)
           AS in_analysis_area
FROM crash c;

-- 3. Source provenance. One row per source; S1 fills the dates from evidence it holds.
--    Predictor and history sources must be dated, and available, no later than 2022-12-31.
CREATE TABLE IF NOT EXISTS s2_source_availability (
    source          text PRIMARY KEY,   -- must equal site_feature.source for predictors
    version         text NOT NULL,
    role            text NOT NULL CHECK (role IN ('predictor', 'history', 'evaluation', 'baseline')),
    as_of_date      date NOT NULL,      -- date the data describes
    available_as_of date NOT NULL,      -- date it was publicly available
    evidence        text NOT NULL       -- where the dates come from
);

-- Example rows. The NULLs are deliberate: S1 must supply real dates before these insert.
-- INSERT INTO s2_source_availability VALUES
--   ('roadway_inventory_2019', 'TxDOT 2019 snapshot', 'predictor', '2019-12-31', NULL, 'TxDOT publication date'),
--   ('network v0_2019',        'v0_2019',             'predictor', '2019-12-31', NULL, 'built from the 2019 snapshot'),
--   ('cris_history',           'CRIS Query 2016-2022','history',   '2022-12-31', '2022-12-31', 'crash facts through the cutoff; CRIS may revise records later'),
--   ('cris_test',              'CRIS Query 2023-2025','evaluation','2025-12-31', '2026-10-07', 'download date');

CREATE OR REPLACE VIEW s2_source_registry AS
SELECT n.network_version, n.feature_set, a.source, a.version, a.as_of_date, a.available_as_of, a.role
FROM (SELECT DISTINCT s.network_version, f.feature_set
      FROM site s JOIN site_feature f USING (site_id)) n
CROSS JOIN s2_source_availability a;

-- 4. HIN membership (s2_hin_site) waits for the MPO layer. Until then, leave hin_view out of the
--    S2 config: methods B and C still run, and method A is reported as unavailable.

-- S2 also needs a read-only role on these views and on site, site_feature, crash, crash_match.
