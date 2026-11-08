import React, { useMemo, useState } from 'react';
import { runPath, useApi } from '../api.js';
import MemoDocument from './MemoDocument.jsx';

const pct = v => (v === null || v === undefined ? 'n/a' : `${(v * 100).toFixed(1)}%`);
const pts = v => `${v >= 0 ? '+' : '−'}${Math.abs(v * 100).toFixed(1)}`;
// Method colors (validated categorical slots): C blue, B aqua, A (the HIN) orange.
export const METHOD_COLOR = { C: '#2a78d6', B: '#1baf7a', A: '#eb6834' };
const METHOD_NAME = { A: 'A · MPO HIN', B: 'B · SPF + EB', C: 'C · ML-EB' };

export function ModelRuns({ resource, runs, activeRun, onChange, onRefresh }) {
  return <section className="run-bar" aria-label="Model run selection">
    <label htmlFor="model-run">Model run</label>
    <select id="model-run" value={activeRun?.run_id || ''} onChange={event => onChange(event.target.value)} disabled={runs.length < 2 || resource.loading}>
      {!runs.length && <option value="">No published runs</option>}
      {runs.map(run => <option key={run.run_id} value={run.run_id}>{run.run_id}{run.is_demo ? ' · EXAMPLE DATA' : ''}</option>)}
    </select>
    {activeRun && <span className="run-meta">{activeRun.model_name} · published {new Date(activeRun.published_at).toLocaleDateString()}</span>}
    <button className="ghost" onClick={onRefresh} disabled={resource.loading}>Refresh</button>
    {resource.error && <p role="alert" className="api-error">{resource.error}</p>}
    {activeRun?.is_demo && <p className="demo-label">Example data, not real predictions or engineering recommendations.</p>}
  </section>;
}

export function Kpis({ run, sites }) {
  if (!run || !sites.length) return null;
  let total = 0, flaggedLen = 0, flagged = 0, cityFlagged = 0, hin = 0;
  for (const s of sites) {
    const p = s.properties, L = p.length_mi || 0;
    total += L;
    if (p.flagged) { flagged++; flaggedLen += L; if (p.rank_city_actionable) cityFlagged++; }
    if (p.in_hin) hin++;
  }
  const drafts = run.memo_counts?.draft ?? 0;
  const tiles = [
    ['Sites ranked', sites.length.toLocaleString(), `${hin.toLocaleString()} are on the MPO HIN`],
    ['Flagged sites', flagged.toLocaleString(), `${pct(flaggedLen / total)} of network length`],
    ['City-actionable flagged', cityFlagged.toLocaleString(), 'City or City/TxDOT jurisdiction'],
    ['Memos drafted', drafts.toLocaleString(), 'top City-actionable sites'],
  ];
  return <section className="kpis" aria-label="Run summary">{tiles.map(([label, value, note]) =>
    <div className="kpi" key={label}><span className="kpi-label">{label}</span><span className="kpi-value">{value}</span><span className="kpi-note">{note}</span></div>)}</section>;
}

function Pill({ on, yes = 'Yes', no = 'No', tone = 'on' }) {
  return <span className={`pill ${on ? `pill-${tone}` : 'pill-off'}`}>{on ? yes : no}</span>;
}

