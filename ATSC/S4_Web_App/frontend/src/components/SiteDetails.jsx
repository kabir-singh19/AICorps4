import React, { useState } from 'react';
import { runPath, useApi } from '../api.js';

const num = (v, d = 2) => (v === null || v === undefined ? 'n/a' : Number(v).toFixed(d));
const yesNo = v => (v === null || v === undefined ? 'n/a' : v ? 'Yes' : 'No');
// Severity tiers on one hue (validated ordinal steps): K+A dark, B+C light.
const KA = '#1c5cab', BC = '#86b6ef';

const yearRows = h => h.by_year.map(r => ({ year: r.year, ka: (r.K ?? 0) + (r.A ?? 0), bc: (r.B ?? 0) + (r.C ?? 0), total: r.total ?? 0 }));

function HistoryChart({ rows }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(1, ...rows.map(r => r.ka + r.bc));
  const W = 560, H = 230, L = 34, T = 24, B = 30, gap = 6;
  const bw = (W - L - 8) / rows.length - gap;
  const y = v => T + (1 - v / max) * (H - T - B);
  const ticks = [0, Math.ceil(max / 2), max];
  const testX = L + rows.findIndex(r => r.year >= 2023) * (bw + gap) - gap / 2;
  return <figure className="chart">
    <figcaption className="chart-title">Injury crashes matched to this site, by year</figcaption>
    <div className="chart-box">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Matched crashes by year: each bar is the injury crashes (K+A+B+C), the dark part is K+A. The table below lists the values.">
        {testX > L && <rect x={testX} y={T} width={W - 8 - testX} height={H - T - B} className="band" />}
        {testX > L && <text x={testX + 4} y={T - 8} className="tick">2023 to 2025: test window</text>}
        {ticks.map(t => <g key={t}><line x1={L} x2={W - 8} y1={y(t)} y2={y(t)} className="grid" /><text x={L - 6} y={y(t) + 4} className="tick" textAnchor="end">{t}</text></g>)}
        {rows.map((r, i) => { const x = L + i * (bw + gap) + gap / 2, tot = r.ka + r.bc;
          return <g key={r.year} onMouseEnter={() => setHover({ r, x: x + bw / 2, yv: tot })} onMouseLeave={() => setHover(null)}>
            <rect x={x - 2} y={T} width={bw + 4} height={H - T - B} fill="transparent" />
            {r.bc > 0 && <rect x={x} y={y(tot)} width={bw} height={Math.max(0, y(r.ka) - y(tot) - (r.ka ? 2 : 0))} rx="4" fill={BC} />}
            {r.ka > 0 && <rect x={x} y={y(r.ka)} width={bw} height={y(0) - y(r.ka)} rx="4" fill={KA} />}
            <text x={x + bw / 2} y={H - B + 16} className="tick" textAnchor="middle">{String(r.year).slice(2)}</text>
          </g>; })}
      </svg>
      {hover && <div className="tooltip" style={{ left: `${(hover.x / W) * 100}%`, top: `${(y(hover.yv) / H) * 100}%` }}>
        <strong>{hover.r.year}</strong><span>{hover.r.ka} K+A</span><span>{hover.r.bc} B+C</span><span>{hover.r.total} crashes of any severity</span></div>}
    </div>
    <div className="legend"><span><i style={{ background: KA }} aria-hidden="true" />K+A (fatal or serious)</span><span><i style={{ background: BC }} aria-hidden="true" />B+C (minor or possible injury)</span></div>
    <details className="table-view"><summary>Show as table</summary><div className="table-scroll"><table className="data-table compact"><thead><tr><th scope="col">Year</th>{rows.map(r => <th key={r.year} scope="col">{r.year}</th>)}</tr></thead>
      <tbody><tr><th scope="row">K+A</th>{rows.map(r => <td key={r.year}>{r.ka}</td>)}</tr><tr><th scope="row">B+C</th>{rows.map(r => <td key={r.year}>{r.bc}</td>)}</tr><tr><th scope="row">All</th>{rows.map(r => <td key={r.year}>{r.total}</td>)}</tr></tbody></table></div></details>
  </figure>;
}

function Stat({ label, value, note }) {
  return <div className="kpi"><span className="kpi-label">{label}</span><span className="kpi-value">{value}</span>{note && <span className="kpi-note">{note}</span>}</div>;
}

