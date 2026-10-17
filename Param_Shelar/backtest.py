"""Paired crash-level bootstrap and capture reports."""
from __future__ import annotations

import numpy as np

# Resamples drawn per batch: bounds memory at about BATCH x crashes x methods bytes.
BATCH = 100


def bootstrap_capture(crashes, flagged_methods, resamples=1000, seed=42, fsi_only=True):
    """Resample the same crashes for every method and paired difference.

    Each resample draws test crashes with replacement and recounts how many fall on each method's
    flagged sites. Every method sees the same draws, so B-A and C-A are paired comparisons.
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
    if any(None in flagged_methods[m] for m in names):
        raise ValueError("unmatched crashes must never be flagged")
    flagged = {m: {str(s) for s in flagged_methods[m]} for m in names}
    n = len(events)
    if n == 0:
        return {"status": "undefined: no test crashes", "n_test_fsi": 0, "methods": {}, "differences": {},
                "resamples": resamples, "target": "fsi" if fsi_only else "total"}
    # captured[i, j] = 1 if crash i fell on a site flagged by method j (unmatched crashes never do).
    captured = np.array([[site is not None and site in flagged[m] for m in names] for site in events],
                        dtype=np.int32).reshape(n, len(names))
    point = captured.sum(axis=0) / n
    rng = np.random.default_rng(seed)
    draws = np.empty((resamples, len(names)))
    for first in range(0, resamples, BATCH):
        size = min(BATCH, resamples - first)
        picks = rng.integers(0, n, size=(size, n))
        draws[first:first + size] = captured[picks].sum(axis=1) / n
    comparisons = [f"{m}-A" for m in ("B", "C") if m in names and "A" in names]
    column = {m: i for i, m in enumerate(names)}

    def interval(values):
        low, high = np.percentile(values, [2.5, 97.5])
        return float(low), float(high)

    methods = {}
    for m, i in column.items():
        low, high = interval(draws[:, i])
        methods[m] = {"capture": float(point[i]), "ci_low": low, "ci_high": high, "n_test_fsi": n,
                      "captured_crashes": int(captured[:, i].sum())}
    differences = {}
    for c in comparisons:
        low, high = interval(draws[:, column[c[0]]] - draws[:, column["A"]])
        differences[c] = {"difference": methods[c[0]]["capture"] - methods["A"]["capture"],
                          "ci_low": low, "ci_high": high}
    return {"status": "ok", "n_test_fsi": n, "unmatched_crashes": sum(s is None for s in events),
            "methods": methods, "differences": differences, "resamples": resamples,
            "seed": seed, "target": "fsi" if fsi_only else "total", "bootstrap_unit": "individual crash"}


def evaluate(predictions, test_crashes, hin_ids, resamples=1000, seed=42):
    methods = {m: frame for m, frame in predictions.items()}
    ids = list(methods["C"]["site_id"].astype(str))
    lengths = methods["C"]["network_length_mi"].to_numpy()
    if any(list(frame.site_id.astype(str)) != ids for frame in methods.values()):
        raise ValueError("ranking methods must use identical sites in identical order")
    hin_share = None if hin_ids is None else sum(lengths[i] for i, sid in enumerate(ids) if sid in hin_ids)/lengths.sum()
    shares = [0.05, 0.11, 0.20]
    if hin_share is not None and hin_share not in shares:
        shares.append(float(hin_share))
    reports = _score_shares(methods, lengths, ids, shares, test_crashes, hin_ids, resamples, seed, "network_length")
    if (lengths == 0).any():
        # Zero-length sites (intersections under the proposed policy) cost nothing against the
        # flagging budget. Charging them their exposure length shows how much capture that buys.
        charged = np.where(lengths > 0, lengths, methods["C"]["risk_length_mi"].to_numpy())
        reports += _score_shares(methods, charged, ids, [0.11], test_crashes, hin_ids, resamples, seed,
                                 "zero_length_sites_charged_risk_length")
    return {"primary": next(r for r in reports if r["requested_share"] == .11 and r["target"] == "fsi"),
            "sensitivity": reports, "hin_share": hin_share,
            "fairness_note": "A stays the published HIN at all thresholds; B/C use closest whole-site prefixes."}


def _score_shares(methods, lengths, ids, shares, test_crashes, hin_ids, resamples, seed, basis):
    try:
        from .ranking import flag_by_length
    except ImportError:
        from ranking import flag_by_length
    total_length = float(lengths.sum())
    hin_share = None if hin_ids is None else sum(lengths[i] for i, sid in enumerate(ids) if sid in hin_ids)/total_length
    reports = []
    for share in shares:
        flagged, length_details = {}, {}
        for m, frame in methods.items():
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
            report["length_basis"] = basis
            report["length_details"] = length_details
            report["hin_available"] = hin_ids is not None
            if hin_ids is None:
                report["method_A_status"] = "unavailable: published HIN membership required"
            for m, detail in length_details.items():
                if m in report["methods"]:
                    report["methods"][m].update(detail)
            reports.append(report)
    return reports


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
