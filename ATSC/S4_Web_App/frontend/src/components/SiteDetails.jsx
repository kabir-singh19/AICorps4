import React from 'react';
import { roadGeometry, segmentLengthMiles } from '../data/corridors.js';

export default function SiteDetails({ selectedRoad, modelSite, run, resource, onBackToMap, onAskAI }) {
  if (!selectedRoad && !modelSite) return <section className="card">
    <h2>Select a road segment</h2>
    <p>Click a highlighted road on the map, or use the road details buttons below it.</p>
    <button onClick={onBackToMap}>Go to map</button>
  </section>;

  const properties = modelSite?.properties;
  const corridor = properties?.road_name || selectedRoad?.properties.corridor;
  const name = properties?.road_name || selectedRoad?.properties.name;
  const osmWayId = selectedRoad?.properties.osm_way_id;
  const length = properties?.length_mi ?? (selectedRoad ? segmentLengthMiles(selectedRoad) : null);
  const formattedLength = length === null ? 'Not provided' : length < 0.01
    ? `${Math.round(length * 5280).toLocaleString()} feet`
    : `${length.toFixed(2)} miles`;

  return <>
    <section className="card" aria-label="Selected road details">
      <div className="details-heading"><div><p className="eyebrow">SELECTED ROAD SEGMENT</p><h2>{corridor}</h2></div><button onClick={onBackToMap}>Back to map</button></div>
      <dl className="details-grid">
        <div><dt>Mapped road name</dt><dd>{name}</dd></div>
        <div><dt>Segment length (approx.)</dt><dd>{formattedLength}</dd></div>
        <div><dt>{modelSite ? 'Coordinates (latitude, longitude)' : 'Location'}</dt><dd>{modelSite ? (modelSite.geometry.type === 'Point' ? modelSite.geometry.coordinates : modelSite.geometry.coordinates[0]).slice().reverse().map(value => value.toFixed(5)).join(', ') : 'College Station, Texas'}</dd></div>
        <div><dt>Map source</dt><dd>{osmWayId ? <a href={`https://www.openstreetmap.org/way/${osmWayId}`} target="_blank" rel="noopener noreferrer">OpenStreetMap road reference {osmWayId}</a> : 'Published model site geometry'}</dd></div>
      </dl>
      <p className="map-note">{properties ? `Model site: ${properties.site_id} · Run: ${run.run_id}. Length is supplied by the model when available; otherwise it is estimated from the mapped section.` : `Length is calculated from the mapped section. Map snapshot: ${roadGeometry.metadata.retrieved_on}.`}</p>
    </section>
    <section className="card" aria-label="Model results">
      <h2>Model results</h2>
      {properties && <button onClick={onAskAI}>Ask AI about this site</button>}
      {resource.loading && <p role="status">Loading model site results…</p>}
      {resource.error && <p role="alert" className="api-error">{resource.error}</p>}
      {!properties && !resource.loading && !resource.error && <p>{run ? 'No model result is linked to this mapped section in the selected run.' : 'Select a published model run to see results for this site.'}</p>}
      {properties && <dl className="details-grid">
        <div><dt>Crash history</dt><dd>{properties.crash_history || 'Not provided'}</dd></div>
        <div><dt>Fatal and serious-injury risk</dt><dd>{properties.fsi_rate === null ? 'Not provided' : `${properties.fsi_rate} ${run.risk_unit}`}</dd></div>
        <div><dt>Priority rank</dt><dd>{properties.rank}</dd></div>
        <div><dt>Flagged for review</dt><dd>{properties.flagged ? 'Yes' : 'No'}</dd></div>
        <div><dt>Top risk factors</dt><dd>{properties.top_factors.length ? properties.top_factors.join(', ') : 'Not provided'}</dd></div>
      </dl>}
    </section>
  </>;
}
