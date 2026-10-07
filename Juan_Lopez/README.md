# S4 — Web application starter

Owner: Juan Lopez. React/Vite + MapLibre frontend and FastAPI backend, following ConOps Revision C and ICD IF-08. This is a local development scaffold, not a deployable finished system.

## Files

- `frontend/src/App.jsx`: risk map, site detail, backtest, and memo page shells.
- `frontend/src/components/RiskMap.jsx`: MapLibre canvas centered on College Station.
- `frontend/src/api.js`: same-origin API requests.
- `backend/app/main.py`: health endpoint, OpenAPI document, and read-route stubs.
- `docs/integration.md`: integration checklist and subsystem boundaries.

## Run locally

Use Node.js 20.19+ or 22.12+ and Python 3.11+. From `Juan_Lopez/`:

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, from `Juan_Lopez/frontend/`:

```bash
npm install
npm run dev
```

Open http://localhost:5173. API docs: http://127.0.0.1:8000/api/v1/docs.
The Vite development server proxies `/api` to FastAPI; no CORS setup is needed locally.

## Current behavior

Navigation, responsive layout, retry/error handling, and the map canvas are implemented. The map has a local blank background; a basemap provider and attribution still need selection. API read stubs return `503 integration_pending`; no synthetic crash/risk figures are presented as results. Export and generation controls remain disabled.

Authentication, published-run database reads, site selection, actual map layers, memo grounding integration, CSV/GeoJSON/PDF exports, containers, TLS, and production deployment are pending. No API keys belong in the frontend. Chat remains a stretch goal.

## Checks

```bash
cd frontend
npm run build
```

See `docs/validation.md` for checks actually performed while preparing this scaffold. Full accessibility, performance, ARM64 deployment, and end-to-end validation remain pending.
