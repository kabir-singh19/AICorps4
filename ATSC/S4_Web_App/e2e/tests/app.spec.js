import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { stubTiles, firstRun, topSites } from './helpers.js';

test.beforeEach(async ({ context }) => { await stubTiles(context); });

async function axe(page, name) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  const bad = result.violations.map(v => `${v.id} (${v.impact}): ${v.nodes.length} nodes`);
  test.info().annotations.push({ type: 'axe', description: `${name}: ${result.violations.length} violations, ${result.passes.length} rules passed${bad.length ? ': ' + bad.join('; ') : ''}` });
  expect(bad, `axe violations on ${name}`).toEqual([]);
}

test('map draws every site, legend, HIN toggle, no key in the page', async ({ page, request }) => {
  const run = await firstRun(request);
  expect(run, 'a real artifact run is bundled').toBeTruthy();
  const scripts = [];
  page.on('response', async r => { if (/\.(js|html)$/.test(new URL(r.url()).pathname) || r.url().endsWith('/')) scripts.push(await r.text().catch(() => '')); });
  await page.goto('/');
  const map = page.getByTestId('risk-map');
  await expect(map).toHaveAttribute('data-ready', 'true', { timeout: 30_000 });
  await expect(map).toHaveAttribute('data-sites', String(run.site_count));
  await expect(page.getByLabel('Map legend')).toContainText('K+A crashes per mile per year');
  await page.getByLabel('Show MPO high-injury network').check();
  await expect(page.getByLabel('Show MPO high-injury network')).toBeChecked();
  await axe(page, 'map');
  for (const body of scripts) expect(body).not.toMatch(/sk-[A-Za-z0-9]{20,}|MEMO_API_KEY|Bearer\s+[A-Za-z0-9]/);
});

test('ranked list opens a site page with history, factors and memo state', async ({ page, request }) => {
  const run = await firstRun(request);
  const [top] = await topSites(request, run.run_id, 1);
  await page.goto('/');
  await expect(page.getByRole('status').filter({ hasText: 'matching sites' })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: new RegExp(top.site_id) }).first().click();
  const detail = page.getByTestId('site-detail');
  await expect(detail).toBeVisible();
  await expect(detail).toContainText(String(top.site_id));
  await expect(page.getByRole('img', { name: /Matched crashes by year/ })).toBeVisible();
  await expect(page.getByLabel('Why this site ranks here').locator('li')).toHaveCount(5);
  await axe(page, 'site');
});

test('backtest page shows A, B, C with intervals for both targets', async ({ page }) => {
  await page.goto('/?page=backtest');
  const bt = page.getByTestId('backtest');
  await expect(bt.locator('tbody tr')).toHaveCount(5, { timeout: 15_000 });
  await expect(bt).toContainText("HIN's own share");
  await page.getByLabel('Crash severity scored').selectOption('KABC');
  await expect(bt.locator('caption')).toContainText('KABC');
  await axe(page, 'backtest');
});

test('memos page and exports', async ({ page, request }) => {
  const run = await firstRun(request);
  await page.goto('/?page=memos');
  const memos = page.getByTestId('memos');
  await expect(memos).toBeVisible();
  await expect(memos.locator('select#memo-site, p').first()).toBeVisible({ timeout: 30_000 });
  await axe(page, 'memos');
  const csv = await request.get(`/api/v1/export/sites.csv?run_id=${run.run_id}&flagged=true`);
  expect(csv.status()).toBe(200);
  expect((await csv.text()).split('\n')[0]).toContain('site_id,site_type,road_name,length_mi,fsi_rate,rank,flagged,in_hin,memo_status');
  const gj = await request.get(`/api/v1/export/sites.geojson?run_id=${run.run_id}`);
  expect((await gj.json()).features.length).toBe(run.site_count);
});
