import React, { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import SiteDetails from './components/SiteDetails.jsx';
import Assistant from './components/Assistant.jsx';
import ExampleLab from './components/ExampleLab.jsx';
import { ModelRuns, RankedSites, Backtest, BitLog, Memos, Kpis } from './components/ModelPanels.jsx';
import { runPath, useApi } from './api.js';

const RiskMap = lazy(() => import('./components/RiskMap.jsx'));
const emptySites = { type: 'FeatureCollection', features: [] };
const PAGE_KEYS = { map: 'Risk map', site: 'Site details', backtest: 'Backtest', memos: 'Memos', assistant: 'AI assistant', example: 'Example lab' };
const INTRO = {
  'Risk map': 'Every College Station road segment and intersection, ranked by expected fatal and serious-injury (K+A) crashes per mile per year in 2026.',
  'Site details': 'Why one site ranks where it does: its prediction, crash history and the factors behind the model.',
  'Backtest': 'How well each method, trained only on data known by the end of 2022, found the K+A crashes of 2023 to 2025.',
  'Memos': 'Countermeasure memos for the highest-ranked City-actionable sites. Drafts: every number comes from a tool result, and an engineer must review them.',
  'AI assistant': 'Ask questions about published results.',
  'Example lab': 'A synthetic example of the modeling steps, for teaching only.',
};

function initialState() {
  const params = new URLSearchParams(window.location.search);
  return { page: PAGE_KEYS[params.get('page')] || (params.get('assistant') === '1' ? 'AI assistant' : params.get('example') === '1' ? 'Example lab' : 'Risk map'),
           site: params.get('site'), run: params.get('run') || '' };
}

export default function App() {
  const start = useRef(initialState()).current;
  const [page, setPage] = useState(start.page);
  const [preferredRunId, setPreferredRunId] = useState(start.run);
  const [selectedSiteId, setSelectedSiteId] = useState(start.site);
  const health = useApi('/api/v1/health');
  const assistantEnabled = Boolean(health.data?.assistant_enabled);
  const pages = ['Risk map', 'Site details', 'Backtest', 'Memos', ...(assistantEnabled ? ['AI assistant'] : []), 'Example lab'];
  const runsResource = useApi('/api/v1/runs');
  // Example runs are listed only when no real run is published.
  const allRuns = runsResource.data || [];
  const realRuns = allRuns.filter(run => !run.is_demo);
  const runs = realRuns.length ? realRuns : allRuns;
  const activeRun = runs.find(run => run.run_id === preferredRunId) || runs[0] || null;
  // The site page loads its own record, so a deep link does not wait for the whole network.
  const needSites = page === 'Risk map' || page === 'Memos' || page === 'AI assistant';
  const sitesResource = useApi(needSites ? runPath('sites', activeRun?.run_id) : null);
  const sites = sitesResource.data?.features || [];
  const selectedSite = sites.find(site => site.properties.site_id === selectedSiteId) || null;
  const heading = useRef(null);
  const previousPage = useRef(page);
  const openSite = useCallback(siteId => {
    setSelectedSiteId(siteId);
    setPage('Site details');
  }, []);
  useEffect(() => {
    if (previousPage.current !== page) { heading.current?.focus(); window.scrollTo(0, 0); }
    previousPage.current = page;
    const params = new URLSearchParams();
    const key = Object.keys(PAGE_KEYS).find(k => PAGE_KEYS[k] === page);
    if (key && key !== 'map') params.set('page', key);
    if (selectedSiteId && page === 'Site details') params.set('site', selectedSiteId);
    if (preferredRunId) params.set('run', preferredRunId);
    const query = params.toString();
    window.history.replaceState(null, '', query ? `?${query}` : window.location.pathname);
  }, [page, selectedSiteId, preferredRunId]);
  return <>
    <a className="skip" href="#content">Skip to content</a>
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand-block"><span className="brand" aria-hidden="true">ATSC</span><div><strong>AI Traffic-Safety Consultant</strong><span>College Station, Texas · Texas A&amp;M ECEN 403 Team 4</span></div></div>
        <span className="badge">Research preview</span>
      </div>
      <nav aria-label="Main navigation"><div className="tabs">{pages.map(name => <button key={name} aria-current={page === name ? 'page' : undefined} onClick={() => setPage(name)}>{name}</button>)}</div></nav>
    </header>
    <main id="content">
      <div className="page-head">
        <div><h1 ref={heading} tabIndex={-1}>{page}</h1><p className="lede">{INTRO[page]}</p></div>
        {page !== 'Example lab' && <ModelRuns resource={runsResource} runs={runs} activeRun={activeRun} onChange={id => { setPreferredRunId(id); setSelectedSiteId(null); }} onRefresh={() => { runsResource.refresh(); sitesResource.refresh(); }} />}
      </div>
      {page === 'Risk map' && <>
        <Kpis run={activeRun} sites={sites} />
        <Suspense fallback={<p role="status">Loading the interactive map…</p>}><RiskMap run={activeRun} resource={sitesResource} sites={sitesResource.data || emptySites} selectedSiteId={selectedSiteId} onSelectSite={openSite} /></Suspense>
        <RankedSites resource={sitesResource} run={activeRun} onSelect={openSite} />
      </>}
      {page === 'Site details' && <SiteDetails run={activeRun} siteId={selectedSiteId} onBackToMap={() => setPage('Risk map')} onOpenMemo={() => setPage('Memos')} />}
      {page === 'Backtest' && <><Backtest run={activeRun} /><BitLog run={activeRun} /></>}
      {page === 'Memos' && <Memos run={activeRun} sites={sites} resource={sitesResource} selectedSiteId={selectedSiteId} onSelectSite={setSelectedSiteId} onOpenSite={openSite} />}
      {page === 'AI assistant' && assistantEnabled && <Assistant run={activeRun} sites={sites} selectedSite={selectedSite} onSelectSite={setSelectedSiteId} />}
      {page === 'Example lab' && <ExampleLab />}
      <footer>Planning-level outputs. Every recommendation needs review by a qualified traffic engineer. Map data &copy; OpenStreetMap contributors; crashes from TxDOT CRIS.</footer>
    </main>
  </>;
}
