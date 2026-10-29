"""Issue #6: watches CRUD plus manual Plan -> acquire -> receipt run."""

import pytest
from fastapi.testclient import TestClient

from argus.server.app import app
from argus.store.db import init_db

CREATE_BODY = {
    "name": "t",
    "region": {"type": "bbox", "coords": [24, -12.5, 30, -8]},
    "question": "Is vegetation declining?",
    "cadence": "daily",
}


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "watches.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    init_db()
    yield


def _client() -> TestClient:
    return TestClient(app)


def _create(body: dict | None = None) -> dict:
    resp = _client().post("/api/watches", json=body or dict(CREATE_BODY))
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_returns_id_and_plan():
    body = _create()
    assert body["id"]
    assert body["plan"]
    assert body["template"] == "vegetation_decline"
    assert set(body["plan"]) >= {"sensor", "aoi", "window", "comparison", "cadence"}


def test_acceptance_trio_create_run_receipts():
    created = _create()
    watch_id = created["id"]
    run = _client().post(f"/api/watches/{watch_id}/run")
    assert run.status_code == 200, run.text
    assert run.json()["receipt_id"]
    receipts = _client().get(f"/api/watches/{watch_id}/receipts")
    assert receipts.status_code == 200
    assert isinstance(receipts.json(), list)
    assert len(receipts.json()) >= 1


def test_list_contains_created():
    created = _create()
    body = _client().get("/api/watches").json()
    assert isinstance(body, list)
    assert any(w["id"] == created["id"] for w in body)


def test_delete_removes_watch():
    watch_id = _create()["id"]
    assert _client().delete(f"/api/watches/{watch_id}").status_code == 200
    assert _client().get(f"/api/watches/{watch_id}").status_code == 404


def test_invalid_region_is_422():
    bad = dict(CREATE_BODY)
    bad["region"] = {"type": "bbox", "coords": [1, 2, 3]}
    assert _client().post("/api/watches", json=bad).status_code == 422


def test_invalid_cadence_is_422():
    bad = dict(CREATE_BODY)
    bad["cadence"] = "hourly"
    assert _client().post("/api/watches", json=bad).status_code == 422


def test_unknown_watch_is_404():
    client = _client()
    assert client.get("/api/watches/does-not-exist").status_code == 404
    assert client.post("/api/watches/does-not-exist/run").status_code == 404
    assert client.get("/api/watches/does-not-exist/receipts").status_code == 404
    assert client.delete("/api/watches/does-not-exist").status_code == 404


def test_offline_run_no_egress(monkeypatch):
    import httpx

    def _blocked(*args, **kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)
    monkeypatch.setattr(httpx, "post", _blocked)
    watch_id = _create()["id"]
    run = _client().post(f"/api/watches/{watch_id}/run")
    assert run.status_code == 200
    assert run.json()["receipt_id"]
    receipts = _client().get(f"/api/watches/{watch_id}/receipts")
    assert len(receipts.json()) >= 1


def test_healthz_still_ok():
    assert _client().get("/healthz").status_code == 200
