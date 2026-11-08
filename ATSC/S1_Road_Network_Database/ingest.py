"""TASC S1 ingest: load public crash and road files into the PostGIS database.

    python ingest.py crashes data/cris_2022.csv --dry-run     # validate only, no database needed
    python ingest.py crashes data/cris_2022.csv               # validate, then load
    python ingest.py roads   data/roadway_brazos.geojson --as-of 2022-12-31
    python ingest.py corridors                                # study-corridor street spellings
    python ingest.py road-names data/roadway_brazos.geojson --source roadway_inventory_2019
    python ingest.py road-attrs data/roadway_brazos.geojson --source roadway_inventory_2019
    python ingest.py street-keys                              # name keys for city-wide matching
    python ingest.py boundary ../../raw/boundary/college_station_2022.geojson   # city limits
    python ingest.py osm-roads ../../raw/osm/osm_college_station_100m_2022-12-31_road.json \
        --campus ../../raw/osm/osm_college_station_100m_2022-12-31_campus.json   # streets TxDOT lacks
    python ingest.py crash-details data/new_features_2022.csv # extra crash columns (weather, ...)

A crash file with more than 2% bad records is rejected whole: nothing is loaded, the run is
logged as 'rejected', and the script exits with code 2 so a pipeline stops there.

Database: set DATABASE_URL, default postgresql://tasc:tasc@localhost:5432/tasc
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime

BAD_RECORD_LIMIT = 0.02            # FSR: more than 2% bad records stops the pipeline
YEAR_RANGE = (2015, date.today().year)     # crash years accepted: 2015 through the current year
# Brazos County (crash ingest covers the county): extent of the TxDOT roads with CO = 21,
# lat 30.361-30.974, lon -96.585 to -96.106, plus about 2 km. A crash outside it was mis-geocoded.
BRAZOS_BBOX = (30.34, 30.99, -96.61, -96.08)   # lat_min, lat_max, lon_min, lon_max
# Text CRIS uses for "no value". A coordinate with one of these means "not geocoded", not bad.
MISSING_VALUES = {"", "NO DATA", "NA", "N/A", "NULL", "NONE"}
DEFAULT_DB = "postgresql://tasc:tasc@localhost:5432/tasc"

# CHECK THESE AGAINST YOUR ACTUAL CRIS FILE. Header names differ between the CRIS bulk
# extract (Crash_ID, Crash_Sev_ID, ...) and CRIS Query exports (Crash ID, Crash Severity, ...).
# Matching ignores case, spaces and underscores, so list each name once in any style.
CRIS_COLUMNS = {
    "crash_id":        ["Crash_ID"],
    "crash_date":      ["Crash_Date"],
    "severity":        ["Crash_Sev_ID", "Crash_Severity"],
    "lat":             ["Latitude"],
    "lon":             ["Longitude"],
    "crash_type":      ["FHE_Collsn_ID", "Manner_of_Collision"],     # optional
    "light_condition": ["Light_Cond_ID", "Light_Condition"],         # optional
    "street_name":     ["Street_Name", "Rpt_Street_Name"],           # optional; needed for corridors
}
REQUIRED = ["crash_id", "crash_date", "severity", "lat", "lon"]

# CRIS numeric severity codes -> KABCO. Verify against the CRIS extract file specification.
SEVERITY_CODES = {"4": "K", "1": "A", "2": "B", "3": "C", "5": "O", "0": "U"}

# TxDOT roadway inventory field names (checked against the TxDOT open-data layer, Oct 2026).
ROAD_FIELDS = {
    "route_name": "HWY", "street_name": "STE_NAM", "roadbed": "RDBD_ID", "city_code": "CITY", "func_class": "F_SYSTEM", "num_lanes": "NUM_LANES",
    "speed_limit": "SPD_MAX", "median_type": "MED_TYPE", "aadt": "ADT_CUR", "aadt_year": "ADT_YEAR",
}


# --------------------------------------------------------------------------- validation

def _norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve_columns(header):
    """Map our field names to the file's actual header names. Raises if a required one is missing."""
    by_norm = {_norm(h): h for h in header}
    found = {}
    for field, candidates in CRIS_COLUMNS.items():
        for cand in candidates:
            if _norm(cand) in by_norm:
                found[field] = by_norm[_norm(cand)]
                break
    missing = [f for f in REQUIRED if f not in found]
    if missing:
        raise ValueError(
            f"Could not find column(s) for {missing}. File header is: {header}. "
            "Add the right names to CRIS_COLUMNS at the top of ingest.py."
        )
    return found


def parse_severity(value):
    """Accept a CRIS numeric code ('4') or a label ('K - FATAL INJURY', 'Suspected Serious Injury')."""
    v = value.strip().upper()
    if v in SEVERITY_CODES:
        return SEVERITY_CODES[v]
    m = re.match(r"^([KABCNO])\s*-", v)
    if m:
        return "O" if m.group(1) == "N" else m.group(1)
    if "FATAL" in v or "KILLED" in v:
        return "K"
    if "NON-INCAPACITATING" in v or "MINOR" in v:
        return "B"
    if "SERIOUS" in v or "INCAPACITATING" in v:
        return "A"
    if "POSSIBLE" in v:
        return "C"
    if "NOT INJURED" in v:
        return "O"
    if "UNKNOWN" in v:
        return "U"
    return None


