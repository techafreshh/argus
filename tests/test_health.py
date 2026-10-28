from fastapi import FastAPI
from fastapi.testclient import TestClient

from argus.server.app import app


def _client() -> TestClient:
    return TestClient(app)


def test_app_is_fastapi_instance() -> None:
    assert isinstance(app, FastAPI)


def test_healthz_exact_body() -> None:
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_api_healthz_alias() -> None:
    resp = _client().get("/api/healthz")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_root_serves_placeholder() -> None:
    resp = _client().get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "under construction" in resp.text


def test_malformed_json_post_is_4xx_never_500() -> None:
    client = _client()
    for path in ("/healthz", "/api/healthz", "/", "/api/watches"):
        resp = client.post(
            path,
            content=b"{bad json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 404, 422), (path, resp.status_code)


def test_wrong_method_is_404_not_405() -> None:
    assert _client().post("/healthz").status_code == 404
    assert _client().post("/api/healthz").status_code == 404
