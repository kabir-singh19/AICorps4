# S1 · Road Network, Features & Database

The S1 subsystem of TASC (Kabir). It gives the team a real PostGIS database (IF-09) to point at.
Two networks live side by side: **`v1_2022`, the whole city** (the FSR analysis area, 402 mi;
use this one) and `v0_2019`, the three corridors of the M2 diagnostic, kept unchanged.

## What is here

| File | What it does | Slide requirement |
|---|---|---|
| `docker-compose.yml` | PostgreSQL 16 + PostGIS on port 5432, 2 GB cap | IF-09, container budget |
| `sql/init/01_schema.sql` | Tables, views, and the leakage trigger. Runs on first start. | "owns the database schema" |
| `ingest.py crashes` | Validates a CRIS CSV, rejects the whole file at more than 2% bad records, loads the rest | 2% bad-record stop (FSR 3.2.3.1.2) |
| `ingest.py roads` | Loads TxDOT roadway inventory GeoJSON into UTM 14N | IF-02 |
| `ingest.py crash-details` | Adds weather, surface, deaths and officer-recorded road columns to loaded crashes | IF-01 crash attributes |
| `fetch_osm.py` | Downloads OpenStreetMap near the network as of a date (ohsome API history) | IF-03 |
| `ingest.py osm` | Loads a `fetch_osm.py` snapshot into `osm_feature` | IF-03 |
| `sql/06_osm_features.sql` | OSM site features (crossings, signalized intersections, sidewalks, schools, bars, restaurants), dated | IF-03 features |
| `ingest.py corridors` | Loads the study-corridor street spellings from `corridors.py` | Corridor scope |
| `ingest.py road-names` | Fills `road.street_name` (TxDOT `STE_NAM`) on roads already loaded, without reloading | City-wide matching |
| `ingest.py road-attrs` | Fills `road.attrs` (9 more TxDOT fields: lane width, shoulders, median width, curbs, access control, truck %) the same way | IF-02 features |
| `street_names.py`, `ingest.py street-keys` | One key per street spelling (typos, suffixes, directions, route names) in `street_key` | City-wide matching |
| `fetch_boundary.py`, `ingest.py boundary` | College Station city limits (Census, 2022 vintage) into `boundary` | Analysis area |
| `ingest.py osm-roads` | Adds the named streets TxDOT 2019 lacks, from OSM as of 2022-12-31; tags Texas A&M campus streets | IF-03, network coverage |
| `sql/07_map_match_city.sql` | Matches every crash to the city-wide network by street name and distance, logs every miss | 95% matched |
| `fetch_roads.py` | Downloads Brazos County roadway inventory snapshots from TxDOT | IF-02 |
| `corridors.py` | The three corridors: TxDOT route code + every CRIS street spelling | Corridor scope |
| `filter_corridors.py` | Writes the `*_3roads.csv` corridor files from the CRIS exports | Corridor scope |
| `sql/02_build_network.sql` | 0.1-mi segments and 3+ leg intersections; optional OSM roads, city boundary, stub and junction clean-up, interchange flag | Network build (due 10/20) |
| `sql/03_map_match.sql` | Matches corridor crashes to sites, logs every miss, prints the F&SI match rate | 95% matched (due 10/20) |
| `sql/04_features.sql` | Fills `site_feature` (speed, lanes, AADT, class, median, the `road.attrs` fields, curvature, distance to intersection; intersection legs and interchange), each value dated | Feature tables with as-of dates (due 11/3) |
| `tests/test_validate.py` | 15 tests for the crash validator (incl. guardrails), no database needed | Ingest tests (due 11/17) |
| `make_figures.py` | Draws the progress figures in `figures/` straight from the database | Progress evidence |
| `make_map.py`, `map/` | Writes `map/index.html`, an interactive map of every v1_2022 site with crash totals per year and its features (from `map/template.html`; open the file in a browser, no database needed). Totals per site only, no crash locations | Progress evidence |
| `sql/05_s2_interface.sql` | S2 views (`s2_site_scope`, `s2_crash_scope`, `s2_crash_scope_corridor`, `s2_source_registry`), source provenance, read-only role `s2_reader` | IF-09 to S2 |
| `dumps/tasc_v1_2022_2026-11-04.sql.gz` | **Current** database copy: both networks, city-wide matching and features; see "For S2" | IF-09 to S2 |
| `dumps/tasc_v0_2019_2026-10-28.sql.gz` | 28 Oct copy (corridor network with crash details and OSM features) | IF-09 to S2 |
| `dumps/tasc_v0_2019.sql.gz` | Frozen 18 Oct 2026 copy used for S2's M2 run `m2-corridor-001`; kept unchanged | IF-09 to S2 |
| `tests/test_database.py` | 4 leakage + 7 S2-view contract + 7 guardrail tests against the live database (skipped if it is not running) | Leakage check blocks a seeded post-2022 feature (due 11/3) |
| `tests/test_street_names.py` | 6 tests for the street-name keys, no database needed | City-wide matching |

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

