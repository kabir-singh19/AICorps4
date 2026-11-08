import React, { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

// Sequential classes of expected K+A crashes per mile per year (ICD 5.4). Breaks are the run's
// quintiles of sites with a nonzero rate, so the legend always states the values used.
const COLORS = ['#fde68a', '#fbbf24', '#f97316', '#dc2626', '#7f1d1d'];

function quantileBreaks(features) {
  const values = features.map(f => f.properties.fsi_rate).filter(v => v > 0).sort((a, b) => a - b);
  if (!values.length) return [0, 0, 0, 0];
  return [0.2, 0.4, 0.6, 0.8].map(q => values[Math.min(values.length - 1, Math.floor(q * values.length))]);
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
    let map;
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
            { id: 'streets', type: 'raster', source: 'streets', paint: { 'raster-opacity': 0.55 } },
            { id: 'flagged-casing', type: 'line', source: 'sites', filter: ['all', ['==', ['geometry-type'], 'LineString'], ['get', 'flagged']], layout: { 'line-cap': 'round' }, paint: { 'line-color': '#111827', 'line-width': 7 } },
            { id: 'segments', type: 'line', source: 'sites', filter: ['==', ['geometry-type'], 'LineString'], layout: { 'line-cap': 'round' }, paint: { 'line-color': '#9ca3af', 'line-width': ['case', ['get', 'flagged'], 4.5, 2] } },
            { id: 'hin', type: 'line', source: 'sites', filter: ['all', ['==', ['geometry-type'], 'LineString'], ['get', 'in_hin']], layout: { visibility: 'none' }, paint: { 'line-color': '#6d28d9', 'line-width': 2, 'line-dasharray': [2, 1.5], 'line-offset': 4 } },
            { id: 'intersections', type: 'circle', source: 'sites', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': ['case', ['get', 'flagged'], 5.5, 3], 'circle-color': '#9ca3af', 'circle-stroke-color': ['case', ['get', 'flagged'], '#111827', '#ffffff'], 'circle-stroke-width': ['case', ['get', 'flagged'], 2, 0.5] } },
            { id: 'hin-points', type: 'circle', source: 'sites', filter: ['all', ['==', ['geometry-type'], 'Point'], ['get', 'in_hin']], layout: { visibility: 'none' }, paint: { 'circle-radius': 8, 'circle-color': 'transparent', 'circle-stroke-color': '#6d28d9', 'circle-stroke-width': 1.5 } },
            { id: 'selected-line', type: 'line', source: 'selected', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-color': '#0ea5e9', 'line-width': 9, 'line-opacity': 0.6 } },
            { id: 'selected-point', type: 'circle', source: 'selected', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 11, 'circle-color': 'transparent', 'circle-stroke-color': '#0ea5e9', 'circle-stroke-width': 3 } },
          ] },
      });
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl(), 'top-right');
      map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }), 'bottom-left');
      map.addControl(new maplibregl.AttributionControl({ compact: false }), 'bottom-right');
      map.on('load', () => setLoaded(true));
      for (const layer of ['segments', 'intersections']) {
        map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = ''; });
        map.on('click', layer, event => { const id = event.features?.[0]?.properties.site_id; if (id) selectRef.current(String(id)); });
      }
      map.on('error', event => { if (event?.sourceId === 'streets') setError('Basemap tiles could not load; sites are still shown.'); });
    } catch { setError('The map could not start. Check that your browser supports WebGL and retry the map.'); }
    return () => { mapRef.current = null; map?.remove(); };
  }, [retry]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || !sites.features.length) return;
    const data = flaggedOnly ? { type: 'FeatureCollection', features: sites.features.filter(f => f.properties.flagged) } : sites;
    map.getSource('sites').setData(data);
    map.setPaintProperty('segments', 'line-color', colorExpression(breaks));
    map.setPaintProperty('intersections', 'circle-color', colorExpression(breaks));
    setReady(false);
    map.once('idle', () => setReady(true));
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
  const fmt = v => v.toFixed(2);
  return <section aria-label="Risk map">
    <div className="map-toolbar" role="group" aria-label="Map layers">
      <label><input type="checkbox" checked={showHin} onChange={e => setShowHin(e.target.checked)} /> Show MPO high-injury network</label>
      <label><input type="checkbox" checked={flaggedOnly} onChange={e => setFlaggedOnly(e.target.checked)} /> Flagged sites only</label>
      {error && <button onClick={() => setRetry(v => v + 1)}>Retry map</button>}
    </div>
    <div ref={container} className="map" data-testid="risk-map" data-ready={ready ? 'true' : 'false'} data-sites={n} role="img" aria-label={`Map of ${n} road sites colored by expected fatal and serious-injury crashes per mile per year; ${nFlagged} flagged sites drawn with a thick dark outline.`} />
    {n > 0 && <div className="map-legend" aria-label="Map legend">
      <strong>K+A crashes per mile per year</strong>
      {COLORS.map((c, i) => <span key={c}><i style={{ background: c }} aria-hidden="true" />{i === 0 ? `under ${fmt(breaks[0])}` : i === 4 ? `${fmt(breaks[3])} or more` : `${fmt(breaks[i - 1])} to ${fmt(breaks[i])}`}</span>)}
      <span><i className="legend-flagged" aria-hidden="true" />Flagged (top 11% of length): thick dark outline</span>
      <span><i className="legend-hin" aria-hidden="true" />MPO HIN (dashed purple, when shown)</span>
      <span>Lines are segments; circles are intersections.</span>
    </div>}
    <p role="status" data-testid="map-status">{error || (resource.loading ? 'Loading sites…' : resource.error ? resource.error : ready ? `Map ready: ${n} sites, ${nFlagged} flagged. Click a site to open its details.` : n ? 'Drawing sites…' : run ? 'No sites in this run.' : 'Loading…')}</p>
  </section>;
}
