import React, { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

// Ordinal classes of expected K+A crashes per mile per year (ICD 5.4): one hue, light to dark
// (validated ramp). Breaks are the run's quintiles of sites with a nonzero rate, so the legend
// states the values used. The MPO HIN overlay is orange, the same color as method A on the backtest.
const COLORS = ['#86b6ef', '#5598e7', '#2a78d6', '#1c5cab', '#0d366b'];
const HIN = '#eb6834';
const INK = '#0b0b0b';

// Breaks at the 75th, 89th, 95th and 99th percentiles of all sites, so the darker classes
// separate the top of the ranking (the 89th percentile is close to the flagging cut).
const PCTS = [0.75, 0.89, 0.95, 0.99];
function quantileBreaks(features) {
  const values = features.map(f => f.properties.fsi_rate || 0).sort((a, b) => a - b);
  if (!values.length) return [0, 0, 0, 0];
  return PCTS.map(q => values[Math.min(values.length - 1, Math.floor(q * values.length))]);
}

function colorExpression(breaks) {
  return ['step', ['coalesce', ['get', 'fsi_rate'], 0], COLORS[0], breaks[0], COLORS[1], breaks[1], COLORS[2], breaks[2], COLORS[3], breaks[3], COLORS[4]];
}

function bounds(features) {
  let w = 180, s = 90, e = -180, n = -90;
  for (const f of features) {
    const pts = f.geometry.type === 'Point' ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const [x, y] of pts) { w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y); }
  }
  return w < e ? [[w, s], [e, n]] : [[-96.4, 30.53], [-96.22, 30.66]];
}