# 1b. Extra crash columns (second CRIS export: weather, surface, deaths, reported road)
for f in "../../new features for database"/new_features_20*.csv; do .venv/bin/python ingest.py crash-details "$f"; done

# 1c. OpenStreetMap as of 2022-12-31 near the network (after step 3 builds it), then its features
.venv/bin/python fetch_osm.py --date 2022-12-31 --out ../../raw/osm
.venv/bin/python ingest.py osm ../../raw/osm/osm_v0_2019_600m_2022-12-31.json
docker compose exec -T db psql -U tasc -d tasc -v network_version=v0_2019 -v feature_set=backtest_2022 \
    -v osm_source=osm_2022-12-31 < sql/06_osm_features.sql

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

# 6. S2 interface: views, provenance and the read-only role (password from your environment)
docker compose exec -T db psql -U tasc -d tasc -v s2_password="$S2_PASSWORD" < sql/05_s2_interface.sql

# 7. Database copy for teammates
docker compose exec -T db pg_dump -U tasc -d tasc -n tasc --clean --if-exists --no-owner --no-privileges | gzip -9 > dumps/tasc_v0_2019_$(date +%F).sql.gz

# Optional: corridor-only CSVs
.venv/bin/python filter_corridors.py ../../raw/data_*.csv --out ../../filtered
```

**City-wide network `v1_2022`** (after steps 1–2 above; the run recorded below, 4 Nov 2026):

```bash
# a. Street names on the 2019 roads, the city limits, and the streets TxDOT lacks (OSM 2022)
.venv/bin/python ingest.py road-names ../../raw/roads/roadway_brazos_2019.geojson --source roadway_inventory_2019
.venv/bin/python ingest.py road-attrs ../../raw/roads/roadway_brazos_2019.geojson --source roadway_inventory_2019
.venv/bin/python fetch_boundary.py --out ../../raw/boundary
.venv/bin/python ingest.py boundary ../../raw/boundary/college_station_2022.geojson
.venv/bin/python fetch_osm.py --date 2022-12-31 --out ../../raw/osm --boundary "College Station" --margin-m 100 --groups road
.venv/bin/python fetch_osm.py --date 2022-12-31 --out ../../raw/osm --boundary "College Station" --margin-m 100 --groups campus
.venv/bin/python ingest.py osm-roads ../../raw/osm/osm_college_station_100m_2022-12-31_road.json \
    --campus ../../raw/osm/osm_college_station_100m_2022-12-31_campus.json
.venv/bin/python ingest.py street-keys

# b. Build the network (about 5 minutes under emulation) and match crashes
docker compose exec -T db psql -U tasc -d tasc -v network_version=v1_2022 -v as_of=2022-12-31 -v routes=ALL \
    -v city_code=ALL -v road_source=roadway_inventory_2019 -v osm_source=osm_roads_2022-12-31 \
    -v "boundary=College Station" -v stub_m=15 -v merge_m=15 < sql/02_build_network.sql
docker compose exec -T db psql -U tasc -d tasc -v network_version=v1_2022 -v tol_m=45.72 \
    -v "boundary=College Station" < sql/07_map_match_city.sql