export default function SiteDetails({ run, siteId, onBackToMap, onOpenMemo }) {
  const isArtifact = run && !run.is_demo;
  const res = useApi(isArtifact && siteId ? runPath(`sites/${encodeURIComponent(siteId)}`, run.run_id) : null);
  if (!siteId) return <section className="card empty"><h2>Select a site</h2><p>Click a road segment or intersection on the map, or pick one from the ranked list.</p><button onClick={onBackToMap}>Go to the map</button></section>;
  if (!isArtifact) return <section className="card"><h2>Site {siteId}</h2><p>Site pages need a published model run.</p></section>;
  if (res.loading) return <p role="status">Loading site {siteId}…</p>;
  if (res.error) return <p role="alert" className="api-error">{res.error}</p>;
  const d = res.data;
  if (!d) return null;
  const a = d.attributes, p = d.prediction, h = d.crash_history, l3 = h.last_3_years;
  const pdf = `/api/v1/sites/${encodeURIComponent(siteId)}/memo.pdf?run_id=${encodeURIComponent(run.run_id)}`;
  const types = [['angle', l3.angle_3y], ['rear-end', l3.rear_end_3y], ['single-vehicle', l3.single_vehicle_3y], ['opposite-direction', l3.opposite_direction_3y], ['night', l3.night_3y], ['wet surface', l3.wet_3y]];
  return <div className="site-page" data-testid="site-detail">
    <section className="card site-hero" aria-label="Site summary">
      <div className="card-head">
        <div><p className="eyebrow">{a.site_type} · site {siteId}</p><h2 className="site-title">{a.road_name || 'Unnamed road'}</h2>
          <div className="badges">{p.flagged && <span className="pill pill-on">Flagged</span>}{p.in_hin && <span className="pill pill-hin">On MPO HIN</span>}<span className="pill pill-off">{a.jurisdiction}{a.route_name ? ` · ${a.route_name}` : ''}</span>{d.memo_status === 'draft' && <span className="pill pill-on">Memo drafted</span>}</div></div>
        <button className="ghost" onClick={onBackToMap}>← Back to map</button>
      </div>
      <div className="kpis inner">
        <Stat label="K+A crashes per mile per year" value={num(p.fsi_rate, 2)} note="2026 forecast, method C" />
        <Stat label="K+A crashes per year" value={num(p.annual_fsi, 2)} note={`over ${num(a.length_mi, 3)} mi${a.site_type === 'intersection' ? ' (250 ft zone)' : ''}`} />
        <Stat label="Citywide rank" value={p.rank} note={`of ${run.site_count.toLocaleString()} sites`} />
        <Stat label="City-actionable rank" value={p.rank_city_actionable ?? 'n/a'} note={p.rank_city_actionable ? 'City or City/TxDOT' : 'not City-actionable'} />
      </div>
    </section>
    <div className="two-col">
      <section className="card" aria-label="Crash history">
        <h2>Crash history</h2>
        <HistoryChart rows={yearRows(h)} />
        <p className="small">2023 to 2025: <strong>{l3.ka_3y}</strong> K+A, <strong>{l3.kabc_3y}</strong> injury, <strong>{l3.tot_3y}</strong> total crashes.</p>
        <div className="type-chips">{types.map(([k, v]) => <span key={k} className="type-chip"><b>{v ?? 0}</b> {k}</span>)}</div>
      </section>
      <section className="card" aria-label="Why this site ranks here">
        <h2>Why it ranks here</h2>
        <p className="muted small">The five factors that moved this site's prediction most (SHAP).</p>
        {d.shap_factors.length ? <ol className="factors">{d.shap_factors.map(f => <li key={f.rank}><span className={`pill ${f.direction === 'raises risk' ? 'pill-up' : 'pill-down'}`}>{f.direction === 'raises risk' ? '▲ raises' : '▼ lowers'}</span><span>{f.text}</span></li>)}</ol>
          : <p>Factors are computed for flagged sites only.</p>}
      </section>
    </div>
    <div className="two-col">
      <section className="card" aria-label="Site attributes">
        <h2>Road attributes</h2>
        <dl className="details-grid">
          <div><dt>AADT</dt><dd>{a.aadt ? Math.round(a.aadt).toLocaleString() : 'n/a'}{a.aadt_imputed ? ' (class median)' : ''}</dd></div>
          <div><dt>Posted speed</dt><dd>{a.speed_limit ? `${a.speed_limit} mph` : 'n/a'}</dd></div>
          {a.site_type === 'intersection' ? <><div><dt>Legs</dt><dd>{a.legs ?? 'n/a'}</dd></div><div><dt>Signalized</dt><dd>{yesNo(a.signalized)}</dd></div></>
            : <><div><dt>Lanes</dt><dd>{a.num_lanes ?? 'n/a'}</dd></div><div><dt>Functional class</dt><dd>{a.func_class ?? 'n/a'}</dd></div></>}
          <div><dt>Median</dt><dd>{a.median_type ?? 'n/a'}</dd></div>
          <div><dt>Location</dt><dd>{num(a.lat, 5)}, {num(a.lon, 5)}</dd></div>
        </dl>
      </section>
      <section className="card" aria-label="Model details">
        <h2>Model details</h2>
        <dl className="details-grid">
          <div><dt>Model crashes per year (μ)</dt><dd>{num(p.mu, 3)}</dd></div><div><dt>Overdispersion k</dt><dd>{num(p.k, 3)}</dd></div>
          <div><dt>EB weight on the model</dt><dd>{num(p.eb_weight, 3)}</dd></div><div><dt>EB crashes per year</dt><dd>{num(p.n_eb, 3)}</dd></div>
          <div><dt>P(K or A | crash)</dt><dd>{num(p.p_fsi, 4)}</dd></div><div><dt>Method B rate / rank</dt><dd>{num(p.fsi_rate_spf_eb, 2)} / {p.rank_spf_eb}</dd></div>
        </dl>
      </section>
    </div>
    <section className="card memo-cta" aria-label="Countermeasure memo">
      <div><h2>Countermeasure memo</h2>
        {d.memo_status === 'none' && <p className="muted">No memo for this site. Memos are drafted for the top 25 City-actionable sites.</p>}
        {d.memo_status === 'pending' && <p>Memo pending: the LLM service was unreachable when the batch ran.</p>}
        {d.memo_status === 'blocked' && <p className="api-error">The drafted memo failed a grounding or completeness check and is withheld.</p>}
        {d.memo_status === 'draft' && <p className="muted">Draft: passed every automated check; not yet reviewed by an engineer.</p>}
      </div>
      {d.memo_status === 'draft' && <div className="download-links"><button onClick={onOpenMemo}>Read memo</button><a className="button-link primary" href={pdf} download>Download PDF</a></div>}
    </section>
  </div>;
}
