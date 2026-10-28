"""TASC S1 ingest: load public crash and road files into the PostGIS database.

    python ingest.py crashes data/cris_2022.csv --dry-run     # validate only, no database needed
    python ingest.py crashes data/cris_2022.csv               # validate, then load
    python ingest.py roads   data/roadway_brazos.geojson --as-of 2022-12-31
    python ingest.py corridors                                # study-corridor street spellings
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
    "route_name": "HWY", "roadbed": "RDBD_ID", "city_code": "CITY", "func_class": "F_SYSTEM", "num_lanes": "NUM_LANES",
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
        # Reloading a source replaces it rather than adding a second copy of every road. If a
        # built network still uses those roads, stop: delete or rebuild that network version first.
        cur.execute("""SELECT count(*), string_agg(DISTINCT s.network_version, ', ')
                       FROM tasc.site s JOIN tasc.road r USING (road_id) WHERE r.source = %s""", (args.source,))
        used, versions = cur.fetchone()
        if used:
            print(f"STOPPED: network {versions} is built from source {args.source!r} ({used} sites). "
                  f"Delete it first (DELETE FROM tasc.site WHERE network_version = ...), reload, then rebuild it. "
                  f"Nothing changed.")
            return 2
        cur.execute("DELETE FROM tasc.road WHERE source = %s", (args.source,))
        replaced = cur.rowcount
        run_id = log_run(cur, args.source, args.file, len(features), skipped, "loaded",
                         note="rows_bad = features with no geometry"
                              + (f"; replaced {replaced} earlier rows of this source" if replaced else ""))
        cur.executemany(
            """INSERT INTO tasc.road (geom, route_name, roadbed, city_code, func_class, num_lanes, speed_limit,
                                      median_type, aadt, aadt_year, source, as_of_date, run_id)
               SELECT (ST_Dump(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%(geojson)s), 4326), 32614))).geom,
                      %(route_name)s, %(roadbed)s, %(city_code)s, %(func_class)s, %(num_lanes)s, %(speed_limit)s, %(median_type)s,
                      %(aadt)s, %(aadt_year)s, %(source)s, %(as_of)s::date, %(run_id)s""",
            [dict(r, run_id=run_id) for r in rows],
        )
    print(f"Loaded {len(rows)} road features ({skipped} skipped, no geometry"
          + (f"; replaced {replaced} earlier rows" if replaced else "") + f"). run_id {run_id}")
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
