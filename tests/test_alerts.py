"""Issue #10: run queues an alert; approve/reject decide; approved is a report."""

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
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "alerts.db"))
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


def _run(watch_id: str) -> dict:
    resp = _client().post(f"/api/watches/{watch_id}/run")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _alerts() -> list[dict]:
    resp = _client().get("/api/alerts")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    return body


def test_run_queues_alert():
    watch_id = _create()["id"]
    run = _run(watch_id)
    assert run["ok"] is True
    assert run["alert_status"] == "queued"
    alerts = _alerts()
    queued = [a for a in alerts if a["id"] == run["alert_id"]]
    assert len(queued) == 1
    assert queued[0]["status"] == "queued"
    assert queued[0]["watch_id"] == watch_id


def test_approve_flow():
    watch_id = _create()["id"]
    alert_id = _run(watch_id)["alert_id"]
    resp = _client().post(f"/api/alerts/{alert_id}/approve")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"
    by_id = {a["id"]: a for a in _alerts()}
    assert by_id[alert_id]["status"] == "approved"
    report = _client().get(f"/api/reports/{alert_id}")
    assert report.status_code == 200, report.text
    assert report.json()["status"] == "approved"


def test_reject_flow():
    watch_id = _create()["id"]
    first = _run(watch_id)["alert_id"]
    second = _run(watch_id)["alert_id"]
    assert second != first
    resp = _client().post(f"/api/alerts/{second}/reject")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"
    by_id = {a["id"]: a for a in _alerts()}
    assert by_id[second]["status"] == "rejected"
    assert by_id[first]["status"] == "queued"


def test_report_404_while_queued():
    alert_id = _run(_create()["id"])["alert_id"]
    assert _client().get(f"/api/reports/{alert_id}").status_code == 404


def test_unknown_ids_are_404():
    client = _client()
    assert client.post("/api/alerts/does-not-exist/approve").status_code == 404
    assert client.post("/api/alerts/does-not-exist/reject").status_code == 404
    assert client.get("/api/reports/does-not-exist").status_code == 404


def test_double_decide_is_409():
    watch_id = _create()["id"]
    approved = _run(watch_id)["alert_id"]
    rejected = _run(watch_id)["alert_id"]
    assert _client().post(f"/api/alerts/{approved}/approve").status_code == 200
    assert _client().post(f"/api/alerts/{approved}/approve").status_code == 409
    assert _client().post(f"/api/alerts/{approved}/reject").status_code == 409
    assert _client().post(f"/api/alerts/{rejected}/reject").status_code == 200
    assert _client().post(f"/api/alerts/{rejected}/approve").status_code == 409
