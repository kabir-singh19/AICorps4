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
| `ingest.py corridors` | Loads the study-corridor street spellings from `corridors.py` | Corridor scope |
| `fetch_roads.py` | Downloads Brazos County roadway inventory snapshots from TxDOT | IF-02 |
| `corridors.py` | The three corridors: TxDOT route code + every CRIS street spelling | Corridor scope |
| `filter_corridors.py` | Writes the `*_3roads.csv` corridor files from the CRIS exports | Corridor scope |
| `sql/02_build_network.sql` | 0.1-mi segments and 3+ leg intersections | Network build (due 10/20) |
| `sql/03_map_match.sql` | Matches corridor crashes to sites, logs every miss, prints the F&SI match rate | 95% matched (due 10/20) |
| `sql/04_features.sql` | Fills `site_feature` (speed, lanes, AADT, class, median; intersection legs), each value dated | Feature tables with as-of dates (due 11/3) |
| `tests/test_validate.py` | 10 tests for the crash validator, no database needed | Ingest tests (due 11/17) |
| `make_figures.py` | Draws the progress figures in `figures/` straight from the database | Progress evidence |
| `tests/test_database.py` | 4 leakage tests against the live database (skipped if it is not running) | Leakage check blocks a seeded post-2022 feature (due 11/3) |

## Quickstart (the run recorded below)

CRIS files are CRIS Query exports (Brazos County, City of College Station, one year each) with
columns Crash ID, Crash Date, Crash Severity, Latitude, Longitude, Light Condition,
Manner of Collision, Street Name. They are not in the repo; paths below assume `../../raw/`.

> **Provenance note (7 Oct 2026):** the 2023–2025 files used here were downloaded from CRIS Query
> with all 8 columns. The 2016–2022 files were not: they were made by a one-off script (not in the
> repo) that took a 7-column download (without Street Name) and copied Street Name in from an
> earlier 13-column download of the same years, matching on Crash ID. Every Crash ID matched and the
> shared columns were identical, so the result equals a direct 8-column download. To reproduce from
> scratch, download all ten years directly with the 8 columns above.

```bash
docker compose up -d                      # database + schema (01_schema.sql runs on first start)
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. Crashes: check, then load (one file per year)
.venv/bin/python ingest.py crashes ../../raw/data_2022.csv --dry-run
for f in ../../raw/data_20*.csv; do .venv/bin/python ingest.py crashes "$f"; done

# 2. Roads (2019 snapshot for the backtest) and the corridor spellings
.venv/bin/python fetch_roads.py 2019 --out ../../raw/roads
.venv/bin/python ingest.py roads ../../raw/roads/roadway_brazos_2019.geojson --as-of 2019-12-31 --source roadway_inventory_2019
.venv/bin/python ingest.py corridors

# 3. Build the three-corridor network and match crashes
docker compose exec -T db psql -U tasc -d tasc -v network_version=v0_2019 -v as_of=2019-12-31 \
    -v routes=BS0006R,FM0060,FM2154 -v city_code=9050 < sql/02_build_network.sql
docker compose exec -T db psql -U tasc -d tasc -v network_version=v0_2019 -v tol_m=45.72 < sql/03_map_match.sql

# 4. Features for the backtest, then all tests (validator + leakage)
docker compose exec -T db psql -U tasc -d tasc -v network_version=v0_2019 -v feature_set=backtest_2022 < sql/04_features.sql
.venv/bin/python -m unittest discover -s tests -v

# 5. Progress figures (figures/*.png), every number queried from the database
.venv/bin/python make_figures.py

# Optional: corridor-only CSVs
.venv/bin/python filter_corridors.py ../../raw/data_*.csv --out ../../filtered
```

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
- **Map-matching v0_2019 (7 Oct 2026), full pipeline from an empty database:** only crashes whose
  CRIS Street Name is a corridor spelling are matched, each to its own corridor (a crash CRIS records
  on a cross street is `off_corridor`, logged but not counted). At `tol_m=45.72`:
  **F&SI matched 156 / 159 geocoded = 98.1%** (2016–2022: 102/105 = 97.1%; 2023–2025: 54/54 = 100%).
  All crashes: 5,167 matched, 80 outside tolerance, 484 corridor crashes with no coordinates,
  10,808 off corridor. The 3 F&SI misses are Wellborn crashes 115–402 m from the network (two
  recorded as N Wellborn Rd, probably past the College Station end of FM 2154).
- **Features v0_2019 / backtest_2022 (7 Oct 2026):** `04_features.sql` wrote 925 segment values
  (speed_limit, num_lanes, aadt, func_class, median_type for all 185 segments) and `legs` for both
  intersections, all dated 2019-12-31. Ranges: speed 35–70 mph, AADT 5,900–55,742.
  `tests/test_database.py`: a seeded 2024 feature is refused from `backtest_2022` and accepted into
  `current`; a feature dated exactly 2022-12-31 is accepted; 14/14 tests pass.
- **Not yet run:** OSM, streetlights, HIN. `func_class` and `median_type` are TxDOT codes, not yet
  translated to plain language.

## Check these first

1. **CRIS column names.** Checked against CRIS Query exports (`Crash ID`, `Crash Date`,
   `Crash Severity`, `Latitude`, `Longitude`, `Light Condition`, `Manner of Collision`). The 11-line
   preamble those exports start with is skipped automatically. Bulk extract files are still unchecked.
2. **Severity codes.** CRIS Query exports use labels (`K - FATAL INJURY`, `A - SUSPECTED SERIOUS
   INJURY`, `99 - UNKNOWN`), which parse correctly. The numeric `SEVERITY_CODES` (4 = fatal,
   1 = serious injury) only matter for bulk extract files and are still unconfirmed.

## Decisions that are yours to make

- **Match tolerance.** `tol_m=45.72` (150 ft) is still a placeholder, but it barely matters: CRIS places
  corridor crashes close to the TxDOT centerline (outside intersection zones, measured to their own
  corridor: median 0.7 m, 95th percentile 9.4 m; see `figures/fig3_map_matching.png`), and in a
  2016–2022 check the F&SI match rate was the same at every tolerance from 15 m to 100 m. `crash_match.distance_m` is stored for
  every corridor crash, so any other tolerance can be checked with one query.
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
