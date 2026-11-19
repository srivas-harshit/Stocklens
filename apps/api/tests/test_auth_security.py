"""Offline regressions for OAuth binding, secret handling, and persistence."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from routers import auth
from services import rag_service


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    async def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl

    async def getdel(self, key):
        return self.values.pop(key, None)


@pytest.fixture
def oauth(monkeypatch, tmp_path):
    monkeypatch.setattr(auth.settings, "UPSTOX_API_KEY", "test-client")
    monkeypatch.setattr(auth.settings, "UPSTOX_API_SECRET", "test-secret")
    monkeypatch.setattr(auth.settings, "UPSTOX_ACCESS_TOKEN", "")
    monkeypatch.setattr(auth.settings, "UPSTOX_REDIRECT_URI", "http://testserver/api/v1/auth/upstox/callback")
    monkeypatch.setattr(auth, "TOKEN_FILE", tmp_path / "upstox_token.json")
    cache = FakeRedis()
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.dependency_overrides[auth.get_redis_client] = lambda: cache
    with TestClient(app) as client:
        yield client, cache


def start(client):
    response = client.get("/api/v1/auth/upstox", follow_redirects=False)
    assert response.status_code == 307
    return parse_qs(urlsplit(response.headers["location"]).query)["state"][0]


def fake_provider(monkeypatch, *, status=200, payload=None, failure=None):
    calls = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            if failure:
                raise failure
            return httpx.Response(status, json=payload or {"access_token": "synthetic-access-token"})

    monkeypatch.setattr(httpx, "AsyncClient", Provider)
    return calls


def test_start_encodes_redirect_and_binds_state(oauth, monkeypatch):
    client, cache = oauth
    redirect = "http://testserver/api/v1/auth/upstox/callback?return=a&b=two words"
    monkeypatch.setattr(auth.settings, "UPSTOX_REDIRECT_URI", redirect)
    response = client.get("/api/v1/auth/upstox", follow_redirects=False)
    query = parse_qs(urlsplit(response.headers["location"]).query)
    state = query["state"][0]
    assert query["redirect_uri"] == [redirect]
    assert len(state) >= 32
    assert client.cookies.get(auth.STATE_COOKIE) == state
    assert cache.ttls[auth._state_key(state)] == 600
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"


def test_https_callback_uses_secure_cookie(oauth, monkeypatch):
    client, _ = oauth
    monkeypatch.setattr(auth.settings, "UPSTOX_REDIRECT_URI", "https://testserver/api/v1/auth/upstox/callback")
    response = client.get("/api/v1/auth/upstox", follow_redirects=False)
    assert "Secure" in response.headers["set-cookie"]


@pytest.mark.parametrize("case", ["missing", "mismatch", "expired", "wrong_browser"])
def test_invalid_state_never_exchanges_code(oauth, monkeypatch, case):
    client, cache = oauth
    state = start(client)
    params = {"code": "synthetic-code", "state": state}
    if case == "missing":
        params.pop("state")
    elif case == "mismatch":
        params["state"] = "wrong-state"
    elif case == "expired":
        cache.values.clear()
    else:
        client.cookies.clear()
    calls = fake_provider(monkeypatch)
    response = client.get("/api/v1/auth/upstox/callback", params=params)
    assert response.status_code == 400
    assert calls == []
    assert not auth.TOKEN_FILE.exists()


def test_success_saves_token_once_without_returning_credentials(oauth, monkeypatch):
    client, _ = oauth
    state = start(client)
    calls = fake_provider(monkeypatch)
    params = {"code": "synthetic-code", "state": state}
    response = client.get("/api/v1/auth/upstox/callback", params=params)
    assert response.status_code == 200
    saved = json.loads(auth.TOKEN_FILE.read_text())
    assert saved["access_token"] == "synthetic-access-token"
    assert datetime.fromisoformat(saved["expires_at"]) > datetime.now(timezone.utc)
    assert "synthetic-access-token" not in response.text
    assert "token_preview" not in response.json()
    assert response.headers["cache-control"] == "no-store"
    # Restore the original browser cookie to prove server-side replay prevention.
    client.cookies.set(auth.STATE_COOKIE, state, path=auth.STATE_COOKIE_PATH)
    assert client.get("/api/v1/auth/upstox/callback", params=params).status_code == 400
    assert len(calls) == 1


def test_save_failure_returns_error_and_preserves_existing_token(oauth, monkeypatch, caplog):
    client, _ = oauth
    auth.TOKEN_FILE.write_text('{"access_token":"previous-test-token"}')
    state = start(client)
    fake_provider(monkeypatch)

    def fail_replace(*args):
        raise OSError("synthetic-secret-must-not-leak")

    monkeypatch.setattr(auth.os, "replace", fail_replace)
    response = client.get("/api/v1/auth/upstox/callback", params={"code": "test-code", "state": state})
    assert response.status_code == 500
    assert json.loads(auth.TOKEN_FILE.read_text())["access_token"] == "previous-test-token"
    assert list(auth.TOKEN_FILE.parent.glob(".upstox_token-*")) == []
    assert "synthetic-secret-must-not-leak" not in response.text + caplog.text


@pytest.mark.parametrize("provider_failure", [False, True])
def test_provider_errors_do_not_expose_payloads(oauth, monkeypatch, caplog, provider_failure):
    client, _ = oauth
    state = start(client)
    marker = "synthetic-sensitive-provider-message"
    fake_provider(monkeypatch, status=401, payload={"error": marker},
                  failure=RuntimeError(marker) if provider_failure else None)
    response = client.get("/api/v1/auth/upstox/callback", params={"code": "test-code", "state": state})
    assert response.status_code == 502
    assert marker not in response.text + caplog.text
    assert not auth.TOKEN_FILE.exists()


def test_status_has_no_token_fragments_and_uses_current_host(oauth, monkeypatch):
    client, _ = oauth
    monkeypatch.setattr(auth.settings, "UPSTOX_ACCESS_TOKEN", "synthetic-env-token")
    auth._save_token("synthetic-file-token")
    response = client.get("/api/v1/auth/upstox/status")
    assert response.json()["token_file_valid"] is True
    assert response.json()["authorize_url"] == "http://testserver/api/v1/auth/upstox"
    assert "token_preview" not in response.json()
    assert "synthetic" not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("contents", ["broken json", "[]", '{"expires_at":"2026-01-01T00:00:00"}'])
def test_status_handles_invalid_cache(oauth, contents):
    client, _ = oauth
    auth.TOKEN_FILE.write_text(contents)
    response = client.get("/api/v1/auth/upstox/status")
    assert response.status_code == 200
    assert response.json()["token_file_valid"] is False


@pytest.mark.parametrize(("now", "expiry"), [
    ("2026-09-08T21:00:00+00:00", "2026-09-08T22:00:00+00:00"),
    ("2026-09-08T22:00:00+00:00", "2026-09-09T22:00:00+00:00"),
    ("2026-09-08T14:30:00+00:00", "2026-09-08T22:00:00+00:00"),
])
def test_expiry_matches_next_0330_ist(now, expiry):
    assert auth._token_expiry(datetime.fromisoformat(now)) == datetime.fromisoformat(expiry)


def test_embedding_key_is_only_in_header(monkeypatch):
    calls = fake_provider(monkeypatch, payload={"embedding": {"values": [0.1, 0.2]}})
    result = asyncio.run(rag_service.get_embedding("test summary", "synthetic-key"))
    assert result == [0.1, 0.2]
    url, options = calls[0]
    assert "synthetic-key" not in url
    assert options["headers"] == {"x-goog-api-key": "synthetic-key"}


def test_embedding_failure_does_not_log_sensitive_exception(monkeypatch, caplog):
    fake_provider(monkeypatch, failure=RuntimeError("synthetic-sensitive-detail"))
    assert asyncio.run(rag_service.get_embedding("test summary", "synthetic-key")) is None
    assert "synthetic-sensitive-detail" not in caplog.text