def parse_date(value):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def validate_row(row, cols, seen_ids, file_year=None):
    """Return (record, None) for a good row or (None, reason) for a bad one.

    A crash with no coordinates (blank, 0,0, or text like 'No Data') is NOT a bad record: it is
    loaded without a location and logged later by the map-matching step as 'no_coordinates'.
    file_year, when the export says which Crash Year it was filtered to, must match the crash date.
    """
    raw_id = (row.get(cols["crash_id"]) or "").strip()
    if not raw_id.isdigit():
        return None, "crash_id missing or not a number"
    crash_id = int(raw_id)
    if crash_id in seen_ids:
        return None, "duplicate crash_id in file"

    crash_date = parse_date(row.get(cols["crash_date"]) or "")
    if crash_date is None:
        return None, "crash_date missing or unreadable"
    if not YEAR_RANGE[0] <= crash_date.year <= YEAR_RANGE[1]:
        return None, f"crash_date outside {YEAR_RANGE[0]}-{YEAR_RANGE[1]}"
    if file_year is not None and crash_date.year != file_year:
        return None, "crash_date year differs from the file's Crash Year filter"

    severity = parse_severity(row.get(cols["severity"]) or "")
    if severity is None:
        return None, "severity missing or not recognized"

    lat_s = (row.get(cols["lat"]) or "").strip()
    lon_s = (row.get(cols["lon"]) or "").strip()
    if lat_s.upper() in MISSING_VALUES:
        lat_s = ""
    if lon_s.upper() in MISSING_VALUES:
        lon_s = ""
    lat = lon = None
    if lat_s or lon_s:
        try:
            lat, lon = float(lat_s), float(lon_s)
        except ValueError:
            return None, "latitude/longitude not numeric"
        if lat == 0 and lon == 0:
            lat = lon = None                      # 0,0 means "not geocoded"
        elif not (BRAZOS_BBOX[0] <= lat <= BRAZOS_BBOX[1] and BRAZOS_BBOX[2] <= lon <= BRAZOS_BBOX[3]):
            return None, "coordinates outside Brazos County"

    seen_ids.add(crash_id)
    return {
        "crash_id": crash_id,
        "crash_date": crash_date,
        "severity": severity,
        "lat": lat,
        "lon": lon,
        "crash_type": (row.get(cols.get("crash_type", ""), "") or "").strip() or None,
        "light_condition": (row.get(cols.get("light_condition", ""), "") or "").strip() or None,
        "street_name": (row.get(cols.get("street_name", ""), "") or "").strip() or None,
    }, None


def skip_preamble(f):
    """Move the file position to the header row.

    CRIS Query exports start with a disclaimer, result counts and the filters used, and put the
    column names on about line 12. Search for the row whose first cell is 'Crash ID' rather than
    skipping a fixed number of lines, so a longer or missing preamble still works.
    Returns the preamble lines (empty when the file starts with the header).
    """
    preamble = []
    while True:
        pos = f.tell()
        line = f.readline()
        if not line:
            raise ValueError("No header row starting with 'Crash ID' found in the file.")
        first_cell = next(csv.reader([line]), [""])
        if first_cell and _norm(first_cell[0]) == _norm(CRIS_COLUMNS["crash_id"][0]):
            f.seek(pos)
            return preamble
        preamble.append(line)


