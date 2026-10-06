# S1 · Road Network, Features & Database — baseline v0

Starting point for the S1 subsystem of TASC (Kabir). It gives the team a real PostGIS database
(IF-09) to point at, and a first pass at each S1 requirement from the midterm slides.

## What is here

| File | What it does | Slide requirement |
|---|---|---|
| `docker-compose.yml` | PostgreSQL 16 + PostGIS on port 5432, 2 GB cap | IF-09, container budget |
| `sql/init/01_schema.sql` | Tables, views, and the leakage trigger. Runs on first start. | "owns the database schema" |
| `ingest.py crashes` | Validates a CRIS CSV, rejects the whole file at 3% bad records, loads the rest | 3% bad-record stop |
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

- **Run and passing:** the 8 validator tests; the schema's tables, views and leakage trigger on plain
  PostgreSQL 16 (a 2024-dated feature was refused from `backtest_2022` and accepted into `current`).
- **Not yet run:** anything that needs PostGIS itself, which means `ingest.py` writing to the database,
  `02_build_network.sql` and `03_map_match.sql`. Expect to fix small things the first time you run them.

## Check these first

1. **CRIS column names.** `CRIS_COLUMNS` at the top of `ingest.py` is a best guess. The dry run tells
   you exactly which column it could not find and prints your file's header.
2. **Severity codes.** `SEVERITY_CODES` assumes 4 = fatal, 1 = serious injury. Confirm against the
   CRIS extract file specification; if it is wrong, F&SI counts are wrong everywhere downstream.

## Decisions that are yours to make

- **Match tolerance.** `tol_m=45.72` (150 ft) is a placeholder. `crash_match.distance_m` is stored for
  every crash, so you can see the match rate at any tolerance with one query.
- **Is exactly 3.00% a stop?** The code stops at 3% or more.
- **Intersection zone vs. segment length.** Segments currently run all the way to the intersection
  point. Crashes inside the 250 ft zone go to the intersection, so agree with Param whether segment
  length (his per-mile denominator) should exclude the zone.

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
