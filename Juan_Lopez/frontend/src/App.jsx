import { useEffect, useState } from 'react';
import RiskMap from './components/RiskMap.jsx';
import { getRuns } from './api.js';

const pages = ['Risk map', 'Site details', 'Backtest', 'Memos'];
export default function App() {
  const [page, setPage] = useState(pages[0]);
  const [status, setStatus] = useState('Checking model runs…');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setStatus('Checking model runs…');
    getRuns(controller.signal).then(runs => setStatus(runs.length ? 'Runs available; data display integration pending.' : 'No published model runs available.'))
      .catch(error => { if (error.name !== 'AbortError') setStatus(error.message); });
    return () => controller.abort();
  }, [retry]);
  return <>
    <a className="skip" href="#content">Skip to content</a>
    <header><span className="brand">ATSC</span><div><strong>AI Traffic-Safety Consultant</strong><p>College Station · AI Corps Team 4</p></div><span className="badge">Development starter</span></header>
    <div className="layout"><nav aria-label="Main navigation">{pages.map(name => <button key={name} aria-current={page === name ? 'page' : undefined} onClick={() => setPage(name)}>{name}</button>)}</nav>
      <main id="content"><p className="eyebrow">TRAFFIC SAFETY / {page.toUpperCase()}</p><h1>{page}</h1><p className="intro">Explore road risk, understand flagged sites, and review the evidence behind planning decisions.</p>
        <div className="notice" role="status">{status} <button onClick={() => setRetry(value => value + 1)}>Retry connection</button></div>
        {page === 'Risk map' && <><RiskMap /><section className="card"><h2>Ranked sites</h2><p>Connect the published run and site GeoJSON endpoint to display rankings. No computed results are included in this starter.</p><button disabled>Export CSV</button> <button disabled>Export GeoJSON</button></section></>}
        {page === 'Site details' && <section className="card"><h2>Select a road segment or intersection</h2><p>This page will show crash history, expected fatal and serious-injury risk, and the top five risk factors for the selected run.</p></section>}
        {page === 'Backtest' && <section className="card"><h2>Compare methods A, B, and C</h2><p>Training cutoff: December 31, 2022. Test window: 2023–2025.</p><table><caption>Results pending model integration</caption><thead><tr><th>Method</th><th>Capture rate</th><th>95% confidence interval</th></tr></thead><tbody>{['A · Consultant HIN', 'B · Negative binomial + EB', 'C · ATSC ML + EB'].map(method => <tr key={method}><th scope="row">{method}</th><td>Pending</td><td>Pending</td></tr>)}</tbody></table></section>}
        {page === 'Memos' && <section className="card"><h2>Countermeasure memos</h2><p>No memo selected. Site memos will show crash profiles, countermeasures, benefit/cost assumptions, and references.</p><p>Generation requires an editor role. Grounding failures block publication.</p><button disabled>Generate memo</button> <button disabled>Export PDF</button></section>}
        <footer>Planning-level outputs require review by qualified traffic engineers.</footer>
      </main></div>
  </>;
}
