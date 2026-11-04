"""Private prototype access. This is project access, not university SSO."""
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field, SecretStr

router = APIRouter(prefix="/api/v1/auth", tags=["Project access"])
COOKIE = "atsc_project_access"


class RateLimit:
    def __init__(self):
        self.entries = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key, limit, window):
        now = time.monotonic()
        with self.lock:
            for existing in list(self.entries):
                if not self.entries[existing] or self.entries[existing][-1] <= now - window:
                    self.entries.pop(existing, None)
            bucket = self.entries[key]
            while bucket and bucket[0] <= now - window:
                bucket.popleft()
            if len(bucket) >= limit or len(self.entries) > 2000:
                raise HTTPException(429, "Too many requests. Please try again later.")
            bucket.append(now)


login_limit = RateLimit()
ai_limit = RateLimit()


def access_configured():
    return len(os.environ.get("ATSC_SESSION_SECRET", "")) >= 32 and len(os.environ.get("ATSC_ASSISTANT_PASSWORD", "")) >= 12


def signer():
    return URLSafeTimedSerializer(os.environ["ATSC_SESSION_SECRET"], salt="atsc-project-access-v1")


def authenticated(request):
    if not access_configured():
        return False
    try:
        data = signer().loads(request.cookies.get(COOKIE, ""), max_age=3600)
        return data.get("role") == "project_member"
    except (BadSignature, SignatureExpired, ValueError):
        return False


def same_origin(request):
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "This action requires the same website origin.")


def require_access(request):
    same_origin(request)
    if not authenticated(request):
        raise HTTPException(401, "Sign in with project access before using the assistant.")


class Login(BaseModel):
    password: SecretStr = Field(min_length=1, max_length=512)


@router.get("/session")
def session(request: Request):
    return {"authenticated": authenticated(request), "configured": access_configured()}


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    same_origin(request)
    login_limit.check(request.client.host if request.client else "unknown", 8, 600)
    if not access_configured():
        raise HTTPException(503, "Project access has not been configured by the deployment owner.")
    if not hmac.compare_digest(body.password.get_secret_value().encode(), os.environ["ATSC_ASSISTANT_PASSWORD"].encode()):
        raise HTTPException(401, "The project access password is incorrect.")
    token = signer().dumps({"role": "project_member", "session_id": secrets.token_urlsafe(18)})
    response.set_cookie(COOKIE, token, max_age=3600, httponly=True, secure=os.environ.get("ATSC_ENV") == "production", samesite="strict", path="/")
    return {"authenticated": True}


@router.post("/logout")
def logout(request: Request, response: Response):
    same_origin(request)
    response.delete_cookie(COOKIE, path="/", secure=os.environ.get("ATSC_ENV") == "production", httponly=True, samesite="strict")
    return {"authenticated": False}
