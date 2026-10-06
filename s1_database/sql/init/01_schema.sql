-- TASC S1 schema (IF-09). Baseline v0.
-- All geometry is stored in UTM Zone 14N (EPSG:32614), so lengths and distances are in meters.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS tasc;
SET search_path = tasc, public;

-- ---------------------------------------------------------------------------
-- Ingest bookkeeping: one row per file we try to load, plus every bad record.
-- FSR: "A file with 3% bad records stops the pipeline."
-- ---------------------------------------------------------------------------
CREATE TABLE ingest_run (
    run_id      bigserial PRIMARY KEY,
    source      text        NOT NULL,              -- 'cris', 'roadway_inventory', ...
    file_name   text        NOT NULL,
    file_sha256 text,
    started_at  timestamptz NOT NULL DEFAULT now(),
    rows_total  integer     NOT NULL,
    rows_bad    integer     NOT NULL,
    bad_pct     numeric(6,3) NOT NULL,
    status      text        NOT NULL CHECK (status IN ('loaded', 'rejected')),
    note        text
);

CREATE TABLE ingest_reject (
    run_id     bigint  NOT NULL REFERENCES ingest_run ON DELETE CASCADE,
    row_number integer NOT NULL,                   -- 1 = first data row of the file
    reason     text    NOT NULL,
    raw        jsonb   NOT NULL                    -- the original row, untouched
);

-- ---------------------------------------------------------------------------
-- Crashes (IF-01, TxDOT CRIS)
-- ---------------------------------------------------------------------------
CREATE TABLE crash (
    crash_id        bigint PRIMARY KEY,
    crash_date      date    NOT NULL,
    crash_year      integer GENERATED ALWAYS AS (EXTRACT(year FROM crash_date)::integer) STORED,
    severity        char(1) NOT NULL CHECK (severity IN ('K','A','B','C','O','U')),  -- KABCO, U = unknown
    is_fsi          boolean GENERATED ALWAYS AS (severity IN ('K','A')) STORED,      -- fatal + serious injury
    crash_type      text,
    light_condition text,
    lat             double precision,
    lon             double precision,
    geom            geometry(Point, 32614),        -- NULL when CRIS has no coordinates
    run_id          bigint REFERENCES ingest_run
);
CREATE INDEX crash_geom_gix ON crash USING gist (geom);
CREATE INDEX crash_year_ix  ON crash (crash_year);

-- ---------------------------------------------------------------------------
-- Source road linework (IF-02, TxDOT roadway inventory), one row per line part.
-- ---------------------------------------------------------------------------
CREATE TABLE road (
    road_id     bigserial PRIMARY KEY,
    geom        geometry(LineString, 32614) NOT NULL,
    route_name  text,
    func_class  text,
    num_lanes   integer,
    speed_limit integer,                           -- mph
    median_type text,
    aadt        integer,
    aadt_year   integer,
    source      text NOT NULL,
    as_of_date  date NOT NULL,                     -- date the source data describes
    run_id      bigint REFERENCES ingest_run
);
CREATE INDEX road_geom_gix ON road USING gist (geom);

-- ---------------------------------------------------------------------------
-- Sites: the unit every other subsystem ranks, explains and maps.
--   segment      = LineString, at most 0.1 mi (160.934 m)
--   intersection = Point where 3+ legs meet; crashes within 250 ft (76.2 m) belong to it
-- ---------------------------------------------------------------------------
CREATE TABLE site (
    site_id         bigserial PRIMARY KEY,
    site_type       text NOT NULL CHECK (site_type IN ('segment', 'intersection')),
    geom            geometry(Geometry, 32614) NOT NULL,
    length_m        double precision,              -- segments only
    legs            integer,                       -- intersections only
    road_id         bigint REFERENCES road,        -- segments: source road nearest the midpoint
    network_version text NOT NULL,
    as_of_date      date NOT NULL
);
CREATE INDEX site_geom_gix ON site USING gist (geom);
CREATE INDEX site_version_ix ON site (network_version, site_type);

