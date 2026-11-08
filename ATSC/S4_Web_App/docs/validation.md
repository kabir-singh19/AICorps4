# Starter validation

## Working local language model — November 4, 2026

- Installed the official Ollama 0.40.14 command-line runtime in ignored local storage and verified its code signature. Downloaded Qwen 2.5 1.5B; a real inference explained the Texas Avenue fixture's synthetic 0.94 rate and rank 1 without a provider API key.
- A full browser request from the assistant tab generated an answer identifying Texas Avenue and University Drive as the two flagged sites in example-dashboard-002, with rates 0.94 and 0.78. It explicitly identified the records as synthetic and not real predictions. This is a language-model response, not a canned answer. The UI retained draft and synthetic labels; no captured browser console errors/warnings appeared.
- Twenty-eight backend tests pass. Five new checks cover loopback-only access, production/remote/origin rejection, runtime/model availability checks, native provider requests without credentials or arbitrary URLs, and bounded concurrent local requests. Existing hosted-provider access protections remain covered by prior tests.
- Production frontend build passed with the existing separately loaded MapLibre warning. A project launcher starts the website and reuses or starts the local runtime; development at port 5173 also uses the configured backend environment.
- This verifies local language-model inference only. It does not establish factual reliability, university endorsement/access, public AI hosting, real model accuracy, or engineering approval. Render continues to require a separately configured authenticated HTTPS provider and a completed deployment.

## Populated dashboard examples — November 4, 2026

- Two synthetic runs are now bundled at the user's request. Each contains all four road sites, a complete A/B/C comparison, and a memo for every site. Risks and comparison counts are invented interface fixtures, separate from the trained synthetic Example lab classifier.
- Twenty-three backend tests pass. Two new checks cover completeness and same-run memo reads, unchanged OSM section geometry/mappings, explicit demo status, and rejection of example memos in a run relabeled as real. Example memos use `is_example=true` with `grounding_passed=false`; the UI does not claim completed grounding.
- The frontend production build passes with the existing separate MapLibre size warning. Browser checks loaded both run choices and four ranked/mapped sites, opened the synthetic backtest table, switched runs, and opened road-specific memos. Memos automatically select the first available site when no site was selected.
- Earlier entries documenting an empty default directory describe the earlier installation. It is now populated with the two explicitly labeled examples. Remove `backend/data/published/example-dashboard-*.json` for real-only operation.

## Example lab — November 4, 2026

- Twenty-one backend tests pass, including four new example tests. They verify the score against the saved learned model, changed-input behavior, range/type validation, ranked report/prediction consistency, HTML escaping/downloads, synthetic labels, and isolation from published runs.
- The production frontend build passes. The core script is approximately 302 kB; the separate MapLibre chunk retains its size warning.
- In the production preview, Example lab loaded without credentials. Changing the University Drive preset's speed from 45 to 25 changed its synthetic score from 0.704 to 0.407 after running the model. The fixed four-scenario report remained unchanged, as labeled. No captured browser console errors or warnings appeared during this check.
- These checks concern a teaching model trained on invented data. No real traffic-risk validation, university AI connection, or public deployment is implied.

## Render package and AI connector — November 4, 2026

- Seventeen backend tests pass: the existing eight model-contract tests plus nine hosted/assistant checks. New checks cover signed Secure/HttpOnly/SameSite cookies, incorrect/tampered credentials, origin rejection, logout, login and AI quotas, disabled providers, client configuration rejection, run/site evidence isolation, draft/demo labeling, CSV formula escaping and explicit zero/false preservation, GeoJSON exports, same-origin static/API delivery, production headers, missing-build readiness, and mocked provider payload/error mapping.
- Production frontend build passed. Lazy loading separates the core script (~293 kB uncompressed) from MapLibre (~1.06 MB); the map chunk still produces Vite's size warning. No performance target is claimed.
- A production-configured FastAPI process served the built frontend and API together. Browser inspection confirmed the four-corridor map loaded with no captured console warnings/errors. The AI tab correctly showed an unavailable connection with input disabled when credentials were absent.
- An isolated production-configured preview loaded the explicitly synthetic documentation example from a temporary directory. It showed the published-site legend and two ranked results, opened model Site details from the ranking, and retained selection/focus on returning to the map without captured console warnings/errors. Download URLs were present; their content was checked through API tests. Direct pointer selection of the newly added model overlay was not separately exercised.
- The normal published-data directory remains empty; no sample predictions were added to the live app. The isolated sample preview was stopped after inspection.
- A Docker engine was unavailable locally, so the Docker image build has not been executed here. Render account access is still required for a deployment/build and public HTTPS verification. Tests use a mocked AI provider; a live university endpoint, model ID, credentials, quota, and permitted public use must be verified separately. Shared-database, actual inference, university SSO, independent memo grounding, full accessibility, and performance validation remain pending.

