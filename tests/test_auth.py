"""GitHub OAuth gate: disabled by default, 401s when armed, cookie round-trip.

Existing mutation tests run with the OAuth keys absent, so the gate is a
no-op there; this module arms it via monkeypatch and checks both sides.
The GitHub token exchange is stubbed — no test ever leaves localhost.
"""

import pytest
from fastapi.testclient import TestClient

from argus.server import routes_auth
from argus.server.app import app
from argus.store.db import init_db


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    monkeypatch.delenv("ARGUS_GITHUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("ARGUS_GITHUB_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("ARGUS_GITHUB_ADMINS", raising=False)
    init_db()
    yield


def _client() -> TestClient:
    return TestClient(app)


def _arm(monkeypatch, admins: str = "") -> None:
    monkeypatch.setenv("ARGUS_GITHUB_CLIENT_ID", "test-client")
    monkeypatch.setenv("ARGUS_GITHUB_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("ARGUS_SESSION_SECRET", "test-session-secret")
    if admins:
        monkeypatch.setenv("ARGUS_GITHUB_ADMINS", admins)


def _session_cookie(login: str = "operator") -> str:
    return routes_auth.make_session({"login": login, "avatar_url": ""})


def test_disabled_by_default_writes_pass() -> None:
    resp = _client().post(
        "/api/watches",
        json={"name": "w", "question": "Is flooding worsening here?"},
    )
    assert resp.status_code in (200, 201), resp.text
    status = _client().get("/api/auth/status").json()
    assert status["enabled"] is False


def test_armed_gate_locks_writes_reads_and_the_shell(monkeypatch) -> None:
    _arm(monkeypatch)
    client = _client()
    blocked = client.post(
        "/api/watches",
        json={"name": "w", "question": "Is flooding worsening here?"},
    )
    assert blocked.status_code == 401
    assert "Sign in with GitHub" in blocked.json()["detail"]
    assert client.post("/api/ask", json={"question": "hello"}).status_code == 401
    # reads are locked too: the dashboard is for signed-in operators
    assert client.get("/api/watches").status_code == 401
    assert client.get("/api/enso/status").status_code == 401
    # the SPA shell bounces to GitHub sign-in (deep links, not the root)
    page = client.get("/watchlist", follow_redirects=False)
    assert page.status_code == 302, page.text[:200]
    assert "/api/auth/login" in page.headers["location"]
    root = client.get("/")
    assert root.status_code == 200  # preview crawlers need the bare shell
    assert "og:image" in root.text and "og-image" in root.text
    # crawlers + uptime probes stay open
    assert client.get("/healthz").status_code == 200
    assert client.get("/api/healthz").status_code == 200
    og = client.get("/og-image.jpg")
    assert og.status_code in (200, 404)  # 404 only if the asset is not shipped yet


def test_armed_gate_accepts_signed_session(monkeypatch) -> None:
    _arm(monkeypatch)
    client = _client()
    client.cookies.set(routes_auth.SESSION_COOKIE, _session_cookie("operator"))
    resp = client.post(
        "/api/watches",
        json={"name": "w", "question": "Is flooding worsening here?"},
    )
    assert resp.status_code in (200, 201), resp.text


def test_session_cookie_rejects_tamper_and_expiry(monkeypatch) -> None:
    _arm(monkeypatch)
    good = routes_auth.make_session({"login": "operator", "avatar_url": ""})
    assert routes_auth.read_session(good) is not None
    assert routes_auth.read_session(good[:-2] + "xx") is None
    import base64
    import json

    body = json.dumps({"login": "operator", "avatar": "", "exp": 1, "nonce": "x"}, sort_keys=True).encode()
    expired = base64.urlsafe_b64encode(body).decode().rstrip("=") + "." + routes_auth._sign(body)
    assert routes_auth.read_session(expired) is None


def test_admin_allowlist_blocks_unknown_logins(monkeypatch) -> None:
    _arm(monkeypatch, admins="techafreshh")
    client = _client()
    client.cookies.set(routes_auth.SESSION_COOKIE, _session_cookie("not-allowed"))
    resp = client.post(
        "/api/watches",
        json={"name": "w", "question": "Is flooding worsening here?"},
    )
    assert resp.status_code == 401


def test_login_redirect_and_callback_round_trip(monkeypatch) -> None:
    _arm(monkeypatch)
    client = _client()

    async def _fake_exchange(code: str, redirect_uri: str) -> dict:
        assert redirect_uri.endswith("/api/auth/callback")
        return {"login": "techafreshh", "avatar_url": "https://example.com/a.png"}

    monkeypatch.setattr(routes_auth, "_exchange_code", _fake_exchange)

    login = client.get("/api/auth/login", follow_redirects=False)
    assert login.status_code == 302
    assert "github.com/login/oauth/authorize" in login.headers["location"]
    assert "argus_oauth_state" in login.cookies

    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    callback = client.get(
        f"/api/auth/callback?code=abc&state={state}", follow_redirects=False
    )
    assert callback.status_code == 302
    assert routes_auth.SESSION_COOKIE in callback.cookies


def test_callback_rejects_state_mismatch(monkeypatch) -> None:
    _arm(monkeypatch)
    resp = _client().get(
        "/api/auth/callback?code=abc&state=forged", follow_redirects=False
    )
    assert resp.headers["location"].startswith("/?auth=retry")


def test_logout_clears_session(monkeypatch) -> None:
    _arm(monkeypatch)
    client = _client()
    client.cookies.set(routes_auth.SESSION_COOKIE, _session_cookie("operator"))
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert "argus_session=;" in resp.headers["set-cookie"] or 'argus_session=""' in resp.headers["set-cookie"]
