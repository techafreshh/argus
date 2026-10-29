"""Issue #16: control-room bundle served at / plus UI-shaped API loop."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from argus.server.app import app
from argus.store.db import init_db

UI_WATCH_BODY = {
    "name": "UI watch",
    "region": {"type": "bbox", "coords": [24, -12.5, 30, -8]},
    "question": "Is vegetation declining?",
    "cadence": "daily",
}


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "web.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    init_db()
    yield


def _client() -> TestClient:
    return TestClient(app)


def test_root_serves_bundle_html():
    resp = _client().get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "ARGUS" in resp.text
    assert "maplibre" in resp.text.lower() or "globe" in resp.text.lower()


def test_healthz_still_200():
    assert _client().get("/healthz").status_code == 200


def test_static_index_on_disk_references_bundle():
    index_file = Path("argus/server/static/index.html")
    assert index_file.is_file()
    text = index_file.read_text(encoding="utf-8")
    assert "ARGUS" in text
    assert "maplibre" in text.lower() or "globe" in text.lower()


def test_ui_shaped_watch_create_then_run_then_approve():
    client = _client()
    created = client.post("/api/watches", json=dict(UI_WATCH_BODY))
    assert created.status_code == 201, created.text
    watch_id = created.json()["id"]
    run = client.post(f"/api/watches/{watch_id}/run")
    assert run.status_code == 200, run.text
    alert_id = run.json().get("alert_id")
    assert alert_id
    approved = client.post(f"/api/alerts/{alert_id}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"


def test_assets_mount_serves_built_js():
    static_dir = Path("argus/server/static")
    assets = sorted((static_dir / "assets").glob("*.js"))
    assert assets, "expected hashed Vite JS under argus/server/static/assets/"
    name = assets[0].name
    resp = _client().get(f"/assets/{name}")
    assert resp.status_code == 200, resp.text[:200]
