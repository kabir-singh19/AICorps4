"""S2 built-in checks, structured test records and pre-run tests."""
from __future__ import annotations

import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def preflight(log_dir=None):
    root = Path(__file__).resolve().parent
    completed = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(root/"tests/core"), "-v"],
                               cwd=root, capture_output=True, text=True, timeout=120)
    record = {"test": "S2 pre-run core suite", "timestamp": datetime.now(timezone.utc).isoformat(),
              "result": "pass" if completed.returncode == 0 else "fail",
              "details": completed.stdout + completed.stderr}
    if log_dir is not None:
        import json
        from uuid import uuid4
        directory = Path(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory/f"{uuid4().hex}.json").write_text(json.dumps(record, indent=2) + "\n")
    if completed.returncode:
        raise RuntimeError("S2 built-in test failed: " + record["details"])
    return record


def check_predictions(rows, expected_ids, target_share=.11, tolerance=.005):
    ids, ranks = [], []
    flagged_miles, network_miles = 0.0, 0.0
    for row in rows:
        ids.append(str(row["site_id"]))
        ranks.append(row["rank"])
        for key in ("mu", "k", "n_eb", "p_fsi", "fsi_rate", "annual_total", "annual_fsi", "risk_length_mi", "network_length_mi"):
            value = row[key]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"BIT: invalid {key}")
        if not 0 < row["eb_weight"] < 1 or not 0 <= row["p_fsi"] <= 1:
            raise ValueError("BIT: invalid EB weight or severity probability")
        if row["mu"] <= 0 or row["k"] <= 0 or row["risk_length_mi"] <= 0:
            raise ValueError("BIT: positive model counts, k and risk exposure required")
        if not isinstance(row["flagged"], bool):
            raise ValueError("BIT: flagged must be boolean")
        network_miles += row["network_length_mi"]
        flagged_miles += row["network_length_mi"] if row["flagged"] else 0
        if row["annual_fsi"] > row["annual_total"] + 1e-10:
            raise ValueError("BIT: F&SI annual estimate exceeds all crashes")
        if not math.isclose(row["fsi_rate"]*row["risk_length_mi"], row["annual_fsi"], rel_tol=1e-9, abs_tol=1e-10):
            raise ValueError("BIT: rate/count units disagree")
    if len(ids) != len(set(ids)) or set(ids) != {str(v) for v in expected_ids}:
        raise ValueError("BIT: missing, duplicate or extra predictions")
    if sorted(ranks) != list(range(1, len(rows)+1)):
        raise ValueError("BIT: invalid ranks")
    flagged_ranks = sorted(row["rank"] for row in rows if row["flagged"])
    if flagged_ranks != list(range(1, len(flagged_ranks)+1)):
        raise ValueError("BIT: flags are not the highest-ranked prefix")
    if network_miles <= 0 or abs(flagged_miles/network_miles-target_share) > tolerance + 1e-12:
        raise ValueError("BIT: flagged network outside required length budget")
    return {"test": "prediction coverage, ranges, units, rank prefix and length", "result": "pass",
            "details": {"sites": len(rows), "flagged_miles": flagged_miles, "network_miles": network_miles}}


def check_explanations(explanations, flagged_ids):
    grouped = {}
    for row in explanations:
        if not math.isfinite(row["shap_value"]):
            raise ValueError("BIT: invalid SHAP value")
        grouped.setdefault(str(row["site_id"]), []).append(row)
    if set(grouped) != {str(v) for v in flagged_ids}:
        raise ValueError("BIT: missing/extra flagged-site explanations")
    for factors in grouped.values():
        if len(factors) != 5 or len({f["feature"] for f in factors}) != 5 or sorted(f["rank"] for f in factors) != [1,2,3,4,5]:
            raise ValueError("BIT: exactly five unique ranked source features required")
    return {"test": "top-five explanation coverage", "result": "pass", "details": {"flagged_sites": len(grouped)}}


def main():
    import json
    try:
        print(json.dumps(preflight(log_dir="outputs/bit_log")))
        return 0
    except Exception as exc:
        print(json.dumps({"test": "S2 core suite", "result": "fail", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
