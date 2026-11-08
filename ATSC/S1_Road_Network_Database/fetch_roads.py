"""Download the TxDOT Roadway Inventory for Brazos County as GeoJSON (IF-02).

    python fetch_roads.py 2019    --out ../../raw/roads     # snapshot published for 2019
    python fetch_roads.py 2023    --out ../../raw/roads
    python fetch_roads.py current --out ../../raw/roads     # live layer, changes over time

TxDOT publishes yearly snapshots on its open-data portal (gis-txdot.opendata.arcgis.com). There is
no 2020, 2021 or 2022 snapshot. The service returns at most 2,000 records per request, so this
pages through the results and writes one FeatureCollection in WGS84 lon/lat, which is what
`ingest.py roads` expects. Uses only the standard library.
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

BASE = "https://services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services"
SNAPSHOTS = {
    "2019": "TxDOT_Roadway_Inventory_2019",
    "2023": "Roadway_Inventory_2023",
    "current": "TxDOT_Roadway_Inventory",
}
BRAZOS_COUNTY = 21          # TxDOT county number (field CO)
PAGE_SIZE = 2000


def query(service, offset):
    params = urllib.parse.urlencode({
        "where": f"CO={BRAZOS_COUNTY}",
        "outFields": "*",
        "outSR": 4326,
        "orderByFields": "OBJECTID",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "f": "geojson",
    })
    url = f"{BASE}/{service}/FeatureServer/0/query?{params}"
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = json.load(resp)
    if "error" in data:
        raise RuntimeError(f"{service}: {data['error']}")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download Brazos County roads from TxDOT")
    parser.add_argument("snapshot", choices=SNAPSHOTS)
    parser.add_argument("--out", required=True, help="folder for the .geojson file")
    args = parser.parse_args(argv)

    service = SNAPSHOTS[args.snapshot]
    features, offset = [], 0
    while True:
        page = query(service, offset)
        features.extend(page["features"])
        if len(page["features"]) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, f"roadway_brazos_{args.snapshot}.geojson")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "type": "FeatureCollection",
            "source": f"{BASE}/{service}/FeatureServer/0",
            "filter": f"CO={BRAZOS_COUNTY} (Brazos County)",
            "downloaded": date.today().isoformat(),
            "features": features,
        }, f)
    print(f"{path}: {len(features)} road records from {service}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
