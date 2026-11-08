import React, { useMemo, useState } from 'react';
import { runPath, useApi } from '../api.js';

export function ModelRuns({ resource, runs, activeRun, onChange, onRefresh }) {
  return <section className="card model-controls" aria-label="Model run selection">
    <div className="details-heading"><label htmlFor="model-run">Published model run</label><button onClick={onRefresh} disabled={resource.loading}>Refresh runs</button></div>
    <select id="model-run" value={activeRun?.run_id || ''} onChange={event => onChange(event.target.value)} disabled={!runs.length || resource.loading}>
      {!runs.length && <option value="">No published runs</option>}
      {runs.map(run => <option key={run.run_id} value={run.run_id}>{run.model_name} · {run.run_id}{run.is_demo ? ' · EXAMPLE DATA' : ''}</option>)}
    </select>
    {resource.loading && <p role="status">Loading published runs…</p>}
    {resource.error && <p role="alert" className="api-error">{resource.error}</p>}
    {!resource.loading && !resource.error && !runs.length && <p>No model results have been published yet.</p>}
    {activeRun && <p>Published {new Date(activeRun.published_at).toLocaleString()} · {activeRun.site_count} sites · {activeRun.risk_unit}{activeRun.as_of ? ` · data as of ${activeRun.as_of.crashes_through || activeRun.as_of.last_crash_date || ''}` : ''}</p>}
    {activeRun?.is_demo && <p className="demo-label">Example data, not real predictions or engineering recommendations.</p>}
  </section>;
}

const exportBase = run => `/api/v1/export/sites`;

export function RankedSites({ resource, run, onSelect }) {
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState('flagged');
  const all = resource.data?.features || [];
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all.filter(s => (scope === 'all' || (scope === 'flagged' ? s.properties.flagged : s.properties.rank_city_actionable))
      && (!q || (s.properties.road_name || '').toLowerCase().includes(q) || String(s.properties.site_id) === q));
  }, [all, query, scope]);
  const shown = rows.slice(0, 200);
  const rid = run ? encodeURIComponent(run.run_id) : '';
  return <section className="card" aria-label="Ranked sites">
    <h2>Ranked sites</h2>
    {!run && <p>Select a published model run to load site rankings.</p>}
    {resource.error && <p role="alert" className="api-error">{resource.error} <button onClick={resource.refresh}>Retry sites</button></p>}
    {all.length > 0 && <>
      <div className="filters">
        <label htmlFor="site-search">Search street name or site ID</label>
        <input id="site-search" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="e.g. Texas Ave" />
        <label htmlFor="site-scope">Show</label>
        <select id="site-scope" value={scope} onChange={e => setScope(e.target.value)}>
          <option value="flagged">Flagged sites</option><option value="city">City-actionable sites</option><option value="all">All sites</option>
        </select>
      </div>
      <p role="status">{rows.length} matching sites{rows.length > shown.length ? `; showing the top ${shown.length}` : ''}.</p>
      <div className="table-scroll"><table><caption>Ranking for {run.run_id}: expected K+A crashes per mile per year, 2026</caption>
        <thead><tr><th scope="col">Rank</th><th scope="col">Site</th><th scope="col">Type</th><th scope="col">K+A / mi / yr</th><th scope="col">Flagged</th><th scope="col">HIN</th><th scope="col">Jurisdiction</th><th scope="col">Memo</th></tr></thead>
        <tbody>{shown.map(site => { const p = site.properties; return <tr key={p.site_id}><td>{p.rank}</td><th scope="row"><button className="link" onClick={() => onSelect(String(p.site_id))}>{p.road_name || 'Unnamed road'}<small>{p.site_id}</small></button></th><td>{p.site_type}</td><td>{p.fsi_rate?.toFixed(3)}</td><td>{p.flagged ? 'Yes' : 'No'}</td><td>{p.in_hin ? 'Yes' : 'No'}</td><td>{p.jurisdiction}</td><td>{p.memo_status}</td></tr>; })}</tbody></table></div>
      <div className="download-links">
        <a className="button-link" href={`${exportBase(run)}.csv?run_id=${rid}`} download>Export all sites (CSV)</a>
        <a className="button-link" href={`${exportBase(run)}.csv?run_id=${rid}&flagged=true`} download>Export flagged (CSV)</a>
        <a className="button-link" href={`${exportBase(run)}.geojson?run_id=${rid}`} download>Export all sites (GeoJSON)</a>
      </div>
    </>}
  </section>;
}

