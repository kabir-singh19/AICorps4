from pathlib import Path

import pytest

from artifacts import file_hash, save_bundle, verify_bundle


class State:
    parameters = {"test": True}
    rounds = 1
    k = .5
    def to_dict(self):
        return {"test": True}
    def save(self,path):
        Path(path).write_bytes(b"test model bytes")


class Frame:
    def to_csv(self,path,**kwargs):
        Path(path).write_text("site_id,fsi_rate\ns1,0.5\n")
    def to_dict(self,orient):
        return [{"site_id": "s1", "fsi_rate": .5}]


def bundle_args():
    return dict(snapshot={"metadata": {"data_versions": {"test": "1"}, "network_version": "test-network", "length_policy": "test"}, "features": []},
                config={"seed": 1, "history_start": 2015, "history_end": 2022}, models={"B": State(), "C": State(), "severity": State()},
                encoder=State(), predictions={"B": Frame(), "C": Frame()}, explanations=[],
                backtest={}, calibration={}, diagnostics={"runtime_versions": {"test": "1"}},
                bit_records=[], code_version="test-code", duration=.1)


def test_successful_bundle_is_immutable_and_checksummed(tmp_path):
    saved = save_bundle(tmp_path,"test-run",verifier=lambda p: verify_bundle(p, require_complete=False),**bundle_args())
    manifest = verify_bundle(saved)
    assert not manifest["published"]
    assert (saved/"ml_model.ubj").exists()
    with pytest.raises(FileExistsError):
        save_bundle(tmp_path,"test-run",verifier=lambda _: None,**bundle_args())


def test_failed_reload_never_completes_new_run(tmp_path):
    def fail(_):
        raise RuntimeError("seeded artifact reload failure")
    with pytest.raises(RuntimeError):
        save_bundle(tmp_path,"failed",verifier=fail,**bundle_args())
    assert not (tmp_path/"failed").exists()
    assert not list(tmp_path.glob(".s2-staging-*"))


def test_previous_bundle_survives_next_failure(tmp_path):
    previous = save_bundle(tmp_path,"old",verifier=lambda _: None,**bundle_args())
    digest = file_hash(previous/"manifest.json")
    def fail(_):
        raise ValueError("new model failure")
    with pytest.raises(ValueError):
        save_bundle(tmp_path,"new",verifier=fail,**bundle_args())
    assert file_hash(previous/"manifest.json") == digest
