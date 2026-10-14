"""Write a deterministic synthetic contract fixture. Never use it as City evidence."""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


def poisson(rng, mean):
    threshold, product, n = math.exp(-mean), 1.0, 0
    while product > threshold:
        product *= rng.random()
        n += 1
    return n-1


def demo_snapshot(seed=7, n_sites=100):
    rng = random.Random(seed)
    metadata = {"network_version": "synthetic-network-v1", "feature_set": "backtest_2022",
                "analysis_scope": "college_station_public_roads", "synthetic": True,
                "as_of_date": "2022-12-31", "length_policy": "SYNTHETIC: disjoint 0.1-mile segments; intersection exposure untested",
                "data_versions": {"all": "synthetic-v1"}, "history_years_loaded": list(range(2015, 2023)),
                "test_years_loaded": [2023, 2024, 2025], "hin_version": "synthetic-hin-v1",
                "hin_source": "synthetic-hin", "hin_as_of_date": "2022-12-31",
                "sources": [{"source": "synthetic-features", "role": "predictor", "version": "v1",
                             "as_of_date": "2022-01-01", "available_as_of": "2022-01-01"},
                            {"source": "synthetic-history", "role": "history", "version": "v1",
                             "as_of_date": "2022-12-31", "available_as_of": "2022-12-31"},
                            {"source": "synthetic-test", "role": "evaluation", "version": "v1",
                             "as_of_date": "2025-12-31", "available_as_of": "2026-01-01"},
                            {"source": "synthetic-hin", "role": "baseline", "version": "v1",
                             "as_of_date": "2022-12-31", "available_as_of": "2024-01-01"}]}
    sites, features, history, test = [], [], [], []
    for i in range(n_sites):
        sid = f"s{i:04d}"
        speed, lanes, traffic = rng.choice([25,35,45,55]), rng.choice([2,4,6]), rng.randint(1000, 25000)
        sites.append({"site_id": sid, "site_type": "segment", "road_name": f"Synthetic road {i}",
                      "as_of_date": "2022-01-01", "risk_length_mi": .1, "network_length_mi": .1,
                      "in_hin": i < round(.11*n_sites)})
        attrs = {"speed_limit": speed, "num_lanes": lanes, "aadt": traffic, "func_class": "3" if lanes >= 4 else "5",
                 "median_type": "divided" if lanes >= 4 else "undivided"}
        features.extend({"site_id": sid, "feature_name": name, "value": value, "as_of_date": "2022-01-01",
                         "source": "synthetic-features"} for name, value in attrs.items())
        mu = .1 * math.exp(1.2 + .012*(speed-25) + .00003*traffic) * rng.gammavariate(2, .5)
        p = .015 + .001*speed
        for year in range(2015,2023):
            total = poisson(rng, mu)
            known = sum(rng.random() > .02 for _ in range(total))
            fatal = sum(rng.random() < p for _ in range(known))
            history.append({"site_id": sid, "year": year, "crashes": total, "known_crashes": known, "fsi_crashes": fatal})
        for year in range(2023,2026):
            for _ in range(poisson(rng, mu)):
                test.append({"crash_id": f"c{len(test):05d}", "crash_date": f"{year}-06-01", "site_id": sid,
                             "severity": "A" if rng.random() < p else "O", "in_analysis_area": True})
    test.append({"crash_id": "unmatched-fatal", "crash_date": "2024-03-01", "site_id": None,
                 "severity": "K", "in_analysis_area": True})
    return {"metadata": metadata, "sites": sites, "features": features, "history": history, "test_crashes": test}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="demo_snapshot.json")
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(demo_snapshot(), indent=2) + "\n")


if __name__ == "__main__":
    main()