# c. City-wide OSM features (2022 for the backtest, latest for the live set), sources, features
G=bus_stop,school,bar,restaurant,crossing,traffic_signals,street_lamp,sidewalk,major_road
F=bus_stop_school_bar_restaurant_crossing_traffic_signals_street_lamp_sidewalk_major_road
.venv/bin/python fetch_osm.py --date 2022-12-31 --out ../../raw/osm --boundary "College Station" --margin-m 400 --groups $G
.venv/bin/python fetch_osm.py --date latest --out ../../raw/osm --boundary "College Station" --margin-m 400 --groups $G
.venv/bin/python ingest.py osm ../../raw/osm/osm_college_station_400m_2022-12-31_$F.json --source osm_city_2022-12-31
.venv/bin/python ingest.py osm ../../raw/osm/osm_college_station_400m_latest_$F.json --source osm_city_latest
docker compose exec -T db psql -U tasc -d tasc -v s2_password="$S2_PASSWORD" < sql/05_s2_interface.sql
docker compose exec -T db psql -U tasc -d tasc -v network_version=v1_2022 -v feature_set=backtest_2022 < sql/04_features.sql
docker compose exec -T db psql -U tasc -d tasc -v network_version=v1_2022 -v feature_set=backtest_2022 \
    -v osm_source=osm_city_2022-12-31 < sql/06_osm_features.sql
docker compose exec -T db psql -U tasc -d tasc -v network_version=v1_2022 -v feature_set=current \
    -v osm_source=osm_city_latest < sql/06_osm_features.sql

# d. Tests, figures 12-15, interactive map, database copy
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python make_figures.py --only 12,13,14,15
.venv/bin/python make_map.py
docker compose exec -T db pg_dump -U tasc -d tasc -n tasc --clean --if-exists --no-owner --no-privileges | gzip -9 > dumps/tasc_v1_2022_$(date +%F).sql.gz
```

## For S2 (Param): getting and reading the database

**Option 1, restore the copy (recommended, about 2 minutes).** Use the newest dump,
`dumps/tasc_v1_2022_2026-11-04.sql.gz` (both networks; `v1_2022` is the city-wide one). The
18 Oct dump `tasc_v0_2019.sql.gz` stays as the exact input of M2 run `m2-corridor-001`. Works the same on Windows, macOS
and Linux; run from `Kabir_Singh/` after `git pull`. Docker Desktop must be running.

```bash
docker compose up -d
# wait until the first start has finished creating the schema:
docker compose logs db          # look for "PostgreSQL init process complete"
docker compose cp dumps/tasc_v1_2022_2026-11-04.sql.gz db:/tmp/tasc.sql.gz
docker compose exec db sh -c "gunzip -c /tmp/tasc.sql.gz | psql -q -v ON_ERROR_STOP=1 -U tasc -d tasc"
docker compose cp sql/05_s2_interface.sql db:/tmp/05_s2_interface.sql
docker compose exec db psql -U tasc -d tasc -v s2_password=CHOOSE_A_PASSWORD -f /tmp/05_s2_interface.sql
```

The dump replaces everything in schema `tasc`; the last command recreates the `s2_reader` role
(roles are not in a dump) with the password you choose. Then connect S2 as the read-only role:
`DATABASE_URL=postgresql://s2_reader:<that password>@localhost:5432/tasc` (PowerShell:
`$env:DATABASE_URL = "..."`). Keep the password out of files you commit.

