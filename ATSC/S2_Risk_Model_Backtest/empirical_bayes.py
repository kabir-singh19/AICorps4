"""Production EB functions shared with the exploratory notebook."""
from __future__ import annotations

import warnings
from typing import NamedTuple

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import gammaln

K_BOUNDS = (1e-4, 100.0)


class EBResult(NamedTuple):
    weight: np.ndarray
    expected: np.ndarray


def counts(values, name="counts"):
    a = np.asarray(values, dtype=float)
    if not a.size or not np.isfinite(a).all() or (a < 0).any() or (a != np.floor(a)).any():
        raise ValueError(f"{name} must contain finite nonnegative integer counts")
    return a


def positive(values, name):
    a = np.asarray(values, dtype=float)
    if not a.size or not np.isfinite(a).all() or (a <= 0).any():
        raise ValueError(f"{name} must be finite and positive")
    return a


def eb_weight(sum_mu, k):
    mu, dispersion = positive(sum_mu, "sum_mu"), positive(k, "k")
    with np.errstate(over="raise"):
        w = 1 / (1 + dispersion * mu)
    if not ((w > 0) & (w < 1)).all():
        raise ValueError("EB weights are outside (0, 1); check numerical scale")
    return w


def eb_estimate(sum_mu, sum_observed, k):
    mu, obs = positive(sum_mu, "sum_mu"), counts(sum_observed)
    if mu.shape != obs.shape:
        raise ValueError("predictions and observed totals must have identical shapes")
    w = eb_weight(mu, k)
    if w.shape != mu.shape:
        raise ValueError("k must be scalar or have one value per site")
    return EBResult(w, w * mu + (1 - w) * obs)


def nb_nll(log_k, y, mu):
    r = np.exp(-log_k)
    ll = (gammaln(y + r) - gammaln(r) - gammaln(y + 1)
          - r * np.log1p(mu / r) + y * (np.log(mu) - np.log(r + mu)))
    return -float(ll.sum())


def estimate_k(sum_observed, sum_mu):
    y, mu = counts(sum_observed).ravel(), positive(sum_mu, "sum_mu").ravel()
    if y.shape != mu.shape or len(y) < 2:
        raise ValueError("k estimation requires at least two aligned sites")
    fit = minimize_scalar(nb_nll, bounds=np.log(K_BOUNDS), args=(y, mu),
                          method="bounded", options={"xatol": 1e-8})
    if not fit.success or not np.isfinite(fit.fun):
        raise RuntimeError("overdispersion optimization failed")
    k = float(np.exp(fit.x))
    if k < K_BOUNDS[0] * 1.01 or k > K_BOUNDS[1] / 1.01:
        warnings.warn(f"dispersion k={k:.6g} reached a search bound", stacklevel=2)
    return k
