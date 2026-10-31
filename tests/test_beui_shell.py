"""Issue #41: beUI dark ops-room shell served at / with live ENSO contract."""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from argus.server.app import app
from argus.store.db import init_db

STATIC = Path("argus/server/static")


def _client() -> TestClient:
    return TestClient(app)


def _setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "beui.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    init_db()


def _bundle_js() -> str:
    chunks = []
    for asset in sorted((STATIC / "assets").glob("*.js")):
        chunks.append(asset.read_text(encoding="utf-8", errors="replace"))
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    # Inline-module scripts are bundled; also scan index.html itself.
    return "\n".join([index, *chunks])


def test_enso_status_contract_shape(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    resp = _client().get("/api/enso/status")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("phase", "intensity", "trajectory", "month", "subwatchers"):
        assert key in body, f"missing {key}: {sorted(body)}"
    assert body["phase"] in ("El Nino", "La Nina", "Neutral")
    assert isinstance(body["subwatchers"], list)
    assert all(isinstance(entry.get("id"), str) for entry in body["subwatchers"])


def test_root_bundle_has_dark_tokens_and_card_surfaces(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    resp = _client().get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    bundle = _bundle_js()
    assert "--background" in bundle, "dark root token missing from built bundle"
    assert "beui-card" in bundle, "card surface class missing from built bundle"


def test_bundle_hooks_live_badge_and_no_fixture(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    bundle = _bundle_js()
    assert "enso-badge" in bundle
    assert "loop-status" in bundle
    assert "ENSO_FIXTURE" not in bundle
    assert re.search(r"chip-", bundle), "sub-watcher chip hook missing"
    assert "globe-map" in bundle


def test_app_source_wires_live_enso(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    src = Path("web/src/App.tsx").read_text(encoding="utf-8")
    assert "getEnsoStatus" in src
    assert "ENSO_FIXTURE" not in src
    api = Path("web/src/api.ts").read_text(encoding="utf-8")
    assert "getEnsoStatus" in api
    assert "ENSO_FIXTURE" not in api
    css = Path("web/src/index.css").read_text(encoding="utf-8")
    assert ":root" in css and "--background" in css
