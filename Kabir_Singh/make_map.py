"""Interactive map of the city-wide network, built from the live database.

    .venv/bin/python make_map.py                         # writes map/index.html
    .venv/bin/python make_map.py --fragment out.html     # also a page body for publishing as an Artifact

Every road site of the network, with its crash totals per year (all crashes and fatal + serious)
and its backtest features. Totals per site only: no individual crash locations are written.
The basemap is drawn from the same data (sites, city limits), so the page needs no map tiles and
works offline once the Leaflet script has loaded. The page itself is map/template.html.
"""
import argparse
import json
import os

import ingest

HERE = os.path.dirname(os.path.abspath(__file__))
# Map labels only: TxDOT route codes as people in College Station know the roads.
ROUTE_LABELS = {
    "SH0006": "SH 6 (Earl Rudder Fwy)", "FM2818": "Harvey Mitchell Pkwy", "SH0030": "Harvey Rd (SH 30)",
    "FM2347": "George Bush Dr", "SH0040": "William D. Fitch Pkwy (SH 40)", "SH0047": "SH 47", "SH0308": "SH 308",
    "FM0060": "University Dr", "BS0006R": "Texas Ave", "FM2154": "Wellborn Rd",
}


def label(name):
    return " & ".join(sorted(ROUTE_LABELS.get(part, part) for part in name.split(" & "))) if name else ""
YEARS = list(range(2016, 2026))
# Features shown on the site card, in this order (label, unit). All from feature set backtest_2022.
FEATURES = [
    ("speed_limit", "Speed limit", "mph"), ("num_lanes", "Lanes", ""), ("aadt", "Traffic (AADT)", "vehicles/day"),
    ("lane_width_ft", "Lane width", "ft"), ("shoulder_outside_ft", "Outside shoulder", "ft"),
    ("median_width_ft", "Median width", "ft"), ("access_control", "Access control (TxDOT code)", ""),
    ("func_class", "Functional class (code)", ""), ("curvature_deg_per_mi", "Curvature", "°/mi"),
    ("dist_to_intersection_m", "Nearest intersection", "m"), ("legs", "Legs", ""),
    ("osm_signalized_intersections_30m", "Traffic signals within 30 m (OSM)", ""),
    ("osm_crossings_30m", "Crosswalks within 30 m (OSM)", ""), ("osm_sidewalk_share", "Sidewalk share (OSM)", ""),
    ("osm_bus_stops_200m", "Bus stops within 200 m (OSM)", ""), ("osm_schools_400m", "Schools within 400 m (OSM)", ""),
    ("osm_bars_200m", "Bars within 200 m (OSM)", ""),
]


def build(cur, net):
    cur.execute("SELECT DISTINCT route_name FROM tasc.corridor_street")
    corridor_routes = {r[0] for r in cur.fetchall()}
    cur.execute(
        """SELECT s.site_id, s.site_type, v.road_name, round((v.risk_length_mi)::numeric, 3),
                  coalesce(s.interchange, false), r.maintainer, r.source, r.route_name,
                  ST_AsGeoJSON(ST_Transform(CASE WHEN s.site_type = 'segment'
                                                 THEN ST_SimplifyPreserveTopology(s.geom, 1) ELSE s.geom END, 4326), 5)
           FROM tasc.site s
           JOIN tasc.s2_site_scope v USING (site_id, network_version)
           LEFT JOIN tasc.road r USING (road_id)
           WHERE s.network_version = %s ORDER BY s.site_id""", (net,))
    sites, index = [], {}
    for sid, kind, name, length, interchange, maintainer, source, route, geojson in cur.fetchall():
        g = json.loads(geojson)
        index[sid] = len(sites)
        sites.append({
            "id": sid, "t": "s" if kind == "segment" else "i", "n": label(name), "len": float(length),
            "x": 1 if interchange else 0, "tamu": 1 if maintainer == "TAMU" else 0,
            "src": "osm" if (source or "").startswith("osm_") else ("txdot" if source else ""),
            "cor": 1 if route in corridor_routes else 0,
            "g": g["coordinates"], "c": [0] * len(YEARS), "k": [0] * len(YEARS), "f": {},
        })
    cur.execute(
        """SELECT m.site_id, c.crash_year, count(*), count(*) FILTER (WHERE c.is_fsi)
           FROM tasc.crash_match m JOIN tasc.crash c USING (crash_id)
           WHERE m.network_version = %s AND m.status = 'matched' GROUP BY 1, 2""", (net,))
    for sid, year, n, fsi in cur.fetchall():
        if sid in index and year in YEARS:
            sites[index[sid]]["c"][YEARS.index(year)] = n
            sites[index[sid]]["k"][YEARS.index(year)] = fsi
    names = [f[0] for f in FEATURES]
    cur.execute(
        """SELECT f.site_id, f.feature_name, f.value_num, f.value_text
           FROM tasc.site_feature f JOIN tasc.site s USING (site_id)
           WHERE s.network_version = %s AND f.feature_set = 'backtest_2022' AND f.feature_name = ANY(%s)""",
        (net, names))
    for sid, fname, num, text in cur.fetchall():
        if fname == "legs" or fname.startswith("osm_") and fname != "osm_sidewalk_share":
            value = int(num) if num is not None else text
        else:
            value = round(num, 2) if num is not None else text
        sites[index[sid]]["f"][fname] = value
    # ST_Multi: simplifying a one-part MultiPolygon returns a Polygon, one nesting level less.
    cur.execute("""SELECT ST_AsGeoJSON(ST_Transform(ST_Multi(ST_SimplifyPreserveTopology(geom, 5)), 4326), 5)
                   FROM tasc.boundary WHERE name = 'College Station'""")
    boundary = json.loads(cur.fetchone()[0])["coordinates"]
    cur.execute("SELECT fsi_geocoded, fsi_matched, fsi_match_pct FROM tasc.match_rate WHERE network_version = %s", (net,))
    fsi_geocoded, fsi_matched, pct = cur.fetchone()
    cur.execute("""SELECT count(*) FILTER (WHERE status = 'matched'), count(*) FROM tasc.crash_match
                   WHERE network_version = %s""", (net,))
    matched, crashes = cur.fetchone()
    return {
        "network": net, "years": YEARS, "sites": sites, "boundary": boundary,
        "features": [{"key": k, "label": label, "unit": unit} for k, label, unit in FEATURES],
        "summary": {"crashes": crashes, "matched": matched, "fsi_geocoded": fsi_geocoded,
                    "fsi_matched": fsi_matched, "fsi_pct": float(pct)},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the interactive network map")
    parser.add_argument("--network", default="v1_2022")
    parser.add_argument("--out", default=os.path.join(HERE, "map", "index.html"))
    parser.add_argument("--fragment", help="also write the page without <!doctype>/<head>, for an Artifact")
    args = parser.parse_args(argv)
    with ingest.connect() as conn, conn.cursor() as cur:
        data = build(cur, args.network)
    with open(os.path.join(HERE, "map", "template.html"), encoding="utf-8") as f:
        template = f.read()
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    page = template.replace("__MAP_DATA__", payload)
    full = ('<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + page)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"wrote {args.out}: {len(data['sites']):,} sites, {len(full) / 1e6:.1f} MB")
    if args.fragment:
        with open(args.fragment, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"wrote {args.fragment}")
    return 0


if __name__ == "__main__":
    main()
