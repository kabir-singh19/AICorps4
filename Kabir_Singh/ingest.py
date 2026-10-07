"""TASC S1 ingest: load public crash and road files into the PostGIS database.

    python ingest.py crashes data/cris_2022.csv --dry-run     # validate only, no database needed
    python ingest.py crashes data/cris_2022.csv               # validate, then load
    python ingest.py roads   data/roadway_brazos.geojson --as-of 2022-12-31

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
from datetime import datetime

BAD_RECORD_LIMIT = 0.02            # FSR: more than 2% bad records stops the pipeline
YEAR_RANGE = (2015, 2025)          # crash years the project uses
TEXAS_BBOX = (25.8, 36.6, -106.7, -93.5)   # lat_min, lat_max, lon_min, lon_max
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


def validate_row(row, cols, seen_ids):
    """Return (record, None) for a good row or (None, reason) for a bad one.

    A crash with no coordinates (blank, 0,0, or text like 'No Data') is NOT a bad record: it is
    loaded without a location and logged later by the map-matching step as 'no_coordinates'.
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
        elif not (TEXAS_BBOX[0] <= lat <= TEXAS_BBOX[1] and TEXAS_BBOX[2] <= lon <= TEXAS_BBOX[3]):
            return None, "coordinates outside Texas"

    seen_ids.add(crash_id)
    return {
        "crash_id": crash_id,
        "crash_date": crash_date,
        "severity": severity,
        "lat": lat,
        "lon": lon,
        "crash_type": (row.get(cols.get("crash_type", ""), "") or "").strip() or None,
        "light_condition": (row.get(cols.get("light_condition", ""), "") or "").strip() or None,
    }, None


def skip_preamble(f):
    """Move the file position to the header row.

    CRIS Query exports start with a disclaimer, result counts and the filters used, and put the
    column names on about line 12. Search for the row whose first cell is 'Crash ID' rather than
    skipping a fixed number of lines, so a longer or missing preamble still works.
    """
    while True:
        pos = f.tell()
        line = f.readline()
        if not line:
            raise ValueError("No header row starting with 'Crash ID' found in the file.")
        first_cell = next(csv.reader([line]), [""])
        if first_cell and _norm(first_cell[0]) == _norm(CRIS_COLUMNS["crash_id"][0]):
            f.seek(pos)
            return


def validate_crash_file(path):
    """Read a CRIS CSV. Returns (good_records, rejects, total) where rejects = [(row_number, reason, raw_row)]."""
    good, rejects, seen = [], [], set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        skip_preamble(f)
        reader = csv.DictReader(f)
        cols = resolve_columns(reader.fieldnames or [])
        total = 0
        for total, row in enumerate(reader, start=1):
            record, reason = validate_row(row, cols, seen)
            if record:
                good.append(record)
            else:
                rejects.append((total, reason, row))
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


def cmd_crashes(args):
    good, rejects, total = validate_crash_file(args.file)
    n_bad = len(rejects)
    pct = 100.0 * n_bad / total if total else 100.0
    stop = exceeds_limit(n_bad, total)
    print(f"{args.file}: {total} rows, {n_bad} bad ({pct:.2f}%), limit {BAD_RECORD_LIMIT:.0%}")
    reasons = {}
    for _, reason, _ in rejects:
        reasons[reason] = reasons.get(reason, 0) + 1
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {n:6d}  {reason}")
    if stop:
        print("REJECTED: bad-record limit reached. Nothing loaded.")

    if not args.dry_run:
        with connect() as conn, conn.cursor() as cur:
            run_id = log_run(cur, "cris", args.file, total, n_bad, "rejected" if stop else "loaded")
            cur.executemany(
                "INSERT INTO tasc.ingest_reject (run_id, row_number, reason, raw) VALUES (%s, %s, %s, %s)",
                [(run_id, n, reason, json.dumps(raw)) for n, reason, raw in rejects],
            )
            if not stop:
                cur.executemany(
                    """INSERT INTO tasc.crash (crash_id, crash_date, severity, crash_type, light_condition, lat, lon, geom, run_id)
                       VALUES (%(crash_id)s, %(crash_date)s, %(severity)s, %(crash_type)s, %(light_condition)s,
                               %(lat)s, %(lon)s,
                               ST_Transform(ST_SetSRID(ST_MakePoint(%(lon)s::float8, %(lat)s::float8), 4326), 32614),
                               %(run_id)s)
                       ON CONFLICT (crash_id) DO UPDATE SET
                           crash_date = EXCLUDED.crash_date, severity = EXCLUDED.severity,
                           crash_type = EXCLUDED.crash_type, light_condition = EXCLUDED.light_condition,
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
        run_id = log_run(cur, args.source, args.file, len(features), skipped, "loaded",
                         note="rows_bad = features with no geometry")
        cur.executemany(
            """INSERT INTO tasc.road (geom, route_name, roadbed, city_code, func_class, num_lanes, speed_limit,
                                      median_type, aadt, aadt_year, source, as_of_date, run_id)
               SELECT (ST_Dump(ST_Transform(ST_SetSRID(ST_GeomFromGeoJSON(%(geojson)s), 4326), 32614))).geom,
                      %(route_name)s, %(roadbed)s, %(city_code)s, %(func_class)s, %(num_lanes)s, %(speed_limit)s, %(median_type)s,
                      %(aadt)s, %(aadt_year)s, %(source)s, %(as_of)s::date, %(run_id)s""",
            [dict(r, run_id=run_id) for r in rows],
        )
    print(f"Loaded {len(rows)} road features ({skipped} skipped, no geometry). run_id {run_id}")
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