Checked on October 7, 2026:

- `npm run build` completed with Vite 6.4.4. Vite reported a large JavaScript bundle; MapLibre loading and code splitting remain optimization work.
- FastAPI imported successfully and served HTTP requests through Uvicorn on localhost.
- `/api/v1/health` and `/api/v1/openapi.json` returned HTTP 200.
- All read stubs (runs, sites, site detail, memo, backtest) returned HTTP 503 with a run ID supplied where required.
- `/api/v1/sites` without its required run ID returned HTTP 422.

These checks cover starter build and HTTP behavior only. Browser rendering, accessibility, live database integration, authentication, export generation, performance targets, and ARM64 deployment have not been verified.

## Local street map validation — October 14, 2026

- The production frontend build passed with Vite 6.4.4; the large-bundle warning remains.
- Browser inspection confirmed OpenStreetMap tiles and road labels around College Station, visible contributor attribution, and the distance scale.
- Panning, zooming, reset to College Station, and navigation away from and back to the map were checked in the local browser.
- Traffic-risk overlays and site selection remain pending database integration. Network-error retry and WebGL failure handling have not been exercised under simulated failures.

## Corridor focus validation — October 14, 2026

- The OpenStreetMap snapshot contains 175 road segments across University Drive (78), Harvey Road (25), Texas Avenue (46), and Wellborn Road (26). Coordinates were clipped to central College Station and each corridor has valid line geometry.
- Browser inspection confirmed all four colored road highlights and the default overview. Each road-focus button updated the selected state and map view; the All corridors button restored the overview.
- The production frontend build passed. Corridor colors identify roads only; no traffic-risk results were added.

## Clickable roads validation — October 14, 2026

- Clicking University Drive on the actual map opened Site details for the selected OpenStreetMap section, with its name, approximate length, location, and source reference.
- Returning to the map retained the selected road and focused its corridor. Pressing Enter on the Harvey Road details button selected a real mapped section and opened its details.
- Crash history, predicted risk, priority rank, and risk factors were visibly marked pending. No model results were fabricated or requested using OpenStreetMap way IDs.
- The final production frontend build passed; the existing large-bundle warning remains.
- Full accessibility and model-data integration tests remain pending.

## Basic model adapter — October 18, 2026

- Eight backend tests passed through the ASGI application, covering empty installation, valid published runs, zero/false values, run/site isolation, backtest and memo reads, invalid-new-file preservation, invalid-only files, required parameters, bounding-box validation, and rejection of invalid model output. Invalid-output subcases include negative risk, duplicate site IDs and map mappings, out-of-range coordinates, failed memo grounding markers, and reversed confidence intervals.
- The production frontend build passed with the existing large-bundle warning.
- An isolated backend/frontend pair used two explicitly synthetic runs outside the normal results directory. Browser checks loaded ranked sites, selected site results, A/B/C backtest values, a published memo, a missing-memo empty state, and a second run with no sites/backtest/memos. Switching runs cleared the preceding run's results.
- The normal local app was verified with Backtest and Memos enabled and no synthetic files loaded. The isolated test servers were stopped after verification.
- This verifies the starter JSON adapter, not a real AI model, the final shared database, independently executed grounding checks, authentication, production hosting, full accessibility, or performance targets.
