import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import calc
from core import BUNDLE, CACHE, read_json, ranking_hash

needs_cache = pytest.mark.skipif(not (CACHE / "metadata.json").exists(), reason="run prepare.py first")


def test_eb_toy_hand_check():
    # k=0.2, sum_mu=4, observed=10: w = 1/1.8, EB = 4/1.8 + 10*0.8/1.8
    r = calc.eb_numbers(0.2, 1.0, 4, 10)
    assert r["w"] == pytest.approx(1 / 1.8)
    assert r["eb_total"] == pytest.approx(4 / 1.8 + 10 * (0.8 / 1.8))
    assert r["eb_per_year"] == pytest.approx(r["eb_total"] / 4)
    assert 0 < r["w"] < 1


def test_eb_matches_hand_formula_random():
    rng = np.random.default_rng(0)
    for _ in range(50):
        k, mu, h, obs = rng.uniform(0.01, 2), rng.uniform(0.05, 20), 5, int(rng.integers(0, 40))
        r = calc.eb_numbers(k, mu, h, obs)
        w, est = calc.eb_by_hand(k, h * mu, obs)
        assert r["w"] == pytest.approx(w) and r["eb_total"] == pytest.approx(est)


def test_eb_rejects_bad_inputs():
    with pytest.raises(ValueError):
        calc.eb_numbers(0.1, 1.0, 5, 2.5)  # non-integer observed count


def test_rate_per_mile():
    assert calc.rate_per_mile(0.9345, 1.0, 0.0473) == pytest.approx(0.9345 / 0.0473)
    with pytest.raises(ValueError):
        calc.rate_per_mile(1.0, 1.2, 0.1)  # probability above 1


def test_flag_share_and_prefix():
    ids = np.arange(1, 101)
    rate = np.linspace(10, 0, 100)
    length = np.full(100, 0.1)
    rank, flags, share = calc.flag_top_share(rate, ids, length, 0.11, tolerance=0.005)
    assert share == pytest.approx(0.11) and flags.sum() == 11
    assert set(np.flatnonzero(flags)) == set(np.flatnonzero(rank <= 11))


def test_hash_check():
    assert calc.hash_matches("abc", "abc") and not calc.hash_matches("abc", "abd")


def test_shap_sum_helper():
    ok, total = calc.shap_sums_to_raw(np.array([0.5, -0.2, 0.1, 1.0]), 1.4)
    assert ok and total == pytest.approx(1.4)
    assert not calc.shap_sums_to_raw(np.array([0.5, 0.5]), 2.0)[0]


def test_headline_follows_interval():
    assert calc.headline(-0.099, -0.152, -0.047) == "HIN better"
    assert calc.headline(0.012, -0.029, 0.058) == "statistical tie"
    assert calc.headline(0.053, 0.04, 0.065) == "C better"


@needs_cache
def test_live_hash_matches_manifest():
    from core import load_live, integrity
    live = load_live()
    actual, errors = integrity(live)
    assert errors == []
    assert actual == read_json(BUNDLE / "manifest.json")["ranking_hash"]
    assert calc.hash_matches(ranking_hash(live["table"]), actual)


@needs_cache
def test_real_site_shap_sums_to_raw_and_rank():
    from core import load_live, site_score
    live = load_live()
    i = int(np.flatnonzero(live["sites"].site_id.astype(str) == "17683")[0])
    row = live["fut"].iloc[[i]]
    sc = site_score(live, row)
    ok, total = calc.shap_sums_to_raw(sc["contrib"], sc["raw"].mean(), tol=1e-6)
    assert ok, total
    assert len(sc["contrib"]) - 1 == len(live["models"]["intersection"]["me"]["feats"])
    assert sc["rank"] == int(live["table"].set_index("site_id").loc["17683", "rank"])
    assert sc["p"]["mu"][0] == pytest.approx(float(np.exp(sc["raw"].mean()) * row.exposure.iloc[0]))
