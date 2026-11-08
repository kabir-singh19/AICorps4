import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { corridors, selectableRoadGeometry, corridorBounds, roadById, roadChoices } from '../data/corridors.js';

export default function RiskMap({ selectedRoad, onSelectRoad, modelSites, selectedModelSite, onSelectModelSite }) {
  const container = useRef(null);
  const mapRef = useRef(null);
  const modelSitesRef = useRef(modelSites);
  const modelSelectRef = useRef(onSelectModelSite);
  modelSitesRef.current = modelSites;
  modelSelectRef.current = onSelectModelSite;
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [retry, setRetry] = useState(0);
  const [focusedCorridor, setFocusedCorridor] = useState('All corridors');
  useEffect(() => {
    let map;
    setError('');
    setLoaded(false);
    const initialCorridor = selectedRoad?.properties.corridor || 'All corridors';
    setFocusedCorridor(initialCorridor);
    try {
      map = new maplibregl.Map({
        container: container.current,
        bounds: corridorBounds(initialCorridor), fitBoundsOptions: { padding: 28, maxZoom: 15 }, maxZoom: 19,
        attributionControl: false,
        style: {
          version: 8,
          sources: {
            streets: {
              type: 'raster',
              tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
              tileSize: 256,
              maxzoom: 19,
              attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>',
            },
            corridors: { type: 'geojson', data: selectableRoadGeometry },
            selected: { type: 'geojson', data: { type: 'FeatureCollection', features: selectedRoad ? [selectedRoad] : [] } },
            'model-sites': { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
            'selected-model': { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
          },
          layers: [
            { id: 'streets', type: 'raster', source: 'streets' },
            {
              id: 'corridor-outline', type: 'line', source: 'corridors',
              layout: { 'line-cap': 'round', 'line-join': 'round' },
              paint: { 'line-color': '#ffffff', 'line-width': 8, 'line-opacity': 0.9 },
            },
            {
              id: 'corridor-lines', type: 'line', source: 'corridors',
              layout: { 'line-cap': 'round', 'line-join': 'round' },
              paint: {
                'line-color': ['match', ['get', 'corridor'], ...corridors.flatMap(road => [road.name, road.color]), '#173e34'],
                'line-width': 4,
                'line-opacity': initialCorridor === 'All corridors' ? 1 : ['case', ['==', ['get', 'corridor'], initialCorridor], 1, 0.3],
              },
            },
            {
              id: 'selected-road', type: 'line', source: 'selected',
              layout: { 'line-cap': 'round', 'line-join': 'round' },
              paint: { 'line-color': '#192d29', 'line-width': 8, 'line-gap-width': 4 },
            },
            {
              id: 'road-hit-area', type: 'line', source: 'corridors',
              layout: { 'line-cap': 'round', 'line-join': 'round' },
              paint: { 'line-width': 18, 'line-opacity': 0 },
            },
            { id: 'model-sites-line', type: 'line', source: 'model-sites', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-width': 7, 'line-color': ['case', ['get', 'flagged'], '#9a3412', '#0369a1'] } },
            { id: 'model-sites-point', type: 'circle', source: 'model-sites', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 7, 'circle-color': ['case', ['get', 'flagged'], '#9a3412', '#0369a1'], 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2 } },
            { id: 'model-line-hit', type: 'line', source: 'model-sites', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-width': 20, 'line-opacity': 0 } },
            { id: 'model-point-hit', type: 'circle', source: 'model-sites', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 14, 'circle-opacity': 0 } },
            { id: 'selected-model-line', type: 'line', source: 'selected-model', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-width': 3, 'line-color': '#111827', 'line-dasharray': [2, 2] } },
            { id: 'selected-model-point', type: 'circle', source: 'selected-model', filter: ['==', ['geometry-type'], 'Point'], paint: { 'circle-radius': 11, 'circle-color': 'transparent', 'circle-stroke-color': '#111827', 'circle-stroke-width': 3 } },
          ],
        },
      });
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl(), 'top-right');
      map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }), 'bottom-left');
      map.addControl(new maplibregl.AttributionControl({ compact: false }), 'bottom-right');
      map.on('load', () => setLoaded(true));
      map.on('mouseenter', 'road-hit-area', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'road-hit-area', () => { map.getCanvas().style.cursor = ''; });
      map.on('click', 'road-hit-area', event => {
        if (map.queryRenderedFeatures(event.point, { layers: ['model-line-hit', 'model-point-hit'] }).length) return;
        const road = roadById.get(event.features?.[0]?.properties.map_segment_id);
        if (road) onSelectRoad(road);
      });
      for (const layer of ['model-line-hit', 'model-point-hit']) {
        map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = ''; });
        map.on('click', layer, event => {
          const id = event.features?.[0]?.properties.site_id;
          const site = modelSitesRef.current?.features.find(feature => feature.properties.site_id === id);
          if (site) modelSelectRef.current(site);
        });
      }
      map.on('error', () => setError('Street map tiles could not load. Check your internet connection and retry the map.'));
    } catch { setError('The map could not start. Check that your browser supports WebGL and retry the map.'); }
    return () => {
      mapRef.current = null;
      map?.remove();
    };
  }, [retry, selectedRoad, onSelectRoad]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const update = () => {
      map.getSource('model-sites')?.setData(modelSites);
      map.getSource('selected-model')?.setData({ type: 'FeatureCollection', features: selectedModelSite ? [selectedModelSite] : [] });
    };
    if (map.isStyleLoaded()) update();
    else map.once('load', update);
    return () => map.off('load', update);
  }, [modelSites, selectedModelSite, loaded, retry, selectedRoad]);
  function focusRoad(name) {
    const map = mapRef.current;
    if (!map || !loaded) return;
    setFocusedCorridor(name);
    map.fitBounds(corridorBounds(name), { padding: 28, maxZoom: 15, bearing: 0, pitch: 0 });
    map.setPaintProperty('corridor-lines', 'line-opacity', name === 'All corridors' ? 1 : ['case', ['==', ['get', 'corridor'], name], 1, 0.3]);
  }
  return <section aria-label="Risk map">
    <div className="map-toolbar" role="group" aria-label="Focus on a road">
      <button disabled={!loaded} aria-pressed={focusedCorridor === 'All corridors'} onClick={() => focusRoad('All corridors')}>All corridors</button>
      {corridors.map(road => <button key={road.name} disabled={!loaded} aria-pressed={focusedCorridor === road.name} onClick={() => focusRoad(road.name)}><span className="road-swatch" style={{ backgroundColor: road.color }} aria-hidden="true" />{road.name}</button>)}
      {error && <button onClick={() => setRetry(value => value + 1)}>Retry map</button>}
    </div>
    <div ref={container} className="map" />
    {modelSites.features.length > 0 && <div className="map-legend" aria-label="Published model site legend"><span><i style={{background:'#9a3412'}} aria-hidden="true"/>Flagged for review</span><span><i style={{background:'#0369a1'}} aria-hidden="true"/>Other published sites</span><span>{modelSites.features.length} published sites</span></div>}
    <p role="status">{error || (loaded ? `Viewing ${focusedCorridor === 'All corridors' ? 'all four corridors' : focusedCorridor}. Click a highlighted road to open its details.` : 'Loading the corridor map…')}</p>
    <p className="map-note"></p>
    {selectedRoad && <p className="map-note">Selected: {selectedRoad.properties.corridor}. The outlined section is your last selection.</p>}
    <section className="card" aria-label="Road selection">
      <h2>Road details</h2>
      <p>Select a road below to view one mapped section, or click the map to choose a specific section.</p>
      <div className="road-choices">{roadChoices.map(road => <button key={road.name} onClick={() => onSelectRoad(road.feature)}><span className="road-swatch" style={{ backgroundColor: road.color }} aria-hidden="true" />{road.name} — view details</button>)}</div>
    </section>
  </section>;
}
