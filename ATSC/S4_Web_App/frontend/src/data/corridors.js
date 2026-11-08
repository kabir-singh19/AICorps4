import roadGeometry from './corridors.geojson.json';

export const corridors = [
  { name: 'University Drive', color: '#2563eb' },
  { name: 'Harvey Road', color: '#a21caf' },
  { name: 'Texas Avenue', color: '#c2410c' },
  { name: 'Wellborn Road', color: '#047857' },
];

export { roadGeometry };

export const roadById = new Map(roadGeometry.features.map(feature => [feature.id, feature]));
export const selectableRoadGeometry = {
  ...roadGeometry,
  features: roadGeometry.features.map(feature => ({
    ...feature,
    properties: { ...feature.properties, map_segment_id: feature.id },
  })),
};

export function segmentLengthMiles(feature) {
  const radians = degrees => degrees * Math.PI / 180;
  const points = feature.geometry.coordinates;
  let miles = 0;
  for (let index = 1; index < points.length; index += 1) {
    const [lon1, lat1] = points[index - 1];
    const [lon2, lat2] = points[index];
    const distance = Math.sin(radians(lat2 - lat1) / 2) ** 2
      + Math.cos(radians(lat1)) * Math.cos(radians(lat2)) * Math.sin(radians(lon2 - lon1) / 2) ** 2;
    miles += 2 * 3958.7613 * Math.asin(Math.sqrt(Math.min(1, distance)));
  }
  return miles;
}

// Offer one real mapped section per corridor for keyboard selection.
export const roadChoices = corridors.map(road => ({
  ...road,
  feature: roadGeometry.features
    .filter(feature => feature.properties.corridor === road.name)
    .reduce((longest, feature) => segmentLengthMiles(feature) > segmentLengthMiles(longest) ? feature : longest),
}));

export function corridorBounds(name = 'All corridors') {
  const points = roadGeometry.features
    .filter(feature => name === 'All corridors' || feature.properties.corridor === name)
    .flatMap(feature => feature.geometry.coordinates);
  return [
    [Math.min(...points.map(point => point[0])), Math.min(...points.map(point => point[1]))],
    [Math.max(...points.map(point => point[0])), Math.max(...points.map(point => point[1]))],
  ];
}
