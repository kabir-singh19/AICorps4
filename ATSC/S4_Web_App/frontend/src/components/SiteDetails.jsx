import React from 'react';
import { runPath, useApi } from '../api.js';

const num = (v, d = 2) => (v === null || v === undefined ? 'Not available' : Number(v).toFixed(d));
const yesNo = v => (v === null || v === undefined ? 'Not available' : v ? 'Yes' : 'No');

function HistoryChart({ rows }) {
  const max = Math.max(1, ...rows.map(r => r.kabc ?? 0));
  const w = 34, h = 120;
  return <figure className="history-chart">
    <svg viewBox={`0 0 ${rows.length * w + 40} ${h + 34}`} role="img" aria-label="Matched crashes by year: bars show K+A+B+C injury crashes, the dark part is K+A.">
      <line x1="30" y1={h} x2={rows.length * w + 36} y2={h} stroke="#9aa8a2" />
      <text x="26" y="12" textAnchor="end" fontSize="10" fill="#52645e">{max}</text>
      <text x="26" y={h} textAnchor="end" fontSize="10" fill="#52645e">0</text>
      {rows.map((r, i) => {
        const x = 36 + i * w, kabc = r.kabc ?? 0, ka = r.ka ?? 0;
        return <g key={r.year}>
          <rect x={x} y={h - (kabc / max) * h} width={w - 10} height={(kabc / max) * h} fill="#f4b183" />
          <rect x={x} y={h - (ka / max) * h} width={w - 10} height={(ka / max) * h} fill="#9b2424" />
          <text x={x + (w - 10) / 2} y={h + 14} textAnchor="middle" fontSize="10" fill="#52645e">{String(r.year).slice(2)}</text>
          <title>{`${r.year}: ${kabc} injury crashes (K+A+B+C), ${ka} K+A, ${r.total ?? 0} total`}</title>
        </g>;
      })}
    </svg>
    <figcaption><span className="swatch" style={{ background: '#9b2424' }} /> K+A <span className="swatch" style={{ background: '#f4b183' }} /> B+C injury crashes. Years 2016 to 2025; 2023 to 2025 is the backtest test window.</figcaption>
  </figure>;
}

const yearRows = h => h.by_year.map(r => ({ year: r.year, ka: (r.K ?? 0) + (r.A ?? 0), kabc: (r.K ?? 0) + (r.A ?? 0) + (r.B ?? 0) + (r.C ?? 0), total: r.total ?? 0 }));

