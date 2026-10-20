-- PROPOSAL from S2 for S1 (Kabir) to review. Not run, and not part of the S1 schema until S1
-- adopts it. It adds the published MPO High-Injury Network (IF-05) and the view S2 reads for
-- method A, tasc.s2_hin_site (see docs/interfaces.md). Written against
-- Kabir_Singh/sql/init/01_schema.sql and sql/05_s2_interface.sql as of 20 Oct 2026.
--
-- Load only the real MPO layer. Do not draw, approximate or reconstruct HIN lines here; if the
-- layer cannot be obtained, that is a separate team decision (CLAUDE.md, IF-05).
--
-- Run after 05_s2_interface.sql. Every variable is required; there are no defaults:
--   psql "$DATABASE_URL" \
--     -v network_version=v0_2019 \
--     -v hin_version='<version as published, e.g. the CSAP edition>' \
--     -v hin_available_as_of=YYYY-MM-DD \
--     -v hin_evidence='<where the layer came from and how its dates are known>' \
--     -v hin_buffer_m=<tolerance in meters> \
--     -f s1_hin_view_proposal.sql

\set ON_ERROR_STOP on
\if :{?network_version}
\else
  \echo 'network_version is required' \quit
\endif
\if :{?hin_version}
\else
  \echo 'hin_version is required' \quit
\endif
\if :{?hin_available_as_of}
\else
  \echo 'hin_available_as_of is required' \quit
\endif
\if :{?hin_evidence}
\else
  \echo 'hin_evidence is required' \quit
\endif
\if :{?hin_buffer_m}
\else
  \echo 'hin_buffer_m is required (buffer tolerance in meters around HIN lines)' \quit
\endif

SET search_path = tasc, public;
BEGIN;

-- 1. The HIN layer as published, one row per line feature, in EPSG:32614 like every S1 geometry.
--    Loading is S1's choice. One way, from the MPO's GeoJSON or shapefile on the host:
--      ogr2ogr -f PostgreSQL PG:"$DATABASE_URL" hin.geojson -nln tasc.hin_staging \
--              -t_srs EPSG:32614 -nlt PROMOTE_TO_MULTI -lco GEOMETRY_NAME=geom
--      INSERT INTO tasc.hin_line (hin_version, source, geom, attributes)
--      SELECT :'hin_version', 'mpo_hin', (ST_Dump(geom)).geom, to_jsonb(h) - 'geom'
--      FROM tasc.hin_staging h;
--    An `ingest.py hin` subcommand would fit the existing loaders equally well.
CREATE TABLE IF NOT EXISTS hin_line (
    hin_line_id bigserial PRIMARY KEY,
    hin_version text NOT NULL,
    source      text NOT NULL,                       -- equals s2_source_availability.source
    geom        geometry(LineString, 32614) NOT NULL,
    attributes  jsonb                                -- original fields, kept for audit
);
CREATE INDEX IF NOT EXISTS hin_line_geom_gix ON hin_line USING gist (geom);
CREATE INDEX IF NOT EXISTS hin_line_version_ix ON hin_line (hin_version);

-- 2. Provenance. Role 'baseline': the HIN is method A, never a model feature. as_of_date is the
--    consultant's crash-history cutoff (2017-2022 crashes, so 2022-12-31). available_as_of is the
--    publication date, which may be after 2022; S2 checks only the crash-history cutoff.
--    S2 config must then set hin_source = 'mpo_hin' and hin_as_of_date = '2022-12-31'.
INSERT INTO s2_source_availability (source, version, role, as_of_date, available_as_of, evidence) VALUES
  ('mpo_hin', :'hin_version', 'baseline', '2022-12-31', :'hin_available_as_of', :'hin_evidence')
ON CONFLICT (source) DO UPDATE SET
    version = EXCLUDED.version, role = EXCLUDED.role, as_of_date = EXCLUDED.as_of_date,
    available_as_of = EXCLUDED.available_as_of, evidence = EXCLUDED.evidence;

-- 3. Membership: one row per site in the network, every site exactly once.
--    Segments (ICD Table 5): in_hin when at least 50% of the segment's length lies within
--    hin_buffer_m of the HIN. Same rule as Param_Shelar/hin_baseline.py overlap_membership():
--    overlap_length >= 0.5 * segment_length. The buffer absorbs small offsets between the MPO's
--    linework and the TxDOT centerline; record the value used and check sensitivity to it.
--    Overlap is clipped to the segment, so it can never exceed the segment's own length.
--
--    Intersections: TODO, NOT AGREED BY THE TEAM. Until a rule is chosen, in_hin is NULL for
--    intersections. S2 treats any NULL as a partial mapping and refuses to run method A, so this
--    fails closed rather than guessing. Options:
--      (a) Zone rule: in_hin when any HIN line passes within the 250 ft (76.2 m) influence zone:
--            EXISTS (SELECT 1 FROM hin_line h WHERE h.hin_version = :'hin_version'
--                    AND ST_DWithin(s.geom, h.geom, 76.2))
--      (b) Leg rule: in_hin when at least one segment that ends at the intersection is in_hin
--          (same adjacency test as s2_site_scope's intersection_name: ST_DWithin(i.geom, seg.geom, 1)).
--    Note that under the agreed length policy intersections add 0 flagging miles, so the choice
--    changes which crashes A captures but not A's share of network length.
CREATE OR REPLACE VIEW s2_hin_site AS
WITH hin AS (
    SELECT hin_version, ST_Union(ST_Buffer(geom, :hin_buffer_m)) AS zone
    FROM hin_line
    WHERE hin_version = :'hin_version'
    GROUP BY hin_version
)
SELECT s.site_id,
       s.network_version,
       h.hin_version,
       CASE s.site_type
           WHEN 'segment' THEN
               ST_Length(ST_Intersection(s.geom, h.zone)) >= 0.5 * ST_Length(s.geom)
           ELSE NULL::boolean   -- TODO: intersection rule, see options (a) and (b) above
       END AS in_hin
FROM site s
CROSS JOIN hin h
WHERE s.network_version = :'network_version';

COMMIT;

GRANT SELECT ON tasc.s2_hin_site TO s2_reader;

-- Checks. Expect: sites = number of sites in the network, duplicates = 0, and null_in_hin equal
-- to the intersection count until the intersection rule is agreed (then 0).
SELECT count(*)                                        AS sites,
       count(*) - count(DISTINCT site_id)              AS duplicates,
       count(*) FILTER (WHERE in_hin)                  AS in_hin,
       count(*) FILTER (WHERE in_hin IS NULL)          AS null_in_hin
FROM s2_hin_site;
SELECT round((100 * sum(v.network_length_mi) FILTER (WHERE h.in_hin) / sum(v.network_length_mi))::numeric, 2)
           AS hin_share_of_network_pct
FROM s2_hin_site h JOIN s2_site_scope v USING (site_id, network_version);
