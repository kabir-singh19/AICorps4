"""Empirical Bayes correction for methods B and C (FSR 3.2.1.7, HSM Part B).

EB blends each site's model prediction with its own crash history so that sites with a few
unlucky years are pulled back toward what similar sites experience (regression to the mean):

    w    = 1 / (1 + k * sum_mu)
    n_eb = w * sum_mu + (1 - w) * sum_observed

Units: every input and output here is a per-site total over the same history window (for
the backtest, the training years ending 31 Dec 2022), not a per-year value. Divide n_eb by the
number of history years to get crashes per year; the per-mile F&SI rate is built in ranking.py.

Overdispersion: k comes from Var(y) = mu + k * mu**2 on those site totals. Method B takes k
from its fitted negative binomial SPF. Method C has a Poisson model with no k of its own, so
estimate_k() fits one by maximum likelihood with the predictions held fixed. Pass out-of-fold
predictions for C: in-sample boosted predictions sit too close to the observed counts and
understate k, which pushes w toward 1 and switches the correction off.

k may be a single value or one value per site, so a length-scaled k (HSM segment SPFs use
k = k0 / L) can be passed without changing this module.
"""

from __future__ import annotations

import warnings
from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike
from scipy.optimize import minimize_scalar
from scipy.special import gammaln

# Search range for k in estimate_k(). Below 1e-4 the data are effectively Poisson; above 100
# a single site's history carries almost all the weight.
K_BOUNDS = (1e-4, 100.0)


class EBResult(NamedTuple):
    weight: np.ndarray    # w per site, strictly between 0 and 1
    expected: np.ndarray  # n_eb per site, crashes over the history window


def eb_weight(sum_mu: ArrayLike, k: ArrayLike) -> np.ndarray:
    """Return the EB weight w = 1 / (1 + k * sum_mu) for each site."""
    mu = _positive(sum_mu, "sum_mu")
    k_arr = _positive(k, "k")
    return 1.0 / (1.0 + k_arr * mu)


def eb_estimate(sum_mu: ArrayLike, sum_observed: ArrayLike, k: ArrayLike) -> EBResult:
    """Blend predicted and observed crash totals for each site."""
    mu = _positive(sum_mu, "sum_mu")
    obs = _counts(sum_observed, "sum_observed")
    if mu.shape != obs.shape:
        raise ValueError(f"sum_mu has shape {mu.shape} but sum_observed has shape {obs.shape}")
    w = eb_weight(mu, k)
    return EBResult(weight=w, expected=w * mu + (1.0 - w) * obs)


def estimate_k(sum_observed: ArrayLike, sum_mu: ArrayLike) -> float:
    """Fit the overdispersion k by maximum likelihood with the predictions held fixed.

    Uses the negative binomial (NB2) likelihood on per-site totals. Warns if the fit lands on
    the lower bound, which means the data show no overdispersion beyond Poisson.
    """
    y = _counts(sum_observed, "sum_observed").ravel()
    mu = _positive(sum_mu, "sum_mu").ravel()
    if y.shape != mu.shape:
        raise ValueError(f"sum_observed has {y.size} sites but sum_mu has {mu.size}")
    if y.size < 2:
        raise ValueError("estimate_k needs at least two sites")

    def neg_log_likelihood(log_k: float) -> float:
        r = np.exp(-log_k)  # NB size parameter, r = 1 / k
        ll = (gammaln(y + r) - gammaln(r) - gammaln(y + 1)
              - r * np.log1p(mu / r) + y * (np.log(mu) - np.log(r + mu)))
        return -float(ll.sum())

    lo, hi = np.log(K_BOUNDS[0]), np.log(K_BOUNDS[1])
    fit = minimize_scalar(neg_log_likelihood, bounds=(lo, hi), method="bounded",
                          options={"xatol": 1e-8})
    k = float(np.exp(fit.x))
    if fit.x - lo < 1e-3:
        warnings.warn(f"estimate_k hit the lower bound ({K_BOUNDS[0]}): no overdispersion "
                      "found, so EB weights will be close to 1", stacklevel=2)
    elif hi - fit.x < 1e-3:
        warnings.warn(f"estimate_k hit the upper bound ({K_BOUNDS[1]}): check the predictions",
                      stacklevel=2)
    return k


def _positive(values: ArrayLike, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(arr)) or np.any(arr <= 0):
        raise ValueError(f"{name} must be finite and greater than 0")
    return arr


def _counts(values: ArrayLike, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(arr)) or np.any(arr < 0) or np.any(arr != np.floor(arr)):
        raise ValueError(f"{name} must be non-negative whole-number crash counts")
    return arr
