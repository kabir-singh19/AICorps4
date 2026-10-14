"""S2 operator CLI: train, score, explain and store an immutable frozen run."""
from __future__ import annotations

import argparse
import json
import sys
import time
from importlib.metadata import version
from pathlib import Path

try:
    from .artifacts import canonical_json, json_hash, load_bundle, load_models, save_bundle, source_version, validate_run_id
    from .bit import check_explanations, check_predictions, preflight
    from .leakage import validate_snapshot
except ImportError:
    from artifacts import canonical_json, json_hash, load_bundle, load_models, save_bundle, source_version, validate_run_id
    from bit import check_explanations, check_predictions, preflight
    from leakage import validate_snapshot

DEFAULT_CONFIG = {"seed": 42, "history_start": 2015, "history_end": 2022,
                  "features": ["speed_limit", "num_lanes", "aadt", "func_class", "median_type"],
                  "bootstrap_resamples": 1000, "rounds": 200, "max_depth": 3,
                  "learning_rate": .05, "threads": 2, "nb_ridge": .01, "severity_C": 1.0,
                  "feature_labels": {}}


def load_config(path=None):
    provided = json.loads(Path(path).read_text()) if path else {}
    extra = set(provided) - set(DEFAULT_CONFIG) - {"database"}
    if extra:
        raise ValueError(f"unknown config fields: {sorted(extra)}")
    config = {**DEFAULT_CONFIG, **provided}
    for key in ("seed", "history_start", "history_end", "bootstrap_resamples", "rounds", "max_depth", "threads"):
        if isinstance(config[key], bool) or not isinstance(config[key], int):
            raise ValueError(f"{key} must be an integer")
    if config["seed"] < 0 or config["bootstrap_resamples"] < 1000 or not 1 <= config["threads"] <= 2:
        raise ValueError("invalid seed, bootstrap resamples or worker thread budget")
    return config


def normalize_snapshot(snapshot):
    snapshot = json.loads(canonical_json(snapshot))
    for key in ("sites", "features", "history", "test_crashes"):
        for row in snapshot[key]:
            if row.get("site_id") is not None:
                row["site_id"] = str(row["site_id"])
        snapshot[key].sort(key=canonical_json)
    snapshot["metadata"]["sources"].sort(key=canonical_json)
    for site in snapshot["sites"]:
        site.setdefault("road_name", "")
    return snapshot


def runtime_versions():
    return {"python": sys.version.split()[0], **{p: version(p) for p in ("numpy", "scipy", "pandas", "xgboost")}}


def prepare_inputs(snapshot, config):
    import pandas as pd
    validate_snapshot(snapshot, config["features"], config["history_start"], config["history_end"])
    sites = pd.DataFrame(snapshot["sites"]).sort_values("site_id", kind="stable").reset_index(drop=True)
    records = [r for r in snapshot["features"] if r["feature_name"] in config["features"]]
    raw = pd.DataFrame(records).pivot(index="site_id", columns="feature_name", values="value").reindex(sites.site_id)
    # Object dtype from the long table must not turn numerical attributes into categories.
    for column in raw:
        values = raw[column].dropna()
        if len(values) and values.map(lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)).all():
            raw[column] = pd.to_numeric(raw[column], errors="raise")
    raw = raw[config["features"]].reset_index(drop=True)
    panel = pd.MultiIndex.from_product([sites.site_id, range(config["history_start"], config["history_end"]+1)], names=["site_id", "year"])
    if snapshot["history"]:
        history = pd.DataFrame(snapshot["history"]).set_index(["site_id", "year"])
        history = history[["crashes", "known_crashes", "fsi_crashes"]].reindex(panel, fill_value=0)
    else:
        history = pd.DataFrame(0, index=panel, columns=["crashes", "known_crashes", "fsi_crashes"])
    totals = history.groupby("site_id").sum().reindex(sites.site_id)
    return sites, raw, history.reset_index(), totals.reset_index()


def make_predictions(sites, models, X, totals, exposure, n_years):
    try:
        from .empirical_bayes import eb_estimate
        from .ranking import flag_by_length, fsi_rate, rank_sites
    except ImportError:
        from empirical_bayes import eb_estimate
        from ranking import flag_by_length, fsi_rate, rank_sites
    result = {}
    p = models["severity"].predict(X)
    for method in ("B", "C"):
        mu = models[method].predict(X, exposure)
        k = models[method].k
        eb = eb_estimate(mu, totals.crashes.to_numpy(), k)
        frame = sites.copy()
        frame["mu"], frame["k"] = mu, k
        frame["eb_weight"], frame["n_eb"], frame["p_fsi"] = eb.weight, eb.expected, p
        frame["annual_total"] = eb.expected/n_years
        frame["annual_fsi"] = frame.annual_total*p
        frame["fsi_rate"] = fsi_rate(eb.expected, p, frame.risk_length_mi, n_years)
        frame["rank"] = rank_sites(frame.site_id, frame.fsi_rate)
        frame["flagged"] = flag_by_length(frame["rank"], frame.network_length_mi, allow_zero_lengths=True)
        frame["n_history_years"] = n_years
        # Unknown/unavailable HIN is a JSON null, not NaN.
        if "in_hin" not in frame:
            frame["in_hin"] = None
        result[method] = frame
    return result


