# S1 · Road Network, Features & Database — baseline v0

Starting point for the S1 subsystem of TASC (Kabir). It gives the team a real PostGIS database
(IF-09) to point at, and a first pass at each S1 requirement from the midterm slides.

## What is here

| File | What it does | Slide requirement |
|---|---|---|
| `docker-compose.yml` | PostgreSQL 16 + PostGIS on port 5432, 2 GB cap | IF-09, container budget |
| `sql/init/01_schema.sql` | Tables, views, and the leakage trigger. Runs on first start. | "owns the database schema" |
| `ingest.py crashes` | Validates a CRIS CSV, rejects the whole file at more than 2% bad records, loads the rest | 2% bad-record stop (FSR 3.2.3.1.2) |
| `ingest.py roads` | Loads TxDOT roadway inventory GeoJSON into UTM 14N | IF-02 |
| `sql/02_build_network.sql` | 0.1-mi segments and 3+ leg intersections | Network build (due 10/20) |
| `sql/03_map_match.sql` | Matches crashes to sites, logs every miss, prints the F&SI match rate | 95% matched (due 10/20) |
| `tests/test_validate.py` | 8 tests for the crash validator, no database needed | Ingest tests (due 11/17) |

## Quickstart

```bash
docker compose up -d                      # database + schema
pip install -r requirements.txt

# 1. Check your CRIS download before touching the database
python ingest.py crashes data/cris_2022.csv --dry-run

# 2. Load crashes (one file per year) and roads
python ingest.py crashes data/cris_2022.csv
python ingest.py roads data/roadway_brazos.geojson --as-of 2022-12-31

# 3. Build the network and match crashes
export DATABASE_URL=postgresql://tasc:tasc@localhost:5432/tasc
psql "$DATABASE_URL" -v network_version=v0 -v as_of=2022-12-31 -f sql/02_build_network.sql
psql "$DATABASE_URL" -v network_version=v0 -v tol_m=45.72      -f sql/03_map_match.sql
```

No `psql` on your machine? Use the one in the container:
`docker compose exec -T db psql -U tasc -d tasc -v network_version=v0 -v as_of=2022-12-31 < sql/02_build_network.sql`

Road data: on the TxDOT open-data portal, filter the Roadway Inventory layer to Brazos County
before downloading as GeoJSON. The statewide file is too big to load this way.

## What has and has not been run

- **Run and passing:** the 10 validator tests; the schema's tables, views and leakage trigger on plain
  PostgreSQL 16 (a 2024-dated feature was refused from `backtest_2022` and accepted into `current`).
- **Dry run on real data (7 Oct 2026):** CRIS Query exports for 2016–2025, filtered to Brazos County,
  City of College Station, one file per year. All 10 files: 0% bad, and the row count read by
  `ingest.py` equals the "Your query returned a total of N Crashes" line in each file's preamble.
  CRIS keeps 10 years plus the current one, so 2015 is no longer available from CRIS Query.
- **Loaded into PostGIS (7 Oct 2026):** all 10 files through `ingest.py crashes`: 16,539 crashes,
  10 `ingest_run` rows marked `loaded`, geometry stored in EPSG:32614 and converting back to the
  source lat/lon exactly. Runs on Apple Silicon under amd64 emulation (see below).
- **Network v0_2019 (7 Oct 2026):** `fetch_roads.py 2019` → `ingest.py roads --as-of 2019-12-31` →
  `02_build_network.sql` with `routes=BS0006R,FM0060,FM2154 city_code=9050` (Texas Ave, University Dr,
  Wellborn Rd inside College Station, centerline only). Result: 185 segments, 18.1 mi, all 0.055–0.099 mi;
  2 intersections (University & Wellborn, University & Texas). The 2019 snapshot is used because TxDOT
  publishes no 2020–2022 snapshot and later ones carry post-2022 AADT.
- **Not yet run:** `03_map_match.sql`.

## Check these first

1. **CRIS column names.** Checked against CRIS Query exports (`Crash ID`, `Crash Date`,
   `Crash Severity`, `Latitude`, `Longitude`, `Light Condition`, `Manner of Collision`). The 11-line
   preamble those exports start with is skipped automatically. Bulk extract files are still unchecked.
2. **Severity codes.** CRIS Query exports use labels (`K - FATAL INJURY`, `A - SUSPECTED SERIOUS
   INJURY`, `99 - UNKNOWN`), which parse correctly. The numeric `SEVERITY_CODES` (4 = fatal,
   1 = serious injury) only matter for bulk extract files and are still unconfirmed.

## Decisions that are yours to make

- **Match tolerance.** `tol_m=45.72` (150 ft) is a placeholder. `crash_match.distance_m` is stored for
  every crash, so you can see the match rate at any tolerance with one query.
- ~~**Is exactly 3.00% a stop?**~~ Decided: the FSR says *more than* 2%, so exactly 2.00% loads and
  anything above it stops. Covered by `test_exactly_two_percent_loads` and `test_over_two_percent_bad_stops`.
- **Intersection zone vs. segment length.** Segments currently run all the way to the intersection
  point. Crashes inside the 250 ft zone go to the intersection, so agree with Param whether segment
  length (his per-mile denominator) should exclude the zone.

## Known limits of the database container

- `postgis/postgis:16-3.4` is published for amd64 only. On Apple Silicon (and the arm64 Raspberry Pi 5
  reference host) it runs under emulation, which works but is slow to start. An image built for both
  amd64 and arm64 is still to be chosen.

## Known limits of the network build

- Lines are split wherever they cross on the map, so an overpass (SH 6 over a cross street) becomes a
  false intersection. OpenStreetMap has bridge tags that can fix this later.
- Divided roads drawn as two lines will produce two intersections close together.
- Segment attributes come from the nearest source road at the segment midpoint.

## Next steps (in slide order)

1. Get real CRIS and roadway files through the quickstart; fix what breaks.
2. Tune the tolerance until `SELECT * FROM tasc.match_rate;` shows 95% or better, and look at what is
   in `crash_match WHERE status = 'unmatched'`.
3. Fill `site_feature` from `road` (lanes, speed, AADT with `as_of_date` from `aadt_year`), then add
   OSM, streetlights and the HIN layer.
4. Add a read-only database role for S2, S3 and S4.
