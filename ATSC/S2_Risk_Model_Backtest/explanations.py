"""Top-five source-feature TreeSHAP explanations on the ML log-count scale."""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_LABELS = {"speed_limit": {"label": "posted speed", "unit": "mph"},
                  "num_lanes": {"label": "traffic lanes"}, "aadt": {"label": "daily traffic", "unit": "vehicles/day"},
                  "legs": {"label": "intersection road legs"}, "site_type": {"label": "site type"},
                  "func_class": {"label": "road functional class code"}, "median_type": {"label": "median type code"}}


def top_factors(model, X, exposure, raw, encoder, sites, labels=None):
    if len(encoder.groups) < 5:
        raise ValueError("five source features required")
    descriptions = {**DEFAULT_LABELS, **(labels or {})}
    shap = model.contributions(X, exposure)
    rows = []
    for i, site in enumerate(sites.to_dict("records")):
        if not site["flagged"]:
            continue
        # Sum encoded columns first, so one categorical feature cannot fill all five slots.
        grouped = [(name, float(shap[i, columns].sum())) for name, columns in encoder.groups.items()]
        top = sorted(grouped, key=lambda v: (-abs(v[1]), v[0]))[:5]
        for rank, (name, contribution) in enumerate(top, 1):
            value = raw.iloc[i][name]
            spec = descriptions.get(name, {"label": name.replace("_", " ")})
            if pd.isna(value):
                phrase = f"{spec['label']} unavailable (historical imputation used)"
                displayed = None
            else:
                displayed = value.item() if isinstance(value, np.generic) else value
                text_value = spec.get("values", {}).get(str(displayed), str(displayed))
                phrase = f"{text_value} {spec.get('unit', '')} {spec['label']}".replace("  ", " ").strip()
            rows.append({"site_id": site["site_id"], "feature": name, "value": displayed,
                         "shap_value": contribution, "rank": rank, "description": phrase,
                         "direction": "increases" if contribution > 0 else "decreases" if contribution < 0 else "neutral",
                         "scale": "log predicted history crash count; before EB and severity",
                         "causal": False})
    return rows
