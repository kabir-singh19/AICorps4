import pytest

from leakage import historical_date, iso_date
from train import load_config, normalize_snapshot
from make_demo import demo_snapshot


def test_cutoff_boundary():
    assert str(historical_date("2022-12-31","test")) == "2022-12-31"
    with pytest.raises(ValueError):
        historical_date("2023-01-01","test")


def test_snapshot_normalization_deterministic():
    original = demo_snapshot(n_sites=10)
    reversed_rows = {**original, **{key: list(reversed(original[key])) for key in ("sites","features","history","test_crashes")}}
    assert normalize_snapshot(original) == normalize_snapshot(reversed_rows)


def test_config_rejects_typos(tmp_path):
    path = tmp_path/"bad.json"
    path.write_text('{"future_feature": true}')
    with pytest.raises(ValueError):
        load_config(path)