const MEMO_TONE = { draft: 'on', blocked: 'warn', pending: 'off', none: 'off' };

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
  const max = Math.max(...shown.map(s => s.properties.fsi_rate || 0), 1e-9);
  const rid = run ? encodeURIComponent(run.run_id) : '';
  return <section className="card" aria-label="Ranked sites">
    <div className="card-head"><h2>Ranked sites</h2>
      {all.length > 0 && <div className="download-links">
        <a className="button-link" href={`/api/v1/export/sites.csv?run_id=${rid}`} download>CSV · all</a>
        <a className="button-link" href={`/api/v1/export/sites.csv?run_id=${rid}&flagged=true`} download>CSV · flagged</a>
        <a className="button-link" href={`/api/v1/export/sites.geojson?run_id=${rid}`} download>GeoJSON</a>
      </div>}
    </div>
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
      <p className="muted small" role="status">{rows.length.toLocaleString()} matching sites{rows.length > shown.length ? `; showing the top ${shown.length}` : ''}.</p>
      <div className="table-scroll"><table className="data-table"><caption className="sr-only">Ranking for {run.run_id}: expected K+A crashes per mile per year, 2026</caption>
        <thead><tr><th scope="col" className="num">Rank</th><th scope="col">Site</th><th scope="col">Type</th><th scope="col">K+A per mile per year</th><th scope="col">Flagged</th><th scope="col">On HIN</th><th scope="col">Jurisdiction</th><th scope="col">Memo</th></tr></thead>
        <tbody>{shown.map(site => { const p = site.properties; return <tr key={p.site_id}>
          <td className="num"><span className="rank">{p.rank}</span></td>
          <th scope="row"><button className="link" onClick={() => onSelect(String(p.site_id))}>{p.road_name || 'Unnamed road'}<small>{p.site_id}</small></button></th>
          <td className="muted">{p.site_type}</td>
          <td><span className="rate"><span className="rate-bar" style={{ width: `${Math.max(2, (p.fsi_rate / max) * 100)}%` }} aria-hidden="true" /><span className="rate-num">{p.fsi_rate?.toFixed(2)}</span></span></td>
          <td><Pill on={p.flagged} /></td><td><Pill on={p.in_hin} tone="hin" /></td>
          <td className="muted">{p.jurisdiction}</td>
          <td>{p.memo_status === 'none' ? <span className="muted">none</span> : <span className={`pill pill-${MEMO_TONE[p.memo_status]}`}>{p.memo_status}</span>}</td>
        </tr>; })}</tbody></table></div>
    </>}
  </section>;
}

const SCEN = { '5pct': '5% of length', '11pct': '11% of length (FSR flagging rule)', '20pct': '20% of length', hin_share: "HIN's own share of length", hin_matched_counts: 'HIN segment miles + intersection count' };

function verdict(d) {
  if (d.ci_low > 0) return 'better than the HIN; the interval is above zero';
  if (d.ci_high < 0) return 'worse than the HIN; the interval is below zero';
  return 'not distinguishable from the HIN; the interval includes zero';
}

