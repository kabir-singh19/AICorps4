import React, { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import SiteDetails from './components/SiteDetails.jsx';
import Assistant from './components/Assistant.jsx';
import ExampleLab from './components/ExampleLab.jsx';
import { ModelRuns, RankedSites, Backtest, Memos } from './components/ModelPanels.jsx';
import { runPath, useApi } from './api.js';
import { roadById } from './data/corridors.js';

const RiskMap = lazy(() => import('./components/RiskMap.jsx'));
const emptySites = { type: 'FeatureCollection', features: [] };
const pages = ['Risk map', 'Site details', 'Backtest', 'Memos', 'AI assistant', 'Example lab'];
export default function App() {
  const [page, setPage] = useState(() => new URLSearchParams(window.location.search).get('example') === '1' ? 'Example lab' : pages[0]);
  const [selectedRoad, setSelectedRoad] = useState(null);
  const [preferredRunId, setPreferredRunId] = useState('');
  const [selectedSiteId, setSelectedSiteId] = useState(null);
  const runsResource = useApi('/api/v1/runs');
  const runs = runsResource.data || [];
  const activeRun = runs.find(run => run.run_id === preferredRunId) || runs[0] || null;
  const sitesResource = useApi(runPath('sites', activeRun?.run_id));
  const sites = sitesResource.data?.features || [];
  const selectedSite = selectedSiteId !== null
    ? sites.find(site => site.properties.site_id === selectedSiteId)
    : sites.find(site => site.properties.map_segment_id && site.properties.map_segment_id === selectedRoad?.id);
  const heading = useRef(null);
  const previousPage = useRef(page);
  const selectRoad = useCallback(feature => {
    setSelectedRoad(feature);
    setSelectedSiteId(null);
    setPage('Site details');
  }, []);
  const selectModelSite = useCallback(feature => {
    setSelectedSiteId(feature.properties.site_id);
    setSelectedRoad(roadById.get(feature.properties.map_segment_id) || null);
    setPage('Site details');
  }, []);
  useEffect(() => {
    if (previousPage.current !== page) heading.current?.focus();
    previousPage.current = page;
  }, [page]);
  return <>
    <a className="skip" href="#content">Skip to content</a>
    <header><span className="brand">ATSC</span><div><strong>AI Traffic-Safety Consultant</strong><p>Texas A&amp;M capstone · College Station</p></div><span className="badge">Research preview</span></header>
    <div className="layout"><nav aria-label="Main navigation">{pages.map(name => <button key={name} aria-current={page === name ? 'page' : undefined} onClick={() => setPage(name)}>{name}</button>)}</nav>
      <main id="content"><p className="eyebrow">TRAFFIC SAFETY / {page.toUpperCase()}</p><h1 ref={heading} tabIndex={-1}>{page}</h1><p className="intro">Explore road risk, understand flagged sites, and review the evidence behind planning decisions.</p>
        {page !== 'Example lab' && <ModelRuns resource={runsResource} runs={runs} activeRun={activeRun} onChange={id => { setPreferredRunId(id); setSelectedSiteId(null); }} onRefresh={() => { runsResource.refresh(); sitesResource.refresh(); }} />}
        {page === 'Risk map' && <><Suspense fallback={<p role="status">Loading the interactive map…</p>}><RiskMap selectedRoad={selectedRoad} onSelectRoad={selectRoad} modelSites={sitesResource.data || emptySites} selectedModelSite={selectedSite} onSelectModelSite={selectModelSite} /></Suspense><RankedSites resource={sitesResource} run={activeRun} onSelect={selectModelSite} /></>}
        {page === 'Site details' && <SiteDetails selectedRoad={selectedRoad} modelSite={selectedSite} run={activeRun} resource={sitesResource} onBackToMap={() => setPage('Risk map')} />}
        {page === 'Backtest' && <Backtest run={activeRun} />}
        {page === 'Memos' && <Memos run={activeRun} sites={sites} selectedSite={selectedSite} onSelectSite={setSelectedSiteId} />}
        {page === 'AI assistant' && <Assistant run={activeRun} sites={sites} selectedSite={selectedSite} onSelectSite={setSelectedSiteId} />}
        {page === 'Example lab' && <ExampleLab />}
        <footer>Planning-level outputs require review by qualified traffic engineers.</footer>
      </main></div>
  </>;
}
