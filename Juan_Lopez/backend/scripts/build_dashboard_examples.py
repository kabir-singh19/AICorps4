"""Build opt-in dashboard fixtures requested for the website demonstration.

Run from backend/: .venv/bin/python scripts/build_dashboard_examples.py
Geometry is real OSM reference data; every risk, comparison, and memo is invented.
These fixtures are not outputs of the Example lab classifier or the team's model.
"""
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROADS = ["University Drive", "Harvey Road", "Texas Avenue", "Wellborn Road"]
SLUGS = ["university", "harvey", "texas", "wellborn"]


def length(feature):
    total = 0
    points = feature["geometry"]["coordinates"]
    for (lon1, lat1), (lon2, lat2) in zip(points, points[1:]):
        a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
        total += 2 * 3958.7613 * math.asin(math.sqrt(min(1, a)))
    return total


def interval(captured, count):
    proportion, z = captured / count, 1.96
    denominator = 1 + z * z / count
    center = (proportion + z * z / (2 * count)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / count + z * z / (4 * count * count)) / denominator
    return [round(max(0, center - half), 6), round(min(1, center + half), 6)]


def build():
    geometry = json.loads((ROOT / "frontend/src/data/corridors.geojson.json").read_text())
    sections = [max((feature for feature in geometry["features"] if feature["properties"]["corridor"] == road), key=length) for road in ROADS]
    scenarios = [
        {"run_id": "example-dashboard-002", "name": "Example run 2 — revised fictional scenario", "hour": 14, "rates": [0.78, 0.28, 0.94, 0.48], "captured": [12, 14, 16]},
        {"run_id": "example-dashboard-001", "name": "Example run 1 — baseline fictional scenario", "hour": 13, "rates": [0.84, 0.36, 0.68, 0.52], "captured": [10, 13, 15]},
    ]
    concerns = ["turning and pedestrian conflicts", "driveway access and crossing visibility", "intersection turning conflicts", "approach speed and crossing visibility"]
    for scenario in scenarios:
        order = sorted(range(4), key=lambda index: scenario["rates"][index], reverse=True)
        sites, memos = [], {}
        for index, (road, section, slug) in enumerate(zip(ROADS, sections, SLUGS)):
            site_id = f"example-{slug}"
            rank = order.index(index) + 1
            sites.append({"type": "Feature", "geometry": copy.deepcopy(section["geometry"]), "properties": {"site_id": site_id, "site_type": "segment", "road_name": road, "map_segment_id": section["id"], "length_mi": round(length(section), 4), "fsi_rate": scenario["rates"][index], "rank": rank, "flagged": rank <= 2, "in_hin": None, "top_factors": [f"Fictional scenario: {concerns[index]}", "Illustrative risk value entered for interface testing; not model inference"], "crash_history": "Synthetic historical summary: this scenario assumes recurring conflicts for demonstration. No real crash counts or records have been loaded."}})
            memos[site_id] = {"title": f"Example screening memo — {road}", "is_example": True, "grounding_passed": False, "text": f"PURPOSE\nThis sample shows what a site memo could look like for {road} in {scenario['run_id']}. All safety observations and risk values are invented. The road name and mapped section are geographic references only.\n\nILLUSTRATIVE FINDING\nThe fictional scenario assigns this section rank {rank} of four, with a synthetic rate of {scenario['rates'][index]:.2f} F&SI events per mile per year. These numbers demonstrate the interface and are not estimates of actual road safety. The scenario assumes {concerns[index]}; this has not been observed or verified.\n\nQUESTIONS FOR A FUTURE SITE REVIEW\nA real study would check crash diagrams, turning movements, pedestrian activity, sight distance, exposure, and existing traffic controls. Any possible treatment would depend on those findings and an engineering review. No treatment, cost, or safety benefit is recommended by this example.\n\nLIMITATIONS AND STATUS\nThis is a manually authored demonstration memo, not an AI-generated or grounded engineering document. No site inspection, source grounding, or approval has been completed. The revised example run changes fictional inputs only; it does not show a measured improvement.", "references": [f"Synthetic fixture {scenario['run_id']}; site {site_id}. All risk and narrative values are invented.", f"Map reference: OpenStreetMap way {section['properties']['osm_way_id']}; geometry snapshot metadata in frontend/src/data/corridors.geojson.json. Geometry does not substantiate safety claims.", "Grounding status: not performed. is_example=true permits this memo only inside an is_demo=true run."]}
        methods = []
        for method, label, captured in zip("ABC", ["Consultant HIN", "Negative binomial + EB", "ATSC ML + EB"], scenario["captured"]):
            methods.append({"method": method, "label": label + " (example only)", "capture_rate": captured / 24, "confidence_interval": interval(captured, 24), "flagged_mileage": 2.0, "test_fsi_count": 24})
        yield {"schema_version": "1.0", "run_id": scenario["run_id"], "model_name": scenario["name"], "published_at": f"2026-11-04T{scenario['hour']}:00:00-06:00", "status": "published", "is_demo": True, "risk_unit": "synthetic F&SI events per mile per year (invented)", "sites": sites, "backtest": {"training_cutoff": "2022-12-31 (fictional setup)", "test_window": "2023–2025 (synthetic example; no real test performed)", "methods": methods}, "memos": memos}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.model_results import PublishedRun
    target = ROOT / "backend/data/published"
    target.mkdir(parents=True, exist_ok=True)
    for run in build():
        PublishedRun.model_validate(run)
        (target / f"{run['run_id']}.json").write_text(json.dumps(run, indent=2) + "\n")
        print(f"Saved {run['run_id']} — synthetic dashboard fixture")