export default function RiskMap({ run, resource, sites, selectedSiteId, onSelectSite }) {
  const container = useRef(null);
  const mapRef = useRef(null);
  const selectRef = useRef(onSelectSite);
  selectRef.current = onSelectSite;
  const [loaded, setLoaded] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [showHin, setShowHin] = useState(false);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [retry, setRetry] = useState(0);
  const breaks = useMemo(() => quantileBreaks(sites.features), [sites]);

  useEffect(() => {
    let map, cleanupPoll = () => {};
    setLoaded(false); setReady(false); setError('');
    try {
      map = new maplibregl.Map({
        container: container.current, bounds: [[-96.4, 30.53], [-96.22, 30.66]], maxZoom: 19, attributionControl: false,
        style: { version: 8,
          sources: {
            streets: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, maxzoom: 19,
                       attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>' },
            sites: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
            selected: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
          },
          layers: [
            { id: 'streets', type: 'raster', source: 'streets', paint: { 'raster-opacity': 0.45, 'raster-saturation': -0.9 } },
            { id: 'flagged-casing', type: 'line', source: 'sites', filter: ['all', ['==', ['geometry-type'], 'LineString'], ['get', 'flagged']], layout: { 'line-cap': 'round' }, paint: { 'line-color': INK, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 3.5, 16, 8.5], 'line-opacity': ['interpolate', ['linear'], ['zoom'], 12, 0, 13.5, 1] } },
            { id: 'segments', type: 'line', source: 'sites', filter: ['==', ['geometry-type'], 'LineString'], layout: { 'line-cap': 'round' }, paint: { 'line-color': COLORS[0], 'line-width': ['interpolate', ['linear'], ['zoom'], 11, ['case', ['get', 'flagged'], 2.5, 1.2], 16, ['case', ['get', 'flagged'], 6, 3]] } },
            { id: 'hin', type: 'line', source: 'sites', filter: ['all', ['==', ['geometry-type'], 'LineString'], ['get', 'in_hin']], layout: { visibility: 'none' }, paint: { 'line-color': HIN, 'line-width': 2, 'line-dasharray': [2, 1.5], 'line-offset': 4 } },
            { id: 'intersections', type: 'circle', source: 'sites', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, ['case', ['get', 'flagged'], 2.6, 1.3], 16, ['case', ['get', 'flagged'], 7, 4.5]], 'circle-color': COLORS[0], 'circle-stroke-color': ['case', ['get', 'flagged'], INK, '#ffffff'], 'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 12, ['case', ['get', 'flagged'], 0, 0], 13.5, ['case', ['get', 'flagged'], 1.5, 0.6], 16, ['case', ['get', 'flagged'], 2, 1]] } },
            { id: 'hin-points', type: 'circle', source: 'sites', filter: ['all', ['==', ['geometry-type'], 'Point'], ['get', 'in_hin']], layout: { visibility: 'none' }, paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 6, 16, 11], 'circle-color': 'transparent', 'circle-stroke-color': HIN, 'circle-stroke-width': 2 } },
            { id: 'selected-line', type: 'line', source: 'selected', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-color': '#eda100', 'line-width': 10, 'line-opacity': 0.7 } },
            { id: 'selected-point', type: 'circle', source: 'selected', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 11, 'circle-color': 'transparent', 'circle-stroke-color': '#eda100', 'circle-stroke-width': 4 } },
          ] },
      });
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl(), 'top-right');
      map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }), 'bottom-left');
      map.addControl(new maplibregl.AttributionControl({ compact: false }), 'bottom-right');
      // 'load' alone can be missed when tile errors arrive during start-up, so also accept any
      // later event, or a poll, that finds the style loaded.
      const markLoaded = () => { if (map.isStyleLoaded()) { setLoaded(true); clearInterval(poll); } };
      const poll = setInterval(markLoaded, 250);
      map.on('load', () => { setLoaded(true); clearInterval(poll); });
      map.on('styledata', markLoaded);
      map.on('idle', markLoaded);
      cleanupPoll = () => clearInterval(poll);
      for (const layer of ['segments', 'intersections']) {
        map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = ''; });
        map.on('click', layer, event => { const id = event.features?.[0]?.properties.site_id; if (id) selectRef.current(String(id)); });
      }
      map.on('error', event => { if (event?.sourceId === 'streets') setError('Basemap tiles could not load; sites are still shown.'); });
    } catch { setError('The map could not start. Check that your browser supports WebGL and retry the map.'); }
    return () => { cleanupPoll(); mapRef.current = null; map?.remove(); };
  }, [retry]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || !sites.features.length) return;
    const data = flaggedOnly ? { type: 'FeatureCollection', features: sites.features.filter(f => f.properties.flagged) } : sites;
    map.getSource('sites').setData(data);
    map.setPaintProperty('segments', 'line-color', colorExpression(breaks));
    map.setPaintProperty('intersections', 'circle-color', colorExpression(breaks));
    setReady(false);
    // Ready: the site layer's data is loaded and a frame including it has been drawn (basemap
    // tiles are not waited for).
    let done = false;
    const onData = event => {
      if (done || event.sourceId !== 'sites' || !map.isSourceLoaded('sites')) return;
      done = true;
      map.once('render', () => setReady(true));
      map.triggerRepaint();
    };
    // Fallback: the map going idle also means the new data has been drawn.
    const onIdle = () => { if (!done && map.isSourceLoaded('sites')) { done = true; setReady(true); } };
    map.on('sourcedata', onData);
    map.on('idle', onIdle);
    onData({ sourceId: 'sites' });
    // Last fallback: poll until the worker has the new data, then wait one frame.
    const poll = setInterval(() => { if (!done && map.isSourceLoaded('sites')) { done = true; clearInterval(poll); requestAnimationFrame(() => setReady(true)); } }, 250);
    return () => { done = true; clearInterval(poll); map.off('sourcedata', onData); map.off('idle', onIdle); };
  }, [sites, loaded, breaks, flaggedOnly]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    map.setLayoutProperty('hin', 'visibility', showHin ? 'visible' : 'none');
    map.setLayoutProperty('hin-points', 'visibility', showHin ? 'visible' : 'none');
  }, [showHin, loaded]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    const f = sites.features.find(site => site.properties.site_id === selectedSiteId);
    map.getSource('selected').setData({ type: 'FeatureCollection', features: f ? [f] : [] });
  }, [selectedSiteId, sites, loaded]);

  useEffect(() => {
    if (mapRef.current && loaded && sites.features.length) mapRef.current.fitBounds(bounds(sites.features), { padding: 20, duration: 0 });
  }, [loaded, sites]);

  const n = sites.features.length;
  const nFlagged = sites.features.filter(f => f.properties.flagged).length;
  const fmt = v => (v >= 10 ? v.toFixed(0) : v >= 1 ? v.toFixed(1) : v.toPrecision(2));
  return <section className="card map-card" aria-label="Risk map">
    <div className="map-toolbar" role="group" aria-label="Map layers">
      <label className="chip"><input type="checkbox" checked={showHin} onChange={e => setShowHin(e.target.checked)} /> Show MPO high-injury network</label>
      <label className="chip"><input type="checkbox" checked={flaggedOnly} onChange={e => setFlaggedOnly(e.target.checked)} /> Flagged sites only</label>
      <span className="map-hint">Click any road or intersection for its details.</span>
      {error && <button onClick={() => setRetry(v => v + 1)}>Retry map</button>}
    </div>
    <p id="map-description" className="sr-only">{`Map of ${n} road sites colored by expected fatal and serious-injury crashes per mile per year; ${nFlagged} flagged sites drawn with a dark outline. The ranked list below the map has the same sites in table form.`}</p>
    <div className="map-wrap">
      <div ref={container} className="map" data-testid="risk-map" data-ready={ready ? 'true' : 'false'} data-loaded={loaded ? 'true' : 'false'} data-sites={n} aria-describedby="map-description" />
      {n > 0 && <div className="map-legend" aria-label="Map legend">
        <strong>K+A crashes per mile per year</strong>
        <div className="legend-ramp">{COLORS.map(c => <i key={c} style={{ background: c }} aria-hidden="true" />)}</div>
        <div className="legend-scale"><span>{fmt(breaks[0])}</span><span>{fmt(breaks[1])}</span><span>{fmt(breaks[2])}</span><span>{fmt(breaks[3])}</span></div>
        <span className="legend-row muted">Classes: lowest 75% of sites, then 75-89th, 89-95th, 95-99th percentile, top 1%</span>
        <span className="legend-row"><i className="legend-flagged" aria-hidden="true" />Flagged: top 11% of length (thicker; outlined when zoomed in)</span>
        <span className="legend-row"><i className="legend-hin" aria-hidden="true" />MPO high-injury network{showHin ? '' : ' (toggle above)'}</span>
        <span className="legend-row muted">Lines: segments · circles: intersections</span>
      </div>}
    </div>
    <p className="map-status" role="status" data-testid="map-status">{resource.loading ? 'Loading sites…' : resource.error ? resource.error : ready ? `${n.toLocaleString()} sites drawn, ${nFlagged.toLocaleString()} flagged.${error ? ' ' + error : ''}` : error || (n ? 'Drawing sites…' : run ? 'No sites in this run.' : 'Loading…')}</p>
  </section>;
}
