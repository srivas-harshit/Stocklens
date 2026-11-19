"""Upstox OAuth authorization and token status for the personal worker."""
import hashlib
import json
import logging
import os
import secrets
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse

from config import settings
from dependencies.redis import get_redis_client

router = APIRouter()
log = logging.getLogger("auth")

# The API and worker must share this file when running in separate containers.
TOKEN_FILE = Path(__file__).resolve().parent.parent.parent.parent / "apps" / "worker" / "upstox_token.json"
UPSTOX_AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
STATE_COOKIE = "stocklens_upstox_state"
STATE_COOKIE_PATH = "/api/v1/auth/upstox"
STATE_TTL_SECONDS = 600
IST = timezone(timedelta(hours=5, minutes=30))


def _state_key(state: str) -> str:
    return "oauth:upstox:state:" + hashlib.sha256(state.encode()).hexdigest()


def _token_expiry(now: datetime) -> datetime:
    """Upstox daily tokens expire at the next 03:30 in Asia/Kolkata."""
    local_now = now.astimezone(IST)
    expiry = local_now.replace(hour=3, minute=30, second=0, microsecond=0)
    if expiry <= local_now:
        expiry += timedelta(days=1)
    return expiry.astimezone(timezone.utc)


def _save_token(access_token: str, refresh_token: str = "") -> str:
    """Atomically replace the token cache; propagate persistence failures."""
    now = datetime.now(timezone.utc)
    expires_at = _token_expiry(now).isoformat()
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "saved_at": now.isoformat(),
    }
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_path = tempfile.mkstemp(prefix=".upstox_token-", dir=TOKEN_FILE.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as token_file:
            json.dump(data, token_file, indent=2)
            token_file.flush()
            os.fsync(token_file.fileno())
        os.replace(temp_path, TOKEN_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    log.info("Upstox token cache updated")
    return expires_at


@router.get("/auth/upstox")
async def upstox_auth_start(request: Request, redis=Depends(get_redis_client)):
    """Start a browser-bound authorization that expires after ten minutes."""
    if not settings.UPSTOX_API_KEY or not settings.UPSTOX_API_SECRET:
        raise HTTPException(
            status_code=400,
            detail="UPSTOX_API_KEY and UPSTOX_API_SECRET must be configured",
        )

    state = secrets.token_urlsafe(32)
    try:
        await redis.setex(_state_key(state), STATE_TTL_SECONDS, "1")
    except Exception as exc:
        log.error("OAuth state storage unavailable (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Authorization temporarily unavailable") from None

    params = {
        "response_type": "code",
        "client_id": settings.UPSTOX_API_KEY,
        "redirect_uri": settings.UPSTOX_REDIRECT_URI,
        "state": state,
    }
    response = RedirectResponse(url=f"{UPSTOX_AUTH_URL}?{urlencode(params)}")
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https" or urlsplit(settings.UPSTOX_REDIRECT_URI).scheme == "https",
        samesite="lax",
        path=STATE_COOKIE_PATH,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/auth/upstox/callback")
async def upstox_auth_callback(
    request: Request,
    code: str | None = Query(None, max_length=2048),
    state: str | None = Query(None, max_length=128),
    error: str | None = Query(None, max_length=256),
    redis=Depends(get_redis_client),
):
    """Validate and consume OAuth state before exchanging an authorization code."""
    cookie_state = request.cookies.get(STATE_COOKIE, "")
    if not state or not cookie_state or not secrets.compare_digest(state.encode(), cookie_state.encode()):
        raise HTTPException(status_code=400, detail="Invalid authorization state. Start authorization again.")
    try:
        # GETDEL is atomic: concurrent callbacks cannot reuse the same state.
        valid_state = await redis.getdel(_state_key(state))
    except Exception as exc:
        log.error("OAuth state storage unavailable (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Authorization temporarily unavailable") from None
    if not valid_state:
        raise HTTPException(status_code=400, detail="Authorization expired or already used. Start authorization again.")
    if error or not code:
        raise HTTPException(status_code=400, detail="Authorization was not completed. Start authorization again.")
    if not settings.UPSTOX_API_KEY or not settings.UPSTOX_API_SECRET:
        raise HTTPException(status_code=400, detail="Upstox credentials must be configured")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            upstream = await client.post(
                UPSTOX_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.UPSTOX_API_KEY,
                    "client_secret": settings.UPSTOX_API_SECRET,
                    "redirect_uri": settings.UPSTOX_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
        if upstream.status_code != 200:
            log.warning("Upstox token exchange failed with status %s", upstream.status_code)
            raise HTTPException(status_code=502, detail="Token exchange failed. Start authorization again.")
        data = upstream.json()
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token") or ""
        if not isinstance(access_token, str) or not access_token or not isinstance(refresh_token, str):
            raise HTTPException(status_code=502, detail="Invalid response from authorization provider")
    except HTTPException:
        raise
    except Exception as exc:
        # Provider responses and exceptions may contain credentials or codes.
        log.error("Upstox token exchange unavailable (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Authorization provider temporarily unavailable") from None

    try:
        expires_at = _save_token(access_token, refresh_token)
    except Exception as exc:
        log.error("Unable to save Upstox token (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Could not save authorization. Check token storage and retry.") from None

    response = JSONResponse(content={
        "status": "success",
        "message": "Upstox authorization saved successfully.",
        "expires_at": expires_at,
        "next": "Restart the worker to connect using the saved token. Authorize again after it expires.",
    })
    response.delete_cookie(STATE_COOKIE, path=STATE_COOKIE_PATH)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/auth/upstox/status")
async def upstox_auth_status(request: Request):
    """Expose configuration and expiry status without credential fragments."""
    token_file_exists = TOKEN_FILE.exists()
    token_file_valid = False
    expires_at = None
    if token_file_exists:
        try:
            data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            expiry = datetime.fromisoformat(data.get("expires_at", ""))
            token_file_valid = bool(data.get("access_token")) and datetime.now(timezone.utc) < expiry
            expires_at = expiry.isoformat()
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    return JSONResponse(content={
        "has_env_token": bool(settings.UPSTOX_ACCESS_TOKEN),
        "has_token_file": token_file_exists,
        "token_file_valid": token_file_valid,
        "expires_at": expires_at,
        "authorize_url": str(request.url_for("upstox_auth_start")),
        "api_key_set": bool(settings.UPSTOX_API_KEY),
        "api_secret_set": bool(settings.UPSTOX_API_SECRET),
    }, headers={"Cache-Control": "no-store"})
