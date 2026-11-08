# S4 — Traffic-safety research dashboard

Owner: Juan Lopez. React/Vite + MapLibre frontend and FastAPI backend, following ConOps Revision C and ICD IF-08. The project now includes a Render deployment package and a protected university AI connector. It remains a research prototype; live university AI, the shared database, and engineering approval workflows require integration.

## Files

- `frontend/src/App.jsx`: navigation, published model run selection, and site selection.
- `frontend/src/components/RiskMap.jsx`: MapLibre map of every site in the run: segments colored by expected K+A crashes per mile per year, intersections as circles, flagged sites outlined, MPO HIN toggle.
- `frontend/src/components/SiteDetails.jsx`: site page: prediction, attributes, crash history by year, top 5 SHAP factors, memo status and PDF.
- `frontend/src/components/ModelPanels.jsx`: run selector, searchable ranked list with exports, backtest table and capture curve, memos.
- `frontend/src/components/Assistant.jsx`: project access, evidence selection, and AI draft answers.
- `frontend/src/components/ExampleLab.jsx`: interactive synthetic ML example and printable/downloadable report.
- `frontend/src/data/corridors.geojson.json`: attributed OpenStreetMap road geometry for the central College Station corridor sections.
- `frontend/src/api.js`: same-origin API requests.
- `backend/app/main.py`: health, runs, sites, site detail, memo, memo PDF, backtest and export endpoints.
- `backend/app/artifact_runs.py`: read-only adapter for S2/S3 run artifacts (`backend/data/artifacts/<run_id>/`), SHA-256 checked against the manifest.
- `backend/app/memo_pdf.py`: memo PDF export (IF-11).
- `e2e/`: Playwright tests (Chromium, Firefox, WebKit at desktop and tablet sizes, axe scan, 5-user load).
- `DEPLOY.md`: what the image contains, Render steps, HTTPS and key handling, endpoint list.
- `backend/app/model_results.py`: validated model-output contract and temporary local JSON adapter.
- `backend/app/assistant.py`: server-side provider adapter and published-evidence assembly.
- `backend/app/access.py`: expiring project-access cookies and prototype usage limits.
- `Dockerfile`, `render.yaml`, `render.monorepo.yaml`: one-origin deployment package.
- `docs/deployment.md`: Render setup for standalone and team repositories.
- `docs/ai-assistant.md`: provider configuration, data flow, and limitations.
- `docs/model-integration.md`: integration setup, result format, and optional synthetic example.
- `docs/integration.md`: integration checklist and subsystem boundaries.

## Run locally

Use Node.js 20.19+ or 22.12+ and Python 3.11+. From the project root:

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, from the project's `frontend/` folder:

```bash
npm install
npm run dev
```

Open http://localhost:5173. API docs: http://127.0.0.1:8000/api/v1/docs.
The Vite development server proxies `/api` to FastAPI; no CORS setup is needed locally.

## Current behavior

Navigation, responsive layout, retry/error handling, and the street map are implemented. The map loads OpenStreetMap raster tiles over HTTPS with visible contributor attribution; internet access is required even when the app runs locally. It supports panning, zooming, an imperial distance scale, focus on all four corridors or an individual road, and retry after map errors. Road highlights use an OpenStreetMap geometry snapshot retrieved October 14, 2026, clipped to central College Station; they are geographic reference layers, not risk results or complete road lengths. The geometry is provided under ODbL-1.0 (see [OpenStreetMap copyright](https://www.openstreetmap.org/copyright)); provenance is included in the GeoJSON metadata. Tile use must follow the [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/).

Backtest and Memos are enabled. The backend reads validated model output JSON files from `backend/data/published/` or `ATSC_MODEL_RESULTS_DIR`. The frontend can select a run and load ranked sites, model-site results, backtests, and published memos. Published Point/LineString sites appear on the map and can open Site details; flagged and other sites have a labeled legend, with no invented risk thresholds. CSV and GeoJSON downloads use the selected run. The default directory includes two explicitly synthetic dashboard runs, each with four mapped sites, an A/B/C comparison, and a memo per site. These are invented interface fixtures, separate from the Example lab classifier and the real model pipeline. Remove `example-dashboard-*.json` when switching to real-only data. The older optional fixture in `docs/example-model-run.json` is not loaded automatically. See [model integration](docs/model-integration.md) for the format and producer workflow. No traffic-risk inference service is invoked.

Clicking a highlighted road selects the specific mapped section and opens Site details. Keyboard-accessible road details buttons select one mapped section per corridor. Returning to the map focuses that corridor and outlines the selected section. Selection is retained while navigating within the app and resets on browser reload. An explicit `map_segment_id` can link that section to a model result; OpenStreetMap references are not model site IDs. Rankings can open a model site without a local map match. Missing model results are shown as unavailable, not invented.

The AI assistant now supports a working local Qwen language model through Ollama, with no paid API key. On this configured Mac, double-click `Start Local AI.command`, open `http://127.0.0.1:8010/`, and choose **AI assistant**. See [local-ai.md](docs/local-ai.md). The public deployment uses the separate server-configured HTTPS provider path and project access; official TAMU provider access remains unverified. Questions use selected published evidence and answers remain drafts. The assistant does not publish approved memos or calculate risk. No provider keys belong in the frontend.

**Example lab** works immediately without a provider key. It includes a small logistic-regression model trained on 400 synthetic records, editable fictional road inputs, and a report for four corridor scenarios. Open `?example=1` to go directly to it. All example scores and reports are labeled synthetic and stay separate from published model runs. See [example-lab.md](docs/example-lab.md).

For public hosting, follow [Render deployment](docs/deployment.md). FastAPI serves the production build and API under the same origin; the map loads separately from other pages to reduce initial script loading. Deployment files alone do not create a public URL: a connected Render account and successful deploy are required. The shared database, confirmed model site mappings, actual inference, university SSO, independently executed memo grounding, and PDF memo export remain pending. Imported grounding markers are validated, but the publishing pipeline must perform the real checks.

## Checks

```bash
cd frontend
npm run build
```

See `docs/validation.md` for checks actually performed while preparing this scaffold. Full accessibility, performance, ARM64 deployment, and end-to-end validation remain pending.

Backend contract/API tests: from `backend/`, run `.venv/bin/python -m unittest discover -s tests -v`.
