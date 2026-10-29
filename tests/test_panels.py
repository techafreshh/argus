"""Issue #17: receipts / reports / spend / eval-status behavior probes."""

import re

import pytest
from fastapi.testclient import TestClient

from argus.server.app import app
from argus.store.db import init_db

CREATE_BODY = {
    "name": "panel watch",
    "region": {"type": "bbox", "coords": [24, -12.5, 30, -8]},
    "question": "Is vegetation declining?",
    "cadence": "daily",
}

HEX64 = re.compile(r"^[0-9a-f]{64}$")


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "panels.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    init_db()
    yield


def _client() -> TestClient:
    return TestClient(app)


def _create_and_run() -> tuple[str, str]:
    created = _client().post("/api/watches", json=dict(CREATE_BODY))
    assert created.status_code == 201, created.text
    watch_id = created.json()["id"]
    run = _client().post(f"/api/watches/{watch_id}/run")
    assert run.status_code == 200, run.text
    return watch_id, run.json()["alert_id"]


def test_receipts_entries_have_64_hex_hash():
    watch_id, _ = _create_and_run()
    resp = _client().get(f"/api/watches/{watch_id}/receipts")
    assert resp.status_code == 200, resp.text
    entries = resp.json()
    assert isinstance(entries, list) and len(entries) >= 1
    for entry in entries:
        assert HEX64.match(entry["data_hash"]), entry["data_hash"]


def test_spend_shape():
    resp = _client().get("/api/spend")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["total_credits"], (int, float))
    assert isinstance(body["calls"], list)


def test_report_has_before_after_keys():
    _, alert_id = _create_and_run()
    assert _client().post(f"/api/alerts/{alert_id}/approve").status_code == 200
    resp = _client().get(f"/api/reports/{alert_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "before_url" in body or "before_path" in body
    assert "after_url" in body or "after_path" in body


def test_eval_status_shape():
    resp = _client().get("/api/eval/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("hits", "misses", "total", "precision"):
        assert key in body, key
    assert isinstance(body["total_credits"], (int, float))
    assert body["probes"]["status"] == "pending"
