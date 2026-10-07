import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function RiskMap() {
  const container = useRef(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let map;
    try {
      map = new maplibregl.Map({
        container: container.current,
        center: [-96.3344, 30.628], zoom: 12,
        // Blank local style until the team selects a basemap provider and attribution.
        style: { version: 8, sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#e7ece9' } }] },
      });
      map.addControl(new maplibregl.NavigationControl(), 'top-right');
      map.on('error', () => setError('Map could not load. Site information remains available below.'));
    } catch { setError('WebGL is unavailable. Use the site list when data is connected.'); }
    return () => map?.remove();
  }, []);
  return <section aria-label="Risk map"><div ref={container} className="map" /><p role="status">{error || 'Map canvas centered on College Station. Basemap and risk layers are pending integration.'}</p></section>;
}
