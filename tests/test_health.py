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
