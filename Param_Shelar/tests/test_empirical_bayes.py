import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from empirical_bayes import K_BOUNDS, eb_estimate, eb_weight, estimate_k  # noqa: E402


def test_hand_checked_toy_example():
    # FSR 3.2.1.7 hand check. k = 0.5, predicted 4 crashes, observed 10 over the history years:
    # w = 1 / (1 + 0.5 * 4) = 1/3, and n_eb = (1/3) * 4 + (2/3) * 10 = 8.
    result = eb_estimate([4.0], [10], 0.5)
    assert result.weight[0] == pytest.approx(1 / 3)
    assert result.expected[0] == pytest.approx(8.0)


def test_weights_strictly_between_zero_and_one():
    rng = np.random.default_rng(0)
    w = eb_weight(rng.uniform(0.01, 50, 1000), rng.uniform(0.01, 5, 1000))
    assert np.all((w > 0) & (w < 1))


def test_estimate_lies_between_prediction_and_observation():
    mu = np.array([2.0, 2.0, 5.0, 0.5])
    obs = np.array([0, 9, 5, 3])
    n_eb = eb_estimate(mu, obs, 0.8).expected
    assert np.all(n_eb >= np.minimum(mu, obs))
    assert np.all(n_eb <= np.maximum(mu, obs))


def test_more_predicted_history_trusts_the_site_more():
    w = eb_weight([0.5, 2.0, 10.0], 0.5)
    assert w[0] > w[1] > w[2]


def test_per_site_k_is_accepted():
    k = 0.236 / np.array([0.1, 0.2])  # HSM-style length-scaled k
    w = eb_weight([1.0, 1.0], k)
    assert w == pytest.approx(1 / (1 + k))


@pytest.mark.parametrize("bad", [
    {"sum_mu": [0.0], "sum_observed": [1], "k": 0.5},
    {"sum_mu": [1.0], "sum_observed": [1], "k": 0.0},
    {"sum_mu": [1.0], "sum_observed": [-1], "k": 0.5},
    {"sum_mu": [1.0], "sum_observed": [1.5], "k": 0.5},
    {"sum_mu": [np.nan], "sum_observed": [1], "k": 0.5},
    {"sum_mu": [1.0, 2.0], "sum_observed": [1], "k": 0.5},
])
def test_invalid_inputs_are_rejected(bad):
    with pytest.raises(ValueError):
        eb_estimate(**bad)


def _simulate_site_totals(k, n_sites, seed):
    rng = np.random.default_rng(seed)
    mu = rng.uniform(0.5, 6.0, n_sites)
    lam = mu if k == 0 else rng.gamma(shape=1 / k, scale=k * mu)
    return rng.poisson(lam), mu


def test_estimate_k_recovers_known_overdispersion():
    y, mu = _simulate_site_totals(k=0.6, n_sites=20_000, seed=1)
    assert estimate_k(y, mu) == pytest.approx(0.6, abs=0.05)


def test_estimate_k_is_near_zero_when_data_are_poisson():
    y, mu = _simulate_site_totals(k=0, n_sites=5_000, seed=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # may or may not land on the bound, depending on noise
        assert estimate_k(y, mu) < 0.02


def test_estimate_k_warns_when_there_is_no_overdispersion():
    mu = np.random.default_rng(4).uniform(0.5, 6.0, 1_000)
    y = np.round(mu)  # less spread than Poisson
    with pytest.warns(UserWarning, match="no overdispersion"):
        k = estimate_k(y, mu)
    assert k == pytest.approx(K_BOUNDS[0], rel=0.01)


def test_estimate_k_does_not_warn_on_normal_data():
    y, mu = _simulate_site_totals(k=0.4, n_sites=5_000, seed=3)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        estimate_k(y, mu)
