"""Deterministic numeric/categorical preprocessing fitted on historical inputs only."""
from __future__ import annotations

import numpy as np
import pandas as pd


class FeatureEncoder:
    def fit(self, frame):
        if not isinstance(frame, pd.DataFrame) or frame.empty or frame.columns.duplicated().any():
            raise ValueError("nonempty feature frame with unique columns required")
        self.columns = sorted(frame.columns)
        self.numeric, self.categories, self.medians = [], {}, {}
        self.names, self.groups = [], {}
        for name in self.columns:
            s = frame[name]
            start = len(self.names)
            if pd.api.types.is_numeric_dtype(s):
                a = s.to_numpy(dtype=float)
                if np.isinf(a).any() or np.isnan(a).all():
                    raise ValueError(f"feature {name} has infinite or entirely missing values")
                self.numeric.append(name)
                self.medians[name] = float(np.nanmedian(a))
                self.names.extend([f"f{len(self.names)}", f"f{len(self.names)+1}"])
            else:
                self.categories[name] = sorted(set(s.dropna().astype(str)))
                # Two explicit categories for missing and previously unseen values.
                self.names.extend(f"f{i}" for i in range(start, start + len(self.categories[name]) + 2))
            self.groups[name] = list(range(start, len(self.names)))
        return self

    def transform(self, frame):
        if set(frame.columns) != set(self.columns):
            raise ValueError("feature columns differ from the fitted encoder")
        blocks = []
        for name in self.columns:
            s = frame[name]
            if name in self.numeric:
                a = pd.to_numeric(s, errors="raise").to_numpy(dtype=float)
                if np.isinf(a).any():
                    raise ValueError(f"feature {name} contains infinity")
                blocks.extend([np.where(np.isnan(a), self.medians[name], a), np.isnan(a).astype(float)])
            else:
                cats = self.categories[name]
                t = s.fillna("").astype(str)
                blocks.extend((t.eq(v) & s.notna()).to_numpy(dtype=float) for v in cats)
                blocks.extend([s.isna().to_numpy(dtype=float), (~t.isin(cats) & s.notna()).to_numpy(dtype=float)])
        return np.column_stack(blocks)

    def to_dict(self):
        return {k: getattr(self, k) for k in ("columns", "numeric", "categories", "medians", "names", "groups")}

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        for k, v in data.items():
            setattr(obj, k, v)
        return obj
