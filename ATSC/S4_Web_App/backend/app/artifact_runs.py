"""Read-only adapter for S2/S3 run artifacts (integration/artifacts/<run_id>/), ICD IF-08.

Each run folder holds manifest.json (SHA-256 of every file), ranking.csv, sites.geojson,
backtest.json, explanations.json, site_history.json and memos/. Files are verified against the
manifest once at load; memo files are S3 outputs and are read as they are.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)
REQUIRED = ("manifest.json", "ranking.csv", "sites.geojson", "backtest.json", "explanations.json")
TABLE9 = ("site_id", "site_type", "road_name", "length_mi", "fsi_rate", "rank", "flagged", "in_hin", "memo_status")
MAP_PROPS = TABLE9 + ("annual_fsi", "jurisdiction", "rank_city_actionable", "ka_3y")
CSV_FIELDS = TABLE9 + ("annual_fsi", "annual_kabc", "mu", "k", "eb_weight", "n_eb", "p_fsi", "jurisdiction",
                       "route_name", "city_actionable", "rank_city_actionable", "fsi_rate_spf_eb", "rank_spf_eb",
                       "ka_3y", "kabc_3y", "tot_3y", "aadt", "aadt_imputed", "speed_limit", "num_lanes",
                       "func_class", "legs", "signalized", "lon", "lat", "why")


def artifacts_directory():
    return Path(os.environ.get("ATSC_ARTIFACTS_DIR", Path(__file__).resolve().parents[1] / "data" / "artifacts"))


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


TEXT = {"site_id", "site_type", "road_name", "route_name", "jurisdiction", "why", "median_type", "memo_status"}


def _cast(row):
    out = {}
    for k, v in row.items():
        if k in TEXT:
            out[k] = v
        elif v == "":
            out[k] = None
        elif v in ("True", "False"):
            out[k] = v == "True"
        else:
            try:
                f = float(v)
                out[k] = int(f) if f.is_integer() and k in ("rank", "rank_spf_eb", "rank_city_actionable", "ka_3y", "kabc_3y",
                                                              "tot_3y", "aadt_imputed", "legs", "num_lanes") else f
            except ValueError:
                out[k] = v
    return out


@dataclass
class ArtifactRun:
    run_id: str
    path: Path
    manifest: dict
    rows: dict
    order: list
    features: dict
    backtest: dict
    explanations: dict
    history: dict
    memos: dict = field(default_factory=dict)
    memo_summary: dict | None = None
    _cache: dict = field(default_factory=dict)

    @property
    def is_demo(self):
        return False

    def summary(self):
        m = self.manifest
        return {"run_id": self.run_id, "created": m["created"], "published_at": m["created"],
                "code_version": m.get("commit"), "data_versions": m.get("data_versions"), "published": True,
                "model_name": f"S2 method C ({m['methods']['C']})", "risk_unit": "expected K+A crashes per mile per year",
                "is_demo": False, "site_count": len(self.order), "as_of": m.get("as_of"), "source": "artifact",
                "memo_counts": (self.memo_summary or {}).get("counts")}

    def memo_status(self, site_id):
        m = self.memos.get(site_id)
        return m["status"] if m else "none"

    def site_feature(self, site_id):
        f = self.features[site_id]
        props = {k: self.rows[site_id].get(k) for k in MAP_PROPS}
        props["memo_status"] = self.memo_status(site_id)
        return {"type": "Feature", "id": site_id, "geometry": f["geometry"], "properties": props}

    def collection_bytes(self, flagged=None):
        """Pre-serialized and gzipped FeatureCollection, cached per filter."""
        key = ("fc", flagged)
        if key not in self._cache:
            feats = [self.site_feature(s) for s in self.order if flagged is None or self.rows[s]["flagged"] == flagged]
            raw = json.dumps({"type": "FeatureCollection", "run_id": self.run_id, "features": feats},
                             separators=(",", ":")).encode()
            self._cache[key] = (raw, gzip.compress(raw, 6))
        return self._cache[key]


def load_run(path: Path) -> ArtifactRun:
    for name in REQUIRED:
        if not (path / name).is_file():
            raise ValueError(f"missing {name}")
    manifest = json.loads((path / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        p = path / name
        if name.startswith("models/") or not p.exists():
            if name in REQUIRED:
                raise ValueError(f"missing {name}")
            continue
        if _sha(p) != digest:
            raise ValueError(f"checksum mismatch: {name}")
    with open(path / "ranking.csv", newline="", encoding="utf-8") as f:
        rows = [_cast(r) for r in csv.DictReader(f)]
    for r in rows:
        r["site_id"] = str(r["site_id"])
    by_id = {r["site_id"]: r for r in rows}
    order = [r["site_id"] for r in sorted(rows, key=lambda r: r["rank"])]
    gj = json.loads((path / "sites.geojson").read_text())
    features = {str(f["properties"]["site_id"]): f for f in gj["features"]}
    if set(features) != set(by_id):
        raise ValueError("sites.geojson and ranking.csv disagree")
    expl = {}
    for e in json.loads((path / "explanations.json").read_text()):
        expl.setdefault(str(e["site_id"]), []).append(e)
    hist = json.loads((path / "site_history.json").read_text()) if (path / "site_history.json").is_file() else {}
    run = ArtifactRun(manifest["run_id"], path, manifest, by_id, order, features,
                      json.loads((path / "backtest.json").read_text()), expl, hist)
    memo_dir = path / "memos"
    if memo_dir.is_dir():
        for p in sorted(memo_dir.glob("*.json")):
            if p.name.endswith(".evidence.json") or p.name == "summary.json":
                continue
            memo = json.loads(p.read_text())
            sid = str(memo.get("site_id"))
            if sid in by_id:
                md = memo_dir / f"{sid}.md"
                memo["markdown"] = md.read_text() if md.is_file() and memo.get("status") == "draft" else None
                run.memos[sid] = memo
        if (memo_dir / "summary.json").is_file():
            run.memo_summary = json.loads((memo_dir / "summary.json").read_text())
    return run


_lock = threading.Lock()
_state = {"key": None, "runs": [], "invalid": 0}


def load_artifact_runs():
    """Runs sorted newest first. Reloaded when the folder listing changes."""
    root = artifacts_directory()
    dirs = sorted(p for p in root.glob("*/manifest.json")) if root.is_dir() else []
    key = tuple((str(p), p.stat().st_mtime_ns) for p in dirs) + tuple(
        (str(m), m.stat().st_mtime_ns) for p in dirs for m in [p.parent / "memos" / "summary.json"] if m.exists())
    with _lock:
        if key != _state["key"]:
            runs, invalid = [], 0
            for p in dirs:
                try:
                    runs.append(load_run(p.parent))
                except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
                    log.warning("Ignoring artifact run %s: %s", p.parent.name, exc)
                    invalid += 1
            runs.sort(key=lambda r: r.manifest["created"], reverse=True)
            _state.update(key=key, runs=runs, invalid=invalid)
        return _state["runs"], _state["invalid"]


def find_artifact_run(run_id):
    return next((r for r in load_artifact_runs()[0] if r.run_id == run_id), None)


def site_detail(run: ArtifactRun, site_id: str):
    row = run.rows[site_id]
    hist = run.history.get("sites", {}).get(site_id, {})
    fields = run.history.get("fields", [])
    years = run.history.get("years", [2016, 2025])
    by_year = [{"year": y, **dict(zip(fields, hist.get(str(y), [0] * len(fields))))} for y in range(years[0], years[1] + 1)]
    memo = run.memos.get(site_id)
    return {"run_id": run.run_id, "site_id": site_id, "feature": run.site_feature(site_id),
            "attributes": {k: row.get(k) for k in ("site_type", "road_name", "jurisdiction", "route_name", "length_mi",
                                                   "aadt", "aadt_imputed", "speed_limit", "num_lanes", "func_class",
                                                   "legs", "signalized", "median_type", "lon", "lat")},
            "prediction": {k: row.get(k) for k in ("fsi_rate", "annual_fsi", "annual_kabc", "rank", "rank_city_actionable",
                                                   "flagged", "in_hin", "mu", "k", "eb_weight", "n_eb", "p_fsi",
                                                   "fsi_rate_spf_eb", "rank_spf_eb", "annual_fsi_stack")},
            "crash_history": {"by_year": by_year, "fields": fields, "matched_crashes_only": True,
                              "last_3_years": {k: row.get(k) for k in ("ka_3y", "kabc_3y", "tot_3y", "angle_3y", "rear_end_3y",
                                                                       "single_vehicle_3y", "opposite_direction_3y", "night_3y", "wet_3y")}},
            "shap_factors": sorted(run.explanations.get(site_id, []), key=lambda e: e["rank"]),
            "memo_status": run.memo_status(site_id),
            "memo": None if memo is None else {k: memo.get(k) for k in ("memo_id", "status", "created", "model", "cost_usd", "seconds")}}


def backtest_summary(run: ArtifactRun):
    bt = run.backtest
    p = bt["primary"]
    def methods(sc):
        return [{"method": m, "label": bt["method_names"].get(m, m), "capture": v["capture"], "ci_low": v["ci_low"],
                 "ci_high": v["ci_high"], "n_test_fsi": v["n_test_fsi"], "flagged_miles": v.get("flagged_miles"),
                 "flagged_share": v.get("flagged_share")} for m, v in sc["methods"].items()]
    scenarios = [{"target": t, "scenario": s["scenario"], "length_basis": s["length_basis"],
                  "requested_share": s.get("requested_share"), "methods": methods(s), "differences": s["differences"]}
                 for t, lst in bt["targets"].items() for s in lst]
    return {"run_id": run.run_id, "training_cutoff": "2022-12-31", "test_window": "2023-2025",
            "protocol": bt.get("protocol"), "bootstrap": bt.get("bootstrap"),
            "methods": methods({"methods": p["methods"]}), "differences": p["differences"],
            "primary": {k: p[k] for k in ("target", "scenario", "length_basis")}, "scenarios": scenarios}


def ranking_csv(run: ArtifactRun, flagged=None):
    import io
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=("run_id",) + CSV_FIELDS)
    w.writeheader()
    for sid in run.order:
        r = run.rows[sid]
        if flagged is not None and r["flagged"] != flagged:
            continue
        row = {"run_id": run.run_id, **{k: r.get(k) for k in CSV_FIELDS}, "memo_status": run.memo_status(sid)}
        w.writerow({k: ("'" + v if isinstance(v, str) and v[:1] in "=+-@" else ("" if v is None else v)) for k, v in row.items()})
    return buf.getvalue()
