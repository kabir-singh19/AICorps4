# S4 — Traffic-safety research dashboard

Owner: Juan Lopez. React/Vite + MapLibre frontend and FastAPI backend, following ConOps Revision C and ICD IF-08. The project now includes a Render deployment package and a protected university AI connector. It remains a research prototype; live university AI, the shared database, and engineering approval workflows require integration.

## Files

- `frontend/src/App.jsx`: navigation, published model run selection, and site selection.
- `frontend/src/components/RiskMap.jsx`: interactive OpenStreetMap basemap focused on University Drive, Harvey Road, Texas Avenue, and Wellborn Road, with individual corridor focus controls.
- `frontend/src/components/SiteDetails.jsx`: mapped road details and matched model site results.
- `frontend/src/components/ModelPanels.jsx`: model run selector, ranked sites, backtest table, and published memos.
- `frontend/src/components/Assistant.jsx`: project access, evidence selection, and AI draft answers.
- `frontend/src/components/ExampleLab.jsx`: interactive synthetic ML example and printable/downloadable report.
- `frontend/src/data/corridors.geojson.json`: attributed OpenStreetMap road geometry for the central College Station corridor sections.
- `frontend/src/api.js`: same-origin API requests.
- `backend/app/main.py`: health, schema, and model-result read endpoints.
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

Backtest and Memos are enabled. The backend reads validated model output JSON files from `backend/data/published/` or `ATSC_MODEL_RESULTS_DIR`. The frontend can select a run and load ranked sites, model-site results, backtests, and published memos. Published Point/LineString sites appear on the map and can open Site details; flagged and other sites have a labeled legend, with no invented risk thresholds. CSV and GeoJSON downloads use the selected run. The default directory is empty; the optional synthetic example in `docs/example-model-run.json` is not loaded automatically. See [model integration](docs/model-integration.md) for the format and producer workflow. No traffic-risk inference service is invoked.

Clicking a highlighted road selects the specific mapped section and opens Site details. Keyboard-accessible road details buttons select one mapped section per corridor. Returning to the map focuses that corridor and outlines the selected section. Selection is retained while navigating within the app and resets on browser reload. An explicit `map_segment_id` can link that section to a model result; OpenStreetMap references are not model site IDs. Rankings can open a model site without a local map match. Missing model results are shown as unavailable, not invented.

The AI assistant uses a server-configured, compatible university provider. It requires project access and remains unavailable until explicitly enabled with credentials. Questions use the selected published evidence, and responses are labeled drafts. It does not automatically generate approved memos or calculate risk. No API keys belong in the frontend. See [AI setup](docs/ai-assistant.md); an actual TAMU provider call is still unverified.

**Example lab** works immediately without a provider key. It includes a small logistic-regression model trained on 400 synthetic records, editable fictional road inputs, and a report for four corridor scenarios. Open `?example=1` to go directly to it. All example scores and reports are labeled synthetic and stay separate from published model runs. See [example-lab.md](docs/example-lab.md).

For public hosting, follow [Render deployment](docs/deployment.md). FastAPI serves the production build and API under the same origin; the map loads separately from other pages to reduce initial script loading. Deployment files alone do not create a public URL: a connected Render account and successful deploy are required. The shared database, confirmed model site mappings, actual inference, university SSO, independently executed memo grounding, and PDF memo export remain pending. Imported grounding markers are validated, but the publishing pipeline must perform the real checks.

## Checks

```bash
cd frontend
npm run build
```

See `docs/validation.md` for checks actually performed while preparing this scaffold. Full accessibility, performance, ARM64 deployment, and end-to-end validation remain pending.

Backend contract/API tests: from `backend/`, run `.venv/bin/python -m unittest discover -s tests -v`.