export default function SiteDetails({ run, siteId, onBackToMap, onOpenMemo }) {
  const isArtifact = run && !run.is_demo;
  const res = useApi(isArtifact && siteId ? runPath(`sites/${encodeURIComponent(siteId)}`, run.run_id) : null);
  if (!siteId) return <section className="card"><h2>Select a site</h2><p>Click a road segment or intersection on the map, or pick one from the ranked list.</p><button onClick={onBackToMap}>Go to map</button></section>;
  if (!isArtifact) return <section className="card"><h2>Site {siteId}</h2><p>Site pages need a published model run. Select one above.</p></section>;
  if (res.loading) return <p role="status">Loading site {siteId}…</p>;
  if (res.error) return <p role="alert" className="api-error">{res.error}</p>;
  const d = res.data;
  if (!d) return null;
  const a = d.attributes, p = d.prediction, h = d.crash_history;
  const pdf = `/api/v1/sites/${encodeURIComponent(siteId)}/memo.pdf?run_id=${encodeURIComponent(run.run_id)}`;
  return <>
    <section className="card" aria-label="Site summary" data-testid="site-detail">
      <div className="details-heading"><div><p className="eyebrow">{a.site_type?.toUpperCase()} · {siteId}</p><h2>{a.road_name || 'Unnamed road'}</h2></div><button onClick={onBackToMap}>Back to map</button></div>
      <dl className="details-grid">
        <div><dt>Expected K+A crashes per mile per year (2026)</dt><dd className="big">{num(p.fsi_rate, 3)}</dd></div>
        <div><dt>Expected K+A crashes per year</dt><dd>{num(p.annual_fsi, 3)}</dd></div>
        <div><dt>Citywide rank</dt><dd>{p.rank} of {run.site_count}</dd></div>
        <div><dt>Rank among City-actionable sites</dt><dd>{p.rank_city_actionable ?? 'Not City-actionable'}</dd></div>
        <div><dt>Flagged (top 11% of length)</dt><dd>{yesNo(p.flagged)}</dd></div>
        <div><dt>In the MPO high-injury network</dt><dd>{yesNo(p.in_hin)}</dd></div>
        <div><dt>Jurisdiction</dt><dd>{a.jurisdiction}{a.route_name ? ` (${a.route_name})` : ''}</dd></div>
        <div><dt>Length used for the rate</dt><dd>{num(a.length_mi, 3)} mi{a.site_type === 'intersection' ? ' (250 ft influence zone)' : ''}</dd></div>
        <div><dt>AADT</dt><dd>{a.aadt ? Math.round(a.aadt).toLocaleString() : 'Not available'}{a.aadt_imputed ? ' (imputed class median)' : ''}</dd></div>
        <div><dt>Posted speed</dt><dd>{a.speed_limit ? `${a.speed_limit} mph` : 'Not available'}</dd></div>
        <div><dt>{a.site_type === 'intersection' ? 'Legs / signalized' : 'Lanes / class'}</dt><dd>{a.site_type === 'intersection' ? `${a.legs ?? '?'} legs · ${yesNo(a.signalized)}` : `${a.num_lanes ?? '?'} lanes · ${a.func_class ?? 'unknown class'}`}</dd></div>
        <div><dt>Location</dt><dd>{num(a.lat, 5)}, {num(a.lon, 5)}</dd></div>
      </dl>
      <details><summary>Model details (method C, ML-EB)</summary><dl className="details-grid">
        <div><dt>Model crashes per year (μ)</dt><dd>{num(p.mu, 3)}</dd></div><div><dt>Overdispersion k</dt><dd>{num(p.k, 3)}</dd></div>
        <div><dt>EB weight on the model</dt><dd>{num(p.eb_weight, 3)}</dd></div><div><dt>EB crashes per year</dt><dd>{num(p.n_eb, 3)}</dd></div>
        <div><dt>P(K or A given a crash)</dt><dd>{num(p.p_fsi, 4)}</dd></div><div><dt>Method B (SPF+EB) rate / rank</dt><dd>{num(p.fsi_rate_spf_eb, 3)} / {p.rank_spf_eb}</dd></div>
      </dl></details>
    </section>
    <section className="card" aria-label="Crash history">
      <h2>Crash history (matched crashes)</h2>
      <HistoryChart rows={yearRows(h)} />
      <p>Last three years (2023 to 2025): {h.last_3_years.ka_3y} K+A, {h.last_3_years.kabc_3y} injury (K+A+B+C), {h.last_3_years.tot_3y} total. Angle {h.last_3_years.angle_3y ?? 0}, rear-end {h.last_3_years.rear_end_3y ?? 0}, single-vehicle {h.last_3_years.single_vehicle_3y ?? 0}, opposite-direction {h.last_3_years.opposite_direction_3y ?? 0}, night {h.last_3_years.night_3y ?? 0}, wet {h.last_3_years.wet_3y ?? 0}.</p>
    </section>
    <section className="card" aria-label="Why this site ranks here">
      <h2>Top factors behind the prediction</h2>
      {d.shap_factors.length ? <ol className="factors">{d.shap_factors.map(f => <li key={f.rank}><span className={f.direction === 'raises risk' ? 'up' : 'down'}>{f.direction === 'raises risk' ? '▲ raises risk' : '▼ lowers risk'}</span> {f.text}</li>)}</ol>
        : <p>Factors are computed for flagged sites only.</p>}
    </section>
    <section className="card" aria-label="Countermeasure memo">
      <h2>Countermeasure memo</h2>
      {d.memo_status === 'none' && <p>No memo for this site. Memos are drafted for the top 25 City-actionable sites.</p>}
      {d.memo_status === 'pending' && <p>Memo pending: the LLM service was unreachable when the batch ran.</p>}
      {d.memo_status === 'blocked' && <p className="api-error">The drafted memo failed a grounding or completeness check and is withheld.</p>}
      {d.memo_status === 'draft' && <div className="download-links"><button onClick={onOpenMemo}>Read memo</button><a className="button-link" href={pdf} download>Download memo PDF</a></div>}
      {d.memo_status === 'draft' && <p className="map-note">Draft: passed every automated check, not yet reviewed by an engineer.</p>}
    </section>
  </>;
}
