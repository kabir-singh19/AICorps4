import pytest

pd = pytest.importorskip("pandas")
from backtest import evaluate


def test_equal_length_fairness_and_total_sensitivity():
    ids = [str(i) for i in range(100)]
    frame = pd.DataFrame({"site_id": ids, "rank": list(range(1,101)), "network_length_mi": [.1]*100,
                          "flagged": [i<11 for i in range(100)]})
    crashes = [{"crash_id": str(i), "site_id": str(i), "in_analysis_area": True, "severity": "K" if i<10 else "O"} for i in range(100)]
    report = evaluate({"B": frame, "C": frame},crashes,{str(i) for i in range(20)})
    assert report["primary"]["methods"]["A"]["flagged_share"] == pytest.approx(.2)
    assert any(r["requested_share"] == pytest.approx(.2) and r["target"] == "total" for r in report["sensitivity"])
    assert report["primary"]["differences"]["B-A"] == report["primary"]["differences"]["C-A"]


def test_missing_hin_is_not_fabricated():
    frame = pd.DataFrame({"site_id": [str(i) for i in range(100)], "rank": list(range(1,101)),
                          "network_length_mi": [.1]*100, "flagged": [i<11 for i in range(100)]})
    report = evaluate({"B": frame, "C": frame},[],None)
    assert "A" not in report["primary"]["methods"]
    assert report["primary"]["hin_available"] is False
