import { defineConfig, devices } from '@playwright/test';

// The server is the production FastAPI app serving the built frontend and the bundled artifact.
const PORT = process.env.ATSC_E2E_PORT || '8765';
const desktop = { viewport: { width: 1280, height: 800 } };
const tablet = { viewport: { width: 820, height: 1180 } };

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  workers: 2,
  reporter: [['list'], ['json', { outputFile: process.env.ATSC_E2E_REPORT || 'results/report.json' }]],
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  webServer: {
    command: `../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port ${PORT} --app-dir ../backend --workers 1`,
    url: `http://127.0.0.1:${PORT}/api/v1/health`,
    reuseExistingServer: false,
    env: { ATSC_FRONTEND_DIST: '../frontend/dist', ATSC_ARTIFACTS_DIR: '../backend/data/artifacts' },
  },
  projects: [
    { name: 'chromium-desktop', use: { ...devices['Desktop Chrome'], ...desktop }, testIgnore: /perf/ },
    { name: 'chromium-tablet', use: { ...devices['Desktop Chrome'], ...tablet }, testIgnore: /perf/ },
    { name: 'edge-desktop', use: { ...devices['Desktop Edge'], channel: 'msedge', ...desktop }, testIgnore: /perf/ },
    { name: 'edge-tablet', use: { ...devices['Desktop Edge'], channel: 'msedge', ...tablet }, testIgnore: /perf/ },
    { name: 'firefox-desktop', use: { ...devices['Desktop Firefox'], ...desktop }, testIgnore: /perf/ },
    { name: 'firefox-tablet', use: { ...devices['Desktop Firefox'], ...tablet }, testIgnore: /perf/ },
    { name: 'webkit-desktop', use: { ...devices['Desktop Safari'], ...desktop }, testIgnore: /perf/ },
    { name: 'webkit-tablet', use: { ...devices['Desktop Safari'], ...tablet }, testIgnore: /perf/ },
    { name: 'perf', use: { ...devices['Desktop Chrome'], ...desktop }, testMatch: /perf/ },
  ],
});
