"""Offline orchestration only; all model calculations use the existing S2 implementation."""
from pathlib import Path
import os
import sys
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
import numpy as np
import pandas as pd
from S2_Risk_Model_Backtest.citywide import (combine, prediction_frame, ranking_table, ranking_hash,
    score_rank, evaluate, seeded_leakage_checks)
from S2_Risk_Model_Backtest.citywide_models import (Encoder, load_models, predict_all, predict_lgb,
    predict_share, eb_annual)
from S2_Risk_Model_Backtest.ranking import flag_by_length, fsi_rate, flagged_share
from S2_Risk_Model_Backtest.artifacts import file_hash
from S2_Risk_Model_Backtest.explain_text import describe
ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'cache'
BUNDLE = ROOT.parents[1] / 'integration/artifacts/s2-citywide-v1.1-2026-11-08'
COLORS = {'A': '#607495', 'B': '#888888', 'C': '#500000'}
def read_json(path):
    return json.loads(Path(path).read_text())
def load_live(mode='forecast'):
    cfg = read_json(BUNDLE/'config.json')
    meta = read_json(CACHE/'metadata.json')
    sites = pd.read_parquet(CACHE/'sites.parquet')
    fut = pd.read_parquet(CACHE/f'{mode}.parquet')
    enc = Encoder(meta['levels'][mode])
    directory = BUNDLE/'models' if mode == 'forecast' else CACHE/'backtest_models'
    models, rows, outs = {}, {}, {}
    for kind in ('segment','intersection'):
        F, w = load_models(read_json(directory/f'model_state_{kind}.json'), directory)
        models[kind] = F
        rows[kind] = fut[fut.site_type == kind].reset_index(drop=True)
        outs[kind] = predict_all(F, rows[kind], cfg, enc, w)
    preds, fut = combine(sites, outs, rows)
    table = ranking_table(sites, fut, preds, prediction_frame(sites,preds['ML-EB'],cfg),
                          prediction_frame(sites,preds['SPF+EB'],cfg),read_json(BUNDLE/'explanations.json'),cfg)
    return dict(cfg=cfg,sites=sites,fut=fut,enc=enc,models=models,preds=preds,table=table,meta=meta)
def integrity(live):
    manifest = read_json(BUNDLE/'manifest.json')
    errors = []
    for name, expected in manifest['files'].items():
        p = BUNDLE/name
        if not p.exists() or file_hash(p) != expected:
            errors.append(f'Bundle file differs: {name}')
    for name, expected in live['meta']['cache_hashes'].items():
        if file_hash(CACHE/name) != expected:
            errors.append(f'Cache file differs: {name}')
    actual = ranking_hash(live['table'])
    if actual != manifest['ranking_hash']:
        errors.append(f'Ranking hash differs: {actual} != {manifest["ranking_hash"]}')
    return actual, errors

def site_score(live, row):
    F = live['models'][row.site_type.iloc[0]]
    p = predict_all(F,row,live['cfg'],live['enc'])['ML-EB']
    X = live['enc'].frame(row,F['me']['feats'])
    contrib = np.mean([b.predict(X,pred_contrib=True,num_threads=2) for b in F['me']['boosters']],axis=0)[0]
    raw = np.array([b.predict(X,raw_score=True,num_threads=2)[0] for b in F['me']['boosters']])
    rates = live['preds']['ML-EB']['ka']/live['sites'].risk_length_mi.to_numpy()
    idx = int(np.flatnonzero(live['sites'].site_id.to_numpy()==row.site_id.iloc[0])[0])
    rates[idx] = fsi_rate(p['n_eb'],p['p_fsi'],row.risk_length_mi,1)[0]
    rank = score_rank(live['sites'].site_id.astype(int).to_numpy(),rates)
    flags = flag_by_length(rank,live['sites'].risk_length_mi.to_numpy(),share=live['cfg']['flag_share'])
    return dict(p=p,X=X,contrib=contrib,raw=raw,seed_mu=np.exp(raw)*row.exposure.iloc[0],
                rate=rates[idx],rank=int(rank[idx]),flagged=bool(flags[idx]),
                p_kabc=predict_share(F['s1'],row,live['cfg']['sev_prior_m'])[0],
                p_ka=predict_share(F['s2'],row,live['cfg']['sev_prior_m'])[0])

def masks_for(live,target,share):
    ids = live['sites'].site_id.astype(str).to_numpy()
    L = live['sites'].risk_length_mi.to_numpy()
    key = 'ka' if target=='KA' else 'kabc'
    result = {'A': set(ids[live['sites'].in_hin.astype(bool)])}
    for method,model in [('B','SPF+EB'),('C','ML-EB')]:
        ranks=score_rank(ids.astype(int),live['preds'][model][key]/L)
        result[method]=set(ids[flag_by_length(ranks,L,share,tolerance=None)])
    return result


def test_crash_records():
    """Cached 2023-2025 crashes in the frozen order; unmatched crashes keep site_id None."""
    t = pd.read_parquet(CACHE/'test_crashes.parquet')
    return [{**r, 'site_id': None if pd.isna(r['site_id']) else str(r['site_id'])} for r in t.to_dict('records')]

def snapshot_from_cache():
    """The frozen S1 snapshot rebuilt from the cache, for the leakage gate (no database)."""
    meta = read_json(CACHE/'snapshot_meta.json')
    def recs(name):
        df = pd.read_parquet(CACHE/name)
        return [{k: (None if (not isinstance(v, (list, dict)) and pd.isna(v)) else (v.item() if hasattr(v, 'item') else v))
                 for k, v in r.items()} for r in df.to_dict('records')]
    feats = recs('features.parquet')
    for f in feats:  # stored as text; numeric strings go back to numbers
        v = f['value']
        if isinstance(v, str):
            try: f['value'] = float(v)
            except ValueError: pass
    return {'metadata': meta, 'sites': recs('snapshot_sites.parquet'), 'features': feats,
            'history': recs('history.parquet'), 'test_crashes': test_crash_records()}
