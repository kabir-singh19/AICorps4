# Basic model-results integration

Backtest and Memos navigation is enabled. The starter now reads validated published results and renders run selection, ranked sites, site details, backtest comparisons, and published memo text. It does not train or invoke a model.

## First adapter: local JSON

The default results directory is `backend/data/published/`. It now includes two synthetic dashboard runs requested for the website demonstration. Each contains all four roads, a memo per site, and a populated A/B/C comparison. Remove `example-dashboard-*.json` for real-only operation, or use an empty `ATSC_MODEL_RESULTS_DIR`. A model producer writes one JSON file per published run there; the backend reads it on the next request. Click **Refresh runs** to discover new results. Backtest and Memos also have refresh buttons.

Set `ATSC_MODEL_RESULTS_DIR` on the **backend** to read another directory. This is a temporary local integration adapter, not the final shared database. Replace `load_runs()` in `backend/app/model_results.py` with the shared database adapter when the S1/S2 schema is agreed. The browser continues using the same API.

## Contract

The complete JSON Schema is available at `/api/v1/model-schema`. The Python contract is `PublishedRun` in `backend/app/model_results.py`. Its default schema version is `1.0`.

Required run fields: `run_id`, `model_name`, `published_at` (with timezone), `status: "published"`, `risk_unit`, and `sites`. Use a new, immutable run ID for every publication. `is_demo: true` is mandatory for examples, test outputs, or synthetic predictions; the UI labels those runs explicitly. The adapter cannot determine whether producer-provided results are genuine.

Each site is a GeoJSON Feature with a Point for an intersection or a LineString for a segment. Coordinates use longitude, latitude in EPSG:4326. Properties include `site_id`, `site_type`, `road_name`, `rank` (one-based), and `flagged` (boolean). Optional fields include `length_mi`, `fsi_rate`, `in_hin`, `top_factors`, and `crash_history`. Risk values require the run's descriptive `risk_unit`; zero is valid and null means not provided. Negative/non-finite risks, invalid coordinates, duplicate site IDs, and unknown fields are rejected.

Optional `map_segment_id` explicitly links a model site to an existing local OpenStreetMap section, such as `1413155047-0`. It must match the local GeoJSON Feature ID, not just the road name. It is separate from the stable model `site_id`. Use it only when the site really represents that mapped section. Supplied mappings must be nonempty and unique within the run so a map click has an unambiguous result. Ranked sites can open model results even when no local map match exists. Published site geometry is displayed and selectable on the map.

Optional `backtest` contains producer-supplied training/test labels and methods A/B/C, with `capture_rate` and 95% confidence interval endpoints expressed as fractions from 0 to 1. The UI displays percentages. Also supply flagged mileage and test F&SI count. Missing methods are displayed as not provided.

Optional `memos` maps site IDs to published memo objects with `title`, plain `text`, `references`, and `grounding_passed: true`. The producer is responsible for actually performing grounding checks and engineering review. The adapter rejects a memo marked false unless it also has `is_example: true` inside an `is_demo: true` run. Example memos cannot be relabeled as real run output. Memo references to sites outside the run are rejected. The bundled demonstration memos use `is_example: true` and `grounding_passed: false`; their UI explicitly states that no grounding or engineering approval occurred. The website displays plain text, not generated HTML. Generation, editor authorization, jobs, and PDF export remain disabled.

## Validate and try an example

`docs/example-model-run.json` is explicitly synthetic and is NOT loaded by default. From the backend directory:

```bash
.venv/bin/python -m app.model_results ../docs/example-model-run.json
```

To opt into the example locally, copy that file to `backend/data/published/example-run-001.json`, then click **Refresh runs**. Remove that copied example when you are done. Do not relabel the fixture as real output.

For real integration, have the model producer serialize the same structure, validate it, write to a temporary file outside the `*.json` pattern, and atomically rename it into the results directory once complete. Do not edit published runs in place or reuse run IDs. Invalid new files are ignored while other valid runs remain available; if every file is invalid the API returns an explicit 503 error. Validation details are in the backend log and `/api/v1/health` reports invalid-file counts.

## Read API

- `GET /api/v1/runs`: published run summaries; empty installation returns `[]`.
- `GET /api/v1/sites?run_id=...`: ranked GeoJSON FeatureCollection. Optional `flagged=true|false` and `bbox=west,south,east,north` filters. The bbox filter uses geometry-envelope overlap.
- `GET /api/v1/sites/{site_id}?run_id=...`: a single site in that run.
- `GET /api/v1/sites/{site_id}/memo?run_id=...`: published memo or `status: "pending"`.
- `GET /api/v1/backtest?run_id=...`: backtest or `status: "pending"`.

Unknown runs/sites return 404. Invalid request parameters return 422. API errors use `{error, message}`. The frontend cancels superseded requests and clears preceding-run results when switching runs. Local road selection is matched by explicit section ID; there are no invented model-site IDs.

## Run and check

From the project root, in separate terminals:

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173/`. Node.js/npm must be installed for the npm command. Use the existing local virtual environment for Python.

Backend tests: from `backend/`, run `.venv/bin/python -m unittest discover -s tests -v`. Frontend check: from `frontend/`, run `npm run build`.

Keep this development service bound to localhost until authentication, authorization, and the deployment configuration are implemented. Do not place database passwords or model-provider keys in frontend code or result files.