**Option 2, rebuild from source.** Follow the Quickstart above. CRIS files come from CRIS Query
(https://cris.dot.state.tx.us/public/Query): filters County = BRAZOS, City = COLLEGE STATION, one
Crash Year per file (2016–2025), CSV, columns Crash ID, Crash Date, Crash Severity, Latitude,
Longitude, Light Condition, Manner of Collision, Street Name; save as `raw/data_YYYY.csv`. Roads
come from `fetch_roads.py 2019`. CRIS revises records over time, so a later download may differ
slightly from the dump; the dump is the frozen copy used for M2.

**What S2 reads** (all `SELECT` only for `s2_reader`): views `s2_site_scope`, `s2_crash_scope`,
`s2_crash_scope_corridor`, `s2_source_registry`, and tables `site`, `site_feature`, `crash`, `crash_match`. Write attempts
are refused (checked: `permission denied for table crash`).

**Agreed with S2 (18 Oct 2026):**
- **Length policy:** S2's proposal. Segments keep their own length for exposure and flagging.
  Intersections get 250 ft (0.0473 mi) exposure for their rate and 0 mi toward the 11% flagging
  total, because segments already run through them. Flagging total: 18.07 mi.
- **Analysis area (corridor diagnostic):** a crash is in the area if CRIS recorded it on a
  corridor street (`corridor_street`), the `03_map_match.sql` rule. Test window 2023–2025: 59 F&SI
  in the area, 54 on a site, 5 without coordinates (they stay in the denominator).
- **Intersection road names:** the corridors that meet there, e.g. "University Dr & Wellborn Rd".

**City-wide network `v1_2022` (4 Nov 2026), what changes for S2:**
- **Analysis area:** `s2_crash_scope` is now the FSR area, the College Station city limits (a crash
  with no coordinates stays in, as before). The corridor rule above moved unchanged to
  `s2_crash_scope_corridor`; to re-run the corridor diagnostic, set
  `"crash_scope_view": "tasc.s2_crash_scope_corridor"` in that config. Test window 2023–2025 in the
  city: 171 F&SI in the area (corridors: 59), 151 on a site, 17 without coordinates, 3 unmatched;
  2016–2022 history: 296 F&SI in the area.
- **Road names:** corridor name on the three corridors, else the street name in capitals, else the
  TxDOT route code; '' for 34 sites on unnamed streets. Intersections: the roads meeting there.
- **Missing values:** OSM streets have no AADT or median type (about 1,070 of 5,590 segments) and
  speed/lanes only where OSM tags them. Not every segment has every feature.
- **New features:** `interchange` (intersections: 1 where a freeway line passes through; 8 sites).
- **OSM 2022 is sparse:** a 2022 zero often means "not mapped yet" (bus stops near 153 sites in 2022,
  1,054 in 2026). The live feature set `current` has OSM features only, not the TxDOT ones yet.

**Source provenance** (`s2_source_availability`; the `evidence` column has the full text):

| source | role | as of | available | evidence |
|---|---|---|---|---|
| `roadway_inventory_2019` | predictor | 2019-12-31 | 2021-08-06 | TxDOT ArcGIS item 9466b4e7c8c94af08d508078ec9e1742 created 2021-08-06; layer `dataLastEditDate` 2021-08-06 (item metadata edited 2025-02-25, data unchanged) |
| `network v0_2019` | predictor | 2019-12-31 | 2021-08-06 | Built only from the 2019 snapshot, so it carries that date |
| `cris_history` | history | 2022-12-31 | 2022-12-31 | Crash facts dated on or before the cutoff; CRIS may add late reports after it |
| `cris_test` | evaluation | 2025-12-31 | 2026-10-07 | Download date of the 2023–2025 files; never used for fitting |
| `osm_2022-12-31` / `osm_latest` | predictor | 2022-12-31 / 2026-07-27 | same | ohsome full history at the snapshot time, 600 m around v0_2019 |
| `osm_roads_2022-12-31` | predictor | 2022-12-31 | 2022-12-31 | OSM streets added where TxDOT 2019 has none; same ohsome method |
| `network v1_2022` | predictor | 2022-12-31 | 2022-12-31 | Built from the 2019 inventory and the 2022 OSM streets inside the Census 2022 limits (the boundary's publication date was not checked; it never sets a feature value) |
| `osm_city_2022-12-31` / `osm_city_latest` | predictor | 2022-12-31 / 2026-07-27 | same | ohsome full history at the snapshot time, within 400 m of the city limits |

**Checked end to end (18 Oct 2026):** S2's own `database.load_snapshot` with
`config/corridor_diagnostic.example.json`, connected as `s2_reader`, loaded 187 sites, 935 feature
records, 818 history rows (102 F&SI in 2016–2022) and 4,869 test crashes, and
`leakage.validate_snapshot` passed. The dump was restored into a scratch database with the
commands above; every table count, the 98.11% match rate and the 18.07 flagging miles matched,
and the leakage trigger still refused a 2024 feature.

**Not provided yet:** `s2_hin_site`. No HIN layer has been loaded into S1, so until it is, S2 runs
methods B and C only.

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
- **Crash details (28 Oct 2026):** a second CRIS Query export per year (same filters, files
  `new_features_YYYY.csv`, same 16,539 Crash IDs) loaded with `ingest.py crash-details`, 0% bad.
  Eight columns added to `crash`: `death_count`, `intersection_related`, `weather_condition`,
  `surface_condition`, and the officer-recorded `speed_limit_reported`, `num_lanes_reported`,
  `median_width_ft_reported`, `roadway_type_reported`. Road Base Type and Surface Type were
  "No Data" for every crash and are not stored. These describe each crash, not the road, so they
  are not `site_feature` values: the reported road columns only exist where a crash happened.
  Checks: deaths sum to 44, one or more on each of the 44 K crashes. Reported speed equals the
  TxDOT 2019 speed on 58.4% of 4,819 matched segment crashes (84% within 5 mph).
- **OSM features (28 Oct 2026):** `fetch_osm.py` downloads OpenStreetMap history from the ohsome API
  (HeiGIT); the public Overpass servers were too overloaded to answer, and ohsome's plain geometry
  endpoint is blocked (403), so it uses `elementsFullHistory/geometry` and keeps the versions valid
  at the snapshot time. Area: 600 m around network v0_2019 (36 km²). The 2022-12-31 snapshot has
  1,606 features (9 bus stops, 6 schools, 12 bars, 127 restaurants/cafés, 415 crossings,
  126 signals, 64 street lamps, 398 sidewalk lines, 449 major-road ways); a bus-stop count in a
  test box (14) agreed between Overpass, ohsome count and ohsome full history.
  `ingest.py osm` loads it into `osm_feature`; `06_osm_features.sql` writes 6 `backtest_2022`
  features dated 2022-12-31: `osm_bars_200m`, `osm_crossings_30m`, `osm_restaurants_100m`,
  `osm_schools_400m`, `osm_signalized_intersections_30m` (all sites) and `osm_sidewalk_share`
  (segments). Signalized intersections merge OSM traffic-signal points within 50 m first: OSM often
  draws one point per approach, so 126 points in 2022 are 58 intersections (162 → 61 in 2026).
  `osm_bus_stops_200m` (200 m, because mapped stops sit on side streets and campus loops, the
  nearest 67 m from a corridor) was 0 at every site in 2022, so the script's no-variation rule drops
  it from `backtest_2022`. Not built: lighting (no corridor road had a `lit` tag in 2022) and
  street-lamp counts (one lamp near one site). Registered as source `osm_2022-12-31`; S2's
  `load_snapshot` + `validate_snapshot` passed with all 11 features as `s2_reader`.
  **Latest snapshot:** ohsome's newest data (2026-07-27), 2,804 features, loaded as source
  `osm_latest` into feature set `current` only (7 features, including bus stops: 31 sites have one
  within 200 m). The registry lists it under `current`, never `backtest_2022`.
  **Caveat:** OSM near the corridors grew a lot from 2022 to 2026 (crossings 415 → 801, sidewalk
  lines 398 → 621, bus stops 9 → 114), so a 2022 zero often means "not mapped yet", not "absent".
- **Guardrails (28 Oct 2026):** checks that stop mistakes instead of letting them through silently.
  (1) `ingest.py roads` replaces a source's earlier rows on reload, and refuses if a built network
  still uses them. (2) Crash years are accepted through the current year (`YEAR_RANGE`), so 2026
  loads without a code change. (3) Bad data now rejected: a crash dated outside its export's
  "Crash Year Is Equal To" filter (shifted date); coordinates outside Brazos County
  (`BRAZOS_BBOX`, from the TxDOT county road extent, replacing the all-Texas box); a Crash ID
  already loaded from a different file (duplicate across files; checked on load, not in a dry
  run). (4) `03_map_match.sql` stops with a message if `corridor_street` is empty. All 10 real
  files still dry-run at 0% bad; 28/28 tests pass.
- **City-wide network v1_2022 (4 Nov 2026).**
  *Names.* `road-names` matched all 5,547 stored roads to the 2019 file; 1,234 of 1,243 College Station
  city streets got a name. `street-keys`: 3,380 spellings. Share of geocoded in-city F&SI whose
  street name matches a network road: 84.8% exact spelling, 94.2% with keys, 98.8% with the OSM
  streets (`figures/fig14_name_matching.png`).
  *Area and roads.* City limits 132.5 km² of land (Census GEOID 4815976, vintage 2022-01-01).
  `osm-roads` added 376 OSM pieces, 75.6 mi on 255 named streets (22.8 mi on the Texas A&M campus,
  `maintainer = 'TAMU'`); unnamed OSM streets (12.6 mi) and ramps were left out, since no crash can
  name-match them. 23 added pieces (1.1 mi) lie mostly within 40 m of a TxDOT road; all are short
  real streets (courts, loops).
  *Network.* 5,590 segments, 402.1 mi (TxDOT 326.4, OSM 75.7); 1,634 intersections (1,195 with 3
  legs, 422 with 4, 17 with 5–6), 8 flagged `interchange`. Clean-up at 15 m removed 215 segments
  shorter than 5 m (TxDOT lines drawn past the street they meet) and left no two intersections within
  15 m (54 pairs before); against
  an uncleaned build every intersection is kept except 4 whose extra legs were only stubs. The v0
  build was rebuilt with the new script and compared site by site: identical. Fixed on the way:
  `city_code=ALL` never worked.
  *Matching* (`07_map_match_city.sql`, tol 45.72 m): **F&SI matched 427 / 434 geocoded in the city =
  98.39%**. All crashes: 14,433 matched (9,270 to intersections, 5,059 to segments; segment distance
  median 0.7 m, 95th percentile 10.8 m), 1,826 no coordinates, 53 outside the city, 165 outside
  tolerance, 62 street name not found. The 7 F&SI misses: Dominik Dr ×2 and Corrington Dr (in
  neither source), Wellborn 213 and 402 m off, SH 6 71 and 86 m off (likely frontage roads). Two
  name fixes moved it from 97.24%: TxDOT's direction before the suffix (HOLLEMAN W DR) and its old
  name for Holleman Dr South (N I AND G RD; 68 crashes within 20 m are reported as S HOLLEMAN DR).
  *Features* (`backtest_2022`): func_class on all 5,590 segments; speed 4,718, lanes 4,649, AADT and
  median 4,521; legs and interchange on all 1,634 intersections; 7 OSM features from
  `osm_city_2022-12-31` on all sites, none constant. `current`: the same 7 from `osm_city_latest`.
  Added the same day: `road-attrs` matched all 5,547 roads, and 9 more TxDOT 2019 fields became
  segment features on the 4,521 TxDOT segments (lane width median 10 ft, range 4–21; inside /
  outside shoulder 0 ft on most city streets, up to 20 / 24; median width 0–376 ft; pavement width
  10–98 ft; truck % 0.5–17.2, but 3.2 on most roads, likely a TxDOT default; access control 3 (none)
  on 4,406, 1 (full) on 108; curbs coded 0/1/2, codes not yet translated). Two geometry features on
  all 5,590 segments: `curvature_deg_per_mi` (median 23, 95th percentile 1,106; very high on short
  segments that turn a corner) and `dist_to_intersection_m` (median 62 m). Empty or constant for
  College Station, so not used: turn lanes, signal and stop-sign counts, TxDOT curvature classes,
  terrain, school zones. `04_features.sql` now replaces only the features it writes; before, a
  rerun also deleted the OSM features from `06_osm_features.sql`.
  *Checks.* 39/39 tests pass, including leakage and "every feature source is registered". The
  v0_2019 rows of `s2_site_scope` and the corridor crash scope were compared before and after the
  view change: identical.
- **Not yet run:** streetlights (City GIS), HIN. `func_class` and `median_type` are TxDOT codes, not yet
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

- Lines are split wherever they cross on the map, so an overpass (SH 6 over a cross street) becomes an
  intersection. v1_2022 flags these as `interchange` (8 sites) instead of removing them, since
  crashes near them are real ramp and merge crashes. OpenStreetMap bridge tags could separate them.
- Only centerlines (KG): SH 6 frontage roads are not sites, so frontage crashes land on SH 6 or miss.
- Segment attributes come from the nearest source road at the segment midpoint.
- `GREENS PRAIRIE RD` / `GREENS PRAIRIE TRL` and similar same-name pairs share a name key; distance
  decides between them.

## Next steps

1. S2 runs B and C on `v1_2022` (and points its corridor config at `s2_crash_scope_corridor`).
2. More training data: CRIS exports for other cities (training only; the City backtest stays
   College Station), and more 2019 TxDOT columns (signals, lane width, turn lanes, shoulders).
3. Streetlights (City GIS, IF-04) and the HIN layer (IF-05), when available.
4. TxDOT road features in the live `current` set; translate func_class and median codes.