const pct = v => (v === null || v === undefined ? 'n/a' : `${(v * 100).toFixed(1)}%`);
const pp = v => `${v >= 0 ? '+' : '−'}${Math.abs(v * 100).toFixed(1)} pts`;
const SCEN = { '5pct': '5% of length', '11pct': '11% of length', '20pct': '20% of length', hin_share: "HIN's own share", hin_matched_counts: 'HIN segment miles + intersection count' };

function CaptureChart({ scenarios, target }) {
  const pts = scenarios.filter(s => s.target === target && s.length_basis === 'icd_250ft' && s.scenario !== 'hin_matched_counts');
  const series = ['B', 'C'];
  const colors = { B: '#2563eb', C: '#b45309' };
  const W = 360, H = 200, x = s => 40 + (s / 0.3) * (W - 60), y = c => H - 30 - c * (H - 50);
  const a = pts[0]?.methods.find(m => m.method === 'A');
  const line = id => pts.map(s => s.methods.find(m => m.method === id)).filter(Boolean).sort((p, q) => p.flagged_share - q.flagged_share);
  return <figure className="capture-chart">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${target} capture rate against flagged share of network length for methods B and C, with the HIN (method A) as a single point.`}>
      {[0, 0.25, 0.5, 0.75, 1].map(c => <g key={c}><line x1="40" x2={W - 20} y1={y(c)} y2={y(c)} stroke="#e2e8e5" /><text x="34" y={y(c) + 3} fontSize="9" textAnchor="end" fill="#52645e">{c * 100}%</text></g>)}
      {[0, 0.1, 0.2, 0.3].map(s => <text key={s} x={x(s)} y={H - 14} fontSize="9" textAnchor="middle" fill="#52645e">{s * 100}%</text>)}
      <text x={(W + 20) / 2} y={H - 2} fontSize="9" textAnchor="middle" fill="#52645e">Share of network length flagged</text>
      {series.map(id => { const l = line(id); return <g key={id}><polyline fill="none" stroke={colors[id]} strokeWidth="2" points={l.map(m => `${x(m.flagged_share)},${y(m.capture)}`).join(' ')} />
        {l.map((m, i) => <circle key={i} cx={x(m.flagged_share)} cy={y(m.capture)} r="3" fill={colors[id]}><title>{`${id}: ${pct(m.capture)} at ${pct(m.flagged_share)} of length`}</title></circle>)}</g>; })}
      {a && <g><rect x={x(a.flagged_share) - 4} y={y(a.capture) - 4} width="8" height="8" fill="#6d28d9" /><title>{`A (HIN): ${pct(a.capture)} at ${pct(a.flagged_share)}`}</title></g>}
    </svg>
    <figcaption><span className="swatch" style={{ background: colors.C }} /> C ML-EB <span className="swatch" style={{ background: colors.B }} /> B SPF+EB <span className="swatch" style={{ background: '#6d28d9' }} /> A HIN as published</figcaption>
  </figure>;
}

export function Backtest({ run }) {
  const result = useApi(run ? runPath('backtest', run.run_id) : null);
  const [target, setTarget] = useState('KA');
  const bt = result.data?.backtest;
  const scen = bt?.scenarios?.filter(s => s.target === target && s.length_basis === 'icd_250ft') || [];
  return <section className="card" data-testid="backtest">
    <div className="details-heading"><h2>Methods A, B and C on 2023 to 2025 crashes</h2><button disabled={!run || result.loading} onClick={result.refresh}>Refresh results</button></div>
    {result.loading && <p role="status">Loading backtest…</p>}
    {result.error && <p role="alert" className="api-error">{result.error}</p>}
    {bt && !bt.scenarios && <p>This run has no scenario breakdown.</p>}
    {bt?.scenarios && <>
      <p>Training used only data knowable by {bt.training_cutoff}; crashes from {bt.test_window} are the test. Confidence intervals are 95% from {bt.bootstrap?.resamples} paired bootstrap resamples of test crashes (seed {bt.bootstrap?.seed}). Intersections count as 250 ft of length.</p>
      <label htmlFor="bt-target">Crash severity scored</label>
      <select id="bt-target" value={target} onChange={e => setTarget(e.target.value)}><option value="KA">Fatal and serious injury (K+A)</option><option value="KABC">All injury (K+A+B+C)</option></select>
      <div className="table-scroll"><table><caption>Capture rate: share of {target} test crashes on flagged sites (n = {scen[0]?.methods[0]?.n_test_fsi})</caption>
        <thead><tr><th scope="col">Flagged length</th><th scope="col">A HIN</th><th scope="col">B SPF+EB</th><th scope="col">C ML-EB</th><th scope="col">C − A [95% CI]</th><th scope="col">B − A [95% CI]</th></tr></thead>
        <tbody>{scen.map(s => { const m = id => s.methods.find(v => v.method === id); const d = k => s.differences[k];
          return <tr key={s.scenario}><th scope="row">{SCEN[s.scenario] || s.scenario}{s.scenario === 'hin_share' ? ` (${pct(m('A')?.flagged_share)})` : ''}</th>
            <td>{pct(m('A')?.capture)}{s.scenario !== 'hin_share' && s.scenario !== 'hin_matched_counts' ? <small>at {pct(m('A')?.flagged_share)}</small> : null}</td>
            <td>{pct(m('B')?.capture)}<small>[{pct(m('B')?.ci_low)}, {pct(m('B')?.ci_high)}]</small></td>
            <td>{pct(m('C')?.capture)}<small>[{pct(m('C')?.ci_low)}, {pct(m('C')?.ci_high)}]</small></td>
            <td>{d('C-A') ? <>{pp(d('C-A').difference)}<small>[{pp(d('C-A').ci_low)}, {pp(d('C-A').ci_high)}]</small></> : 'n/a'}</td>
            <td>{d('B-A') ? <>{pp(d('B-A').difference)}<small>[{pp(d('B-A').ci_low)}, {pp(d('B-A').ci_high)}]</small></> : 'n/a'}</td></tr>; })}</tbody></table></div>
      <p className="map-note">The HIN covers its own share of length in every row; only the 11% row is the FSR flagging rule, and there B and C flag less length than the HIN. The HIN-share rows compare all methods at equal length.</p>
      <CaptureChart scenarios={bt.scenarios} target={target} />
    </>}
  </section>;
}

export function Memos({ run, sites, selectedSiteId, onSelectSite, onOpenSite }) {
  const withMemo = sites.filter(s => s.properties.memo_status !== 'none').sort((a, b) => (a.properties.rank_city_actionable ?? 1e9) - (b.properties.rank_city_actionable ?? 1e9));
  const active = withMemo.find(s => s.properties.site_id === selectedSiteId) || withMemo[0];
  const sid = active?.properties.site_id;
  const result = useApi(sid && run ? runPath(`sites/${encodeURIComponent(sid)}/memo`, run.run_id) : null);
  const memo = result.data?.memo;
  const counts = run?.memo_counts;
  return <section className="card" data-testid="memos">
    <h2>Countermeasure memos</h2>
    {counts && <p>{Object.entries(counts).map(([k, v]) => `${v} ${k}`).join(', ')}. Memos cover the top City-actionable sites and are drafts until an engineer reviews them.</p>}
    {!withMemo.length && <p>No memos in this run.</p>}
    {withMemo.length > 0 && <><label htmlFor="memo-site">Site</label>
      <select id="memo-site" value={sid || ''} onChange={e => onSelectSite(e.target.value)}>
        {withMemo.map(s => <option key={s.properties.site_id} value={s.properties.site_id}>#{s.properties.rank_city_actionable} {s.properties.road_name} · {s.properties.site_id} · {s.properties.memo_status}</option>)}
      </select></>}
    {result.loading && <p role="status">Loading memo…</p>}
    {result.error && <p role="alert" className="api-error">{result.error}</p>}
    {memo && memo.status === 'draft' && memo.markdown && <article className="memo">
      <div className="download-links"><button onClick={() => onOpenSite(sid)}>Open site page</button><a className="button-link" href={`/api/v1/sites/${encodeURIComponent(sid)}/memo.pdf?run_id=${encodeURIComponent(run.run_id)}`} download>Download PDF</a></div>
      <pre className="memo-text">{memo.markdown}</pre>
      <p className="map-note">Generated {memo.created?.slice(0, 10)} by {memo.model}. Every number comes from a deterministic tool; every countermeasure cites a CMF record. Draft pending engineering review.</p>
    </article>}
    {memo && memo.status === 'blocked' && <p className="api-error">This memo failed a check and is withheld: {(memo.grounding_check?.errors || []).join('; ') || 'see the evidence file'}.</p>}
    {memo && memo.status === 'pending' && <p>Pending: the LLM service was unreachable during the batch.</p>}
  </section>;
}
