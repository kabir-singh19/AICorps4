"""Paired crash-level bootstrap and capture reports, using only the standard library."""
from __future__ import annotations

import math
import random


def percentile(values, q):
    ordered = sorted(values)
    pos = (len(ordered)-1)*q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return ordered[lo] + (ordered[hi]-ordered[lo])*(pos-lo)


def bootstrap_capture(crashes, flagged_methods, resamples=1000, seed=42, fsi_only=True):
    """Resample the same crashes for every method and paired difference.

    Samples are processed one at a time to avoid a resamples-by-crashes allocation.
    """
    if not isinstance(resamples, int) or isinstance(resamples, bool) or resamples < 1000:
        raise ValueError("at least 1000 bootstrap resamples required")
    seen, events = set(), []
    for row in crashes:
        cid = str(row["crash_id"])
        if cid in seen:
            raise ValueError("duplicate test crash IDs")
        seen.add(cid)
        if row["in_analysis_area"] and (not fsi_only or row["severity"] in {"K", "A"}):
            events.append(None if row.get("site_id") is None else str(row["site_id"]))
    names = sorted(flagged_methods)
    flagged = {m: {str(s) for s in flagged_methods[m]} for m in names}
    if any(None in flagged_methods[m] for m in names):
        raise ValueError("unmatched crashes must never be flagged")
    n = len(events)
    if n == 0:
        return {"status": "undefined: no test crashes", "n_test_fsi": 0, "methods": {}, "differences": {},
                "resamples": resamples, "target": "fsi" if fsi_only else "total"}
    vectors = [tuple(int(site is not None and site in flagged[m]) for m in names) for site in events]
    point = [sum(v[i] for v in vectors)/n for i in range(len(names))]
    draws = {m: [] for m in names}
    comparisons = [f"{m}-A" for m in ("B", "C") if m in names and "A" in names]
    paired = {c: [] for c in comparisons}
    # Sampling whole events preserves correlations between A/B/C capture indicators.
    rng = random.Random(seed)
    for _ in range(resamples):
        total = [0]*len(names)
        for _ in range(n):
            event = vectors[rng.randrange(n)]
            for i, v in enumerate(event):
                total[i] += v
        sample = {m: total[i]/n for i, m in enumerate(names)}
        for m in names:
            draws[m].append(sample[m])
        for c in paired:
            paired[c].append(sample[c[0]]-sample["A"])
    methods = {m: {"capture": point[i], "ci_low": percentile(draws[m], .025),
                   "ci_high": percentile(draws[m], .975), "n_test_fsi": n,
                   "captured_crashes": int(round(point[i]*n))} for i, m in enumerate(names)}
    differences = {c: {"difference": methods[c[0]]["capture"]-methods["A"]["capture"],
                       "ci_low": percentile(paired[c], .025), "ci_high": percentile(paired[c], .975)} for c in paired}
    return {"status": "ok", "n_test_fsi": n, "unmatched_crashes": sum(s is None for s in events),
            "methods": methods, "differences": differences, "resamples": resamples,
            "seed": seed, "target": "fsi" if fsi_only else "total", "bootstrap_unit": "individual crash"}


def evaluate(predictions, test_crashes, hin_ids, resamples=1000, seed=42):
    try:
        from .ranking import flag_by_length
    except ImportError:
        from ranking import flag_by_length
    methods = {m: frame for m, frame in predictions.items()}
    ids = list(methods["C"]["site_id"].astype(str))
    lengths = methods["C"]["network_length_mi"].to_numpy()
    total_length = float(lengths.sum())
    if any(list(frame.site_id.astype(str)) != ids for frame in methods.values()):
        raise ValueError("ranking methods must use identical sites in identical order")
    hin_share = None if hin_ids is None else sum(lengths[i] for i, sid in enumerate(ids) if sid in hin_ids)/total_length
    shares = [0.05, 0.11, 0.20]
    if hin_share is not None and hin_share not in shares:
        shares.append(float(hin_share))
    reports = []
    for share in shares:
        flagged, length_details = {}, {}
        for m, frame in methods.items():
            if share == 0:
                mask = frame["flagged"].to_numpy() & False
            else:
                mask = flag_by_length(frame["rank"], lengths, share=share,
                                      tolerance=0.005 if share == .11 else None, allow_zero_lengths=True)
            flagged[m] = set(frame.loc[mask, "site_id"].astype(str))
            miles = float(lengths[mask].sum())
            length_details[m] = {"flagged_miles": miles, "flagged_share": miles/total_length,
                                 "requested_share": share, "rounding_error": miles/total_length-share}
        if hin_ids is not None:
            flagged["A"] = hin_ids
            length_details["A"] = {"flagged_miles": float(hin_share*total_length), "flagged_share": hin_share,
                                   "requested_share": hin_share, "rounding_error": 0.0}
        for target in ("fsi", "total"):
            report = bootstrap_capture(test_crashes, flagged, resamples, seed, fsi_only=target == "fsi")
            report["requested_share"] = share
            report["length_details"] = length_details
            report["hin_available"] = hin_ids is not None
            if hin_ids is None:
                report["method_A_status"] = "unavailable: published HIN membership required"
            for m, detail in length_details.items():
                if m in report["methods"]:
                    report["methods"][m].update(detail)
            reports.append(report)
    return {"primary": next(r for r in reports if r["requested_share"] == .11 and r["target"] == "fsi"),
            "sensitivity": reports, "hin_share": hin_share,
            "fairness_note": "A stays the published HIN at all thresholds; B/C use closest whole-site prefixes."}


def main(argv=None):
    import argparse
    import json
    import sys
    from pathlib import Path
    try:
        from .artifacts import load_bundle, canonical_json
    except ImportError:
        from artifacts import load_bundle, canonical_json
    parser = argparse.ArgumentParser(description="Recompute scoring from a verified frozen run")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", default="outputs")
    args = parser.parse_args(argv)
    try:
        try:
            from .artifacts import validate_run_id
        except ImportError:
            from artifacts import validate_run_id
        validate_run_id(args.run_id)
        directory = Path(args.output_root)/args.run_id
        bundle = load_bundle(directory)
        snapshot, config = bundle["snapshot"], bundle["config"]
        rows = bundle["predictions"]
        hin = None if not all(s.get("in_hin") is not None for s in snapshot["sites"]) else {str(s["site_id"]) for s in snapshot["sites"] if s["in_hin"]}
        report = evaluate(rows, snapshot["test_crashes"], hin, config["bootstrap_resamples"], config["seed"])
        if canonical_json(report) != canonical_json(bundle["backtest"]):
            raise ValueError("stored backtest did not reproduce exactly")
        print(json.dumps({"event": "backtest_verified", "run_id": args.run_id, "primary": report["primary"]}, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"event": "backtest_failed", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
