"""Pure helpers for the demo. Each one calls the existing S2 function; none re-implements the model."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from S2_Risk_Model_Backtest.empirical_bayes import eb_estimate, eb_weight
from S2_Risk_Model_Backtest.ranking import fsi_rate, flag_by_length, flagged_share, rank_sites


def eb_numbers(k, mu_per_year, hist_years, observed):
    """Everything the EB page shows. mu_per_year is LightGBM's yearly mean; the blend works on the window total."""
    sum_mu = float(hist_years * mu_per_year)
    res = eb_estimate(np.array([sum_mu]), np.array([float(observed)]), k)
    w, est = float(res.weight[0]), float(res.expected[0])
    return {"k": float(k), "sum_mu": sum_mu, "observed": float(observed), "w": w,
            "eb_total": est, "eb_per_year": est / hist_years, "hist_years": int(hist_years)}


def eb_by_hand(k, sum_mu, observed):
    w = 1.0 / (1.0 + k * sum_mu)
    return w, w * sum_mu + (1 - w) * observed


def rate_per_mile(eb_per_year, p_fsi, length_mi):
    return float(np.atleast_1d(fsi_rate(eb_per_year, p_fsi, length_mi, 1))[0])


def flag_top_share(rate, ids, length_mi, share, tolerance=None):
    rank = rank_sites(ids, rate)
    flags = flag_by_length(rank, length_mi, share=share, tolerance=tolerance)
    return rank, flags, flagged_share(flags, length_mi)


def hash_matches(actual, expected):
    return actual == expected


def shap_sums_to_raw(contrib_with_base, raw_score, tol=1e-9):
    """LightGBM pred_contrib rows end with the base value; the row must add up to the raw score."""
    total = float(np.sum(contrib_with_base))
    return abs(total - float(raw_score)) <= tol, total


def headline(diff, lo, hi, a_name="HIN", c_name="C"):
    """Wording that follows the interval, not the point estimate."""
    if hi < 0:
        return f"{a_name} better"
    if lo > 0:
        return f"{c_name} better"
    return "statistical tie"
