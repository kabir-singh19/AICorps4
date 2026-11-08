import React, { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import SiteDetails from './components/SiteDetails.jsx';
import Assistant from './components/Assistant.jsx';
import ExampleLab from './components/ExampleLab.jsx';
import { ModelRuns, RankedSites, Backtest, Memos } from './components/ModelPanels.jsx';
import { runPath, useApi } from './api.js';

const RiskMap = lazy(() => import('./components/RiskMap.jsx'));
const emptySites = { type: 'FeatureCollection', features: [] };
const PAGE_KEYS = { map: 'Risk map', site: 'Site details', backtest: 'Backtest', memos: 'Memos', assistant: 'AI assistant', example: 'Example lab' };

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
    if (previousPage.current !== page) heading.current?.focus();
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
    <header><span className="brand">ATSC</span><div><strong>AI Traffic-Safety Consultant</strong><p>Texas A&amp;M capstone · College Station</p></div><span className="badge">Research preview</span></header>
    <div className="layout"><nav aria-label="Main navigation">{pages.map(name => <button key={name} aria-current={page === name ? 'page' : undefined} onClick={() => setPage(name)}>{name}</button>)}</nav>
      <main id="content"><p className="eyebrow">TRAFFIC SAFETY / {page.toUpperCase()}</p><h1 ref={heading} tabIndex={-1}>{page}</h1>
        {page !== 'Example lab' && <ModelRuns resource={runsResource} runs={runs} activeRun={activeRun} onChange={id => { setPreferredRunId(id); setSelectedSiteId(null); }} onRefresh={() => { runsResource.refresh(); sitesResource.refresh(); }} />}
        {page === 'Risk map' && <><Suspense fallback={<p role="status">Loading the interactive map…</p>}><RiskMap run={activeRun} resource={sitesResource} sites={sitesResource.data || emptySites} selectedSiteId={selectedSiteId} onSelectSite={openSite} /></Suspense><RankedSites resource={sitesResource} run={activeRun} onSelect={openSite} /></>}
        {page === 'Site details' && <SiteDetails run={activeRun} siteId={selectedSiteId} onBackToMap={() => setPage('Risk map')} onOpenMemo={() => setPage('Memos')} />}
        {page === 'Backtest' && <Backtest run={activeRun} />}
        {page === 'Memos' && <Memos run={activeRun} sites={sites} selectedSiteId={selectedSiteId} onSelectSite={setSelectedSiteId} onOpenSite={openSite} />}
        {page === 'AI assistant' && assistantEnabled && <Assistant run={activeRun} sites={sites} selectedSite={selectedSite} onSelectSite={setSelectedSiteId} />}
        {page === 'Example lab' && <ExampleLab />}
        <footer>Planning-level outputs require review by qualified traffic engineers.</footer>
      </main></div>
  </>;
}
