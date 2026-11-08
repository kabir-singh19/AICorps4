-- MPO High-Injury Network (IF-05) membership for S2 method A: tasc.s2_hin_site.
-- Adopted from ATSC/S2_Risk_Model_Backtest/docs/s1_hin_view_proposal.sql (8 Nov 2026).
--
-- Load the lines first:  ingest.py hin <file.geojson> --version <hin_version>
-- Then:
--   psql "$DATABASE_URL" -v network_version=v1_2022 -v hin_version=<hin_version> \
--        -v hin_buffer_m=30 -v hin_available_as_of=YYYY-MM-DD -v hin_evidence='<text>' -f sql/08_hin.sql
--
-- Rule (ICD Table 5, team rule of 8 Nov 2026):
--   segment       in_hin when >= 50% of its length lies within hin_buffer_m of a HIN line
--   intersection  in_hin when its center lies within hin_buffer_m of a HIN line
-- The HIN is method A only. It is never a model feature.

\set ON_ERROR_STOP on
\if :{?network_version}
\else
  \echo 'network_version is required' \quit
\endif
\if :{?hin_version}
\else
  \echo 'hin_version is required' \quit
\endif
\if :{?hin_buffer_m}
\else
  \echo 'hin_buffer_m is required' \quit
\endif
\if :{?hin_available_as_of}
\else
  \echo 'hin_available_as_of is required' \quit
\endif
\if :{?hin_evidence}
\else
  \echo 'hin_evidence is required' \quit
\endif

SET search_path = tasc, public;
BEGIN;

-- Role 'baseline': as_of_date is the consultant's crash-history cutoff (2017-2022 crashes).
INSERT INTO s2_source_availability (source, version, role, as_of_date, available_as_of, evidence) VALUES
  ('mpo_hin', :'hin_version', 'baseline', '2022-12-31', :'hin_available_as_of', :'hin_evidence')
ON CONFLICT (source) DO UPDATE SET
    version = EXCLUDED.version, role = EXCLUDED.role, as_of_date = EXCLUDED.as_of_date,
    available_as_of = EXCLUDED.available_as_of, evidence = EXCLUDED.evidence;

-- Membership is materialized so S2/S4 reads are fast and stable; the view exposes it.
DROP VIEW IF EXISTS s2_hin_site;
CREATE TABLE IF NOT EXISTS hin_site (
    site_id         bigint NOT NULL,
    network_version text   NOT NULL,
    hin_version     text   NOT NULL,
    hin_buffer_m    double precision NOT NULL,
    overlap_share   double precision,          -- segments: share of length within the buffer
    in_hin          boolean NOT NULL,
    PRIMARY KEY (site_id, network_version, hin_version)
);
DELETE FROM hin_site WHERE network_version = :'network_version' AND hin_version = :'hin_version';

WITH zone AS (
    SELECT ST_Union(ST_Buffer(geom, :hin_buffer_m)) AS z
    FROM hin_line WHERE hin_version = :'hin_version'
), lines AS (
    SELECT ST_Union(geom) AS l FROM hin_line WHERE hin_version = :'hin_version'
)
INSERT INTO hin_site (site_id, network_version, hin_version, hin_buffer_m, overlap_share, in_hin)
SELECT s.site_id, s.network_version, :'hin_version', :hin_buffer_m,
       CASE WHEN s.site_type = 'segment'
            THEN ST_Length(ST_Intersection(s.geom, zone.z)) / NULLIF(ST_Length(s.geom), 0) END,
       CASE WHEN s.site_type = 'segment'
            THEN ST_Length(ST_Intersection(s.geom, zone.z)) >= 0.5 * ST_Length(s.geom)
            ELSE ST_DWithin(s.geom, lines.l, :hin_buffer_m) END
FROM site s CROSS JOIN zone CROSS JOIN lines
WHERE s.network_version = :'network_version';

CREATE VIEW s2_hin_site AS
SELECT site_id, network_version, hin_version, in_hin, overlap_share FROM hin_site;

COMMIT;

GRANT SELECT ON tasc.s2_hin_site, tasc.hin_site, tasc.hin_line TO s2_reader;

-- Checks: every site exactly once; HIN share of network length.
SELECT count(*) AS sites, count(*) - count(DISTINCT site_id) AS duplicates,
       count(*) FILTER (WHERE in_hin) AS in_hin, count(*) FILTER (WHERE in_hin IS NULL) AS null_in_hin
FROM s2_hin_site WHERE network_version = :'network_version' AND hin_version = :'hin_version';
SELECT s.site_type, count(*) FILTER (WHERE h.in_hin) AS in_hin, count(*) AS sites,
       round((sum(v.network_length_mi) FILTER (WHERE h.in_hin))::numeric, 1) AS hin_network_mi,
       round((100 * sum(v.network_length_mi) FILTER (WHERE h.in_hin) / NULLIF(sum(v.network_length_mi), 0))::numeric, 2)
           AS hin_share_pct
FROM s2_hin_site h JOIN s2_site_scope v USING (site_id, network_version) JOIN site s USING (site_id, network_version)
WHERE h.network_version = :'network_version' AND h.hin_version = :'hin_version' AND v.in_analysis_area
GROUP BY ROLLUP (s.site_type);
