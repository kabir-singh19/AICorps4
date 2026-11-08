"""Download the College Station city limits from the Census Bureau as GeoJSON (analysis area).

    python fetch_boundary.py --out ../../raw/boundary

Source: Census TIGERweb, ACS 2022 vintage (boundaries as of 1 January 2022), layer
"Incorporated Places", GEOID 4815976 = College Station city, TX. This is the same boundary as
the TIGER/Line 2022 place shapefile, served as GeoJSON so only the standard library is needed.
Load it with:  python ingest.py boundary ../../raw/boundary/college_station_2022.geojson
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SERVICE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2022/MapServer/24"
VINTAGE = "2022-01-01"      # TIGERweb ACS 2022: "January 1, 2022 vintage"
GEOID = "4815976"           # College Station city, Texas


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download the College Station city boundary")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    params = urllib.parse.urlencode({"where": f"GEOID='{GEOID}'", "outFields": "NAME,GEOID,AREALAND",
                                     "outSR": 4326, "f": "geojson"})
    with urllib.request.urlopen(f"{SERVICE}/query?{params}", timeout=120) as resp:
        data = json.load(resp)
    if "error" in data or len(data.get("features", [])) != 1:
        raise RuntimeError(f"expected exactly one place with GEOID {GEOID}, got: {str(data)[:300]}")
    feature = data["features"][0]
    feature["properties"].update({"vintage": VINTAGE, "service": SERVICE,
                                  "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, f"college_station_{VINTAGE[:4]}.geojson")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": [feature]}, f)
    p = feature["properties"]
    print(f"{path}: {p['NAME']}, {p['AREALAND'] / 1e6:.1f} km2 of land, boundary as of {VINTAGE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
