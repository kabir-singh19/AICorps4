"""Production frontend delivery. Both the UI and API use one origin."""
import os
from pathlib import Path

from fastapi import Request
from fastapi.staticfiles import StaticFiles


def frontend_directory():
    default = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return Path(os.environ.get("ATSC_FRONTEND_DIST", default))


def mount_frontend(app, directory=None):
    directory = Path(directory) if directory else frontend_directory()
    if (directory / "index.html").is_file():
        app.mount("/", StaticFiles(directory=directory, html=True), name="frontend")


async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if os.environ.get("ATSC_ENV") == "production":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https://tile.openstreetmap.org; "
            "connect-src 'self' https://tile.openstreetmap.org; worker-src 'self' blob:; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response
