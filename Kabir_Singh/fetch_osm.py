"""Download OpenStreetMap features near the network as they were on a given date (IF-03).

    python fetch_osm.py --date 2022-12-31 --out ../../raw/osm   # backtest snapshot (feature set backtest_2022)
    python fetch_osm.py --date latest     --out ../../raw/osm   # newest available (feature set current)

Uses the ohsome API (api.ohsome.org, HeiGIT / Heidelberg University), which serves the full
OSM history: each query returns features exactly as they stood at the requested time, so the
2022-12-31 snapshot holds nothing added later. "latest" is the newest time ohsome has, which
lags live OSM by weeks to months; the file records it.

The area is a band --margin-m wide around every site of --network (default 600 m around
v0_2019). Ways are clipped to that band. One request per feature group; any HTTP error stops the
run, so a partial snapshot is never written. The output records endpoint, filters, area and time.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import ingest

ENDPOINT = "https://api.ohsome.org/v1"
USER_AGENT = "TASC-S1/0.1 (TAMU capstone; fetch_osm.py)"

# ohsome filter per group; the group name becomes the feature family it feeds.
GROUPS = {
    "bus_stop":        "type:node and (highway=bus_stop or (public_transport=platform and bus=yes))",
    "school":          "amenity in (school, college, university, kindergarten)",
    "bar":             "amenity in (bar, pub, nightclub, biergarten)",
    "restaurant":      "amenity in (restaurant, fast_food, cafe)",
    "crossing":        "type:node and highway=crossing",
    "traffic_signals": "type:node and highway=traffic_signals",
    "street_lamp":     "type:node and highway=street_lamp",
    "sidewalk":        "type:way and highway=footway and footway=sidewalk",
    # Major roads only, for their sidewalk=*, lit=* and lanes tags.
    "major_road":      "type:way and highway in (motorway, trunk, primary, secondary, tertiary, "
                       "motorway_link, trunk_link, primary_link, secondary_link, tertiary_link)",
}


def area_from_db(network_version, margin_m):
    """The band margin_m around every site of the network, as a GeoJSON polygon in lon/lat.
    Holes (gaps enclosed where corridor bands meet) are filled: ohsome rejects them once
    simplified, and a few extra square meters inside the band do no harm."""
    with ingest.connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT ST_AsGeoJSON(ST_Transform(ST_Collect(ARRAY(
                                  SELECT ST_MakePolygon(ST_ExteriorRing((ST_Dump(ST_SimplifyPreserveTopology(
                                             ST_Buffer(ST_Union(geom), %s), 10))).geom)))), 4326), 6)
                       FROM tasc.site WHERE network_version = %s""", (margin_m, network_version))
        geojson = cur.fetchone()[0]
    if geojson is None:
        raise ValueError(f"no sites for network {network_version}")
    return json.loads(geojson)


def call(path, params, retries=3):
    data = urllib.parse.urlencode(params).encode()
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(f"{ENDPOINT}/{path}", data=data, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=600) as resp:
                return json.load(resp)
        except Exception as exc:
            if attempt == retries:
                raise
            wait = 30 * 2 ** (attempt - 1)
            print(f"  attempt {attempt} failed ({str(exc)[:120]}); retrying in {wait} s", file=sys.stderr)
            time.sleep(wait)


def latest_time():
    with urllib.request.urlopen(urllib.request.Request(f"{ENDPOINT}/metadata", headers={"User-Agent": USER_AGENT}),
                                timeout=60) as resp:
        return json.load(resp)["extractRegion"]["temporalExtent"]["toTimestamp"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download historical OSM features near the network")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD, or 'latest'")
    parser.add_argument("--out", required=True)
    parser.add_argument("--network", default="v0_2019")
    parser.add_argument("--margin-m", type=int, default=600)
    args = parser.parse_args(argv)

    if args.date == "latest":
        when = latest_time()
    else:
        datetime.strptime(args.date, "%Y-%m-%d")
        when = f"{args.date}T23:59:59Z"
    area = area_from_db(args.network, args.margin_m)
    bpolys = json.dumps({"type": "FeatureCollection",
                         "features": [{"type": "Feature", "properties": {"id": "band"}, "geometry": area}]})
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # The public server blocks elements/geometry (403) but serves elementsFullHistory/geometry.
    # Ask for every version in the one day ending at `when`, then keep only the versions still
    # valid at its end: that is the map exactly as it stood at `when`.
    end = datetime.fromisoformat(when.replace("Z", "+00:00"))
    start = (end - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_s = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    groups = {}
    for name, flt in GROUPS.items():
        result = call("elementsFullHistory/geometry", {"bpolys": bpolys, "filter": flt,
                                                       "time": f"{start},{end_s}", "properties": "tags"})
        current = [f for f in result["features"] if f["properties"].get("@validTo") == end_s]
        groups[name] = {"filter": flt, "features": current}
        print(f"  {name:16s} {len(current):6d} features", flush=True)

    os.makedirs(args.out, exist_ok=True)
    label = "latest" if args.date == "latest" else args.date
    path = os.path.join(args.out, f"osm_{args.network}_{args.margin_m}m_{label}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "endpoint": f"{ENDPOINT}/elementsFullHistory/geometry",
            "snapshot_time": when,
            "requested": args.date,
            "network": args.network,
            "margin_m": args.margin_m,
            "area": area,
            "downloaded_utc": started,
            "attribution": "© OpenStreetMap contributors (ODbL), via ohsome API (HeiGIT)",
            "groups": groups,
        }, f)
    print(f"{path}: {sum(len(g['features']) for g in groups.values())} features in {len(groups)} groups, "
          f"as of {when}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
