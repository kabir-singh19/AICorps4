// OpenStreetMap tiles are an external service; tests stub them with a blank tile so timings
// measure this app and the suite does not load the public tile servers.
const BLANK_PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=', 'base64');

export async function stubTiles(context) {
  await context.route('https://tile.openstreetmap.org/**', route => route.fulfill({ status: 200, contentType: 'image/png', body: BLANK_PNG }));
}

export async function firstRun(request) {
  const runs = await (await request.get('/api/v1/runs')).json();
  return runs.find(r => !r.is_demo);
}

export async function topSites(request, runId, n = 5) {
  const fc = await (await request.get(`/api/v1/sites?run_id=${encodeURIComponent(runId)}&flagged=true`)).json();
  return fc.features.slice(0, n).map(f => f.properties);
}