def fit_run(snapshot, config, log=None):
    import os
    # Set BLAS/OpenMP budgets before the first numeric imports in the CLI process.
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = str(config["threads"])
    import numpy as np
    stage_records = []
    stage_start = time.monotonic()
    def note(event, **details):
        nonlocal stage_start
        now = time.monotonic()
        record = {"event": event, "duration_seconds": now-stage_start, **details}
        stage_start = now
        stage_records.append(record)
        if log:
            log(event, **details, duration_seconds=record["duration_seconds"])
    try:
        from .preprocessing import FeatureEncoder
        from .nb_spf import NegativeBinomialSPF
        from .ml_risk import PoissonRiskModel
        from .severity import SeverityModel, calibration_report
        from .empirical_bayes import estimate_k
        from .explanations import top_factors
        from .hin_baseline import hin_membership
        from .backtest import evaluate
    except ImportError:
        from preprocessing import FeatureEncoder
        from nb_spf import NegativeBinomialSPF
        from ml_risk import PoissonRiskModel
        from severity import SeverityModel, calibration_report
        from empirical_bayes import estimate_k
        from explanations import top_factors
        from hin_baseline import hin_membership
        from backtest import evaluate
    sites, raw, panel, totals = prepare_inputs(snapshot, config)
    encoder = FeatureEncoder().fit(raw)
    X = encoder.transform(raw)
    note("features_prepared", sites=len(sites), panel_rows=len(panel), encoded_features=X.shape[1])
    years = config["history_end"]-config["history_start"]+1
    exposure = sites.risk_length_mi.to_numpy()*years
    nb = NegativeBinomialSPF(ridge=config["nb_ridge"]).fit(X, totals.crashes.to_numpy(), exposure)
    note("nb_spf_fitted", k=nb.k)
    ml = PoissonRiskModel(seed=config["seed"], rounds=config["rounds"], max_depth=config["max_depth"],
                          learning_rate=config["learning_rate"], threads=config["threads"]).fit(X, totals.crashes.to_numpy(), exposure)
    ml.k = estimate_k(totals.crashes.to_numpy(), ml.predict(X, exposure))
    note("ml_eb_fitted", k=ml.k)
    severity = SeverityModel(config["seed"], config["severity_C"])
    # Calibration evidence uses held-out sites from the historical period only.
    # This diagnostic fit has its own train-only preprocessing; it never sees test-window labels.
    eligible = np.flatnonzero(totals.known_crashes.to_numpy() > 0)
    if len(eligible) >= 5:
        permutation = np.random.default_rng(config["seed"]).permutation(eligible)
        n_validation = max(1, int(np.ceil(.2*len(eligible))))
        valid, fitting = permutation[:n_validation], permutation[n_validation:]
        validation_encoder = FeatureEncoder().fit(raw.iloc[fitting])
        diag_model = SeverityModel(config["seed"], config["severity_C"]).fit(validation_encoder.transform(raw.iloc[fitting]),
                            totals.fsi_crashes.to_numpy()[fitting], totals.known_crashes.to_numpy()[fitting])
        probabilities = diag_model.predict(validation_encoder.transform(raw.iloc[valid]))
        calibration = calibration_report(probabilities, totals.fsi_crashes.to_numpy()[valid], totals.known_crashes.to_numpy()[valid])
        calibration.update({"evaluation": "20% held-out sites in the historical period; final severity model refit on all history",
                            "validation_site_ids": sites.site_id.iloc[valid].tolist()})
    else:
        calibration = {"status": "unavailable: fewer than five sites with known-severity crashes", "bins": []}
    severity.fit(X, totals.fsi_crashes.to_numpy(), totals.known_crashes.to_numpy())
    note("severity_fitted", calibration_status=calibration["status"])
    models = {"B": nb, "C": ml, "severity": severity}
    predictions = make_predictions(sites, models, X, totals, exposure, years)
    explanation = top_factors(ml, X, exposure, raw, encoder, predictions["C"], config["feature_labels"])
    records = [check_predictions(f.to_dict("records"), sites.site_id) for f in predictions.values()]
    records.append(check_explanations(explanation, predictions["C"].loc[predictions["C"]["flagged"], "site_id"]))
    note("predictions_and_shap_checked", explanations=len(explanation))
    report = evaluate(predictions, snapshot["test_crashes"], hin_membership(snapshot["sites"]),
                      config["bootstrap_resamples"], config["seed"])
    note("backtest_scored", resamples=config["bootstrap_resamples"], n_test_fsi=report["primary"]["n_test_fsi"])
    diagnostics = {"runtime_versions": runtime_versions(), "nb": nb.diagnostics, "ml_k": ml.k,
                   "missing_features": {name: int(raw[name].isna().sum()) for name in raw},
                   "panel_rows": len(panel), "history_years": years, "site_count": len(sites),
                   "severity_constant": severity.constant,
                   "mu_units": "predicted total crashes over the historical window",
                   "n_eb_units": "EB total crashes over the historical window",
                   "annual_fsi_units": "expected K/A crashes per site per year",
                   "fsi_rate_units": "expected K/A crashes per mile per year", "stages": stage_records}
    return {"models": models, "encoder": encoder, "predictions": predictions, "explanations": explanation,
            "backtest": report, "calibration": calibration, "diagnostics": diagnostics, "bit_records": records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--config")
    parser.add_argument("--snapshot", help="Frozen IF-09 snapshot JSON, not another subsystem's raw CSV")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--replay", action="store_true", help="Refit frozen inputs and verify exact ranking and scores")
    args = parser.parse_args(argv)
    started = time.monotonic()
    def log_event(event, **details):
        from datetime import datetime, timezone
        print(json.dumps({"event": event, "run_id": args.run_id,
                          "timestamp": datetime.now(timezone.utc).isoformat(), **details}, allow_nan=False), flush=True)
    try:
        validate_run_id(args.run_id)
        record = preflight(log_dir=Path(args.output_root)/"bit_log")
        log_event("bit_pass")
        code = source_version(Path(__file__).parent)
        if args.replay:
            stored = load_bundle(Path(args.output_root)/args.run_id)
            snapshot, config = stored["snapshot"], stored["config"]
            if args.config or args.snapshot:
                raise ValueError("replay uses only the stored config and snapshot")
            if stored["manifest"]["code_version"] != code or stored["manifest"]["runtime_versions"] != runtime_versions():
                raise ValueError("exact replay requires the original source and library versions")
            result = fit_run(snapshot, config, log=log_event)
            actual = {m: f.to_dict("records") for m, f in result["predictions"].items()}
            expected = {m: f.to_dict("records") for m, f in stored["predictions"].items()}
            if canonical_json(actual) != canonical_json(expected) or canonical_json(result["backtest"]) != canonical_json(stored["backtest"]):
                raise ValueError("frozen run did not reproduce exactly")
            print(json.dumps({"event": "replay_pass", "run_id": args.run_id, "duration_seconds": time.monotonic()-started}))
            return 0
        config = load_config(args.config)
        if args.snapshot:
            snapshot = json.loads(Path(args.snapshot).read_text())
        else:
            try:
                from .database import load_snapshot
            except ImportError:
                from database import load_snapshot
            snapshot = load_snapshot(config.get("database", {}), config["features"], config["history_start"], config["history_end"])
        validation = validate_snapshot(snapshot, config["features"], config["history_start"], config["history_end"])
        log_event("snapshot_validated", **validation)
        snapshot = normalize_snapshot(snapshot)
        result = fit_run(snapshot, config, log=log_event)
        # The saved native/JSON model state must reproduce predictions before the run can complete.
        duration = time.monotonic()-started
        if duration > 14400:
            raise RuntimeError("training/backtest exceeded the four-hour budget")
        def verify_reload(staging):
            encoder, models = load_models(staging, require_complete=False)
            models["C"].k = result["diagnostics"]["ml_k"]
            sites, raw, _, totals = prepare_inputs(snapshot, config)
            years = config["history_end"]-config["history_start"]+1
            reloaded = make_predictions(sites, models, encoder.transform(raw), totals, sites.risk_length_mi.to_numpy()*years, years)
            if json_hash({m: f.to_dict("records") for m, f in reloaded.items()}) != json_hash({m: f.to_dict("records") for m, f in result["predictions"].items()}):
                raise RuntimeError("artifact reload changed predictions")
            full_duration = time.monotonic()-started
            if full_duration > 14400:
                raise RuntimeError("full run including reload exceeded the four-hour budget")
            return full_duration
        directory = save_bundle(args.output_root, args.run_id, snapshot, config, code_version=code,
                                duration=duration, verifier=verify_reload,
                                **{**result, "bit_records": [record, *result["bit_records"]]})
        print(json.dumps({"event": "run_complete", "run_id": args.run_id, "path": str(directory),
                          "duration_seconds": time.monotonic()-started, "primary": result["backtest"]["primary"]}, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"event": "run_failed", "run_id": args.run_id, "error_type": type(exc).__name__, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
