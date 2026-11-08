"""Crash-weighted binomial severity model; unknown severity never counts as a negative."""
from __future__ import annotations

import numpy as np
from scipy.special import expit
from scipy.optimize import minimize

try:
    from .empirical_bayes import counts
except ImportError:
    from empirical_bayes import counts


class SeverityModel:
    def __init__(self, seed=42, C=1.0):
        if C <= 0:
            raise ValueError("severity regularization C must be positive")
        self.seed, self.C = seed, C

    def fit(self, X, fsi, known):
        x, f, n = np.asarray(X, dtype=float), counts(fsi), counts(known)
        if x.ndim != 2 or f.shape != n.shape or f.shape != (len(x),) or (f > n).any() or n.sum() == 0:
            raise ValueError("severity requires aligned K/A and known-severity counts")
        if not np.isfinite(x).all():
            raise ValueError("severity features must be finite")
        self.mean, self.scale = x.mean(axis=0), x.std(axis=0)
        self.scale[self.scale == 0] = 1
        z = (x-self.mean)/self.scale
        self.constant = float(f.sum()/n.sum()) if f.sum() in (0, n.sum()) else None
        if self.constant is None:
            design = np.column_stack([np.ones(len(x)), z])
            def objective(beta):
                eta = design @ beta
                loss = np.sum(n*np.logaddexp(0, eta)-f*eta) + np.dot(beta[1:], beta[1:])/(2*self.C)
                gradient = design.T @ (n*expit(eta)-f)
                gradient[1:] += beta[1:]/self.C
                return float(loss), gradient
            start = np.zeros(design.shape[1])
            prevalence = f.sum()/n.sum()
            start[0] = np.log(prevalence/(1-prevalence))
            fit = minimize(objective, start, jac=True, method="L-BFGS-B",
                           options={"maxiter": 2000, "ftol": 1e-12})
            if not fit.success or not np.isfinite(fit.fun):
                raise RuntimeError(f"severity optimizer did not converge: {fit.message}")
            self.coef, self.intercept = fit.x[1:], float(fit.x[0])
        return self

    def predict(self, X):
        x = np.asarray(X, dtype=float)
        if x.ndim != 2 or x.shape[1] != len(self.mean) or not np.isfinite(x).all():
            raise ValueError("invalid severity prediction inputs")
        if self.constant is not None:
            return np.full(len(x), self.constant)
        return expit(((x-self.mean)/self.scale) @ self.coef + self.intercept)

    def to_dict(self):
        return {"seed": self.seed, "C": self.C, "mean": self.mean.tolist(), "scale": self.scale.tolist(),
                "constant": self.constant, "coef": None if self.constant is not None else self.coef.tolist(),
                "intercept": None if self.constant is not None else self.intercept}

    @classmethod
    def from_dict(cls, data):
        obj = cls(data["seed"], data["C"])
        obj.mean, obj.scale = np.array(data["mean"]), np.array(data["scale"])
        obj.constant = data["constant"]
        if obj.constant is None:
            obj.coef, obj.intercept = np.array(data["coef"]), data["intercept"]
        return obj


def calibration_report(probabilities, fsi, known, bins=10):
    p, f, n = np.asarray(probabilities), counts(fsi), counts(known)
    if p.shape != f.shape or f.shape != n.shape or (f > n).any() or not np.isfinite(p).all() or ((p < 0)|(p > 1)).any():
        raise ValueError("invalid calibration inputs")
    if n.sum() == 0:
        return {"status": "undefined: no known-severity validation crashes", "bins": []}
    membership = np.minimum((p*bins).astype(int), bins-1)
    rows = []
    for i in range(bins):
        mask = membership == i
        total = n[mask].sum()
        if total:
            rows.append({"bin": i, "known_crashes": int(total),
                         "mean_prediction": float(np.sum(p[mask]*n[mask])/total),
                         "observed_fsi_fraction": float(f[mask].sum()/total)})
    brier = float(np.sum(f*(1-p)**2 + (n-f)*p**2)/n.sum())
    return {"status": "ok", "bins": rows, "brier_score": brier, "known_crashes": int(n.sum())}
