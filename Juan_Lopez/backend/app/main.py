"""Published model reads, protected AI assistance, and same-origin frontend delivery."""
import math
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from .model_results import load_runs, PublishedRun, run_summary
from .exports import sites_csv
from .web import mount_frontend, security_headers, frontend_directory
from .access import router as access_router
from .assistant import router as assistant_router, status as assistant_status
from .examples import router as examples_router

app = FastAPI(title="ATSC API", version="0.3.0", openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs")
app.middleware("http")(security_headers)
app.include_router(access_router)
app.include_router(assistant_router)
app.include_router(examples_router)

class ApiError(Exception):
    def __init__(self, status, error, message):
        self.status, self.error, self.message = status, error, message

@app.exception_handler(ApiError)
async def api_error(request: Request, error: ApiError):
    return JSONResponse(status_code=error.status, content={"error": error.error, "message": error.message})

@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "invalid_request", "message": "Check the required fields, allowed ranges, and value types."})

@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, error: StarletteHTTPException):
    message = error.detail if isinstance(error.detail, str) and error.status_code != 404 else "The requested resource is unavailable."
    return JSONResponse(status_code=error.status_code, content={"error": "not_found" if error.status_code == 404 else "http_error", "message": message}, headers=error.headers)

def available_runs():
    runs, invalid = load_runs()
    if invalid and not runs:
        raise ApiError(503, "invalid_model_output", "No valid published model results are available. Check the backend validation log.")
    return runs

def find_run(run_id: str) -> PublishedRun:
    for run in available_runs():
        if run.run_id == run_id:
            return run
    raise ApiError(404, "run_not_found", "The requested published model run was not found.")

def find_site(run, site_id):
    for feature in run.sites:
        if feature.properties.site_id == site_id:
            return feature
    raise ApiError(404, "site_not_found", "This site was not found in the selected model run.")

@app.get("/api/v1/health")
def health():
    runs, invalid = load_runs()
    return {"status": "degraded" if invalid else "ok", "db": "not_configured", "llm": "configured" if assistant_status()["available"] else "not_configured", "model_adapter": "local_json", "published_runs": len(runs), "invalid_files": invalid, "version": "0.3.0"}

@app.get("/api/v1/ready")
def ready():
    import os
    if os.environ.get("ATSC_ENV") == "production" and not (frontend_directory() / "index.html").is_file():
        raise ApiError(503, "frontend_missing", "The frontend build is not available.")
    return {"status": "ready", "version": "0.3.0"}

@app.get("/api/v1/runs/{run_id}/exports/sites.csv")
def export_csv(run_id: str):
    run = find_run(run_id)
    return Response(sites_csv(run), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{run.run_id}-sites.csv"'})

@app.get("/api/v1/runs/{run_id}/exports/sites.geojson")
def export_geojson(run_id: str):
    run = find_run(run_id)
    return JSONResponse({"type": "FeatureCollection", "run_id": run.run_id, "risk_unit": run.risk_unit, "is_demo": run.is_demo, "features": [site.model_dump(mode="json") for site in sorted(run.sites, key=lambda feature: feature.properties.rank)]}, media_type="application/geo+json", headers={"Content-Disposition": f'attachment; filename="{run.run_id}-sites.geojson"'})

@app.get("/api/v1/model-schema")
def model_schema():
    return PublishedRun.model_json_schema()

@app.get("/api/v1/runs")
def runs():
    return [run_summary(run) for run in available_runs()]

@app.get("/api/v1/sites")
def sites(run_id: str, bbox: str | None = None, flagged: bool | None = None):
    run = find_run(run_id)
    bounds = None
    if bbox is not None:
        try:
            west, south, east, north = (float(value) for value in bbox.split(","))
            if not all(math.isfinite(value) for value in [west, south, east, north]) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
                raise ValueError()
            bounds = (west, south, east, north)
        except ValueError:
            raise ApiError(422, "invalid_bbox", "Use west,south,east,north in longitude/latitude degrees.")
    features = []
    for feature in sorted(run.sites, key=lambda site: site.properties.rank):
        if flagged is not None and feature.properties.flagged != flagged:
            continue
        if bounds:
            points = feature.geometry.coordinates if feature.geometry.type == "LineString" else [feature.geometry.coordinates]
            xs, ys = zip(*points)
            west, south, east, north = bounds
            if max(xs) < west or min(xs) > east or max(ys) < south or min(ys) > north:
                continue
        features.append(feature.model_dump(mode="json"))
    return {"type": "FeatureCollection", "run_id": run.run_id, "features": features}

@app.get("/api/v1/sites/{site_id}")
def site(site_id: str, run_id: str):
    return find_site(find_run(run_id), site_id).model_dump(mode="json")

@app.get("/api/v1/sites/{site_id}/memo")
def memo(site_id: str, run_id: str):
    run = find_run(run_id)
    find_site(run, site_id)
    memo = run.memos.get(site_id)
    return {"run_id": run.run_id, "site_id": site_id, "status": "published" if memo else "pending", "memo": memo.model_dump() if memo else None}

@app.get("/api/v1/backtest")
def backtest(run_id: str):
    run = find_run(run_id)
    return {"run_id": run.run_id, "status": "available" if run.backtest else "pending", "backtest": run.backtest.model_dump() if run.backtest else None}

mount_frontend(app)
