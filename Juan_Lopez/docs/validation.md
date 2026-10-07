# Starter validation

Checked on October 7, 2026:

- `npm run build` completed with Vite 6.4.4. Vite reported a large JavaScript bundle; MapLibre loading and code splitting remain optimization work.
- FastAPI imported successfully and served HTTP requests through Uvicorn on localhost.
- `/api/v1/health` and `/api/v1/openapi.json` returned HTTP 200.
- All read stubs (runs, sites, site detail, memo, backtest) returned HTTP 503 with a run ID supplied where required.
- `/api/v1/sites` without its required run ID returned HTTP 422.

These checks cover starter build and HTTP behavior only. Browser rendering, accessibility, live database integration, authentication, export generation, performance targets, and ARM64 deployment have not been verified.
