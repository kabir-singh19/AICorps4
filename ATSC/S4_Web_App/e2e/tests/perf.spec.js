import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { stubTiles, firstRun, topSites } from './helpers.js';

// 10 trials; each trial opens 5 browser contexts at once. A trial passes when all 5 users see the
// map ready within 5 s and then a site page within 2 s. Pass: 9 of 10 trials.
const USERS = 5, TRIALS = 10, MAP_S = 5, SITE_S = 2;

test('5 concurrent users, map and site page timings', async ({ browser, request }) => {
  test.setTimeout(600_000);
  const run = await firstRun(request);
  const sites = await topSites(request, run.run_id, 50);
  const trials = [];
  for (let t = 0; t < TRIALS; t++) {
    const users = await Promise.all(Array.from({ length: USERS }, async (_, u) => {
      const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      await stubTiles(context);
      const page = await context.newPage();
      const t0 = Date.now();
      await page.goto('/');
      await expect(page.getByTestId('risk-map')).toHaveAttribute('data-ready', 'true', { timeout: 60_000 });
      const map = (Date.now() - t0) / 1000;
      const site = sites[(t * USERS + u) % sites.length];
      const t1 = Date.now();
      await page.goto(`/?page=site&site=${encodeURIComponent(site.site_id)}&run=${encodeURIComponent(run.run_id)}`);
      await expect(page.getByTestId('site-detail')).toContainText(String(site.site_id), { timeout: 30_000 });
      const sitePage = (Date.now() - t1) / 1000;
      await context.close();
      return { map, site: sitePage };
    }));
    const pass = users.every(x => x.map <= MAP_S && x.site <= SITE_S);
    trials.push({ trial: t + 1, pass, max_map_s: Math.max(...users.map(x => x.map)), max_site_s: Math.max(...users.map(x => x.site)), users });
  }
  const passed = trials.filter(x => x.pass).length;
  const all = trials.flatMap(x => x.users);
  const q = (arr, p) => { const s = [...arr].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };
  const summary = { users: USERS, trials: TRIALS, limits_s: { map: MAP_S, site: SITE_S }, trials_passed: passed, pass: passed >= 9,
    map_s: { median: q(all.map(x => x.map), 0.5), p90: q(all.map(x => x.map), 0.9), max: Math.max(...all.map(x => x.map)) },
    site_s: { median: q(all.map(x => x.site), 0.5), p90: q(all.map(x => x.site), 0.9), max: Math.max(...all.map(x => x.site)) },
    note: 'OpenStreetMap basemap tiles stubbed; server is one uvicorn worker on the local host serving the bundled artifact.',
    run_id: run.run_id, trials: trials };
  fs.mkdirSync('results', { recursive: true });
  fs.writeFileSync('results/perf.json', JSON.stringify(summary, null, 2));
  console.log(JSON.stringify({ ...summary, trials: undefined }));
  expect(passed).toBeGreaterThanOrEqual(9);
});
