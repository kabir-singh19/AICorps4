"""Fail-closed, dependency-free validation of the frozen S1/S2 contract."""
from __future__ import annotations

import math
from datetime import date

CUTOFF = date(2022, 12, 31)
FORBIDDEN_FEATURES = {"in_hin", "hin", "fsi_crashes", "crashes", "crash_count", "site_id",
                      "rank", "flagged", "fsi_rate", "n_eb", "p_fsi", "test_crashes"}


def iso_date(value, name):
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} requires an ISO date (YYYY-MM-DD)") from exc


def historical_date(value, name, cutoff=CUTOFF):
    result = iso_date(value, name)
    if result > cutoff:
        raise ValueError(f"leakage: {name}={result} exceeds {cutoff}")
    return result


def require(mapping, names, context):
    for name in names:
        if name not in mapping or mapping[name] is None or mapping[name] == "":
            raise ValueError(f"{context}: missing {name}")


def validate_snapshot(snapshot, feature_names, history_start=2015, history_end=2022):
    """Validate before importing model libraries or touching existing run outputs.

    Feature names are an explicit allowlist. No target/history aggregates are used
    as features; site crash history is used only as labels and in the EB blend.
    """
    require(snapshot, ("metadata", "sites", "features", "history", "test_crashes"), "snapshot")
    if not 2015 <= history_start <= history_end <= 2022:
        raise ValueError("history window must lie within 2015-2022")
    meta = snapshot["metadata"]
    require(meta, ("network_version", "feature_set", "analysis_scope", "length_policy",
                   "data_versions", "sources", "as_of_date", "history_years_loaded", "test_years_loaded"), "metadata")
    if meta["feature_set"] != "backtest_2022" or meta["analysis_scope"] != "college_station_public_roads":
        raise ValueError("backtest requires backtest_2022 and the complete College Station public-road scope")
    historical_date(meta["as_of_date"], "metadata.as_of_date")
    if not set(range(history_start, history_end+1)) <= set(meta["history_years_loaded"]):
        raise ValueError("history extract is missing required years, including zero-crash years")
    if not {2023, 2024, 2025} <= set(meta["test_years_loaded"]):
        raise ValueError("test extract must cover 2023-2025")
    if len(feature_names) < 5 or len(set(feature_names)) != len(feature_names):
        raise ValueError("at least five unique source features are required for top-five explanations")
    if any(n.lower() in FORBIDDEN_FEATURES or any(w in n.lower() for w in ("2023", "2024", "2025", "future", "target", "hin")) for n in feature_names):
        raise ValueError("outcome, HIN, identity or future features cannot enter the model")
    sources = {}
    for source in meta["sources"]:
        require(source, ("source", "version", "as_of_date", "available_as_of", "role"), "source")
        if source["source"] in sources:
            raise ValueError("duplicate source registry entry")
        if source["role"] not in {"predictor", "history", "evaluation", "baseline"}:
            raise ValueError("invalid source role")
        if source["role"] in {"predictor", "history"}:
            historical_date(source["as_of_date"], source["source"] + ".as_of_date")
            historical_date(source["available_as_of"], source["source"] + ".available_as_of")
        sources[source["source"]] = source
    if not sources or not meta["data_versions"]:
        raise ValueError("source versions and historical availability must be recorded")
    if not {"history", "evaluation"} <= {s["role"] for s in sources.values()}:
        raise ValueError("history and held-out evaluation source provenance are required")
    for value in (meta["network_version"], meta["length_policy"], *meta["data_versions"].values()):
        if not isinstance(value, str) or not value.strip() or value.upper().startswith(("REPLACE", "TBD")):
            raise ValueError("unresolved network, length-policy or data-version placeholder")
    sites = snapshot["sites"]
    if not sites:
        raise ValueError("analysis network is empty")
    ids = []
    for site in sites:
        require(site, ("site_id", "site_type", "risk_length_mi", "network_length_mi", "as_of_date"), "site")
        sid = str(site["site_id"])
        ids.append(sid)
        if site["site_type"] not in {"segment", "intersection"}:
            raise ValueError("site_type must be segment or intersection")
        historical_date(site["as_of_date"], f"site {sid}")
        for name in ("risk_length_mi", "network_length_mi"):
            value = site[name]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid {name} for site {sid}")
        if site["risk_length_mi"] <= 0:
            raise ValueError("positive approved risk exposure required for every site, including intersections")
        if "in_hin" in site and site["in_hin"] is not None and not isinstance(site["in_hin"], bool):
            raise ValueError("HIN membership must be boolean or unavailable")
    if len(set(ids)) != len(ids) or sum(s["network_length_mi"] for s in sites) <= 0:
        raise ValueError("duplicate site IDs or zero total network length")
    id_set = set(ids)
    keys = set()
    for feature in snapshot["features"]:
        require(feature, ("site_id", "feature_name", "as_of_date", "source"), "feature")
        sid, name = str(feature["site_id"]), feature["feature_name"]
        if sid not in id_set:
            raise ValueError("feature references a site outside the frozen network")
        key = (sid, name)
        if key in keys:
            raise ValueError("duplicate site feature")
        keys.add(key)
        historical_date(feature["as_of_date"], f"{sid}.{name}")
        src = sources.get(feature["source"])
        if not src or src["role"] != "predictor":
            raise ValueError("feature lacks registered historical predictor provenance")
        if "value" not in feature:
            raise ValueError("feature must contain value; null explicitly represents missing data")
        value = feature["value"]
        if value is not None and not isinstance(value, (int, float, str, bool)):
            raise ValueError("feature values must be numeric, text, boolean or null")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("use null for missing feature values, never NaN/infinity")
    expected = {(sid, name) for sid in ids for name in feature_names}
    if not expected <= keys:
        raise ValueError(f"feature coverage incomplete: {len(expected-keys)} missing site-feature records")
    history_keys = set()
    for row in snapshot["history"]:
        require(row, ("site_id", "year", "crashes", "known_crashes", "fsi_crashes"), "history")
        if isinstance(row["year"], bool) or not isinstance(row["year"], int):
            raise ValueError("history year must be an integer")
        key = (str(row["site_id"]), row["year"])
        if key[0] not in id_set or key in history_keys or not history_start <= row["year"] <= history_end:
            raise ValueError("duplicate, out-of-network or post-cutoff history row")
        history_keys.add(key)
        for name in ("crashes", "known_crashes", "fsi_crashes"):
            v = row[name]
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError("history counts must be nonnegative integers")
        if not row["fsi_crashes"] <= row["known_crashes"] <= row["crashes"]:
            raise ValueError("history must satisfy F&SI <= known-severity <= total")
    # Zero-crash combinations may be absent; only explicitly loaded years are zero-filled.
    seen = set()
    for row in snapshot["test_crashes"]:
        require(row, ("crash_id", "crash_date", "severity", "in_analysis_area"), "test crash")
        cid = str(row["crash_id"])
        when = iso_date(row["crash_date"], "crash_date")
        if cid in seen or not date(2023, 1, 1) <= when <= date(2025, 12, 31):
            raise ValueError("duplicate crash or crash date outside held-out window")
        seen.add(cid)
        if row["severity"] not in {"K", "A", "B", "C", "O", "U"}:
            raise ValueError("invalid test severity")
        if not isinstance(row["in_analysis_area"], bool):
            raise ValueError("explicit in-area membership required, including unmatched crashes")
        if row.get("site_id") is not None and str(row["site_id"]) not in id_set:
            raise ValueError("test crash references an unknown site")
    hin = [s.get("in_hin") for s in sites]
    if any(v is not None for v in hin) and any(v is None for v in hin):
        raise ValueError("HIN mapping is partial; require full membership or entirely unavailable")
    if all(v is not None for v in hin):
        require(meta, ("hin_version", "hin_source", "hin_as_of_date"), "HIN provenance")
        src = sources.get(meta["hin_source"])
        if not src or src["role"] != "baseline":
            raise ValueError("published HIN needs a registered baseline source")
        # Consultant publication can be later, but its crash data window cannot be later.
        historical_date(meta["hin_as_of_date"], "HIN crash-history cutoff")
    return {"sites": len(sites), "features": len(snapshot["features"]),
            "history_rows": len(history_keys), "test_crashes": len(seen),
            "hin_available": all(v is not None for v in hin)}
