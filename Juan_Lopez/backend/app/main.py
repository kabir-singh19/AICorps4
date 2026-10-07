"""Local-development scaffold. Database and authentication are not wired yet."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="ATSC API", version="0.1.0", openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs")


@app.get("/api/v1/health")
def health():
    return {"status": "degraded", "db": "not_configured", "llm": "not_configured", "version": "0.1.0"}


def pending():
    return JSONResponse(status_code=503, content={"error": "integration_pending", "message": "Published-run database integration is pending. This is a development starter."})


@app.get("/api/v1/runs")
def runs():
    return pending()


@app.get("/api/v1/sites")
def sites(run_id: str, bbox: str | None = None, flagged: bool | None = None):
    return pending()


@app.get("/api/v1/sites/{site_id}")
def site(site_id: str, run_id: str):
    return pending()


@app.get("/api/v1/sites/{site_id}/memo")
def memo(site_id: str, run_id: str):
    return pending()


@app.get("/api/v1/backtest")
def backtest(run_id: str):
    return pending()
