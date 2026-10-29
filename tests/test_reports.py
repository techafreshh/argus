"""Issue #11: filed graded report cards, receipts trail shape, hit/miss ledger."""

import pytest
from fastapi.testclient import TestClient

from argus.reports.ledger import (
    evaluate_prediction,
    get_precision,
    log_prediction,
)
from argus.reports.render import file_report
from argus.server.app import app
from argus.store.db import get_connection, init_db

CREATE_BODY = {
    "name": "t",
    "region": {"type": "bbox", "coords": [24, -12.5, 30, -8]},
    "question": "Is vegetation declining?",
    "cadence": "daily",
}


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "reports.db"))
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


def test_report_404_while_queued_then_200_after_approve():
    watch_id = _create()["id"]
    alert_id = _run(watch_id)["alert_id"]
    assert _client().get(f"/api/reports/{alert_id}").status_code == 404
    assert _client().post(f"/api/alerts/{alert_id}/approve").status_code == 200
    resp = _client().get(f"/api/reports/{alert_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("headline", "confidence", "sources", "receipts"):
        assert key in body, key
    assert isinstance(body["headline"], str) and body["headline"]
    assert isinstance(body["confidence"], float)
    assert isinstance(body["sources"], list)
    assert isinstance(body["receipts"], list)
    for key in ("hectares", "counts", "before_url", "after_url"):
        assert key in body, key
    assert isinstance(body["hectares"], float)
    assert isinstance(body["counts"], dict)


def test_report_unknown_id_is_404_and_double_approve_is_409():
    assert _client().get("/api/reports/does-not-exist").status_code == 404
    alert_id = _run(_create()["id"])["alert_id"]
    client = _client()
    assert client.post(f"/api/alerts/{alert_id}/approve").status_code == 200
    assert client.post(f"/api/alerts/{alert_id}/approve").status_code == 409
    assert client.get(f"/api/reports/{alert_id}").status_code == 200


def test_receipts_trail_shape():
    watch_id = _create()["id"]
    _run(watch_id)
    resp = _client().get(f"/api/watches/{watch_id}/receipts")
    assert resp.status_code == 200, resp.text
    entries = resp.json()
    assert isinstance(entries, list) and len(entries) >= 1
    for entry in entries:
        assert "source_url" in entry
        assert "params" in entry and isinstance(entry["params"], dict)
        assert entry.get("data_hash")
        assert "tokens" in entry and isinstance(entry["tokens"], int)
    assert _client().get("/api/watches/does-not-exist/receipts").status_code == 404


def test_ledger_math_and_invalid_outcome():
    watch_id = _create()["id"]
    p1 = log_prediction(watch_id, {"alert_id": "a", "z_score": 3.0, "confidence": 0.6})
    p2 = log_prediction(watch_id, {"alert_id": "b", "z_score": 4.0, "confidence": 0.8})
    p3 = log_prediction(watch_id, {"alert_id": "c", "z_score": 1.0, "confidence": 0.2})
    assert p1["status"] == "open" and p1["outcome"] is None
    evaluate_prediction(p1["id"], "hit")
    evaluate_prediction(p2["id"], "hit")
    evaluate_prediction(p3["id"], "miss")
    stats = get_precision()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["total"] == 3
    assert stats["precision"] == pytest.approx(2 / 3)
    with pytest.raises(ValueError):
        evaluate_prediction(p1["id"], "maybe")


def test_approve_logs_prediction():
    watch_id = _create()["id"]
    alert_id = _run(watch_id)["alert_id"]
    assert get_precision()["total"] == 0
    assert _client().post(f"/api/alerts/{alert_id}/approve").status_code == 200
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT expectation_json FROM predictions WHERE watch_id = ?;",
            (watch_id,),
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert "alert_id" in rows[0]["expectation_json"]


def test_file_report_pure_shape():
    alert = {
        "id": "a1",
        "watch_id": "w1",
        "title": "Bloom watch",
        "confidence": 0.85,
        "evidence": {"hectares": 12.5, "counts": {"patches": 3}},
    }
    receipts = [
        {"source_url": "https://b.example/x", "params": {}, "data_hash": "h1"},
        {"source_url": "https://a.example/x", "params": {}, "data_hash": "h2"},
        {"source_url": "https://a.example/x", "params": {}, "data_hash": "h3"},
        {"source_url": "", "params": {}, "data_hash": "h4"},
    ]
    card = file_report(alert, receipts)
    assert card["id"] == "a1" and card["alert_id"] == "a1" and card["watch_id"] == "w1"
    assert "Bloom watch" in card["headline"] and "%" in card["headline"]
    assert card["hectares"] == pytest.approx(12.5)
    assert card["counts"] == {"patches": 3}
    assert card["sources"] == ["https://a.example/x", "https://b.example/x"]
    assert card["receipts"] == receipts
    thin = file_report({"id": "a2", "watch_id": "w2"}, [])
    assert thin["hectares"] == 0.0 and thin["counts"] == {}
    assert thin["sources"] == [] and thin["before_url"] == "" and thin["after_url"] == ""


def test_reports_persist_across_restart_and_healthz():
    import os

    watch_id = _create()["id"]
    alert_id = _run(watch_id)["alert_id"]
    assert _client().post(f"/api/alerts/{alert_id}/approve").status_code == 200
    before = _client().get(f"/api/reports/{alert_id}").json()
    assert _client().get("/healthz").status_code == 200
    assert _client().get("/healthz").json() == {"ok": True}
    db_path = os.environ["ARGUS_DB_PATH"]
    init_db(db_path)
    after = _client().get(f"/api/reports/{alert_id}").json()
    assert after["data_hash"] == before["data_hash"]
    assert after["headline"] == before["headline"]
