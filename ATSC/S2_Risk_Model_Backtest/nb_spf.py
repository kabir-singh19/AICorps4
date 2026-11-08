"""Locally fitted NB2 safety performance function with a length/year offset.

This implements the HSM NB-SPF/EB method, not published HSM coefficients or CMFs.
Dispersion is fitted on history-window totals to match the EB time scale.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

try:
    from .empirical_bayes import K_BOUNDS, counts, positive
except ImportError:
    from empirical_bayes import K_BOUNDS, counts, positive


class NegativeBinomialSPF:
    def __init__(self, ridge=0.01, max_iter=2000):
        if ridge < 0 or max_iter < 1:
            raise ValueError("invalid NB optimizer parameters")
        self.ridge, self.max_iter = float(ridge), int(max_iter)

    def fit(self, X, y, exposure):
        x, y, exposure = np.asarray(X, dtype=float), counts(y), positive(exposure, "exposure")
        if x.ndim != 2 or y.shape != (len(x),) or exposure.shape != y.shape or not np.isfinite(x).all():
            raise ValueError("NB inputs must be finite and aligned")
        if y.sum() == 0:
            raise ValueError("cannot fit an SPF to an entirely zero-crash network")
        self.mean = x.mean(axis=0)
        self.scale = x.std(axis=0)
        self.scale[self.scale == 0] = 1
        design = np.column_stack([np.ones(len(x)), (x - self.mean) / self.scale])
        offset = np.log(exposure)

        def objective(theta):
            eta = offset + design @ theta[:-1]
            mu = np.exp(eta)
            r = np.exp(-theta[-1])
            logden = np.logaddexp(np.log(r), eta)
            ll = gammaln(y+r) - gammaln(r) - gammaln(y+1) + r*(np.log(r)-logden) + y*(eta-logden)
            return -float(ll.sum()) + self.ridge * np.dot(theta[1:-1], theta[1:-1]) / 2

        start = np.zeros(design.shape[1] + 1)
        start[0], start[-1] = np.log(y.sum()/exposure.sum()), np.log(0.2)
        # Bound standardized coefficients to avoid exponential overflow during optimization.
        bounds = [(-20, 20)] * design.shape[1] + [tuple(np.log(K_BOUNDS))]
        fit = minimize(objective, start, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": self.max_iter, "ftol": 1e-10, "maxls": 50})
        if not fit.success or not np.isfinite(fit.fun):
            raise RuntimeError(f"NB-SPF optimization failed: {fit.message}")
        self.beta, self.k = fit.x[:-1], float(np.exp(fit.x[-1]))
        self.diagnostics = {"converged": True, "iterations": int(fit.nit), "objective": float(fit.fun),
                            "k_at_bound": bool(self.k < K_BOUNDS[0]*1.01 or self.k > K_BOUNDS[1]/1.01)}
        return self

    def predict(self, X, exposure):
        x, e = np.asarray(X, dtype=float), positive(exposure, "exposure")
        if x.ndim != 2 or x.shape[1] != len(self.mean) or e.shape != (len(x),) or not np.isfinite(x).all():
            raise ValueError("invalid NB prediction inputs")
        design = np.column_stack([np.ones(len(x)), (x-self.mean)/self.scale])
        mu = np.exp(np.log(e) + design @ self.beta)
        return positive(mu, "NB predictions")

    def to_dict(self):
        return {"ridge": self.ridge, "max_iter": self.max_iter, "mean": self.mean.tolist(),
                "scale": self.scale.tolist(), "beta": self.beta.tolist(), "k": self.k,
                "diagnostics": self.diagnostics}

    @classmethod
    def from_dict(cls, data):
        obj = cls(data["ridge"], data["max_iter"])
        for key in ("mean", "scale", "beta"):
            setattr(obj, key, np.asarray(data[key]))
        obj.k, obj.diagnostics = data["k"], data["diagnostics"]
        return obj
