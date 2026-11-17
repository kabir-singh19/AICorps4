"""One-time, read-only S2 snapshot cache; never emits database credentials."""
from core import *
from S2_Risk_Model_Backtest.database import load_snapshot, load_context
from S2_Risk_Model_Backtest.leakage import validate_snapshot
from S2_Risk_Model_Backtest.train import normalize_snapshot
from S2_Risk_Model_Backtest.panel import static_frame, neighbor_matrix, crash_frame, build_panel
from S2_Risk_Model_Backtest.citywide import fit_predict
from S2_Risk_Model_Backtest.citywide_models import save_boosters, model_state

def main():
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--refresh',action='store_true')
    args=ap.parse_args()
    if (CACHE/'metadata.json').exists() and not args.refresh:
        live=load_live(); actual,errors=integrity(live)
        print(json.dumps({'cache':'existing','ranking_hash':actual,'errors':errors}))
        return 1 if errors else 0
    cfg=read_json(BUNDLE/'config.json')
    if cfg != read_json(ROOT.parent/'config/citywide_v1_2022.json'):
        raise ValueError('Frozen bundle and source config differ')
    if not os.environ.get('DATABASE_URL'):
        secret=BUNDLE.parents[1]/'secrets/s2_password'
        os.environ['DATABASE_URL']='postgresql://s2_reader:'+secret.read_text().strip()+'@localhost:5432/tasc'
    # Check identity and read-only setting without displaying the URL or driver errors.
    import psycopg
    try:
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            if conn.execute('SELECT current_user').fetchone()[0]!='s2_reader':
                raise ValueError('Must connect as s2_reader')
        snapshot=load_snapshot(cfg['database'],cfg['features'],cfg['history_start'],cfg['history_end'])
        gate=validate_snapshot(snapshot,cfg['features'],cfg['history_start'],cfg['history_end'])
        seeded=seeded_leakage_checks(snapshot,cfg['features'])
        if not all(c['detected'] for c in seeded): raise ValueError('Seeded leakage check failed')
        ctx=load_context(cfg['database'],'2025-12-31')
    except Exception:
        raise RuntimeError('Read-only S2 database preparation failed; check s2_reader access and S2 views (credentials suppressed)') from None
    CACHE.mkdir(exist_ok=True)
    norm=normalize_snapshot(snapshot)
    static=static_frame(norm,ctx)
    nb,_=neighbor_matrix(static,cfg['neighbor_m'])
    sites=static[['site_id','site_type','risk_length_mi','network_length_mi','road_name','in_hin']].copy()
    sites.to_parquet(CACHE/'sites.parquet',index=False)
    pd.DataFrame(snapshot['features']).assign(value=lambda x:x.value.map(lambda v: None if v is None else str(v))).to_parquet(CACHE/'features.parquet',index=False)
    # Normalized order matters: the paired bootstrap draws crash indices, so order must match the frozen run.
    pd.DataFrame(norm['test_crashes']).to_parquet(CACHE/'test_crashes.parquet',index=False)
    pd.DataFrame(norm['metadata']['sources']).to_parquet(CACHE/'sources.parquet',index=False)
    pd.DataFrame(norm['history']).to_parquet(CACHE/'history.parquet',index=False)
    pd.DataFrame(norm['sites']).to_parquet(CACHE/'snapshot_sites.parquet',index=False)
    (CACHE/'snapshot_meta.json').write_text(json.dumps(norm['metadata'],indent=1,default=str))
    levels={}
    for mode,year,cutoff in [('forecast',2026,'2025-12-31'),('backtest',2023,'2022-12-31')]:
        subset={**ctx,'crashes':[c for c in ctx['crashes'] if c['crash_date']<=cutoff]}
        years=list(range(cfg['first_label_year'],year))
        panel=build_panel(static,crash_frame(subset),years+[year],cfg['history_start'],cfg['hist_years_long'],nb,cutoff)
        enc=Encoder().fit(panel)
        levels[mode]=enc.levels
        fut=panel[panel.year==year].reset_index(drop=True)
        fut.to_parquet(CACHE/f'{mode}.parquet',index=False)
        if mode=='backtest':
            print('Fitting frozen-2022 backtest through existing S2 functions; no forecast model is retrained.',flush=True)
            _,fits,_,_=fit_predict(panel,years,year,cfg,lambda *a,**kw:None)
            directory=CACHE/'backtest_models'; directory.mkdir(exist_ok=True)
            for kind,(F,w) in fits.items():
                save_boosters(F,directory)
                (directory/f'model_state_{kind}.json').write_text(json.dumps(model_state(F,w)))
    metadata={'levels':levels,'gate':gate,'seeded_leakage_checks':seeded,
              'cache_hashes':{str(p.relative_to(CACHE)):file_hash(p) for p in CACHE.rglob('*') if p.is_file() and p.name!='metadata.json'}}
    (CACHE/'metadata.json').write_text(json.dumps(metadata,indent=2))
    fc=load_live(); actual,errors=integrity(fc)
    bt=load_live('backtest')
    report=evaluate(bt['sites'],bt['preds'],test_crash_records(),cfg)
    frozen=read_json(BUNDLE/'backtest.json')
    matches=all(report['targets'][t]==frozen['targets'][t] for t in ('KA','KABC'))
    result={'ranking_hash':actual,'errors':errors,'backtest_targets_match':matches,'sites':len(sites)}
    (ROOT/'preparation_result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    return 1 if errors or not matches else 0
if __name__=='__main__':
    raise SystemExit(main())
