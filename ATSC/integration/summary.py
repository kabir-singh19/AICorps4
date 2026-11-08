"""Print the headline results of one run folder (used by `make demo`)."""
import json
import sys
from pathlib import Path

art = Path(sys.argv[1])
m = json.loads((art / "manifest.json").read_text())
p = json.loads((art / "backtest.json").read_text())["primary"]
print(f"run {m['run_id']}  ranking_hash {m['ranking_hash'][:12]}  refit reproduced {m['independent_refit_reproduced']}")
print(f"primary: {p['target']} capture, {p['scenario']}, {p['length_basis']}, n = {p['n_test_crashes']}")
for k in ("A", "B", "C"):
    v = p["methods"][k]
    print(f"  {k}: {v['capture']:.3f} [{v['ci_low']:.3f}, {v['ci_high']:.3f}] at {v['flagged_share']:.3f} of length")
for k in ("C-A", "B-A"):
    v = p["differences"][k]
    print(f"  {k}: {v['difference']:+.3f} [{v['ci_low']:+.3f}, {v['ci_high']:+.3f}]")
s = art / "memos" / "summary.json"
if s.is_file():
    s = json.loads(s.read_text())
    print("memos:", {k: s.get(k) for k in ("counts", "median_seconds", "median_cost_usd", "total_cost_usd")})
