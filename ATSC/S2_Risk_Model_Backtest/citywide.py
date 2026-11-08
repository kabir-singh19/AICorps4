"""Citywide S2 run on S1 network v1_2022 (College Station): frozen 2022 backtest of methods
A (published HIN), B (NB SPF + EB) and C (ML-EB), then the 2026 forecast and its export.

    cd ATSC && DATABASE_URL=... python -m S2_Risk_Model_Backtest.citywide \
        --config S2_Risk_Model_Backtest/config/citywide_v1_2022.json --run-id <id> \
        --out-root integration/artifacts

Writes integration/artifacts/<run_id>/: ranking.csv, sites.geojson, backtest.json,
explanations.json, calibration.json, bit.json, model_card.md, figures, models/ (LightGBM text
and JSON parameters, not committed) and manifest.json with SHA-256 of every file.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from .artifacts import canonical_json, file_hash, json_hash, validate_run_id, write_json
    from .backtest import bootstrap_capture
    from .bit import check_explanations, check_predictions
    from .database import load_context, load_snapshot
    from .leakage import validate_snapshot
    from .train import normalize_snapshot
except ImportError:
    from artifacts import canonical_json, file_hash, json_hash, validate_run_id, write_json
    from backtest import bootstrap_capture
    from bit import check_explanations, check_predictions
    from database import load_context, load_snapshot
    from leakage import validate_snapshot
    from train import normalize_snapshot

TARGETS = {"KA": ("K", "A"), "KABC": ("K", "A", "B", "C")}
METHOD_NAMES = {"A": "HIN (published MPO CSAP high-injury network)", "B": "SPF+EB", "C": "ML-EB"}
EXTRA_MODELS = ("Stack", "LightGBM", "LGB-Tot", "Naive")
REQUIRED = ("seed", "primary_c", "method_b", "history_start", "history_end", "first_label_year", "test_years",
            "forecast_year", "hist_years_long", "neighbor_m", "sev_prior_m", "bootstrap_resamples", "shares",
            "flag_share", "flag_tolerance", "lgb_params", "lgb_seeds", "lgb_early_stop", "lgb_max_rounds",
            "threads", "features", "database", "verify_refit")


def load_config(path):
    cfg = json.loads(Path(path).read_text())
    missing = [k for k in REQUIRED if k not in cfg]
    if missing:
        raise ValueError(f"config missing {missing}")
    if cfg["primary_c"] != "ML-EB" or cfg["method_b"] != "SPF+EB":
        raise ValueError("methods are fixed in advance: B = SPF+EB, C = ML-EB (EVP 4.2)")
    if cfg["bootstrap_resamples"] < 1000:
        raise ValueError("at least 1000 bootstrap resamples")
    return cfg


def git_commit(root):
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=root, capture_output=True,
                                    text=True, check=True).stdout.strip())
        return {"commit": sha, "dirty_worktree": dirty}
    except Exception as exc:
        return {"commit": None, "error": str(exc)}


# ---------- leakage gate ----------
def seeded_leakage_checks(snapshot, features):
    """Inject post-cutoff records into copies of the real snapshot; each must be refused."""
    import copy
    cases = []

    def attempt(name, mutate, feats=features):
        bad = copy.deepcopy(snapshot)
        mutate(bad)
        try:
            validate_snapshot(bad, feats, 2016, 2022)
            cases.append({"case": name, "detected": False})
        except ValueError as exc:
            cases.append({"case": name, "detected": True, "error": str(exc)})

    def late_feature(s):
        s["features"][0]["as_of_date"] = "2023-06-30"

    def late_history(s):
        s["history"].append({"site_id": s["sites"][0]["site_id"], "year": 2023, "crashes": 1,
                             "known_crashes": 1, "fsi_crashes": 0})

    def late_source(s):
        for src in s["metadata"]["sources"]:
            if src["role"] == "predictor":
                src["available_as_of"] = "2024-01-15"
                break

    def late_site(s):
        s["sites"][0]["as_of_date"] = "2023-01-01"
    attempt("feature dated 2023-06-30", late_feature)
    attempt("history row for 2023", late_history)
    attempt("predictor source available 2024-01-15", late_source)
    attempt("site built 2023-01-01", late_site)
    attempt("HIN membership offered as a feature", lambda s: None, feats=[*features, "in_hin"])
    return cases


# ---------- scoring ----------
def score_rank(ids_int, rate):
    try:
        from .ranking import rank_sites
    except ImportError:
        from ranking import rank_sites
    return rank_sites(ids_int, rate)


def evaluate(sites, preds, test_crashes, cfg):
    """Capture of KA and KABC test crashes for A, B, C (and the comparison models)."""
    import numpy as np
    try:
        from .ranking import flag_by_length
    except ImportError:
        from ranking import flag_by_length
    ids = sites["site_id"].astype(str).to_numpy()
    ids_int = sites["site_id"].astype(int).to_numpy()
    seg = (sites["site_type"] == "segment").to_numpy()
    hin = sites["in_hin"].astype(bool).to_numpy()
    basis = {"icd_250ft": sites["risk_length_mi"].to_numpy(float),
             "s1_zero_length": sites["network_length_mi"].to_numpy(float)}
    names = {"B": cfg["method_b"], "C": cfg["primary_c"], **{m: m for m in EXTRA_MODELS}}
    pairs = [(m, "A") for m in EXTRA_MODELS] + [("C", "B")]
    R, seed = cfg["bootstrap_resamples"], cfg["seed"]
    out = {"bootstrap": {"resamples": R, "seed": seed, "unit": "individual test crash (paired across methods)"},
           "method_names": {**METHOD_NAMES, **{m: m for m in EXTRA_MODELS}}, "targets": {}}
    for tname, sev in TARGETS.items():
        key = "ka" if tname == "KA" else "kabc"
        ranks = {name: score_rank(ids_int, preds[model][key] / basis["icd_250ft"]) for name, model in names.items()}
        scenarios = []

        def run(label, basis_name, flagged_masks, requested):
            L = basis[basis_name]
            flagged = {"A": set(ids[hin])}
            details = {"A": {"flagged_miles": float(L[hin].sum()), "flagged_share": float(L[hin].sum() / L.sum()),
                             "flagged_sites": int(hin.sum())}}
            for name, mask in flagged_masks.items():
                flagged[name] = set(ids[mask])
                details[name] = {"flagged_miles": float(L[mask].sum()), "flagged_share": float(L[mask].sum() / L.sum()),
                                 "flagged_sites": int(mask.sum()), "flagged_segments": int((mask & seg).sum()),
                                 "flagged_intersections": int((mask & ~seg).sum())}
            rep = bootstrap_capture(test_crashes, flagged, R, seed, severities=sev, pairs=pairs)
            for name, d in details.items():
                rep["methods"][name].update(d)
            rep.update({"scenario": label, "length_basis": basis_name, "requested_share": requested})
            scenarios.append(rep)

        for basis_name in ("icd_250ft", "s1_zero_length"):
            L = basis[basis_name]
            hin_share = float(L[hin].sum() / L.sum())
            shares = [*cfg["shares"], hin_share] if basis_name == "icd_250ft" else [cfg["flag_share"], hin_share]
            for share in shares:
                tol = cfg["flag_tolerance"] if share == cfg["flag_share"] else None
                masks = {n: flag_by_length(r, L, share=share, tolerance=tol, allow_zero_lengths=True)
                         for n, r in ranks.items()}
                label = "hin_share" if share == hin_share else f"{round(share * 100)}pct"
                run(label, basis_name, masks, share)
        # Nov 4 comparison: the same segment-miles and the same number of intersections as the HIN.
        seg_len = basis["icd_250ft"][seg]
        seg_share = float(seg_len[hin[seg]].sum() / seg_len.sum())
        n_int = int((hin & ~seg).sum())
        masks = {}
        for n, r in ranks.items():
            m = np.zeros(len(ids), bool)
            seg_rank = score_rank(ids_int[seg], (preds[names[n]][key] / basis["icd_250ft"])[seg])
            m[np.flatnonzero(seg)] = flag_by_length(seg_rank, seg_len, share=seg_share, tolerance=None)
            int_idx = np.flatnonzero(~seg)
            int_rank = score_rank(ids_int[~seg], preds[names[n]][key][~seg])
            m[int_idx[int_rank <= n_int]] = True
            masks[n] = m
        run("hin_matched_counts", "icd_250ft", masks, None)
        out["targets"][tname] = scenarios
    primary = next(s for s in out["targets"]["KA"] if s["scenario"] == "11pct" and s["length_basis"] == "icd_250ft")
    for m in ("B", "C"):
        share = primary["methods"][m]["flagged_share"]
        if abs(share - cfg["flag_share"]) > cfg["flag_tolerance"]:
            raise RuntimeError(f"flagged share {share:.4f} outside 11% +/- 0.5% for method {m}")
    out["primary"] = {"target": "KA", "scenario": "11pct", "length_basis": "icd_250ft",
                      "methods": primary["methods"], "differences": primary["differences"],
                      "n_test_crashes": primary["n_test_fsi"]}
    return out


def calibration(sites, preds, test_crashes, years, cfg):
    import numpy as np
    import pandas as pd
    try:
        from .severity import calibration_report
    except ImportError:
        from severity import calibration_report
    t = pd.DataFrame([c for c in test_crashes if c.get("site_id") is not None and c["in_analysis_area"]])
    t["ka"] = t.severity.isin(["K", "A"]).astype(int)
    t["kabc"] = t.severity.isin(["K", "A", "B", "C"]).astype(int)
    t["known"] = (t.severity != "U").astype(int)
    obs = t.groupby(t.site_id.astype(str))[["ka", "kabc", "known"]].sum().reindex(sites.site_id.astype(str), fill_value=0)
    out = {"window": f"{years[0]}-{years[-1]}", "matched_test_crashes_only": True, "models": {}}
    for model in ("SPF+EB", "ML-EB", "Stack"):
        p = preds[model]
        rec = {}
        for key in ("ka", "kabc"):
            pred3 = p[key] * len(years)
            o = obs[key].to_numpy(float)
            q = pd.qcut(pd.Series(pred3).rank(method="first"), 10, labels=False)
            bins = [{"decile": int(d) + 1, "predicted": float(pred3[q == d].sum()), "observed": float(o[q == d].sum()),
                     "sites": int((q == d).sum())} for d in range(10)]
            rec[key] = {"predicted_total": float(pred3.sum()), "observed_total": float(o.sum()),
                        "ratio_predicted_to_observed": float(pred3.sum() / o.sum()) if o.sum() else None,
                        "deciles": bins}
        out["models"][model] = rec
    sev = calibration_report(preds["ML-EB"]["p_fsi"], obs["ka"].to_numpy(), obs["known"].to_numpy())
    sev["quantity"] = "P(K or A | known-severity crash) from ML-EB severity shares vs 2023-2025 observed"
    out["severity"] = sev
    return out


def explanations_for(F, enc, fut, flagged_ids, aadt):
    import numpy as np
    try:
        from .citywide_models import lgb_contrib
        from .explain_text import describe
    except ImportError:
        from citywide_models import lgb_contrib
        from explain_text import describe
    contrib, names = lgb_contrib(F["me"], enc, fut)
    rows = []
    flagged = set(flagged_ids)
    for i, sid in enumerate(fut["site_id"].astype(str)):
        if sid not in flagged:
            continue
        order = np.argsort(-np.abs(contrib[i]))[:5]
        for r, j in enumerate(order, 1):
            name = names[j]
            value = None if name == "traffic" else fut.iloc[i][name]
            value = None if value is not None and not isinstance(value, str) and np.isnan(float(value)) else value
            if hasattr(value, "item"):
                value = value.item()
            rows.append({"site_id": sid, "rank": r, "feature": name, "value": value,
                         "shap_value": float(contrib[i, j]), "direction": "raises risk" if contrib[i, j] > 0 else "lowers risk",
                         "text": describe(name, value, float(aadt[i]))})
    return rows


# ---------- one fit + predict pass ----------
def fit_predict(panel, train_years, predict_year, cfg, log, seeds=None):
    import numpy as np
    try:
        from .citywide_models import Encoder, fit_all, fit_stack_weights, predict_all
    except ImportError:
        from citywide_models import Encoder, fit_all, fit_stack_weights, predict_all
    enc = Encoder().fit(panel)
    fits, outs, rows = {}, {}, {}
    for kind in ("segment", "intersection"):
        p = panel[panel.site_type == kind]
        train = p[p.year.isin(train_years) & p.labeled]
        fut = p[p.year == predict_year].reset_index(drop=True)
        if not (fut["hist_max_date"].dropna() < np.datetime64(f"{predict_year}-01-01")).all():
            raise ValueError("leakage: prediction-year history reaches the prediction year")
        t0 = time.monotonic()
        F = fit_all(train, kind, cfg, enc, seeds=seeds)
        w = fit_stack_weights(train, kind, cfg, enc)
        outs[kind] = predict_all(F, fut, cfg, enc, w)
        fits[kind] = (F, w)
        rows[kind] = fut
        log("fitted", kind=kind, train_rows=len(train), train_years=[int(y) for y in sorted(train.year.unique())],
            spf=F["spf"]["method"], spf_k=F["spf"]["alpha"], mleb_k=F["me"]["k"], rounds_mleb=F["me"]["n_rounds"],
            stack_weights=[round(float(x), 3) for x in w], seconds=round(time.monotonic() - t0, 1))
    return enc, fits, outs, rows


def combine(sites, outs, rows):
    """Align per-kind predictions to the site order of `sites`."""
    import numpy as np
    import pandas as pd
    order = pd.concat([rows["segment"]["site_id"], rows["intersection"]["site_id"]], ignore_index=True).astype(str)
    pos = pd.Series(np.arange(len(order)), index=order.to_numpy()).reindex(sites.site_id.astype(str)).to_numpy()
    if np.isnan(pos).any():
        raise ValueError("predictions missing sites")
    pos = pos.astype(int)
    merged = {}
    for model in outs["segment"]:
        merged[model] = {}
        for key, val in outs["segment"][model].items():
            if isinstance(val, np.ndarray):
                merged[model][key] = np.concatenate([val, outs["intersection"][model][key]])[pos]
            elif key == "k":
                merged[model][key] = np.concatenate([np.full(len(rows["segment"]), val),
                                                     np.full(len(rows["intersection"]), outs["intersection"][model][key])])[pos]
            else:
                merged[model][key] = val
    fut = pd.concat([rows["segment"], rows["intersection"]], ignore_index=True).iloc[pos].reset_index(drop=True)
    return merged, fut


def prediction_frame(sites, p, cfg, share=None):
    """ICD Table 12 prediction fields for one method, with the 11% flag on ICD lengths."""
    import numpy as np
    try:
        from .ranking import flag_by_length
    except ImportError:
        from ranking import flag_by_length
    f = sites[["site_id", "site_type", "risk_length_mi"]].copy()
    f["site_id"] = f["site_id"].astype(str)
    f["network_length_mi"] = f["risk_length_mi"]
    f["mu"], f["k"], f["eb_weight"], f["n_eb"], f["p_fsi"] = p["mu"], p["k"], p["eb_weight"], p["n_eb"], p["p_fsi"]
    f["annual_total"] = p["n_eb"]
    f["annual_fsi"] = p["n_eb"] * p["p_fsi"]
    f["fsi_rate"] = f["annual_fsi"] / f["risk_length_mi"]
    f["rank"] = score_rank(sites["site_id"].astype(int).to_numpy(), f["fsi_rate"].to_numpy())
    f["flagged"] = flag_by_length(f["rank"].to_numpy(), f["risk_length_mi"].to_numpy(), share=share or cfg["flag_share"],
                                  tolerance=cfg["flag_tolerance"], allow_zero_lengths=True)
    f["flagged"] = f["flagged"].astype(bool)
    if not np.allclose(f["annual_fsi"], p["ka"]):
        raise RuntimeError("annual F&SI must equal the model's KA prediction")
    return f


def ranking_table(sites, fut, preds, frame_c, frame_b, expl, cfg):
    import numpy as np
    import pandas as pd
    t = pd.DataFrame({
        "site_id": frame_c.site_id, "site_type": sites.site_type.to_numpy(), "road_name": sites.road_name.fillna("").to_numpy(),
        "length_mi": sites.risk_length_mi.round(4).to_numpy(), "fsi_rate": frame_c.fsi_rate.round(6).to_numpy(),
        "rank": frame_c["rank"].to_numpy(), "flagged": frame_c.flagged.to_numpy(), "in_hin": sites.in_hin.astype(bool).to_numpy(),
        "memo_status": "none",
        "jurisdiction": fut.jurisdiction.to_numpy(), "route_name": fut.route_name.fillna("").to_numpy(),
        "annual_fsi": frame_c.annual_fsi.round(6).to_numpy(), "annual_kabc": np.round(preds["ML-EB"]["kabc"], 6),
        "mu": frame_c.mu.round(6).to_numpy(), "k": frame_c.k.round(6).to_numpy(), "eb_weight": frame_c.eb_weight.round(6).to_numpy(),
        "n_eb": frame_c.n_eb.round(6).to_numpy(), "p_fsi": frame_c.p_fsi.round(6).to_numpy(),
        "network_length_mi": sites.network_length_mi.round(4).to_numpy(),
        "fsi_rate_spf_eb": frame_b.fsi_rate.round(6).to_numpy(), "rank_spf_eb": frame_b["rank"].to_numpy(),
        "flagged_spf_eb": frame_b.flagged.to_numpy(),
        "annual_fsi_stack": np.round(preds["Stack"]["ka"], 6),
        "ka_3y": fut.ka_3y.to_numpy(), "kabc_3y": fut.kabc_3y.to_numpy(), "tot_3y": fut.tot_3y.to_numpy(),
        **{f"{f}_3y": fut[f"{f}_3y"].to_numpy() for f in ("angle", "rear_end", "single_vehicle", "opposite_direction", "night", "wet")},
        "aadt": np.where(sites.site_type == "segment", fut.aadt, fut.aadt_major + fut.aadt_minor).round(0),
        "aadt_imputed": fut.aadt_imputed.to_numpy(), "speed_limit": fut.speed_limit.to_numpy(),
        "num_lanes": fut.num_lanes.to_numpy(), "func_class": fut.func_class.to_numpy(), "legs": fut.legs.to_numpy(),
        "signalized": fut.signalized.astype(bool).to_numpy(), "median_type": fut.median_type.to_numpy(),
        "lon": fut.lon.round(6).to_numpy(), "lat": fut.lat.round(6).to_numpy(),
    })
    t["city_actionable"] = t.jurisdiction.isin(["City", "City/TxDOT"])
    t["rank_city_actionable"] = pd.array([pd.NA] * len(t), dtype="Int64")
    ca = t[t.city_actionable].sort_values("rank")
    t.loc[ca.index, "rank_city_actionable"] = np.arange(1, len(ca) + 1)
    why = {}
    for r in expl:
        why.setdefault(r["site_id"], []).append(f"{r['direction']}: {r['text']}")
    t["why"] = t.site_id.map(lambda s: "; ".join(why.get(s, [])))
    return t.sort_values("rank").reset_index(drop=True)


def site_history(context):
    """Matched crashes per site and year (2016 to the forecast cutoff), by severity and type, for S4."""
    import pandas as pd
    c = pd.DataFrame(context["crashes"])
    fields = ["total", "K", "A", "B", "C", "O", "U", "angle", "rear_end", "single_vehicle", "opposite_direction",
              "sideswipe", "night", "wet"]
    for sev in "KABCOU":
        c[sev] = (c.severity == sev).astype(int)
    c["total"] = 1
    for f in fields[7:]:
        c[f] = c[f].astype(bool).astype(int)
    g = c.groupby(["site_id", "crash_year"])[fields].sum()
    sites = {}
    for (sid, year), row in g.iterrows():
        sites.setdefault(str(sid), {})[str(int(year))] = [int(v) for v in row.to_numpy()]
    return {"fields": fields, "years": [int(c.crash_year.min()), int(c.crash_year.max())],
            "last_crash_date": context["last_crash_date"], "matched_crashes_only": True, "sites": sites}


def ranking_hash(table):
    cols = ["site_id", "rank", "fsi_rate", "flagged"]
    return json_hash(table[cols].astype({"flagged": bool}).to_dict("records"))


def write_geojson(path, table, context):
    geo = {str(c["site_id"]): c["geojson"] for c in context["context"]}
    props = ["site_id", "site_type", "road_name", "length_mi", "fsi_rate", "rank", "flagged", "in_hin", "memo_status",
             "jurisdiction", "rank_city_actionable", "annual_fsi", "ka_3y", "kabc_3y", "tot_3y"]
    feats = []
    for r in json.loads(table[props].to_json(orient="records")):
        feats.append({"type": "Feature", "id": r["site_id"], "geometry": json.loads(geo[r["site_id"]]), "properties": r})
    Path(path).write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":"), default=str) + "\n")


def figures(directory, bt, cal):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"A": "#6b7280", "B": "#2563eb", "C": "#dc2626", "Stack": "#f59e0b"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, target in zip(axes, ("KA", "KABC")):
        sc = [s for s in bt["targets"][target] if s["length_basis"] == "icd_250ft" and s["scenario"] != "hin_matched_counts"]
        sc.sort(key=lambda s: s["requested_share"])
        for m in ("B", "C", "Stack"):
            xs = [s["methods"][m]["flagged_share"] for s in sc]
            ys = [s["methods"][m]["capture"] for s in sc]
            lo = [s["methods"][m]["capture"] - s["methods"][m]["ci_low"] for s in sc]
            hi = [s["methods"][m]["ci_high"] - s["methods"][m]["capture"] for s in sc]
            label = {"B": "B: SPF+EB", "C": "C: ML-EB", "Stack": "Stack"}[m]
            ax.errorbar(xs, ys, yerr=[lo, hi], marker="o", capsize=3, color=colors[m], label=label)
        a = sc[0]["methods"]["A"]
        ax.errorbar([a["flagged_share"]], [a["capture"]], yerr=[[a["capture"] - a["ci_low"]], [a["ci_high"] - a["capture"]]],
                    marker="s", color=colors["A"], capsize=3, label="A: HIN", linestyle="none")
        ax.set_xlabel("share of network length flagged (intersections 250 ft)")
        ax.set_ylabel(f"share of 2023-2025 {target} crashes captured")
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.3)
        ax.set_title(f"{target} capture, 95% bootstrap CI")
        ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(Path(directory) / "capture_vs_share.png", dpi=130)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(5, 4.2))
    for m, c in (("SPF+EB", colors["B"]), ("ML-EB", colors["C"])):
        d = cal["models"][m]["ka"]["deciles"]
        ax.plot([b["predicted"] for b in d], [b["observed"] for b in d], marker="o", color=c, label=m)
    hi = max(max(b["predicted"], b["observed"]) for m in ("SPF+EB", "ML-EB") for b in cal["models"][m]["ka"]["deciles"])
    ax.plot([0, hi], [0, hi], color="#9ca3af", linestyle="--", label="perfect")
    ax.set_xlabel("predicted KA crashes 2023-2025 (decile total)")
    ax.set_ylabel("observed KA crashes (matched)")
    ax.set_title("KA calibration by decile")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(Path(directory) / "calibration_ka.png", dpi=130)
    plt.close(fig)


def model_card(path, run_id, cfg, bt, cal, timings, manifest_bits, fc_info):
    p = bt["primary"]
    m, d = p["methods"], p["differences"]
    def row(target, scen, basis="icd_250ft"):
        s = next(x for x in bt["targets"][target] if x["scenario"] == scen and x["length_basis"] == basis)
        cells = [f"{s['methods'][k]['capture']:.3f} [{s['methods'][k]['ci_low']:.3f}, {s['methods'][k]['ci_high']:.3f}]"
                 for k in ("A", "B", "C", "Stack")]
        diffs = [f"{s['differences'][k]['difference']:+.3f} [{s['differences'][k]['ci_low']:+.3f}, {s['differences'][k]['ci_high']:+.3f}]"
                 for k in ("B-A", "C-A", "Stack-A")]
        return f"| {target} | {scen} ({basis}) | " + " | ".join(cells + diffs) + " |"
    lines = [f"# Model card: {run_id}", "",
             "S2 crash-risk ranking for College Station (S1 network v1_2022, 5,590 segments and 1,634 intersections).",
             "", "## Methods (fixed in the config before the backtest)", "",
             "- A: published MPO CSAP high-injury network (Fig. 3.9, digitized), membership from S1 `s2_hin_site`.",
             "- B: NB2 safety performance function on KABC crashes with HSM empirical Bayes, times P(KA|KABC).",
             "- C (primary, EVP 4.2): ML-EB. Poisson LightGBM on site features (no own crash history) for all crashes, "
             "EB blend with the site's last 5 years, times P(KABC|crash) and P(KA|KABC) (binomial GLMs shrunk toward the "
             f"site's own history with {cfg['sev_prior_m']} pseudo-crashes).",
             "- Stack, LightGBM, LGB-Tot, Naive: the Nov 4 notebook models, reported for comparison only.",
             "", "## Data and as-of dates", "",
             "- Backtest: label years 2019-2022, crash history 2016-2022, features TxDOT inventory 2019 (available 2021-08-06), "
             "OSM and network as of 2022-12-31. Test: 2023-2025 crashes. The leakage gate refused every seeded post-cutoff record.",
             f"- Forecast {cfg['forecast_year']}: refit on label years 2019-2025 with crash history through 2025-12-31; "
             "static features unchanged (no newer TxDOT snapshot is in S1).",
             "- Ranking metric: expected K+A crashes per mile per year (`fsi_rate`); intersections use the 250 ft influence "
             "length (0.0473 mi) for both rate and flagging (ICD Table 9).",
             "", "## Backtest (frozen 2022, 1,000 paired crash-level bootstrap resamples)", "",
             "| Target | Budget | A | B | C | Stack | B-A | C-A | Stack-A |", "|---|---|---|---|---|---|---|---|---|"]
    for target in ("KA", "KABC"):
        for scen in ("5pct", "11pct", "20pct", "hin_share", "hin_matched_counts"):
            lines.append(row(target, scen))
        lines.append(row(target, "11pct", "s1_zero_length"))
    lines += ["", f"Primary (KA, 11%): C flagged {m['C']['flagged_share']:.4f} of network length, B {m['B']['flagged_share']:.4f}; "
              f"test K+A crashes in the area {p['n_test_crashes']}.", "",
              "## Calibration (2023-2025, matched crashes)", ""]
    for model in ("SPF+EB", "ML-EB", "Stack"):
        c = cal["models"][model]
        lines.append(f"- {model}: predicted/observed KA {c['ka']['ratio_predicted_to_observed']:.2f}, "
                     f"KABC {c['kabc']['ratio_predicted_to_observed']:.2f}")
    sev = cal["severity"]
    if sev.get("status") == "ok":
        lines.append(f"- Severity P(KA|crash): Brier score {sev['brier_score']:.4f} on {sev['known_crashes']} known-severity crashes")
    lines += ["", "## Run facts", "",
              f"- Training and scoring time: {timings['total_seconds']:.0f} s (stages in manifest.json)",
              f"- Reload of saved models reproduced the ranking: {manifest_bits['reload_ok']}",
              f"- Independent refit reproduced the ranking hash: {manifest_bits['refit_ok']}",
              f"- Ranking hash: `{manifest_bits['ranking_hash']}`",
              f"- BIT: {manifest_bits['bit']}",
              f"- Forecast: {fc_info['flagged']} sites flagged ({fc_info['flagged_segments']} segments, "
              f"{fc_info['flagged_intersections']} intersections), {fc_info['flagged_share']:.4f} of network length", "",
              "## Limits", "",
              "- One city: 4 label years for the backtest fit. KA counts are small, so KA intervals are wide.",
              "- No pedestrian/bicycle crash field in the delivered CRIS exports; no streetlight layer.",
              "- AADT is missing on OSM-only streets; those take their functional-class median (flag `aadt_imputed`).",
              "- Explanations are TreeSHAP of the ML-EB prior (site features); the EB history blend is reported separately "
              "as `eb_weight`, `ka_3y`, `kabc_3y`."]
    Path(path).write_text("\n".join(lines) + "\n")


def reload_hash(models_dir, sites, fut, rows, enc, expl, cfg):
    try:
        from .citywide_models import load_models, predict_all
    except ImportError:
        from citywide_models import load_models, predict_all
    outs = {}
    for kind in ("segment", "intersection"):
        state = json.loads((Path(models_dir) / f"model_state_{kind}.json").read_text())
        F2, w2 = load_models(state, models_dir)
        outs[kind] = predict_all(F2, rows[kind], cfg, enc, w2)
    preds, _ = combine(sites, outs, rows)
    table = ranking_table(sites, fut, preds, prediction_frame(sites, preds["ML-EB"], cfg),
                          prediction_frame(sites, preds["SPF+EB"], cfg), expl, cfg)
    return ranking_hash(table)


def bit_campaign(snapshot, cfg, sites, fut, rows, enc, frame_c, expl, flagged_ids, r_hash, models_dir,
                 panel_fc, label_fc, log):
    """EVP BIT test: 20 seeded faults (at least 19 detected) and 20 clean refits (at most 1 alarm)."""
    import copy
    import shutil
    import tempfile
    import numpy as np
    ids = sites.site_id.astype(str)
    good_rows = frame_c.to_dict("records")

    def checks(rows_=None, expl_=None, snap=None, models=None):
        if rows_ is not None:
            check_predictions(rows_, ids)
        if expl_ is not None:
            check_explanations(expl_, flagged_ids)
        if snap is not None:
            validate_snapshot(snap, cfg["features"], cfg["history_start"], cfg["history_end"])
        if models is not None and reload_hash(models, sites, fut, rows, enc, expl, cfg) != r_hash:
            raise ValueError("BIT: reloaded models changed the ranking")

    def rows_with(fn):
        r = copy.deepcopy(good_rows)
        fn(r)
        return r
    top = int(np.argmin([r["rank"] for r in good_rows]))
    last = int(np.argmax([r["rank"] for r in good_rows]))
    unflagged = [i for i, r in enumerate(good_rows) if not r["flagged"]]
    unflagged.sort(key=lambda i: good_rows[i]["rank"])
    flagged_idx = sorted([i for i, r in enumerate(good_rows) if r["flagged"]], key=lambda i: good_rows[i]["rank"])

    def set_(i, **kw):
        return lambda r: r[i].update(kw)

    def flag_more(r):
        total = sum(x["network_length_mi"] for x in r)
        add = 0.0
        for i in unflagged:
            if add > 0.04 * total:
                break
            r[i]["flagged"] = True
            add += r[i]["network_length_mi"]

    def flag_less(r):
        total = sum(x["network_length_mi"] for x in r)
        cut = 0.0
        for i in reversed(flagged_idx):
            if cut > 0.04 * total:
                break
            r[i]["flagged"] = False
            cut += r[i]["network_length_mi"]

    def swap_flag(r):
        r[top]["flagged"], r[last]["flagged"] = False, True

    def bad_units(r):
        r[top]["fsi_rate"] *= 1.1

    def fsi_over_total(r):
        r[top]["annual_fsi"] = r[top]["annual_total"] * 2
        r[top]["fsi_rate"] = r[top]["annual_fsi"] / r[top]["risk_length_mi"]

    def expl_with(fn):
        e = copy.deepcopy(expl)
        fn(e)
        return e
    first_site = expl[0]["site_id"]

    def late_feature():
        s = copy.deepcopy(snapshot)
        s["features"][0]["as_of_date"] = "2023-06-30"
        return s

    def tampered_models():
        d = Path(tempfile.mkdtemp(prefix="bit-models-"))
        shutil.copytree(models_dir, d, dirs_exist_ok=True)
        f = d / "model_state_segment.json"
        state = json.loads(f.read_text())
        state["me"]["k"] *= 2
        f.write_text(json.dumps(state))
        tamper_dirs.append(d)
        return d
    tamper_dirs = []
    faults = [
        ("mu is NaN", lambda: checks(rows_with(set_(top, mu=float("nan"))))),
        ("mu negative", lambda: checks(rows_with(set_(top, mu=-1.0)))),
        ("EB weight = 1", lambda: checks(rows_with(set_(top, eb_weight=1.0)))),
        ("EB weight = 0", lambda: checks(rows_with(set_(top, eb_weight=0.0)))),
        ("p_fsi = 1.2", lambda: checks(rows_with(set_(top, p_fsi=1.2)))),
        ("annual F&SI above all crashes", lambda: checks(rows_with(fsi_over_total))),
        ("rate/count units disagree", lambda: checks(rows_with(bad_units))),
        ("duplicate site row", lambda: checks(rows_with(lambda r: r.append(dict(r[top]))))),
        ("site missing", lambda: checks(rows_with(lambda r: r.pop(last)))),
        ("unknown site", lambda: checks(rows_with(lambda r: r[last].update(site_id="999999999")))),
        ("rank gap", lambda: checks(rows_with(set_(last, rank=len(good_rows) + 5)))),
        ("flags not a rank prefix", lambda: checks(rows_with(swap_flag))),
        ("flagged length about 15%", lambda: checks(rows_with(flag_more))),
        ("flagged length about 7%", lambda: checks(rows_with(flag_less))),
        ("k = 0", lambda: checks(rows_with(set_(top, k=0.0)))),
        ("flagged site without explanation", lambda: checks(expl_=expl_with(
            lambda e: e[:] and [e.remove(x) for x in [x for x in e if x["site_id"] == first_site]]))),
        ("four factors for one site", lambda: checks(expl_=expl_with(lambda e: e.remove(
            next(x for x in e if x["site_id"] == first_site and x["rank"] == 5))))),
        ("SHAP value NaN", lambda: checks(expl_=expl_with(lambda e: e[0].update(shap_value=float("nan"))))),
        ("post-cutoff feature in snapshot", lambda: checks(snap=late_feature())),
        ("saved model state altered", lambda: checks(models=tampered_models())),
    ]
    fault_results = []
    for name, run in faults:
        try:
            run()
            fault_results.append({"fault": name, "detected": False})
        except Exception as exc:
            fault_results.append({"fault": name, "detected": True, "by": f"{type(exc).__name__}: {exc}"[:200]})
    for d in tamper_dirs:
        shutil.rmtree(d, ignore_errors=True)
    good = []
    for i in range(cfg.get("bit_good_runs", 20)):
        seeds = [1000 + 3 * i, 1001 + 3 * i, 1002 + 3 * i]
        t0 = time.monotonic()
        try:
            enc_i, fits_i, outs_i, rows_i = fit_predict(panel_fc, label_fc, cfg["forecast_year"], cfg,
                                                       lambda *a, **k: None, seeds=seeds)
            preds_i, _ = combine(sites, outs_i, rows_i)
            frame_i = prediction_frame(sites, preds_i["ML-EB"], cfg)
            flagged_i = frame_i.loc[frame_i.flagged, "site_id"].tolist()
            expl_i = []
            for kind in ("segment", "intersection"):
                fk = rows_i[kind]
                aadt = np.where(fk.site_type == "segment", fk.aadt, fk.aadt_major + fk.aadt_minor)
                expl_i += explanations_for(fits_i[kind][0], enc_i, fk, flagged_i, aadt)
            check_predictions(frame_i.to_dict("records"), ids)
            check_explanations(expl_i, flagged_i)
            good.append({"run": i + 1, "lgb_seeds": seeds, "alarm": False, "flagged_sites": len(flagged_i),
                         "seconds": round(time.monotonic() - t0, 1)})
        except Exception as exc:
            good.append({"run": i + 1, "lgb_seeds": seeds, "alarm": True, "error": str(exc)[:200]})
        log("bit_good_run", **good[-1])
    detected = sum(f["detected"] for f in fault_results)
    alarms = sum(g["alarm"] for g in good)
    return {"seeded_faults": fault_results, "detected": detected, "faults": len(fault_results),
            "good_runs": good, "false_alarms": alarms,
            "criteria": "detect >= 19 of 20 seeded faults; <= 1 false alarm in 20 clean runs",
            "result": "PASS" if detected >= 19 and alarms <= 1 else "FAIL"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-root", default="integration/artifacts")
    args = ap.parse_args(argv)
    started = time.monotonic()
    stages = []
    last = [started]

    def log(event, **kw):
        now = time.monotonic()
        rec = {"event": event, "t": round(now - started, 1), **kw}
        print(json.dumps(rec, default=str), flush=True)

    def stage(name):
        now = time.monotonic()
        stages.append({"stage": name, "seconds": round(now - last[0], 2)})
        last[0] = now
        log("stage_done", stage=name, seconds=stages[-1]["seconds"])
    try:
        validate_run_id(args.run_id)
        cfg = load_config(args.config)
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ[name] = str(cfg["threads"])
        import numpy as np
        try:
            from .panel import build_panel, crash_frame, neighbor_matrix, static_frame
            from .citywide_models import load_models, model_state, predict_all, save_boosters
        except ImportError:
            from panel import build_panel, crash_frame, neighbor_matrix, static_frame
            from citywide_models import load_models, model_state, predict_all, save_boosters
        out = Path(args.out_root) / args.run_id
        if out.exists():
            raise FileExistsError(f"{out} exists; use a new run ID")
        db = cfg["database"]
        snapshot = load_snapshot(db, cfg["features"], cfg["history_start"], cfg["history_end"])
        gate = validate_snapshot(snapshot, cfg["features"], cfg["history_start"], cfg["history_end"])
        seeded = seeded_leakage_checks(snapshot, cfg["features"])
        if not all(c["detected"] for c in seeded):
            raise RuntimeError(f"leakage gate missed a seeded post-cutoff record: {seeded}")
        snapshot = normalize_snapshot(snapshot)
        log("leakage_gate_pass", **gate, seeded_cases=len(seeded))
        stage("snapshot_and_leakage_gate")

        cutoff = f"{cfg['history_end']}-12-31"
        ctx_bt = load_context(db, cutoff)
        static = static_frame(snapshot, ctx_bt)
        nb, n_pairs = neighbor_matrix(static, cfg["neighbor_m"])
        sites = static[["site_id", "site_type", "risk_length_mi", "network_length_mi", "road_name", "in_hin"]].copy()
        if sites.in_hin.isna().any():
            raise ValueError("HIN membership missing for some sites")
        stage("context")

        # ---- frozen 2022 backtest ----
        test_years = cfg["test_years"]
        label_bt = list(range(cfg["first_label_year"], cfg["history_end"] + 1))
        panel_bt = build_panel(static, crash_frame(ctx_bt), label_bt + [test_years[0]], cfg["history_start"],
                               cfg["hist_years_long"], nb, cutoff)
        _, _, outs, rows = fit_predict(panel_bt, label_bt, test_years[0], cfg, log)
        preds_bt, _ = combine(sites, outs, rows)
        stage("backtest_fit")
        bt = evaluate(sites, preds_bt, snapshot["test_crashes"], cfg)
        bt.update({"run_id": args.run_id, "protocol": "EVP 4.2 frozen 2022: train <= 2022-12-31, test 2023-2025",
                   "network_version": db["network_version"], "hin_version": db["metadata"]["hin_version"],
                   "leakage_gate": gate, "seeded_leakage_checks": seeded, "neighbor_pairs_250m": int(n_pairs),
                   "label_years": label_bt, "test_years": test_years})
        frame_bt_c = prediction_frame(sites, preds_bt["ML-EB"], cfg)
        frame_bt_b = prediction_frame(sites, preds_bt["SPF+EB"], cfg)
        bit_records = [check_predictions(frame_bt_c.to_dict("records"), sites.site_id.astype(str)),
                       check_predictions(frame_bt_b.to_dict("records"), sites.site_id.astype(str))]
        cal = calibration(sites, preds_bt, snapshot["test_crashes"], test_years, cfg)
        stage("backtest_score")

        # ---- 2026 forecast ----
        fc_cut = f"{test_years[-1]}-12-31"
        ctx_fc = load_context(db, fc_cut)
        label_fc = list(range(cfg["first_label_year"], test_years[-1] + 1))
        panel_fc = build_panel(static, crash_frame(ctx_fc), label_fc + [cfg["forecast_year"]], cfg["history_start"],
                               cfg["hist_years_long"], nb, fc_cut)
        enc, fits, outs, rows = fit_predict(panel_fc, label_fc, cfg["forecast_year"], cfg, log)
        preds_fc, fut = combine(sites, outs, rows)
        stage("forecast_fit")
        frame_c = prediction_frame(sites, preds_fc["ML-EB"], cfg)
        frame_b = prediction_frame(sites, preds_fc["SPF+EB"], cfg)
        flagged_ids = frame_c.loc[frame_c.flagged, "site_id"].tolist()
        expl = []
        for kind in ("segment", "intersection"):
            fk = rows[kind]
            aadt = np.where(fk.site_type == "segment", fk.aadt, fk.aadt_major + fk.aadt_minor)
            expl += explanations_for(fits[kind][0], enc, fk, flagged_ids, aadt)
        bit_records += [check_predictions(frame_c.to_dict("records"), sites.site_id.astype(str)),
                        check_predictions(frame_b.to_dict("records"), sites.site_id.astype(str)),
                        check_explanations(expl, flagged_ids)]
        table = ranking_table(sites, fut, preds_fc, frame_c, frame_b, expl, cfg)
        r_hash = ranking_hash(table)
        stage("forecast_score_explain_bit")

        # ---- export ----
        tmp = Path(args.out_root) / f".{args.run_id}.staging"
        if tmp.exists():
            import shutil
            shutil.rmtree(tmp)
        (tmp / "models").mkdir(parents=True)
        for kind, (F, w) in fits.items():
            save_boosters(F, tmp / "models")
            write_json(tmp / "models" / f"model_state_{kind}.json", model_state(F, w))
        # reload check: saved models must give the same ranking
        reload_ok = reload_hash(tmp / "models", sites, fut, rows, enc, expl, cfg) == r_hash
        if not reload_ok:
            raise RuntimeError("artifact reload changed the ranking")
        stage("export_models_and_reload")
        refit_ok = None
        if cfg["verify_refit"]:
            _, _, outs2, rows2 = fit_predict(panel_fc, label_fc, cfg["forecast_year"], cfg, lambda *a, **k: None)
            preds2, _ = combine(sites, outs2, rows2)
            table2 = ranking_table(sites, fut, preds2, prediction_frame(sites, preds2["ML-EB"], cfg),
                                   prediction_frame(sites, preds2["SPF+EB"], cfg), expl, cfg)
            refit_ok = ranking_hash(table2) == r_hash
            stage("independent_refit_check")
        if cfg.get("bit_campaign"):
            campaign = bit_campaign(snapshot, cfg, sites, fut, rows, enc, frame_c, expl, flagged_ids, r_hash,
                                    tmp / "models", panel_fc, label_fc, log)
            write_json(tmp / "bit_campaign.json", campaign)
            stage("bit_campaign")
        table.to_csv(tmp / "ranking.csv", index=False)
        write_geojson(tmp / "sites.geojson", table, ctx_fc)
        write_json(tmp / "backtest.json", bt)
        write_json(tmp / "explanations.json", expl)
        (tmp / "site_history.json").write_text(json.dumps(site_history(ctx_fc), separators=(",", ":")) + "\n")
        write_json(tmp / "calibration.json", cal)
        write_json(tmp / "bit.json", bit_records)
        figures(tmp, bt, cal)
        total = time.monotonic() - started
        fc_info = {"flagged": int(frame_c.flagged.sum()),
                   "flagged_segments": int((frame_c.flagged & (frame_c.site_type == "segment")).sum()),
                   "flagged_intersections": int((frame_c.flagged & (frame_c.site_type == "intersection")).sum()),
                   "flagged_share": float(frame_c.risk_length_mi[frame_c.flagged].sum() / frame_c.risk_length_mi.sum())}
        bits = {"reload_ok": reload_ok, "refit_ok": refit_ok, "ranking_hash": r_hash,
                "bit": (f"{campaign['detected']}/{campaign['faults']} seeded faults detected, "
                        f"{campaign['false_alarms']} false alarms in {len(campaign['good_runs'])} clean refits "
                        f"({campaign['result']})") if cfg.get("bit_campaign") else "not run"}
        model_card(tmp / "model_card.md", args.run_id, cfg, bt, cal, {"total_seconds": total}, bits, fc_info)
        write_json(tmp / "config.json", cfg)
        meta = snapshot["metadata"]
        manifest = {
            "schema_version": 1, "run_id": args.run_id, "created": datetime.now(timezone.utc).isoformat(),
            **git_commit(Path(__file__).resolve().parent),
            "subsystem": "S2", "network_version": db["network_version"], "hin_version": meta["hin_version"],
            "as_of": {"backtest_features_and_history": cutoff, "txdot_inventory": "2019-12-31 (available 2021-08-06)",
                      "osm": "2022-12-31", "network": "2022-12-31", "forecast_crash_history": fc_cut,
                      "forecast_year": cfg["forecast_year"], "test_window": f"{test_years[0]}-{test_years[-1]}"},
            "data_versions": meta["data_versions"], "methods": {"A": METHOD_NAMES["A"], "B": cfg["method_b"], "C": cfg["primary_c"]},
            "input_hash": json_hash(snapshot), "config_hash": json_hash(cfg), "ranking_hash": r_hash,
            "reload_verified": reload_ok, "independent_refit_reproduced": refit_ok,
            "duration_seconds": round(total, 1), "stages": stages,
            "runtime": {"python": sys.version.split()[0], **_versions()},
            "forecast": fc_info,
            "files": {str(p.relative_to(tmp)): file_hash(p) for p in sorted(tmp.rglob("*")) if p.is_file()},
            "files_not_in_git": ["models/"],
        }
        write_json(tmp / "manifest.json", manifest)
        tmp.rename(out)
        if cfg.get("bit_campaign") and campaign["result"] != "PASS":
            raise RuntimeError(f"BIT campaign failed: {campaign['detected']} detected, {campaign['false_alarms']} false alarms")
        latest = Path(args.out_root) / "LATEST"
        latest.write_text(args.run_id + "\n")
        log("run_complete", path=str(out), seconds=round(total, 1), ranking_hash=r_hash, reload_ok=reload_ok,
            refit_ok=refit_ok, primary={k: {kk: v[kk] for kk in ("capture", "ci_low", "ci_high", "flagged_share")}
                                        for k, v in bt["primary"]["methods"].items()},
            differences=bt["primary"]["differences"])
        return 0
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(json.dumps({"event": "run_failed", "error_type": type(exc).__name__, "error": str(exc)}), file=sys.stderr)
        return 1


def _versions():
    from importlib.metadata import version
    return {p: version(p) for p in ("numpy", "pandas", "scipy", "statsmodels", "lightgbm")}


if __name__ == "__main__":
    raise SystemExit(main())
