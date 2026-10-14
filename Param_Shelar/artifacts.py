"""Immutable run bundles, hashes and JSON model state. Never deserialize pickle."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)


def json_hash(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def validate_run_id(run_id):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_id):
        raise ValueError("run ID must be a safe name with 1-80 letters, digits, _, . or -")
    return run_id


def source_version(directory):
    # Includes dirty source content; a git SHA alone does not identify uncommitted code.
    directory = Path(directory)
    paths = sorted([*directory.glob("*.py"), *directory.glob("tests/**/*.py"), directory/"requirements.txt"])
    return json_hash({str(p.relative_to(directory)): file_hash(p) for p in paths if p.is_file()})


def verify_bundle(directory, require_complete=True):
    directory = Path(directory)
    manifest = json.loads((directory/"manifest.json").read_text())
    validate_run_id(manifest["run_id"])
    if require_complete and "complete.json" not in manifest["files"]:
        raise ValueError("run bundle is incomplete")
    for name, digest in manifest["files"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("unsafe bundle manifest path")
        path = directory/name
        if not path.is_file() or path.is_symlink() or file_hash(path) != digest:
            raise ValueError(f"artifact checksum mismatch: {name}")
    return manifest


def save_bundle(output_root, run_id, snapshot, config, models, encoder, predictions,
                explanations, backtest, calibration, diagnostics, bit_records, code_version, duration, verifier):
    validate_run_id(run_id)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    destination = root/run_id
    if destination.exists():
        raise FileExistsError("run ID already exists; use --replay or a new ID")
    staging = Path(tempfile.mkdtemp(prefix=".s2-staging-", dir=root))
    try:
        write_json(staging/"snapshot.json", snapshot)
        write_json(staging/"config.json", config)
        write_json(staging/"encoder.json", encoder.to_dict())
        write_json(staging/"nb_spf.json", models["B"].to_dict())
        write_json(staging/"severity.json", models["severity"].to_dict())
        write_json(staging/"ml_parameters.json", {"parameters": models["C"].parameters, "rounds": models["C"].rounds, "k": models["C"].k})
        models["C"].save(staging/"ml_model.ubj")
        for method, frame in predictions.items():
            frame.to_csv(staging/f"predictions_{method}.csv", index=False, float_format="%.17g")
        # Canonical records preserve exact numeric values and ID types for replay.
        write_json(staging/"predictions.json", {m: f.to_dict("records") for m, f in predictions.items()})
        write_json(staging/"features.json", snapshot["features"])
        write_json(staging/"explanations.json", explanations)
        write_json(staging/"backtest.json", backtest)
        write_json(staging/"calibration.json", calibration)
        write_json(staging/"diagnostics.json", diagnostics)
        write_json(staging/"bit_log.json", bit_records)
        write_model_card(staging/"model_card.md", run_id, snapshot, config, backtest, calibration, diagnostics, code_version, duration)
        write_calibration_svg(staging/"calibration.svg", calibration)
        created = datetime.now(timezone.utc).isoformat()
        manifest = {"schema_version": 1, "run_id": run_id, "created": created, "published": False,
                    "code_version": code_version, "data_versions": snapshot["metadata"]["data_versions"],
                    "as_of_date": "2022-12-31", "seed": config["seed"], "hyperparameters": config,
                    "input_hash": json_hash(snapshot), "config_hash": json_hash(config),
                    "duration_seconds": duration, "training_limit_seconds": 14400,
                    "reference_host_verified": False,
                    "runtime_versions": diagnostics["runtime_versions"],
                    "files": {p.name: file_hash(p) for p in staging.iterdir() if p.is_file()}}
        write_json(staging/"manifest.json", manifest)
        full_duration = verifier(staging)
        if isinstance(full_duration, (int, float)):
            manifest["duration_seconds"] = full_duration
        write_json(staging/"complete.json", {"run_id": run_id, "reload_verified": True})
        manifest["files"]["complete.json"] = file_hash(staging/"complete.json")
        write_json(staging/"manifest.json", manifest)
        verify_bundle(staging)
        # Renaming happens only after every file is ready. Published runs are never touched.
        staging.rename(destination)
        return destination
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def load_bundle(directory):
    manifest = verify_bundle(directory)
    import pandas as pd
    directory = Path(directory)
    read = lambda name: json.loads((directory/name).read_text())
    return {"manifest": manifest, "snapshot": read("snapshot.json"), "config": read("config.json"),
            "predictions": {m: pd.DataFrame(rows) for m, rows in read("predictions.json").items()},
            "backtest": read("backtest.json"), "calibration": read("calibration.json"),
            "explanations": read("explanations.json")}


def load_models(directory, require_complete=True):
    verify_bundle(directory, require_complete=require_complete)
    try:
        from .preprocessing import FeatureEncoder
        from .ml_risk import PoissonRiskModel
        from .nb_spf import NegativeBinomialSPF
        from .severity import SeverityModel
    except ImportError:
        from preprocessing import FeatureEncoder
        from ml_risk import PoissonRiskModel
        from nb_spf import NegativeBinomialSPF
        from severity import SeverityModel
    directory = Path(directory)
    read = lambda name: json.loads((directory/name).read_text())
    encoder = FeatureEncoder.from_dict(read("encoder.json"))
    p = read("ml_parameters.json")
    models = {"B": NegativeBinomialSPF.from_dict(read("nb_spf.json")),
              "C": PoissonRiskModel.load(directory/"ml_model.ubj", p["parameters"], p["rounds"]),
              "severity": SeverityModel.from_dict(read("severity.json"))}
    models["C"].k = p["k"]
    return encoder, models


def write_model_card(path, run_id, snapshot, config, backtest, calibration, diagnostics, code_version, duration):
    primary = backtest.get("primary", {})
    rows = []
    for method in ("A", "B", "C"):
        result = primary.get("methods", {}).get(method)
        if result:
            rows.append(f"| {method} | {result['flagged_miles']:.4f} | {result['capture']:.4f} | [{result['ci_low']:.4f}, {result['ci_high']:.4f}] |")
        else:
            rows.append(f"| {method} | - | unavailable/undefined | - |")
    text = (f"# S2 model card: {run_id}\n\n"
            f"Synthetic inputs: {snapshot['metadata'].get('synthetic', False)}. Published: false.\n\n"
            f"Code fingerprint: {code_version}. Seed: {config['seed']}.\n"
            f"History: {config['history_start']}-{config['history_end']}. Cutoff: 2022-12-31. Test: 2023-2025.\n"
            f"Network: {snapshot['metadata']['network_version']}. Length policy: {snapshot['metadata']['length_policy']}.\n\n"
            "| Method | Flagged miles | F&SI capture | 95% bootstrap interval |\n|---|---:|---:|---|\n" + "\n".join(rows) + "\n\n"
            f"Paired differences: {canonical_json(primary.get('differences', {}))}.\n\n"
            f"Calibration status: {calibration.get('status', 'unknown')}; see calibration.json and calibration.svg.\n"
            f"Measured run before artifact reload: {duration:.2f} seconds. Raspberry Pi performance is unverified.\n\n"
            "B is a locally fitted NB2 SPF with EB; C is Poisson gradient boosting with EB. "
            "Both use the same crash-weighted binomial severity model. Missing numeric values use historical medians. "
            "Unknown severity is excluded from severity labels; multiplying the resulting probability by total crashes assumes unknown severity is missing at random. "
            "ML dispersion is fitted on in-sample site totals and may be understated when boosting overfits. "
            "Predictors are a static historically available snapshot, not reconstructed year-specific conditions. "
            "TreeSHAP explains the ML log-count component before EB/severity and does not establish treatment causality. "
            "Bootstrap intervals condition on the fitted ranking and resample individual crashes, not road clusters or training uncertainty.\n\n"
            "All method outcomes are reported. Full sensitivity and equal-HIN-share results are in backtest.json. "
            "These estimates support planning and need qualified engineering review.\n")
    Path(path).write_text(text, encoding="utf-8")


def write_calibration_svg(path, calibration):
    from html import escape
    bins = calibration.get("bins", [])
    points = " ".join(f"{60+400*b['mean_prediction']:.2f},{450-400*b['observed_fsi_fraction']:.2f}" for b in bins)
    dots = "".join(f'<circle cx="{60+400*b["mean_prediction"]:.2f}" cy="{450-400*b["observed_fsi_fraction"]:.2f}" r="4" fill="#146c94"/>' for b in bins)
    ticks = "".join(f'<text x="{60+100*i}" y="475" text-anchor="middle">{i/4:.2f}</text>'
                    f'<text x="45" y="{454-100*i}" text-anchor="end">{i/4:.2f}</text>' for i in range(5))
    body = (f'<svg xmlns="http://www.w3.org/2000/svg" width="550" height="550" viewBox="0 0 550 550">'
            '<rect width="550" height="550" fill="white"/><g font-family="sans-serif" font-size="12">'
            '<text x="60" y="25" font-size="18">Historical held-out-site severity calibration</text>'
            '<path d="M60 50 V450 H460" fill="none" stroke="#222"/>'
            '<path d="M60 450 L460 50" fill="none" stroke="#888" stroke-dasharray="5 5"/>'
            f'<polyline points="{points}" fill="none" stroke="#146c94" stroke-width="2"/>{dots}{ticks}'
            '<text x="260" y="505" text-anchor="middle">Predicted probability of K/A</text>'
            '<text x="15" y="250" text-anchor="middle" transform="rotate(-90 15 250)">Observed K/A fraction</text>'
            f'<text x="60" y="530">{escape(calibration.get("status", "unavailable"))}</text></g></svg>')
    Path(path).write_text(body, encoding="utf-8")
