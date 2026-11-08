"""Charts and a summary for a stored S2 run, read from its verified bundle.

Reads only outputs/<run-id>/ (checksums verified) and writes to a separate directory, so the run
itself is never changed. Lives outside the S2 code fingerprint (artifacts.source_version hashes
top-level *.py and tests/), so adding it does not block replay of existing runs.

    python reports/m2_report.py --run-id m2-corridor-001 --output docs/m2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from artifacts import load_bundle, validate_run_id  # noqa: E402
from backtest import bootstrap_capture  # noqa: E402
from ranking import flag_by_length  # noqa: E402

# Reference palette (dataviz skill), light mode: categorical slots 1-2 and text inks.
COLORS = {"B": "#2a78d6", "C": "#eb6834"}
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SHARES = (0.05, 0.11, 0.20)
LABEL = {"B": "B: NB SPF + EB", "C": "C: boosting + EB"}


def style(plt):
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
                         "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": .8,
                         "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
                         "axes.titlesize": 11, "axes.titleweight": "bold", "savefig.dpi": 150})


def flagged_sets(predictions, share):
    lengths = predictions["C"]["network_length_mi"].to_numpy()
    out = {}
    for method, frame in predictions.items():
        mask = flag_by_length(frame["rank"], lengths, share=share,
                              tolerance=0.005 if share == .11 else None, allow_zero_lengths=True)
        out[method] = set(frame.loc[mask, "site_id"].astype(str))
    return out


def paired_b_minus_c(predictions, crashes, resamples, seed):
    """B-C on the same crash resamples, reusing the tested paired bootstrap.

    bootstrap_capture reports differences against a method named "A", so C is passed under that
    name; nothing here is HIN data.
    """
    result = {}
    for share in SHARES:
        flags = flagged_sets(predictions, share)
        report = bootstrap_capture(crashes, {"A": flags["C"], "B": flags["B"]}, resamples, seed)
        diff = report["differences"]["B-A"]
        result[str(share)] = {**diff, "sites_only_in_B": len(flags["B"] - flags["C"]),
                              "sites_only_in_C": len(flags["C"] - flags["B"])}
    return result


def observed_test_counts(snapshot):
    test = pd.DataFrame(snapshot["test_crashes"])
    test = test[test.in_analysis_area & test.site_id.notna()]
    total = test.groupby("site_id").size()
    fsi = test[test.severity.isin(["K", "A"])].groupby("site_id").size()
    return total, fsi


def prediction_check(predictions, snapshot, years=3):
    """Expected 2023-2025 counts (annual rate x 3) against what was observed, by predicted quintile."""
    total, fsi = observed_test_counts(snapshot)
    rows = {}
    for method, frame in predictions.items():
        f = frame.assign(site_id=frame.site_id.astype(str))
        f["obs_total"] = f.site_id.map(total).fillna(0)
        f["obs_fsi"] = f.site_id.map(fsi).fillna(0)
        f["exp_total"], f["exp_fsi"] = f.annual_total*years, f.annual_fsi*years
        f["bin"] = pd.qcut(f.exp_total.rank(method="first"), 5, labels=False)
        bins = f.groupby("bin").agg(sites=("site_id", "size"), exp_total=("exp_total", "sum"),
                                    obs_total=("obs_total", "sum"), exp_fsi=("exp_fsi", "sum"),
                                    obs_fsi=("obs_fsi", "sum")).reset_index()
        rows[method] = {"bins": bins.to_dict("records"),
                        "sum_expected_total": float(f.exp_total.sum()), "sum_observed_total": float(f.obs_total.sum()),
                        "sum_expected_fsi": float(f.exp_fsi.sum()), "sum_observed_fsi": float(f.obs_fsi.sum()),
                        "spearman_expected_vs_observed_total": float(f.exp_total.corr(f.obs_total, method="spearman"))}
    return rows


def top_sites(predictions, explanations, snapshot, n=10):
    total, fsi = observed_test_counts(snapshot)
    history = pd.DataFrame(snapshot["history"]).groupby("site_id")[["crashes", "fsi_crashes"]].sum()
    shap = pd.DataFrame(explanations)
    b_rank = predictions["B"].set_index(predictions["B"].site_id.astype(str))["rank"]
    out = []
    for _, row in predictions["C"].sort_values("rank").head(n).iterrows():
        sid = str(row.site_id)
        factors = shap[shap.site_id == sid].sort_values("rank").head(3)
        out.append({"rank_C": int(row["rank"]), "rank_B": int(b_rank[sid]), "site_id": sid,
                    "site_type": row.site_type, "road_name": row.road_name,
                    "fsi_rate": float(row.fsi_rate), "flagged": bool(row.flagged),
                    "history_crashes": int(history.crashes.get(sid, 0)),
                    "history_fsi": int(history.fsi_crashes.get(sid, 0)),
                    "test_fsi": int(fsi.get(sid, 0)), "test_crashes": int(total.get(sid, 0)),
                    "factors": [{"feature": f.feature, "value": f.value, "shap": float(f.shap_value),
                                 "description": f.description} for f in factors.itertuples()]})
    return out


def chart_capture(plt, backtest, paired, path):
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw={"width_ratios": [3, 2]})
    reports = {r["requested_share"]: r for r in backtest["sensitivity"]
               if r["target"] == "fsi" and r["length_basis"] == "network_length"}
    n = reports[.11]["n_test_fsi"]
    x = np.arange(len(SHARES))
    for i, method in enumerate(("B", "C")):
        stats = [reports[s]["methods"][method] for s in SHARES]
        pos = x + (i - .5)*.32
        cap = [s["capture"]*100 for s in stats]
        err = [[c - s["ci_low"]*100 for c, s in zip(cap, stats)], [s["ci_high"]*100 - c for c, s in zip(cap, stats)]]
        ax.bar(pos, cap, width=.3, color=COLORS[method], label=LABEL[method], zorder=2)
        ax.errorbar(pos, cap, yerr=err, fmt="none", ecolor=INK_2, elinewidth=1.2, capsize=3, zorder=3)
        for p, c, s in zip(pos, cap, stats):
            ax.text(p, 2, f"{s['captured_crashes']}", ha="center", va="bottom", color="white", fontsize=9, zorder=4)
    ax.set_xticks(x, [f"{int(s*100)}% of\nnetwork miles" for s in SHARES])
    ax.set_ylabel("2023-2025 F&SI crashes captured (%)")
    ax.set_ylim(0, 100)
    ax.set_title(f"F&SI capture, held-out 2023-2025 (n = {n} in-area F&SI)")
    ax.legend(frameon=False, loc="upper left")
    ax.text(0, -.2, "Bars: point estimate (count inside bar). Whiskers: 95% interval, 1,000 crash-level resamples.\n"
            "Method A (MPO High-Injury Network) unavailable: no HIN layer loaded yet.",
            transform=ax.transAxes, fontsize=8, color=INK_2, va="top")
    diffs = [paired[str(s)] for s in SHARES]
    d = [v["difference"]*100 for v in diffs]
    lo = [v["difference"]*100 - v["ci_low"]*100 for v in diffs]
    hi = [v["ci_high"]*100 - v["difference"]*100 for v in diffs]
    ax2.axhline(0, color=INK_2, linewidth=1)
    ax2.errorbar(x, d, yerr=[lo, hi], fmt="o", color=INK, ecolor=INK_2, markersize=7, capsize=4, zorder=3)
    ax2.set_xticks(x, [f"{int(s*100)}%" for s in SHARES])
    ax2.set_ylabel("B minus C capture (percentage points)")
    ax2.set_title("Paired difference B - C")
    lim = max(10, max(abs(v["ci_low"]) for v in diffs)*100 + 2, max(abs(v["ci_high"]) for v in diffs)*100 + 2)
    ax2.set_ylim(-lim, lim)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_prediction_check(plt, check, path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, (exp, obs, title) in zip(axes, (("exp_total", "obs_total", "All crashes"), ("exp_fsi", "obs_fsi", "F&SI crashes"))):
        top = 0
        for method, marker in (("B", "o"), ("C", "s")):
            bins = pd.DataFrame(check[method]["bins"])
            ax.plot(bins[exp], bins[obs], marker=marker, color=COLORS[method], linewidth=2, markersize=8, label=LABEL[method])
            top = max(top, bins[exp].max(), bins[obs].max())
            if obs == "obs_fsi":
                # Poisson 95% band on the observed count in each bin (normal approximation).
                ax.errorbar(bins[exp], bins[obs], yerr=1.96*np.sqrt(np.maximum(bins[obs], 1)), fmt="none",
                            ecolor=COLORS[method], alpha=.5, capsize=2)
        ax.plot([0, top*1.1], [0, top*1.1], color=INK_2, linestyle="--", linewidth=1, label="predicted = observed")
        ax.set_xlabel("Predicted 2023-2025 count (sum over sites in quintile)")
        ax.set_ylabel("Observed 2023-2025 count")
        ax.set_title(f"{title}: predicted vs observed")
        ax.legend(frameon=False, fontsize=8)
    fig.text(0, -.04, "Each point is one quintile of sites ranked by prediction. Prediction = fitted 2016-2022 annual rate x 3 years.\n"
             "Only crashes matched to a site are counted. F&SI whiskers: Poisson 95% band on the observed count.", fontsize=8, color=INK_2)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_top_sites(plt, top, path):
    fig, ax = plt.subplots(figsize=(10, 4.8))
    labels = [f"#{t['rank_C']}  {t['road_name']} (site {t['site_id']}{', intersection' if t['site_type'] == 'intersection' else ''})"
              for t in top][::-1]
    rates = [t["fsi_rate"] for t in top][::-1]
    y = np.arange(len(top))
    ax.barh(y, rates, color=COLORS["C"], height=.6, zorder=2)
    ax.set_yticks(y, labels, fontsize=8.5)
    for yi, t in zip(y, top[::-1]):
        f = t["factors"][0]
        ax.text(t["fsi_rate"] + .08, yi, f"hist F&SI {t['history_fsi']}, test F&SI {t['test_fsi']} | top SHAP: "
                f"{f['feature']} ({f['shap']:+.2f})", va="center", fontsize=8, color=INK_2)
    ax.set_xlim(0, max(rates)*1.9)
    ax.set_xlabel("Expected F&SI crashes per mile per year (method C)")
    ax.set_title("Top 10 sites, method C")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_severity(plt, calibration, path):
    fig, ax = plt.subplots(figsize=(5, 4))
    bins = calibration.get("bins", [])
    for b in bins:
        k = b["known_crashes"]
        p = b["observed_fsi_fraction"]
        half = 1.96*np.sqrt(max(p*(1-p), 1e-9)/k) if k else 0
        ax.errorbar(b["mean_prediction"], p, yerr=half, fmt="o", color=INK, ecolor=INK_2, capsize=3,
                    markersize=max(5, min(14, 3 + np.log1p(k)*1.5)))
        ax.annotate(f"{k} crash" + ("" if k == 1 else "es"), (b["mean_prediction"], p), textcoords="offset points", xytext=(6, 6), fontsize=8, color=INK_2)
    lim = max([.15] + [b["mean_prediction"]*1.2 for b in bins] + [b["observed_fsi_fraction"]*1.2 for b in bins])
    ax.plot([0, lim], [0, lim], color=INK_2, linestyle="--", linewidth=1)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("Predicted P(F&SI | known severity)")
    ax.set_ylabel("Observed F&SI fraction")
    ax.set_title("Severity calibration (held-out 2016-2022 sites)")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", default=str(ROOT/"outputs"))
    parser.add_argument("--output", required=True, help="directory for charts and summary; a run-id subfolder is created")
    args = parser.parse_args(argv)
    validate_run_id(args.run_id)
    bundle = load_bundle(Path(args.output_root)/args.run_id)
    out = Path(args.output)/args.run_id
    out.mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    style(plt)
    preds, snap, config = bundle["predictions"], bundle["snapshot"], bundle["config"]
    paired = paired_b_minus_c(preds, snap["test_crashes"], config["bootstrap_resamples"], config["seed"])
    check = prediction_check(preds, snap)
    top = top_sites(preds, bundle["explanations"], snap)
    chart_capture(plt, bundle["backtest"], paired, out/"capture.png")
    chart_prediction_check(plt, check, out/"predicted_vs_observed.png")
    chart_top_sites(plt, top, out/"top_sites.png")
    chart_severity(plt, bundle["calibration"], out/"severity_calibration.png")
    capture = {str(r["requested_share"]) + ("" if r["length_basis"] == "network_length" else "_charged"):
               {m: {k: v[k] for k in ("capture", "ci_low", "ci_high", "captured_crashes", "flagged_miles", "flagged_share")}
                for m, v in r["methods"].items()}
               for r in bundle["backtest"]["sensitivity"] if r["target"] == "fsi"}
    m = bundle["manifest"]
    summary = {"run_id": args.run_id, "created": m["created"], "code_version": m["code_version"],
               "analysis_scope": m["analysis_scope"],
               "scope_note": "corridor diagnostic; not the FSR 3.2.1.1 network, not the City backtest",
               "method_A": bundle["backtest"]["primary"].get("method_A_status"),
               "n_test_fsi": bundle["backtest"]["primary"]["n_test_fsi"],
               "unmatched_test_fsi": bundle["backtest"]["primary"]["unmatched_crashes"],
               "fsi_capture": capture, "paired_B_minus_C": paired, "prediction_check": check,
               "severity_calibration": {k: v for k, v in bundle["calibration"].items() if k != "validation_site_ids"},
               "top_sites_C": top}
    (out/"summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False, default=str) + "\n")
    print(out)


if __name__ == "__main__":
    main()