def preamble_year(preamble):
    """The year from a CRIS Query filter line 'Crash Year Is Equal To 2018', or None."""
    for line in preamble:
        m = re.search(r"Crash Year Is Equal To (\d{4})", line, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def validate_crash_file(path):
    """Read a CRIS CSV. Returns (good_records, rejects, total) where rejects = [(row_number, reason, raw_row)]."""
    good, rejects, seen = [], [], set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        file_year = preamble_year(skip_preamble(f))
        reader = csv.DictReader(f)
        cols = resolve_columns(reader.fieldnames or [])
        total = 0
        for total, row in enumerate(reader, start=1):
            record, reason = validate_row(row, cols, seen, file_year)
            if record:
                good.append(record)
            else:
                rejects.append((total, reason, row))
    return good, rejects, total


# Extra per-crash columns from a second CRIS Query export, added to crashes already loaded.
# (database column, CRIS header, kind). Road Base Type and Surface Type are not here: they were
# "No Data" for every 2016-2025 College Station crash. The four *_reported road columns are what
# the officer recorded; road attributes for every segment come from the TxDOT inventory instead.
CRASH_DETAIL_COLUMNS = [
    ("death_count",          "Crash Death Count",                       "int"),
    ("intersection_related", "Intersection Related",                    "text"),
    ("weather_condition",    "Weather Condition",                       "text"),
    ("surface_condition",    "Surface Condition",                       "text"),
    ("speed_limit_reported", "Speed Limit",                             "int"),
    ("num_lanes_reported",   "Number of Lanes",                         "int"),
    ("median_width_ft_reported", "Median Width plus Both Inside Shoulders", "int"),
    ("roadway_type_reported", "Roadway Type",                           "text"),
]


def validate_detail_file(path, known_ids):
    """Read a CRIS export of extra crash columns. Returns (good, rejects, total).

    A row is bad if its Crash ID is missing, repeated, or not already in the crash table, or if
    a number column holds something other than a number or a missing marker. Missing markers
    ('No Data', blank) and the CRIS speed limit -1 become NULL.
    """
    good, rejects, seen = [], [], set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        skip_preamble(f)
        reader = csv.DictReader(f)
        by_norm = {_norm(h): h for h in reader.fieldnames or []}
        cols = {"crash_id": by_norm.get(_norm("Crash ID"))}
        for db_col, header, _ in CRASH_DETAIL_COLUMNS:
            cols[db_col] = by_norm.get(_norm(header))
        missing = [h for (c, h, _) in CRASH_DETAIL_COLUMNS if cols[c] is None]
        if cols["crash_id"] is None or missing:
            raise ValueError(f"Could not find column(s) {missing or ['Crash ID']}. Header: {reader.fieldnames}")
        total = 0
        for total, row in enumerate(reader, start=1):
            raw_id = (row[cols["crash_id"]] or "").strip()
            if not raw_id.isdigit():
                rejects.append((total, "crash_id missing or not a number", row))
                continue
            crash_id = int(raw_id)
            if crash_id in seen:
                rejects.append((total, "duplicate crash_id in file", row))
                continue
            if crash_id not in known_ids:
                rejects.append((total, "crash_id not loaded yet (run ingest.py crashes first)", row))
                continue
            record, reason = {"crash_id": crash_id}, None
            for db_col, _, kind in CRASH_DETAIL_COLUMNS:
                value = (row[cols[db_col]] or "").strip()
                if value.upper() in MISSING_VALUES:
                    record[db_col] = None
                elif kind == "int":
                    try:
                        record[db_col] = int(value)
                    except ValueError:
                        reason = f"{db_col} not a number: {value!r}"
                        break
                    if db_col == "speed_limit_reported" and record[db_col] < 0:
                        record[db_col] = None      # CRIS writes -1 for "not recorded"
                else:
                    record[db_col] = value
            if reason:
                rejects.append((total, reason, row))
                continue
            seen.add(crash_id)
            good.append(record)
    return good, rejects, total


def exceeds_limit(n_bad, n_total):
    """FSR 3.2.3.1.2: stop if MORE than 2% fail. Exactly 2% passes. An empty file also stops."""
    return n_total == 0 or n_bad / n_total > BAD_RECORD_LIMIT


# --------------------------------------------------------------------------- database

def connect():
    import psycopg  # imported here so --dry-run works without it installed
    return psycopg.connect(os.environ.get("DATABASE_URL", DEFAULT_DB))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def log_run(cur, source, path, total, n_bad, status, note=None):
    pct = 100.0 * n_bad / total if total else 100.0
    cur.execute(
        """INSERT INTO tasc.ingest_run (source, file_name, file_sha256, rows_total, rows_bad, bad_pct, status, note)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING run_id""",
        (source, os.path.basename(path), sha256(path), total, n_bad, round(pct, 3), status, note),
    )
    return cur.fetchone()[0]


def cross_file_duplicates(cur, good, path):
    """Split good records into (kept, rejects): a crash already loaded from a DIFFERENT file is a
    duplicate across files (e.g. the same crash in two years' exports). Reloading the same file
    name is allowed and updates the crash."""
    rownum = {r["crash_id"]: i for i, r in enumerate(good, start=1)}
    cur.execute("""SELECT c.crash_id, r.file_name FROM tasc.crash c JOIN tasc.ingest_run r USING (run_id)
                   WHERE c.crash_id = ANY(%s) AND r.file_name <> %s""",
                (list(rownum), os.path.basename(path)))
    clash = dict(cur.fetchall())
    kept = [r for r in good if r["crash_id"] not in clash]
    rejects = [(rownum[r["crash_id"]], f"crash_id already loaded from {clash[r['crash_id']]}",
                {k: str(v) for k, v in r.items()}) for r in good if r["crash_id"] in clash]
    return kept, rejects


def report(path, total, rejects):
    n_bad = len(rejects)
    pct = 100.0 * n_bad / total if total else 100.0
    stop = exceeds_limit(n_bad, total)
    print(f"{path}: {total} rows, {n_bad} bad ({pct:.2f}%), limit {BAD_RECORD_LIMIT:.0%}")
    reasons = {}
    for _, reason, _ in rejects:
        reasons[reason] = reasons.get(reason, 0) + 1
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {n:6d}  {reason}")
    if stop:
        print("REJECTED: bad-record limit reached. Nothing loaded.")
    return stop


def cmd_crashes(args):
    good, rejects, total = validate_crash_file(args.file)

    if args.dry_run:
        stop = report(args.file, total, rejects)
        print("  (dry run: duplicates against crashes already in the database were not checked)")
    else:
        with connect() as conn, conn.cursor() as cur:
            good, dup_rejects = cross_file_duplicates(cur, good, args.file)
            rejects = sorted(rejects + dup_rejects, key=lambda r: r[0])
            n_bad = len(rejects)
            stop = report(args.file, total, rejects)
            run_id = log_run(cur, "cris", args.file, total, n_bad, "rejected" if stop else "loaded")
            cur.executemany(
                "INSERT INTO tasc.ingest_reject (run_id, row_number, reason, raw) VALUES (%s, %s, %s, %s)",
                [(run_id, n, reason, json.dumps(raw)) for n, reason, raw in rejects],
            )
            if not stop:
                cur.executemany(
                    """INSERT INTO tasc.crash (crash_id, crash_date, severity, crash_type, light_condition, street_name,
                                              lat, lon, geom, run_id)
                       VALUES (%(crash_id)s, %(crash_date)s, %(severity)s, %(crash_type)s, %(light_condition)s,
                               %(street_name)s, %(lat)s, %(lon)s,
                               ST_Transform(ST_SetSRID(ST_MakePoint(%(lon)s::float8, %(lat)s::float8), 4326), 32614),
                               %(run_id)s)
                       ON CONFLICT (crash_id) DO UPDATE SET
                           crash_date = EXCLUDED.crash_date, severity = EXCLUDED.severity,
                           crash_type = EXCLUDED.crash_type, light_condition = EXCLUDED.light_condition,
                           street_name = EXCLUDED.street_name,
                           lat = EXCLUDED.lat, lon = EXCLUDED.lon, geom = EXCLUDED.geom, run_id = EXCLUDED.run_id""",
                    [dict(r, run_id=run_id) for r in good],
                )
                print(f"Loaded {len(good)} crashes (run_id {run_id}).")
    return 2 if stop else 0


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _street_name(p):
    name = (p.get(ROAD_FIELDS["street_name"]) or "").strip()
    return name or None


def _replace_road_source(cur, source):
    """Delete a road source's earlier rows before reloading it; returns how many, or None to stop.

    Reloading a source replaces it rather than adding a second copy of every road. If a built
    network still uses those roads, stop: delete or rebuild that network version first.
    """
    cur.execute("""SELECT count(*), string_agg(DISTINCT s.network_version, ', ')
                   FROM tasc.site s JOIN tasc.road r USING (road_id) WHERE r.source = %s""", (source,))
    used, versions = cur.fetchone()
    if used:
        print(f"STOPPED: network {versions} is built from source {source!r} ({used} sites). "
              f"Delete it first (DELETE FROM tasc.site WHERE network_version = ...), reload, then rebuild it. "
              f"Nothing changed.")
        return None
    cur.execute("DELETE FROM tasc.road WHERE source = %s", (source,))
    return cur.rowcount


def cmd_roads(args):
    """Load a GeoJSON FeatureCollection of road lines (WGS84 lon/lat, as the TxDOT portal exports it)."""
    with open(args.file, encoding="utf-8") as f:
        features = json.load(f)["features"]
    rows = []
    for feat in features:
        if not feat.get("geometry"):
            continue
        p = feat.get("properties") or {}
        rows.append({
            "geojson": json.dumps(feat["geometry"]),
            "route_name": p.get(ROAD_FIELDS["route_name"]),
            "street_name": _street_name(p),
            "attrs": _road_attrs(p),
            "roadbed": p.get(ROAD_FIELDS["roadbed"]),
            "city_code": _to_int(p.get(ROAD_FIELDS["city_code"])),
            "func_class": None if p.get(ROAD_FIELDS["func_class"]) is None else str(p.get(ROAD_FIELDS["func_class"])),
            "num_lanes": _to_int(p.get(ROAD_FIELDS["num_lanes"])),
            "speed_limit": _to_int(p.get(ROAD_FIELDS["speed_limit"])),
            "median_type": None if p.get(ROAD_FIELDS["median_type"]) is None else str(p.get(ROAD_FIELDS["median_type"])),
            "aadt": _to_int(p.get(ROAD_FIELDS["aadt"])),
            "aadt_year": _to_int(p.get(ROAD_FIELDS["aadt_year"])),
            "source": args.source,
            "as_of": args.as_of,
        })
    skipped = len(features) - len(rows)
    with connect() as conn, conn.cursor() as cur:
        # Databases created before these columns were added to sql/init/01_schema.sql.
        cur.execute("ALTER TABLE tasc.road ADD COLUMN IF NOT EXISTS street_name text, "
                    "ADD COLUMN IF NOT EXISTS attrs jsonb")
        replaced = _replace_road_source(cur, args.source)
        if replaced is None:
            return 2
        run_id = log_run(cur, args.source, args.file, len(features), skipped, "loaded",
                         note="rows_bad = features with no geometry"
                              + (f"; replaced {replaced} earlier rows of this source" if replaced else ""))
        cur.executemany(
            """INSERT INTO tasc.road (geom, route_name, street_name, attrs, roadbed, city_code, func_class, num_lanes,
                                      speed_limit, median_type, aadt, aadt_year, source, as_of_date, run_id)
               SELECT (ST_Dump(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%(geojson)s), 4326), 32614))).geom,
                      %(route_name)s, %(street_name)s, %(attrs)s::jsonb, %(roadbed)s, %(city_code)s, %(func_class)s, %(num_lanes)s, %(speed_limit)s, %(median_type)s,
                      %(aadt)s, %(aadt_year)s, %(source)s, %(as_of)s::date, %(run_id)s""",
            [dict(r, run_id=run_id) for r in rows],
        )
    print(f"Loaded {len(rows)} road features ({skipped} skipped, no geometry"
          + (f"; replaced {replaced} earlier rows" if replaced else "") + f"). run_id {run_id}")
    return 0


def _backfill_road_column(args, column, sql_type, value_of, command):
    """Fill one road column on roads already loaded from this file, without reloading them.

    Reloading would give every road a new road_id, and a built network (v0_2019) points at the old
    ones, so the guardrail in cmd_roads refuses it. Instead each feature is converted exactly as
    cmd_roads converted it and matched to its stored road by identical geometry. value_of(props)
    gives the new value as text (or None); it is cast to sql_type. Returns (stored, filled) or None.
    """
    with open(args.file, encoding="utf-8") as f:
        features = json.load(f)["features"]
    rows = [(json.dumps(feat["geometry"]), value_of(feat.get("properties") or {}))
            for feat in features if feat.get("geometry")]
    with connect() as conn, conn.cursor() as cur:
        # Databases created before the column was added to sql/init/01_schema.sql.
        cur.execute(f"ALTER TABLE tasc.road ADD COLUMN IF NOT EXISTS {column} {sql_type}")
        cur.execute("SELECT count(*) FROM tasc.road WHERE source = %s", (args.source,))
        stored = cur.fetchone()[0]
        if not stored:
            print(f"STOPPED: no roads with source {args.source!r}. Load them with 'ingest.py roads' first.")
            return None
        cur.execute("CREATE TEMP TABLE backfill (geom geometry(LineString, 32614), value text) ON COMMIT DROP")
        cur.executemany(
            """INSERT INTO backfill
               SELECT (ST_Dump(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 32614))).geom, %s""", rows)
        cur.execute("CREATE INDEX ON backfill USING gist (geom)")
        cur.execute(
            f"""WITH pair AS (
                    SELECT r.road_id, b.value
                    FROM tasc.road r JOIN backfill b ON r.geom && b.geom AND ST_OrderingEquals(r.geom, b.geom)
                    WHERE r.source = %s),
                one AS (SELECT road_id, min(value) AS value FROM pair
                        GROUP BY road_id HAVING count(DISTINCT value) <= 1)
                UPDATE tasc.road r SET {column} = one.value::{sql_type} FROM one
                WHERE r.road_id = one.road_id""", (args.source,))
        updated = cur.rowcount
        cur.execute(f"SELECT count(*) FROM tasc.road WHERE source = %s AND {column} IS NOT NULL", (args.source,))
        filled = cur.fetchone()[0]
        missed = stored - updated
        # A road with no twin in the file, or with two twins that disagree, keeps its old value.
        if missed:
            print(f"STOPPED: {missed} of {stored} roads in {args.source!r} have no single match in "
                  f"{os.path.basename(args.file)}; is it the file they were loaded from? Nothing changed.")
            conn.rollback()
            return None
        log_run(cur, args.source, args.file, len(features), 0, "loaded",
                note=f"{command}: {column} filled on {updated} roads ({filled} not empty)")
    return stored, filled


def cmd_road_names(args):
    """Fill road.street_name (TxDOT STE_NAM) on roads already loaded from this file."""
    result = _backfill_road_column(args, "street_name", "text", _street_name, "road-names")
    if result is None:
        return 2
    stored, named = result
    print(f"Matched all {stored} roads in {args.source!r}; {named} have a street name "
          f"({stored - named} have none, mostly state routes).")
    return 0


# TxDOT inventory fields kept in road.attrs (feature name -> field). Checked on the 2019 snapshot for
# College Station centerlines (1,501 pieces): all filled. Left out because they are empty there:
# RT_TURN_LANE, LT_TURN_LANE, NBR_SGNL, TRFC_SGNL, NBR_STOP_SIGN, CURV_CLASS_*, TRRN, PEAK_PRKG,
# DIR_TRAV; SCHOOL_ZN is 0 everywhere. Codes are TxDOT's, not yet translated.
ROAD_ATTRS = {
    "lane_width_ft": "LANE_WIDTH", "shoulder_inside_ft": "S_WID_I", "shoulder_outside_ft": "S_WID_O",
    "access_control": "ACES_CTRL", "truck_pct": "TRK_AADT_PCT", "median_width_ft": "MED_WID",
    "curb_left": "CURB_L", "curb_right": "CURB_R", "surface_width_ft": "SUR_W",
}


def _road_attrs(p):
    attrs = {name: p[field] for name, field in ROAD_ATTRS.items() if p.get(field) not in (None, "")}
    return json.dumps(attrs, sort_keys=True) if attrs else None


def cmd_road_attrs(args):
    """Fill road.attrs (the ROAD_ATTRS fields, as JSON) on roads already loaded from this file."""
    result = _backfill_road_column(args, "attrs", "jsonb", _road_attrs, "road-attrs")
    if result is None:
        return 2
    stored, filled = result
    print(f"Matched all {stored} roads in {args.source!r}; {filled} have attributes "
          f"({', '.join(ROAD_ATTRS)}).")
    return 0


# OSM highway=* to the nearest FHWA functional class TxDOT uses in F_SYSTEM (an approximation,
# kept apart by road.source): 1 interstate, 2 freeway, 3 principal arterial, 4 minor arterial,
# 5 major collector, 7 local.
OSM_FUNC_CLASS = {"motorway": "1", "trunk": "2", "primary": "3", "secondary": "4", "tertiary": "5",
                  "unclassified": "7", "residential": "7", "living_street": "7"}
OSM_GAP_M = 15           # an OSM street closer than this to a TxDOT road is that road, already loaded
OSM_BESIDE_M = 40        # a one-way OSM street mostly this close to TxDOT is the other half of a divided road
OSM_MIN_PIECE_M = 30     # leftover pieces shorter than this are slivers at TxDOT roads, not streets
OSM_CONNECT_M = 20       # an end this close to a TxDOT centerline is joined to it, so intersections form


def _osm_mph(value):
    """OSM maxspeed: '35 mph' -> 35. A bare number is km/h in OSM; anything else is unknown."""
    m = re.fullmatch(r"\s*(\d+)\s*(mph)?\s*", value or "")
    if not m:
        return None
    return int(m.group(1)) if m.group(2) else round(int(m.group(1)) / 1.609344)


def cmd_osm_roads(args):
    """Add the streets the TxDOT inventory is missing, from a fetch_osm.py `road` snapshot.

    Keeps a piece of an OSM street only if it is named, not a ramp (*_link), inside the boundary,
    more than OSM_GAP_M from every TxDOT road of --against, and not the other direction of a
    divided TxDOT road. Ends within OSM_CONNECT_M of a TxDOT centerline are extended onto it.
    Pieces inside a Texas A&M campus polygon (--campus file) get maintainer 'TAMU'.
    """
    with open(args.file, encoding="utf-8") as f:
        snap = json.load(f)
    as_of = snap["snapshot_time"][:10]
    source = args.source or f"osm_roads_{as_of}"
    ways = snap["groups"]["road"]["features"]
    rows = []
    for feat in ways:
        p = feat.get("properties") or {}
        name = (p.get("name") or "").strip()
        if not feat.get("geometry") or not name or p.get("highway", "").endswith("_link"):
            continue
        rows.append((json.dumps(feat["geometry"]), name, p.get("highway"), p.get("oneway") == "yes",
                     p.get("@osmId"), _to_int(p.get("lanes")), _osm_mph(p.get("maxspeed"))))
    campus = []
    if args.campus:
        with open(args.campus, encoding="utf-8") as f:
            campus = [json.dumps(feat["geometry"]) for feat in json.load(f)["groups"]["campus"]["features"]
                      if (feat["properties"].get("name") or "").startswith("Texas A&M")]
    with connect() as conn, conn.cursor() as cur:
        # Databases created before these columns were added to sql/init/01_schema.sql.
        cur.execute("ALTER TABLE tasc.road ADD COLUMN IF NOT EXISTS osm_id text, "
                    "ADD COLUMN IF NOT EXISTS maintainer text")
        cur.execute("SELECT count(*) FROM tasc.boundary WHERE name = %s", (args.boundary,))
        if not cur.fetchone()[0]:
            print(f"STOPPED: no boundary {args.boundary!r}; run 'ingest.py boundary' first. Nothing changed.")
            return 2
        cur.execute("SELECT count(*) FROM tasc.road WHERE source = %s AND roadbed = 'KG'", (args.against,))
        if not cur.fetchone()[0]:
            print(f"STOPPED: no TxDOT centerlines with source {args.against!r}. Nothing changed.")
            return 2
        replaced = _replace_road_source(cur, source)
        if replaced is None:
            return 2
        cur.execute("""CREATE TEMP TABLE osm (geom geometry(LineString, 32614), name text, highway text,
                                              oneway boolean, osm_id text, lanes int, mph int) ON COMMIT DROP""")
        cur.executemany(
            """INSERT INTO osm SELECT (ST_Dump(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 32614))).geom,
                                      %s, %s, %s, %s, %s, %s""", rows)
        cur.execute("CREATE TEMP TABLE campus (geom geometry) ON COMMIT DROP")
        cur.executemany("INSERT INTO campus SELECT ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 32614)",
                        [(g,) for g in campus])
        cur.execute(
            """CREATE TEMP TABLE txdot ON COMMIT DROP AS
               SELECT r.geom, r.roadbed FROM tasc.road r, tasc.boundary b
               WHERE r.source = %s AND b.name = %s AND ST_DWithin(r.geom, b.geom, 200)""",
            (args.against, args.boundary))
        cur.execute("CREATE INDEX ON txdot USING gist (geom)")
        cur.execute(
            """CREATE TEMP TABLE kept ON COMMIT DROP AS
               SELECT row_number() OVER () AS id, o.name, o.highway, o.osm_id, o.lanes, o.mph, d.geom
               FROM osm o
               JOIN tasc.boundary b ON b.name = %(boundary)s AND ST_Intersects(o.geom, b.geom)
               CROSS JOIN LATERAL (SELECT ST_Union(ST_Buffer(t.geom, %(gap)s)) AS near
                                   FROM txdot t WHERE ST_DWithin(t.geom, o.geom, %(gap)s)) g
               CROSS JOIN LATERAL ST_Dump(ST_Intersection(
                   CASE WHEN g.near IS NULL THEN o.geom ELSE ST_Difference(o.geom, g.near) END, b.geom)) d
               WHERE GeometryType(d.geom) = 'LINESTRING' AND ST_Length(d.geom) > %(min_piece)s
                 AND NOT (o.oneway AND COALESCE(ST_Length(ST_Intersection(o.geom,
                         (SELECT ST_Union(ST_Buffer(t.geom, %(beside)s)) FROM txdot t
                          WHERE ST_DWithin(t.geom, o.geom, %(beside)s)))), 0) > 0.5 * ST_Length(o.geom))""",
            {"boundary": args.boundary, "gap": OSM_GAP_M, "beside": OSM_BESIDE_M, "min_piece": OSM_MIN_PIECE_M})
        # Join each end to the closest point of the nearest TxDOT centerline within OSM_CONNECT_M
        # (position 0 = before the first point, -1 = after the last).
        for end_fn, position in (("ST_StartPoint", 0), ("ST_EndPoint", -1)):
            cur.execute(
                f"""UPDATE kept SET geom = ST_AddPoint(kept.geom, c.pt, {position})
                    FROM (SELECT k.id, (SELECT ST_ClosestPoint(t.geom, {end_fn}(k.geom)) FROM txdot t
                                        WHERE t.roadbed = 'KG' AND ST_DWithin(t.geom, {end_fn}(k.geom), %s)
                                        ORDER BY t.geom <-> {end_fn}(k.geom) LIMIT 1) AS pt
                          FROM kept k) c
                    WHERE kept.id = c.id AND c.pt IS NOT NULL AND NOT ST_Equals(c.pt, {end_fn}(kept.geom))""",
                (OSM_CONNECT_M,))
        run_id = log_run(cur, source, args.file, len(ways), 0, "loaded",
                         note=f"OSM streets missing from {args.against}, as of {snap['snapshot_time']}; "
                              f"{len(ways) - len(rows)} unnamed or ramp ways skipped"
                              + (f"; replaced {replaced} earlier rows" if replaced else ""))
        cur.execute(
            """INSERT INTO tasc.road (geom, street_name, func_class, num_lanes, speed_limit, source,
                                      as_of_date, run_id, osm_id, maintainer)
               SELECT k.geom, k.name, %s::jsonb ->> k.highway, k.lanes, k.mph, %s, %s::date, %s, k.osm_id,
                      CASE WHEN EXISTS (SELECT FROM campus WHERE ST_Length(ST_Intersection(k.geom, campus.geom))
                                                                  > 0.5 * ST_Length(k.geom)) THEN 'TAMU' END
               FROM kept k""",
            (json.dumps(OSM_FUNC_CLASS), source, as_of, run_id))
        added = cur.rowcount
        cur.execute("""SELECT count(*) FILTER (WHERE maintainer = 'TAMU'), sum(ST_Length(geom)) / 1609.344,
                              count(DISTINCT street_name) FROM tasc.road WHERE source = %s""", (source,))
        tamu, miles, names = cur.fetchone()
    print(f"Loaded {added} OSM street pieces as source {source!r}: {miles or 0:.1f} mi on {names} streets, "
          f"{tamu} on the TAMU campus (as of {as_of}). run_id {run_id}")
    return 0


def cmd_crash_details(args):
    """Add the CRASH_DETAIL_COLUMNS to crashes already in tasc.crash, matched by Crash ID."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT crash_id FROM tasc.crash")
        known = {r[0] for r in cur.fetchall()}
        good, rejects, total = validate_detail_file(args.file, known)
        n_bad = len(rejects)
        pct = 100.0 * n_bad / total if total else 100.0
        stop = exceeds_limit(n_bad, total)
        print(f"{args.file}: {total} rows, {n_bad} bad ({pct:.2f}%), limit {BAD_RECORD_LIMIT:.0%}")
        for reason in sorted({r for _, r, _ in rejects}):
            print(f"  {sum(1 for _, r, _ in rejects if r == reason):6d}  {reason}")
        if stop:
            print("REJECTED: bad-record limit reached. Nothing loaded.")
        if args.dry_run:
            conn.rollback()
            return 2 if stop else 0
        run_id = log_run(cur, "cris_details", args.file, total, n_bad, "rejected" if stop else "loaded")
        cur.executemany(
            "INSERT INTO tasc.ingest_reject (run_id, row_number, reason, raw) VALUES (%s, %s, %s, %s)",
            [(run_id, n, reason, json.dumps(raw)) for n, reason, raw in rejects],
        )
        if not stop:
            sets = ", ".join(f"{c} = %({c})s" for c, _, _ in CRASH_DETAIL_COLUMNS)
            cur.executemany(f"UPDATE tasc.crash SET {sets} WHERE crash_id = %(crash_id)s", good)
            print(f"Updated {len(good)} crashes (run_id {run_id}).")
    return 2 if stop else 0


def cmd_osm(args):
    """Load a fetch_osm.py file into tasc.osm_feature, replacing that source's earlier rows."""
    with open(args.file, encoding="utf-8") as f:
        snap = json.load(f)
    snapshot_date = snap["snapshot_time"][:10]
    source = args.source or ("osm_latest" if snap.get("requested") == "latest" else f"osm_{snapshot_date}")
    rows, skipped = [], 0
    for grp, block in snap["groups"].items():
        for feat in block["features"]:
            if not feat.get("geometry"):
                skipped += 1
                continue
            props = feat.get("properties") or {}
            rows.append({
                "source": source, "snapshot_date": snapshot_date, "grp": grp,
                "osm_id": props.get("@osmId"),
                "tags": json.dumps({k: v for k, v in props.items() if not k.startswith("@")}),
                "geojson": json.dumps(feat["geometry"]),
            })
    total = len(rows) + skipped
    with connect() as conn, conn.cursor() as cur:
        run_id = log_run(cur, source, args.file, total, skipped, "loaded",
                         note=f"OSM as of {snap['snapshot_time']} via {snap['endpoint']}; rows_bad = no geometry")
        cur.execute("DELETE FROM tasc.osm_feature WHERE source = %s", (source,))
        cur.executemany(
            """INSERT INTO tasc.osm_feature (source, snapshot_date, grp, osm_id, tags, geom, run_id)
               VALUES (%(source)s, %(snapshot_date)s, %(grp)s, %(osm_id)s, %(tags)s::jsonb,
                       ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%(geojson)s), 4326), 32614), %(run_id)s)
               ON CONFLICT (source, grp, osm_id) DO NOTHING""",
            [dict(r, run_id=run_id) for r in rows],
        )
    print(f"Loaded {len(rows)} OSM features as source {source!r} (as of {snapshot_date}; "
          f"{skipped} without geometry skipped). run_id {run_id}")
    return 0


def cmd_corridors(args):
    """Replace tasc.corridor_street with the spellings in corridors.py."""
    from corridors import CORRIDORS
    rows = [(street.strip().upper(), name, c["route"])
            for name, c in CORRIDORS.items() for street in c["streets"]]
    with connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tasc.corridor_street")
        cur.executemany(
            "INSERT INTO tasc.corridor_street (street_name, corridor, route_name) VALUES (%s, %s, %s)", rows)
    print(f"Loaded {len(rows)} street spellings for {len(CORRIDORS)} corridors.")
    return 0


def cmd_boundary(args):
    """Load a fetch_boundary.py file into tasc.boundary, replacing that boundary's earlier row."""
    with open(args.file, encoding="utf-8") as f:
        features = json.load(f)["features"]
    if len(features) != 1 or not features[0].get("geometry"):
        print(f"STOPPED: {os.path.basename(args.file)} must hold exactly one boundary polygon. Nothing changed.")
        return 2
    p = features[0]["properties"]
    with connect() as conn, conn.cursor() as cur:
        # Databases created before boundary was added to sql/init/01_schema.sql.
        cur.execute("""CREATE TABLE IF NOT EXISTS tasc.boundary (
                           name text PRIMARY KEY, geoid text, as_of_date date NOT NULL,
                           geom geometry(MultiPolygon, 32614) NOT NULL, run_id bigint REFERENCES tasc.ingest_run)""")
        run_id = log_run(cur, "boundary", args.file, 1, 0, "loaded",
                         note=f"{p.get('NAME')} GEOID {p.get('GEOID')}, vintage {p['vintage']}")
        cur.execute(
            """INSERT INTO tasc.boundary (name, geoid, as_of_date, geom, run_id)
               VALUES (%s, %s, %s, ST_Multi(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 32614)), %s)
               ON CONFLICT (name) DO UPDATE SET geoid = EXCLUDED.geoid, as_of_date = EXCLUDED.as_of_date,
                                                geom = EXCLUDED.geom, run_id = EXCLUDED.run_id
               RETURNING ST_Area(geom) / 1e6""",
            (args.name, p.get("GEOID"), p["vintage"], json.dumps(features[0]["geometry"]), run_id))
        km2 = cur.fetchone()[0]
    print(f"Loaded boundary {args.name!r}: {km2:.1f} km2 (land and water), as of {p['vintage']}. run_id {run_id}")
    return 0


def cmd_street_keys(args):
    """Replace tasc.street_key with a key for every crash and road street name now in the database."""
    from street_names import base_key, street_key
    with connect() as conn, conn.cursor() as cur:
        # Databases created before street_key was added to sql/init/01_schema.sql.
        cur.execute("""CREATE TABLE IF NOT EXISTS tasc.street_key (
                           street_name text PRIMARY KEY, name_key text NOT NULL, name_base text NOT NULL)""")
        cur.execute("""SELECT upper(trim(n)) FROM (
                           SELECT street_name FROM tasc.crash UNION SELECT street_name FROM tasc.road
                           UNION SELECT route_name FROM tasc.road) names(n)
                       WHERE trim(n) <> ''
                       GROUP BY 1""")
        names = [r[0] for r in cur.fetchall()]
        rows = [(n, street_key(n), base_key(street_key(n))) for n in names if street_key(n)]
        cur.execute("DELETE FROM tasc.street_key")
        cur.executemany("INSERT INTO tasc.street_key (street_name, name_key, name_base) VALUES (%s, %s, %s)", rows)
    print(f"Loaded {len(rows)} street-name keys ({len({r[1] for r in rows})} distinct keys).")
    return 0


def cmd_hin(args):
    """Load an MPO HIN line layer (GeoJSON, EPSG:4326) into tasc.hin_line, replacing that version's rows."""
    with open(args.file, encoding="utf-8") as f:
        features = json.load(f)["features"]
    lines = []
    for feat in features:
        g = feat.get("geometry") or {}
        if g.get("type") == "LineString" and len(g.get("coordinates", [])) >= 2:
            lines.append((json.dumps(g), json.dumps(feat.get("properties") or {})))
        elif g.get("type") == "MultiLineString":
            for part in g["coordinates"]:
                if len(part) >= 2:
                    lines.append((json.dumps({"type": "LineString", "coordinates": part}),
                                  json.dumps(feat.get("properties") or {})))
    bad = sum(
        1 for feat in features if (feat.get("geometry") or {}).get("type") not in ("LineString", "MultiLineString"))
    if not lines or exceeds_limit(bad, len(features)):
        print(f"STOPPED: {os.path.basename(args.file)}: {bad} of {len(features)} features are not lines. Nothing changed.")
        return 2
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS tasc.hin_line (
                           hin_line_id bigserial PRIMARY KEY, hin_version text NOT NULL, source text NOT NULL,
                           geom geometry(LineString, 32614) NOT NULL, attributes jsonb,
                           run_id bigint REFERENCES tasc.ingest_run)""")
        cur.execute("CREATE INDEX IF NOT EXISTS hin_line_geom_gix ON tasc.hin_line USING gist (geom)")
        run_id = log_run(cur, "hin", args.file, len(features), bad, "loaded", note=f"version {args.version}")
        cur.execute("DELETE FROM tasc.hin_line WHERE hin_version = %s", (args.version,))
        cur.executemany(
            """INSERT INTO tasc.hin_line (hin_version, source, geom, attributes, run_id)
               VALUES (%s, %s, ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 32614), %s::jsonb, %s)""",
            [(args.version, args.source, g, a, run_id) for g, a in lines])
        cur.execute("SELECT count(*), sum(ST_Length(geom)) / 1609.344 FROM tasc.hin_line WHERE hin_version = %s",
                    (args.version,))
        n, miles = cur.fetchone()
    print(f"Loaded HIN {args.version!r}: {n} lines, {miles:.1f} mi. run_id {run_id}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="TASC S1 ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("crashes", help="validate and load a CRIS crash CSV")
    c.add_argument("file")
    c.add_argument("--dry-run", action="store_true", help="validate only; do not touch the database")
    c.set_defaults(func=cmd_crashes)

    r = sub.add_parser("roads", help="load road linework from GeoJSON")
    r.add_argument("file")
    r.add_argument("--as-of", required=True, help="date the data describes, YYYY-MM-DD")
    r.add_argument("--source", default="roadway_inventory")
    r.set_defaults(func=cmd_roads)

    n = sub.add_parser("road-names", help="fill street names on roads already loaded, without reloading")
    n.add_argument("file", help="the GeoJSON the roads were loaded from")
    n.add_argument("--source", required=True)
    n.set_defaults(func=cmd_road_names)

    a = sub.add_parser("road-attrs", help="fill extra TxDOT road attributes (ROAD_ATTRS) on roads already loaded")
    a.add_argument("file", help="the GeoJSON the roads were loaded from")
    a.add_argument("--source", required=True)
    a.set_defaults(func=cmd_road_attrs)

    w = sub.add_parser("osm-roads", help="add streets missing from the TxDOT inventory, from a fetch_osm.py road file")
    w.add_argument("file")
    w.add_argument("--against", default="roadway_inventory_2019", help="TxDOT road source to fill gaps in")
    w.add_argument("--boundary", default="College Station")
    w.add_argument("--campus", help="fetch_osm.py campus file; streets inside Texas A&M get maintainer TAMU")
    w.add_argument("--source", help="source name (default osm_roads_<snapshot date>)")
    w.set_defaults(func=cmd_osm_roads)

    d = sub.add_parser("crash-details", help="add extra CRIS crash columns to crashes already loaded")
    d.add_argument("file")
    d.add_argument("--dry-run", action="store_true", help="validate only; change nothing")
    d.set_defaults(func=cmd_crash_details)

    o = sub.add_parser("osm", help="load a fetch_osm.py snapshot into tasc.osm_feature")
    o.add_argument("file")
    o.add_argument("--source", help="source name (default osm_<date> or osm_latest)")
    o.set_defaults(func=cmd_osm)

    k = sub.add_parser("corridors", help="load the study-corridor street spellings from corridors.py")
    k.set_defaults(func=cmd_corridors)

    b = sub.add_parser("boundary", help="load the city-limits polygon from fetch_boundary.py")
    b.add_argument("file")
    b.add_argument("--name", default="College Station")
    b.set_defaults(func=cmd_boundary)

    h = sub.add_parser("hin", help="load the MPO High-Injury Network line layer (GeoJSON)")
    h.add_argument("file")
    h.add_argument("--version", required=True, help="HIN version label, e.g. csap_fig3.9_digitized")
    h.add_argument("--source", default="mpo_hin")
    h.set_defaults(func=cmd_hin)

    s = sub.add_parser("street-keys", help="key every crash and road street name (street_names.py)")
    s.set_defaults(func=cmd_street_keys)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