function CaptureChart({ scenarios, target }) {
  const [hover, setHover] = useState(null);
  const pts_ = scenarios.filter(s => s.target === target && s.length_basis === 'icd_250ft' && s.scenario !== 'hin_matched_counts');
  const W = 720, H = 320, L = 48, R = 120, T = 16, B = 44, Y0 = 0.4;
  const x = s => L + (s / 0.3) * (W - L - R), y = c => T + (1 - (c - Y0) / (1 - Y0)) * (H - T - B);
  const line = id => pts_.map(s => ({ ...s.methods.find(m => m.method === id), scenario: s.scenario })).filter(m => m.capture !== undefined).sort((p, q) => p.flagged_share - q.flagged_share);
  const a = pts_[0]?.methods.find(m => m.method === 'A');
  const ends = { C: line('C').at(-1), B: line('B').at(-1), A: a };
  // Direct labels in the right margin, spread apart so they never overlap.
  const labels = Object.entries(ends).filter(([, m]) => m).map(([id, m]) => ({ id, y: y(m.capture) })).sort((p, q) => p.y - q.y);
  for (let i = 1; i < labels.length; i++) labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 16);
  return <figure className="chart">
    <figcaption className="chart-title">{target === 'KA' ? 'K+A' : 'K+A+B+C'} capture rate vs. share of network length flagged</figcaption>
    <div className="chart-box">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Capture rate of methods B and C as the flagged share of network length grows, with the HIN (method A) as one point at its own share. The table above lists the same values.`}>
        {[0.4, 0.6, 0.8, 1].map(c => <g key={c}><line x1={L} x2={W - R} y1={y(c)} y2={y(c)} className="grid" /><text x={L - 8} y={y(c) + 4} className="tick" textAnchor="end">{Math.round(c * 100)}%</text></g>)}
        {[0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3].map(s => <text key={s} x={x(s)} y={H - B + 18} className="tick" textAnchor="middle">{Math.round(s * 100)}%</text>)}
        <text x={(L + W - R) / 2} y={H - 4} className="axis-label" textAnchor="middle">Share of network length flagged</text>
        <line x1={x(0.11)} x2={x(0.11)} y1={T} y2={H - B} className="ref-line" /><text x={x(0.11) + 4} y={T + 10} className="tick">11% rule</text>
        {['B', 'C'].map(id => { const l = line(id); return <g key={id}>
          <polyline fill="none" stroke={METHOD_COLOR[id]} strokeWidth="2" strokeLinejoin="round" points={l.map(m => `${x(m.flagged_share)},${y(m.capture)}`).join(' ')} />
          {l.map((m, i) => <g key={i} onMouseEnter={() => setHover({ id, m })} onMouseLeave={() => setHover(null)}>
            <circle cx={x(m.flagged_share)} cy={y(m.capture)} r="12" fill="transparent" />
            <circle cx={x(m.flagged_share)} cy={y(m.capture)} r="4.5" fill={METHOD_COLOR[id]} stroke="var(--surface)" strokeWidth="2" />
          </g>)}</g>; })}
        {a && <g onMouseEnter={() => setHover({ id: 'A', m: a })} onMouseLeave={() => setHover(null)}>
          <circle cx={x(a.flagged_share)} cy={y(a.capture)} r="12" fill="transparent" />
          <rect x={x(a.flagged_share) - 5} y={y(a.capture) - 5} width="10" height="10" rx="2" fill={METHOD_COLOR.A} stroke="var(--surface)" strokeWidth="2" />
        </g>}
        {labels.map(l => <text key={l.id} x={W - R + 12} y={l.y + 4} className="direct-label">{METHOD_NAME[l.id]}</text>)}
      </svg>
      {hover && <div className="tooltip" style={{ left: `${(x(hover.m.flagged_share) / W) * 100}%`, top: `${(y(hover.m.capture) / H) * 100}%` }}>
        <strong>{METHOD_NAME[hover.id]}</strong><span>{pct(hover.m.capture)} captured</span><span>95% CI {pct(hover.m.ci_low)} to {pct(hover.m.ci_high)}</span><span>{pct(hover.m.flagged_share)} of length flagged</span>
      </div>}
    </div>
    <div className="legend">{['C', 'B', 'A'].map(id => <span key={id}><i style={{ background: METHOD_COLOR[id], borderRadius: id === 'A' ? 2 : 8 }} aria-hidden="true" />{METHOD_NAME[id]}</span>)}</div>
  </figure>;
}

export function Backtest({ run }) {
  const result = useApi(run ? runPath('backtest', run.run_id) : null);
  const [target, setTarget] = useState('KA');
  const bt = result.data?.backtest;
  const scen = bt?.scenarios?.filter(s => s.target === target && s.length_basis === 'icd_250ft') || [];
  const eq = scen.find(s => s.scenario === 'hin_share');
  const m = (s, id) => s?.methods.find(v => v.method === id);
  return <section className="card" data-testid="backtest">
    <div className="card-head"><h2>Methods A, B and C on 2023 to 2025 crashes</h2>
      <div className="segmented">
        <label htmlFor="bt-target" className="sr-only">Crash severity scored</label>
        <select id="bt-target" value={target} onChange={e => setTarget(e.target.value)}><option value="KA">Fatal and serious injury (K+A)</option><option value="KABC">All injury (K+A+B+C)</option></select>
      </div>
    </div>
    {result.loading && <p role="status">Loading backtest…</p>}
    {result.error && <p role="alert" className="api-error">{result.error}</p>}
    {bt?.scenarios && <>
      {eq && <div className="callout">
        <span className="callout-label">At equal length</span>
        <p>Flagging the HIN's own {pct(m(eq, 'A').flagged_share)} of network length, method C found <strong>{pct(m(eq, 'C').capture)}</strong> of {target === 'KA' ? 'K+A' : 'injury'} test crashes and the HIN found <strong>{pct(m(eq, 'A').capture)}</strong>: {pts(eq.differences['C-A'].difference)} points (95% CI {pts(eq.differences['C-A'].ci_low)} to {pts(eq.differences['C-A'].ci_high)}), {verdict(eq.differences['C-A'])}.</p>
      </div>}
      <div className="table-scroll"><table className="data-table"><caption>Capture rate: share of the {scen[0]?.methods[0]?.n_test_fsi.toLocaleString()} {target} test crashes that fell on flagged sites. Brackets: 95% CI.</caption>
        <thead><tr><th scope="col">Flagged length</th><th scope="col"><i className="dot" style={{ background: METHOD_COLOR.A }} />A · HIN</th><th scope="col"><i className="dot" style={{ background: METHOD_COLOR.B }} />B · SPF+EB</th><th scope="col"><i className="dot" style={{ background: METHOD_COLOR.C }} />C · ML-EB</th><th scope="col">C − A (points)</th><th scope="col">B − A (points)</th></tr></thead>
        <tbody>{scen.map(s => { const d = k => s.differences[k];
          const diff = k => d(k) ? <span className={d(k).ci_low > 0 ? 'pos' : d(k).ci_high < 0 ? 'neg' : ''}>{pts(d(k).difference)}<small>[{pts(d(k).ci_low)}, {pts(d(k).ci_high)}]</small></span> : 'n/a';
          return <tr key={s.scenario} className={s.scenario === 'hin_share' ? 'highlight' : ''}><th scope="row">{SCEN[s.scenario] || s.scenario}{s.scenario === 'hin_share' ? ` (${pct(m(s, 'A')?.flagged_share)})` : ''}</th>
            <td>{pct(m(s, 'A')?.capture)}<small>at {pct(m(s, 'A')?.flagged_share)} of length</small></td>
            <td>{pct(m(s, 'B')?.capture)}<small>[{pct(m(s, 'B')?.ci_low)}, {pct(m(s, 'B')?.ci_high)}]</small></td>
            <td>{pct(m(s, 'C')?.capture)}<small>[{pct(m(s, 'C')?.ci_low)}, {pct(m(s, 'C')?.ci_high)}]</small></td>
            <td>{diff('C-A')}</td><td>{diff('B-A')}</td></tr>; })}</tbody></table></div>
      <p className="muted small">The HIN always covers its own share of length. In the 11% row, B and C flag less than half the length the HIN does; the HIN-share rows compare all methods at equal length. Training used only data knowable by {bt.training_cutoff}; {bt.bootstrap?.resamples} paired bootstrap resamples (seed {bt.bootstrap?.seed}); intersections count as 250 ft of length.</p>
      <CaptureChart scenarios={bt.scenarios} target={target} />
    </>}
  </section>;
}

// FSR 3.2.5.1.1.3: built-in test results for the run, retrievable by operators.
export function BitLog({ run }) {
  const result = useApi(run ? runPath('bit', run.run_id) : null);
  const b = result.data;
  return <section className="card" data-testid="bit-log" aria-label="Built-in test log">
    <h2>Built-in test (BIT) log</h2>
    {result.loading && <p role="status">Loading test log…</p>}
    {result.error && <p role="alert" className="api-error">{result.error}</p>}
    {b && <>
      <div className="kpis inner">
        <div className="kpi"><span className="kpi-label">Seeded faults detected</span><span className="kpi-value">{b.campaign ? `${b.campaign.detected} / ${b.campaign.faults}` : 'n/a'}</span><span className="kpi-note">pass at 19 or more</span></div>
        <div className="kpi"><span className="kpi-label">False alarms in clean runs</span><span className="kpi-value">{b.campaign ? `${b.campaign.false_alarms} / ${b.campaign.good_runs}` : 'n/a'}</span><span className="kpi-note">pass at 1 or fewer</span></div>
        <div className="kpi"><span className="kpi-label">Model output checks</span><span className="kpi-value">{b.model_checks.passed} / {b.model_checks.runs}</span><span className="kpi-note">runs passed</span></div>
      </div>
      {b.suite_log.length > 0 && <div className="table-scroll"><table className="data-table compact"><caption>Last <code>atsc bit</code> run</caption>
        <thead><tr><th scope="col">Test</th><th scope="col">Result</th><th scope="col">Details</th><th scope="col">Time (UTC)</th></tr></thead>
        <tbody>{b.suite_log.map((r, k) => <tr key={k}><th scope="row">{r.test}</th><td><span className={`pill ${r.result === 'pass' ? 'pill-on' : 'pill-up'}`}>{r.result}</span></td><td>{r.details}</td><td>{r.timestamp}</td></tr>)}</tbody></table></div>}
      {b.campaign && <details className="table-view"><summary>Show the {b.campaign.faults} seeded faults</summary><ul className="small">{b.campaign.seeded_faults.map((f, k) => <li key={k}>{f.detected ? '✓' : '✗'} {f.fault}</li>)}</ul></details>}
    </>}
  </section>;
}

export function Memos({ run, sites, resource, selectedSiteId, onSelectSite, onOpenSite }) {
  const withMemo = sites.filter(s => s.properties.memo_status !== 'none').sort((a, b) => (a.properties.rank_city_actionable ?? 1e9) - (b.properties.rank_city_actionable ?? 1e9));
  const active = withMemo.find(s => s.properties.site_id === selectedSiteId) || withMemo[0];
  const sid = active?.properties.site_id;
  const result = useApi(sid && run ? runPath(`sites/${encodeURIComponent(sid)}/memo`, run.run_id) : null);
  const memo = result.data?.memo;
  return <section className="memos-layout" data-testid="memos">
    <aside className="card memo-list" aria-label="Sites with memos">
      <h2>Sites with memos</h2>
      {resource?.loading && <p role="status">Loading…</p>}
      {!resource?.loading && !withMemo.length && <p>No memos in this run.</p>}
      <ol>{withMemo.map(s => { const p = s.properties; return <li key={p.site_id}>
        <button aria-pressed={p.site_id === sid} onClick={() => onSelectSite(p.site_id)}>
          <span className="rank">{p.rank_city_actionable}</span>
          <span className="memo-item"><span className="memo-item-name">{p.road_name || 'Unnamed road'}</span><small>{p.site_type} · {p.fsi_rate.toFixed(2)} K+A/mi/yr{p.in_hin ? ' · HIN' : ''}</small></span>
          <span className={`pill pill-${MEMO_TONE[p.memo_status]}`}>{p.memo_status}</span>
        </button></li>; })}</ol>
    </aside>
    <div className="card memo-pane">
      {result.loading && <p role="status">Loading memo…</p>}
      {result.error && <p role="alert" className="api-error">{result.error}</p>}
      {memo && <div className="memo-actions">
        <span className={`pill pill-${MEMO_TONE[memo.status]}`}>{memo.status}</span>
        <span className="muted small">Generated {memo.created?.slice(0, 10)} · {memo.model}{memo.cost_usd !== undefined ? ` · $${memo.cost_usd.toFixed(3)}` : ''}</span>
        <span className="spacer" />
        <button onClick={() => onOpenSite(sid)}>Open site page</button>
        {memo.status === 'draft' && <a className="button-link primary" href={`/api/v1/sites/${encodeURIComponent(sid)}/memo.pdf?run_id=${encodeURIComponent(run.run_id)}`} download>Download PDF</a>}
      </div>}
      {memo && memo.status === 'draft' && memo.markdown && <MemoDocument markdown={memo.markdown} />}
      {memo && memo.status === 'blocked' && <p className="api-error">This memo failed a check and is withheld: {(memo.grounding_check?.numeric_grounding_3_2_1_14?.errors || []).join('; ') || 'see the evidence file'}.</p>}
      {memo && memo.status === 'pending' && <p>Pending: the LLM service was unreachable during the batch.</p>}
    </div>
  </section>;
}
