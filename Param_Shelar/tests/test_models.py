import warnings

import numpy as np
import pytest

from empirical_bayes import K_BOUNDS, eb_estimate, eb_weight, estimate_k
from nb_spf import NegativeBinomialSPF
from severity import SeverityModel, calibration_report


def test_eb_hand_calculations():
    result = eb_estimate([4, 4, 2, 10, 1], [10, 0, 2, 3, 6], [.5, .5, .5, .2, 1])
    np.testing.assert_allclose(result.weight, [1/3,1/3,1/2,1/3,1/2])
    np.testing.assert_allclose(result.expected, [8,4/3,2,16/3,3.5])


@pytest.mark.parametrize("mu,y,k", [([0],[1],.5), ([1],[-1],.5), ([1],[1.5],.5), ([1],[1],0), ([1,2],[1],.5)])
def test_eb_invalid_inputs(mu,y,k):
    with pytest.raises(ValueError):
        eb_estimate(mu,y,k)


def test_dispersion_recovers_nb_site_effect():
    rng = np.random.default_rng(5)
    mu = rng.uniform(.5,10,5000)
    true_k = .6
    y = rng.poisson(rng.gamma(1/true_k, true_k*mu))
    assert estimate_k(y,mu) == pytest.approx(true_k, rel=.12)


def test_nb_spf_offset_and_reload():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(800,2))
    exposure = rng.uniform(.4,1.2,800)
    mu = exposure*np.exp(.8 + .3*X[:,0]-.2*X[:,1])
    y = rng.poisson(rng.gamma(2,mu/2))
    model = NegativeBinomialSPF().fit(X,y,exposure)
    assert model.k == pytest.approx(.5, abs=.2)
    base = model.predict(X,exposure)
    np.testing.assert_allclose(model.predict(X,2*exposure),2*base)
    restored = NegativeBinomialSPF.from_dict(model.to_dict())
    np.testing.assert_array_equal(restored.predict(X,exposure),base)
    assert model.diagnostics["converged"]


def test_zero_network_cannot_fit_spf():
    with pytest.raises(ValueError):
        NegativeBinomialSPF().fit(np.ones((3,1)),[0,0,0],[1,1,1])


def test_severity_uses_crash_weights_and_reloads():
    X = np.zeros((3,2))
    model = SeverityModel().fit(X,[1,0,4],[2,20,8])
    np.testing.assert_allclose(model.predict(X),5/30,rtol=1e-6)
    restored = SeverityModel.from_dict(model.to_dict())
    np.testing.assert_array_equal(restored.predict(X),model.predict(X))


@pytest.mark.parametrize("fsi,expected", [([0,0],0), ([2,3],1)])
def test_severity_one_class_constant(fsi, expected):
    model = SeverityModel().fit(np.ones((2,2)),fsi,[2,3])
    np.testing.assert_array_equal(model.predict(np.ones((2,2))),[expected,expected])


def test_severity_requires_known_labels():
    with pytest.raises(ValueError):
        SeverityModel().fit(np.ones((2,2)),[0,0],[0,0])


def test_calibration_weighted_bins_and_brier():
    r = calibration_report([.1,.8],[1,8],[10,10])
    assert r["brier_score"] == pytest.approx(.125)
    assert r["bins"][0]["observed_fsi_fraction"] == .1


def test_ml_offset_and_exact_shap():
    pytest.importorskip("xgboost")
    from ml_risk import PoissonRiskModel
    X = np.arange(200,dtype=float).reshape(100,2)/100
    y = np.random.default_rng(9).poisson(2,size=100)
    e = np.full(100,.8)
    model = PoissonRiskModel(rounds=5).fit(X,y,e)
    p = model.predict(X,e)
    np.testing.assert_allclose(model.predict(X,2*e),2*p,rtol=1e-5)
    assert model.contributions(X,e).shape == (100,3)
