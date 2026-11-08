"""Leakage and label checks for the citywide panel (no database needed)."""
import numpy as np
import pandas as pd
import pytest
from scipy.sparse import csr_matrix

from S2_Risk_Model_Backtest.panel import TYPE_FLAGS, build_panel
from S2_Risk_Model_Backtest.backtest import bootstrap_capture
from S2_Risk_Model_Backtest.explain_text import describe


def crashes(rows):
    c = pd.DataFrame(rows, columns=["site_id", "date", "severity"])
    c["date"] = pd.to_datetime(c["date"])
    c["year"] = c["date"].dt.year
    c["tot"] = 1
    c["kabc"] = c.severity.isin(list("KABC")).astype(int)
    c["ka"] = c.severity.isin(list("KA")).astype(int)
    c["known"] = (c.severity != "U").astype(int)
    for f in TYPE_FLAGS:
        c[f] = 0
    return c


STATIC = pd.DataFrame({"site_id": ["1", "2"], "site_type": ["segment", "segment"]})
NB = csr_matrix(np.array([[0, 1], [1, 0]], float))


def test_history_ends_before_label_year():
    c = crashes([("1", "2020-05-01", "A"), ("1", "2021-12-31", "B"), ("2", "2022-01-01", "O")])
    p = build_panel(STATIC, c, [2021, 2022], 2016, 5, NB, "2022-12-31")
    r21 = p[(p.site_id == "1") & (p.year == 2021)].iloc[0]
    assert r21.ka_5y == 1 and r21.kabc_5y == 1 and r21.y_kabc == 1  # 2021 crash is a label, not history
    r22 = p[(p.site_id == "2") & (p.year == 2022)].iloc[0]
    assert r22.tot_3y == 0 and r22.y_tot == 1 and r22.nb_kabc_3y == 2


def test_crash_after_cutoff_refused():
    c = crashes([("1", "2023-02-01", "K")])
    with pytest.raises(ValueError, match="leakage"):
        build_panel(STATIC, c, [2022], 2016, 5, NB, "2022-12-31")


def test_forecast_row_has_no_label():
    c = crashes([("1", "2025-06-01", "A")])
    p = build_panel(STATIC, c, [2026], 2016, 5, NB, "2025-12-31")
    assert not p.labeled.any() and p.ka_3y.sum() == 1


def test_kabc_target_and_extra_pairs():
    test = [{"crash_id": str(i), "in_analysis_area": True, "severity": s, "site_id": site}
            for i, (s, site) in enumerate([("A", "1"), ("B", "2"), ("C", "2"), ("O", "1"), ("K", None)])]
    rep = bootstrap_capture(test, {"A": {"1"}, "B": {"2"}, "C": {"1", "2"}, "X": set()}, 1000, 1,
                            severities={"K", "A", "B", "C"}, pairs=[("X", "A")])
    assert rep["target"] == "KABC" and rep["n_test_fsi"] == 4
    assert rep["methods"]["C"]["capture"] == 0.75 and "X-A" in rep["differences"]


def test_plain_language():
    assert describe("speed_limit", 45.0, 0) == "45 mph speed limit"
    assert describe("func_class", "4", 0) == "functional class: minor arterial"
    assert describe("traffic", None, 12345.0) == "traffic exposure (12,345 vehicles/day)"
    assert describe("lane_width_ft", float("nan"), 0) == "lane width ft not recorded"
