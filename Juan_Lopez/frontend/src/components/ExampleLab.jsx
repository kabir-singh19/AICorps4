import React, { useEffect, useRef, useState } from 'react';
import { postJson, useApi } from '../api.js';

const number = value => new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 }).format(value);

export default function ExampleLab() {
  const resource = useApi('/api/v1/examples');
  const [values, setValues] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef(null);
  const operation = useRef(0);
  const data = resource.data;
  useEffect(() => () => { operation.current += 1; controller.current?.abort(); }, []);
  useEffect(() => {
    if (data) {
      const first = data.sites.find(site => site.site_id === 'demo-university');
      setValues(first.inputs);
      setResult(first.prediction);
    }
  }, [data]);

  function change(next) {
    operation.current += 1;
    controller.current?.abort();
    setBusy(false); setValues(next); setResult(null); setError('');
  }

  async function run(event) {
    event.preventDefault();
    const id = ++operation.current;
    controller.current?.abort();
    controller.current = new AbortController();
    setBusy(true); setError(''); setResult(null);
    try {
      const prediction = await postJson('/api/v1/examples/predict', Object.fromEntries(Object.entries(values).map(([key, value]) => [key, Number(value)])), controller.current.signal);
      if (operation.current === id) setResult(prediction);
    } catch (failure) {
      if (operation.current === id && failure.name !== 'AbortError') setError(failure.message);
    } finally { if (operation.current === id) setBusy(false); }
  }

  if (resource.loading) return <p role="status">Loading the example model and report…</p>;
  if (resource.error) return <section className="card"><p className="api-error" role="alert">{resource.error}</p><button onClick={resource.refresh}>Retry example</button></section>;
  if (!data || !values) return null;

  return <div className="example-lab">
    <div className="example-notice"><strong>SYNTHETIC EXAMPLE · FOR DEMONSTRATION</strong><p>{data.disclaimer}</p></div>
    <div className="example-columns">
      <section className="card" aria-label="Try the example model">
        <p className="eyebrow">01 / TRY THE MODEL</p><h2>A small, working AI model</h2>
        <p>This example uses logistic regression trained on generated records. Change the fictional road conditions and run the model to see how its score changes. It works without an API key.</p>
        <label htmlFor="example-preset">Start with an invented road scenario</label>
        <select id="example-preset" defaultValue="demo-university" onChange={event => change(data.sites.find(site => site.site_id === event.target.value).inputs)}>{data.sites.map(site => <option key={site.site_id} value={site.site_id}>{site.road_name} — invented inputs</option>)}</select>
        <form onSubmit={run}>
          <div className="example-inputs">{data.model.features.map(feature => <div key={feature.key}><label htmlFor={`example-${feature.key}`}>{feature.label} <small>({feature.unit})</small></label><input id={`example-${feature.key}`} type="number" min={feature.min} max={feature.max} step={feature.step} value={values[feature.key]} onChange={event => change({ ...values, [feature.key]: event.target.value })} required/><small className="map-note">{number(feature.min)}–{number(feature.max)} {feature.unit}</small></div>)}</div>
          <button className="primary-button" disabled={busy}>{busy ? 'Running example…' : 'Run example model'}</button>
        </form>
        {error && <p role="alert" className="api-error">{error}</p>}
        <div aria-live="polite" aria-atomic="true">{result ? <div className="example-result"><p className="eyebrow">SYNTHETIC REVIEW SCORE</p><strong className="example-score">{result.score.toFixed(3)} <small>/ 1</small></strong><p>{result.flagged ? 'At or above the demo review threshold' : 'Below the demo review threshold'} (0.50).</p><p className="map-note">This is a score for an invented review label, not the probability of a crash. Changing these inputs does not demonstrate a real safety benefit.</p><details><summary>How the example calculated this score</summary><p>Each input is scaled to the allowed range. The trained model combines it with a learned weight and converts the total to a score between 0 and 1. Contributions below are weighted inputs before this conversion.</p><ul>{result.contributions.map(item => <li key={item.feature}>{item.label}: {number(item.logit_contribution)}</li>)}</ul><p className="map-note">These contributions describe this example model, not causal effects.</p></details></div> : <p role="status">Inputs changed. Run the example to calculate a new score.</p>}</div>
      </section>
      <aside className="card" aria-label="Example model information"><p className="eyebrow">MODEL CARD</p><h2>What powers this example?</h2><dl className="example-model-card"><div><dt>Method</dt><dd>{data.model.algorithm}</dd></div><div><dt>Training data</dt><dd>{data.model.training_records} synthetic records</dd></div><div><dt>Separate test data</dt><dd>{data.model.holdout_records} synthetic records</dd></div><div><dt>Inputs</dt><dd>Speed, vehicle volume, lanes, crossings</dd></div><div><dt>Output</dt><dd>A demonstration review score</dd></div></dl><p>{data.model.training_source}</p><p className="map-note">This teaching model is separate from your team's traffic-risk model and Texas A&amp;M's AI service. It does not use real crash history.</p><a className="button-link" href="#example-report">Read the example report ↓</a></aside>
    </div>
    <article className="card example-report" id="example-report" aria-label="Example corridor report"><div className="details-heading"><div><p className="eyebrow">02 / EXAMPLE REPORT</p><h2>{data.title}</h2></div><span className="badge">Synthetic data</span></div><p className="map-note">This fixed report uses the four bundled scenarios. Changes in the model form above do not rewrite this report.</p>
      <div className="download-links"><a className="button-link" href="/api/v1/examples/report.html" target="_blank" rel="noopener noreferrer">Open printable report</a><a className="button-link" href="/api/v1/examples/report.html?download=true" download>Download example report</a></div>
      <h3>Summary</h3><p>{data.summary}</p><div className="table-scroll"><table><caption>Invented scenarios ranked by synthetic review score; no real risk ranking is implied.</caption><thead><tr><th scope="col">Rank</th><th scope="col">Road scenario</th><th scope="col">Score (0–1)</th><th scope="col">Demo result</th></tr></thead><tbody>{data.sites.map(site => <tr key={site.site_id}><td>{site.rank}</td><th scope="row">{site.road_name}</th><td>{site.prediction.score.toFixed(3)}</td><td>{site.prediction.flagged ? 'Review' : 'Below threshold'}</td></tr>)}</tbody></table></div>
      <details><summary>View the invented inputs behind this report</summary><div className="table-scroll"><table><thead><tr><th scope="col">Road scenario</th>{data.model.features.map(feature => <th scope="col" key={feature.key}>{feature.label}<small>{feature.unit}</small></th>)}</tr></thead><tbody>{data.sites.map(site => <tr key={site.site_id}><th scope="row">{site.road_name}</th>{data.model.features.map(feature => <td key={feature.key}>{number(site.inputs[feature.key])}</td>)}</tr>)}</tbody></table></div></details>
      <h3>Method</h3><p>{data.method}</p><h3>What the scores mean</h3><p>{data.interpretation}</p><h3>What comes next</h3><ol>{data.next_steps.map(step => <li key={step}>{step}</li>)}</ol><h3>Provenance</h3><ul>{data.provenance.map(item => <li key={item}>{item}</li>)}</ul><p className="demo-label">Example only — no actual crash history, validated backtest, or approved treatment recommendation.</p>
    </article>
  </div>;
}
