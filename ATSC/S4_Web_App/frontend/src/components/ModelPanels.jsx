import React from 'react';
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
    {!resource.loading && !resource.error && !runs.length && <p>No model results have been published yet. The street map is available.</p>}
    {activeRun && <p>Published {new Date(activeRun.published_at).toLocaleString()} · {activeRun.site_count} sites · Risk unit: {activeRun.risk_unit}</p>}
    {activeRun?.is_demo && <p className="demo-label">Example data — not real predictions or engineering recommendations.</p>}
  </section>;
}

export function RankedSites({ resource, run, onSelect }) {
  const sites = resource.data?.features || [];
  return <section className="card" aria-label="Ranked sites">
    <h2>Ranked sites</h2>
    {!run && <p>Select a published model run to load site rankings.</p>}
    {resource.loading && <p role="status">Loading ranked sites…</p>}
    {resource.error && <p role="alert" className="api-error">{resource.error} <button onClick={resource.refresh}>Retry sites</button></p>}
    {run && !resource.loading && !resource.error && !sites.length && <p>This run has no published sites.</p>}
    {sites.length > 0 && <div className="table-scroll"><table><caption>Priority ranking for {run.run_id}; risk unit: {run.risk_unit}</caption><thead><tr><th>Rank</th><th>Site</th><th>Risk</th><th>Flagged</th></tr></thead><tbody>{sites.map(site => <tr key={site.properties.site_id}><td>{site.properties.rank}</td><th scope="row"><button onClick={() => onSelect(site)}>{site.properties.road_name}<small>{site.properties.site_id}</small></button></th><td>{site.properties.fsi_rate ?? 'Not provided'}</td><td>{site.properties.flagged ? 'Yes' : 'No'}</td></tr>)}</tbody></table></div>}
    {run && !resource.loading && !resource.error && sites.length > 0 && <div className="download-links"><a className="button-link" href={`/api/v1/runs/${encodeURIComponent(run.run_id)}/exports/sites.csv`} download>Export CSV</a><a className="button-link" href={`/api/v1/runs/${encodeURIComponent(run.run_id)}/exports/sites.geojson`} download>Export GeoJSON</a></div>}
  </section>;
}

export function Backtest({ run }) {
  const result = useApi(runPath('backtest', run?.run_id));
  const backtest = result.data?.backtest;
  const percent = value => `${(value * 100).toFixed(1)}%`;
  return <section className="card">
    <div className="details-heading"><h2>Compare methods A, B, and C</h2><button disabled={!run || result.loading} onClick={result.refresh}>Refresh results</button></div>
    {!run && <p>Select a published model run to load its backtest.</p>}
    {result.loading && <p role="status">Loading backtest…</p>}
    {result.error && <p role="alert" className="api-error">{result.error}</p>}
    {run && result.data && !backtest && <p>No backtest results have been published for this run.</p>}
    {backtest && <>{run.is_demo && <p className="demo-label">Example comparison — all counts and rates are invented. These are not measured results or performance claims for the team's model.</p>}<p>Training cutoff: {backtest.training_cutoff}. Test window: {backtest.test_window}.</p><div className="table-scroll"><table><caption>{run.is_demo ? 'Synthetic example comparison' : 'Published comparison'} for {run.run_id}</caption><thead><tr><th>Method</th><th>Capture rate</th><th>95% confidence interval</th><th>Flagged miles</th><th>Test F&amp;SI count</th></tr></thead><tbody>{['A', 'B', 'C'].map(id => {
      const method = backtest.methods.find(item => item.method === id);
      return <tr key={id}><th scope="row">{method ? `${id} · ${method.label}` : `Method ${id}`}</th><td>{method ? percent(method.capture_rate) : 'Not provided'}</td><td>{method ? method.confidence_interval.map(percent).join(' – ') : 'Not provided'}</td><td>{method?.flagged_mileage ?? 'Not provided'}</td><td>{method?.test_fsi_count ?? 'Not provided'}</td></tr>;
    })}</tbody></table></div></>}
  </section>;
}

export function Memos({ run, sites, selectedSite, onSelectSite }) {
  const activeSite = selectedSite || sites[0];
  const path = activeSite && run ? runPath(`sites/${encodeURIComponent(activeSite.properties.site_id)}/memo`, run.run_id) : null;
  const result = useApi(path);
  const memo = result.data?.memo;
  return <section className="card">
    <div className="details-heading"><h2>Countermeasure memos</h2><button disabled={!path || result.loading} onClick={result.refresh}>Refresh memo</button></div>
    <label htmlFor="memo-site">Site</label>
    <select id="memo-site" value={activeSite?.properties.site_id || ''} onChange={event => onSelectSite(event.target.value)} disabled={!run || !sites.length}>
      {!sites.length && <option value="">Select a model site</option>}{sites.map(site => <option key={site.properties.site_id} value={site.properties.site_id}>{site.properties.road_name} · {site.properties.site_id}</option>)}
    </select>
    {!path && <p>Select a published run and model site to read its memo.</p>}
    {result.loading && <p role="status">Loading memo…</p>}
    {result.error && <p role="alert" className="api-error">{result.error}</p>}
    {result.data?.status === 'pending' && <p>No grounded memo has been published for this site.</p>}
    {memo && <article>{run.is_demo && <p className="demo-label">Example memo — invented scenario, with no completed grounding check or engineering approval.</p>}<h3>{memo.title}</h3><p className="memo-text">{memo.text}</p><h3>{run.is_demo ? 'Example provenance' : 'References'}</h3><ul>{memo.references.map((reference, index) => <li key={index}>{reference}</li>)}</ul><p className="map-note">{memo.is_example || run.is_demo ? 'This sample demonstrates the memo layout only. No real site inspection, grounding verification, or engineering review has been performed.' : 'Grounding marked passed by the publishing pipeline. Engineering review is required.'}</p></article>}
    <p className="map-note">Memo generation and PDF export will be enabled after the editor workflow is connected.</p><button disabled>Generate memo</button> <button disabled>Export PDF</button>
  </section>;
}
