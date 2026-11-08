import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("xgboost")
from artifacts import canonical_json, load_models, save_bundle
from make_demo import demo_snapshot
from train import DEFAULT_CONFIG, fit_run, normalize_snapshot, prepare_inputs, make_predictions


def test_frozen_run_refit_is_exact_and_models_reload(tmp_path):
    config = {**DEFAULT_CONFIG, "rounds": 5, "threads": 1}
    snapshot = normalize_snapshot(demo_snapshot())
    first = fit_run(snapshot,config)
    second = fit_run(snapshot,config)
    records = lambda run: {m: f.to_dict("records") for m,f in run["predictions"].items()}
    assert canonical_json(records(first)) == canonical_json(records(second))
    assert first["backtest"] == second["backtest"]
    def reload_check(directory):
        encoder, models = load_models(directory, require_complete=False)
        sites, raw, _, totals = prepare_inputs(snapshot,config)
        pred = make_predictions(sites,models,encoder.transform(raw),totals,sites.risk_length_mi.to_numpy()*7,7)
        assert canonical_json({m:f.to_dict("records") for m,f in pred.items()}) == canonical_json(records(first))
    save_bundle(tmp_path,"test",snapshot,config,code_version="test",duration=1,verifier=reload_check,**first)