-- ---------------------------------------------------------------------------
-- Crash-to-site matching. Every crash gets a row, matched or not, so every miss is logged.
-- FSR: ">= 95% of geocoded fatal + serious crashes matched; every miss logged."
-- ---------------------------------------------------------------------------
CREATE TABLE crash_match (
    crash_id        bigint NOT NULL REFERENCES crash ON DELETE CASCADE,
    network_version text   NOT NULL,
    site_id         bigint REFERENCES site ON DELETE CASCADE,   -- NULL when unmatched
    nearest_site_id bigint,                                     -- kept even when unmatched
    distance_m      double precision,                           -- distance to nearest site
    tolerance_m     double precision NOT NULL,                  -- tolerance used for this run
    status          text NOT NULL CHECK (status IN ('matched', 'unmatched')),
    reason          text,                                       -- 'no_coordinates' | 'outside_tolerance'
    matched_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (crash_id, network_version)
);
CREATE INDEX crash_match_site_ix ON crash_match (site_id);

-- ---------------------------------------------------------------------------
-- As-of-dated features, with the leakage rule enforced by the database itself.
-- FSR: "Backtest refuses any feature dated after 31 Dec 2022."
-- ---------------------------------------------------------------------------
CREATE TABLE feature_set (
    name        text PRIMARY KEY,
    cutoff_date date,                              -- NULL = no cutoff
    note        text
);
INSERT INTO feature_set VALUES
    ('backtest_2022', DATE '2022-12-31', 'Backtest features: nothing dated after the cutoff may enter'),
    ('current',       NULL,              'Latest features for the live ranking');

CREATE TABLE site_feature (
    site_id      bigint NOT NULL REFERENCES site ON DELETE CASCADE,
    feature_set  text   NOT NULL REFERENCES feature_set,
    feature_name text   NOT NULL,
    value_num    double precision,
    value_text   text,
    as_of_date   date   NOT NULL,                  -- every feature carries its date
    source       text   NOT NULL,
    PRIMARY KEY (site_id, feature_set, feature_name)
);

CREATE FUNCTION enforce_feature_cutoff() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    cutoff date;
BEGIN
    SELECT cutoff_date INTO cutoff FROM tasc.feature_set WHERE name = NEW.feature_set;
    IF cutoff IS NOT NULL AND NEW.as_of_date > cutoff THEN
        RAISE EXCEPTION 'Leakage check: feature "%" for site % is dated %, after the % cutoff of feature set "%"',
            NEW.feature_name, NEW.site_id, NEW.as_of_date, cutoff, NEW.feature_set;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER site_feature_cutoff
    BEFORE INSERT OR UPDATE ON site_feature
    FOR EACH ROW EXECUTE FUNCTION enforce_feature_cutoff();

-- ---------------------------------------------------------------------------
-- Views the other subsystems read
-- ---------------------------------------------------------------------------

-- Crash counts per site per year (S2 trains on this; filter crash_year <= 2022 for the backtest).
CREATE VIEW site_crash_year AS
SELECT m.network_version, m.site_id, c.crash_year,
       count(*)                           AS crashes,
       count(*) FILTER (WHERE c.is_fsi)   AS fsi_crashes
FROM crash_match m
JOIN crash c USING (crash_id)
WHERE m.status = 'matched'
GROUP BY m.network_version, m.site_id, c.crash_year;

-- The 95% metric, straight from the data.
CREATE VIEW match_rate AS
SELECT m.network_version,
       count(*) FILTER (WHERE c.is_fsi AND c.geom IS NOT NULL)                          AS fsi_geocoded,
       count(*) FILTER (WHERE c.is_fsi AND c.geom IS NOT NULL AND m.status = 'matched') AS fsi_matched,
       round(100.0 * count(*) FILTER (WHERE c.is_fsi AND c.geom IS NOT NULL AND m.status = 'matched')
             / NULLIF(count(*) FILTER (WHERE c.is_fsi AND c.geom IS NOT NULL), 0), 2)    AS fsi_match_pct,
       count(*) FILTER (WHERE m.reason = 'no_coordinates')                              AS no_coordinates,
       count(*) FILTER (WHERE m.reason = 'outside_tolerance')                           AS outside_tolerance
FROM crash_match m
JOIN crash c USING (crash_id)
GROUP BY m.network_version;
