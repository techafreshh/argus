"""Signed webhook channel delivery: CRUD, test-fire, approve-time dispatch."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from argus.adapters import webhook_client
from argus.server.app import app


def _client() -> TestClient:
    return TestClient(app)


def _db(tmp_path, monkeypatch):
    db = tmp_path / "channels.db"
    monkeypatch.setenv("ARGUS_DB_PATH", str(db))
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    from argus.store.db import init_db

    init_db()
    return db


def _mk_watch() -> str:
    from argus.store.db import get_connection

    watch_id = uuid.uuid4().hex
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO watches (id, name, region_json, question, template,"
            " cadence, status, created_at, updated_at)"
            " VALUES (?, 'w', '{}', 'q', 'flooding', 'daily', 'active',"
            " datetime('now'), datetime('now'));",
            (watch_id,),
        )
        conn.commit()
    finally:
        conn.close()
    return watch_id


def _mk_alert(watch_id: str) -> str:
    from argus.store.db import get_connection

    alert_id = uuid.uuid4().hex
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO alerts (id, watch_id, title, confidence, status,"
            " evidence_json, created_at)"
            " VALUES (?, ?, 'Flood expansion', 0.9, 'queued', '{}',"
            " datetime('now'));",
            (alert_id, watch_id),
        )
        conn.commit()
    finally:
        conn.close()
    return alert_id


def test_deliver_offline_never_egresses(tmp_path, monkeypatch) -> None:
    _db(tmp_path, monkeypatch)
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    called = []
    monkeypatch.setattr(
        webhook_client.httpx, "post", lambda *a, **k: called.append(a)
    )
    result = webhook_client.deliver("https://hooks.example/x", "s3cret", {"a": 1})
    assert result["ok"] is False
    assert result["error"] == "offline"
    assert called == []


def test_deliver_signs_and_posts(tmp_path, monkeypatch) -> None:
    _db(tmp_path, monkeypatch)
    seen = {}

    class _Resp:
        status_code = 200

    def _fake_post(url, content=None, headers=None, timeout=None):
        seen["url"] = url
        seen["body"] = content
        seen["headers"] = headers
        return _Resp()

    monkeypatch.setattr(webhook_client.httpx, "post", _fake_post)
    result = webhook_client.deliver("https://hooks.example/x", "s3cret", {"b": 2})
    assert result["ok"] is True
    assert result["http_status"] == 200
    expected = "sha256=" + webhook_client.sign(seen["body"], "s3cret")
    assert seen["headers"]["X-ARGUS-Signature"] == expected
    assert json.loads(seen["body"]) == {"b": 2}


def test_channel_crud_and_validation(tmp_path, monkeypatch) -> None:
    _db(tmp_path, monkeypatch)
    client = _client()
    watch_id = _mk_watch()
    # bad URL is a 4xx, never a 500
    bad = client.post("/api/channels", json={"target": "ftp://nope"})
    assert bad.status_code == 422
    created = client.post(
        "/api/channels", json={"target": "https://hooks.example/argus", "watch_id": watch_id}
    )
    assert created.status_code == 200
    body = created.json()
    assert body["target"] == "https://hooks.example/argus"
    assert "secret" not in body, "the signing secret must never be served back"
    listed = client.get("/api/channels").json()
    assert any(c["id"] == body["id"] for c in listed)
    assert client.delete(f"/api/channels/{body['id']}").json()["ok"] is True
    assert client.delete(f"/api/channels/{body['id']}").status_code == 404


def test_channel_unknown_watch_is_404(tmp_path, monkeypatch) -> None:
    _db(tmp_path, monkeypatch)
    resp = _client().post(
        "/api/channels", json={"target": "https://hooks.example/x", "watch_id": "nope"}
    )
    assert resp.status_code == 404


def test_test_channel_records_delivery(tmp_path, monkeypatch) -> None:
    _db(tmp_path, monkeypatch)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    created = _client().post(
        "/api/channels", json={"target": "https://hooks.example/argus", "secret": "k"}
    )
    channel_id = created.json()["id"]
    monkeypatch.setattr(
        webhook_client,
        "deliver",
        lambda target, secret, payload: {"ok": True, "http_status": 200, "error": "", "attempts": 1},
    )
    fired = _client().post(f"/api/channels/{channel_id}/test")
    assert fired.json()["ok"] is True
    from argus.store.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT status, channel_id FROM deliveries WHERE alert_id IS NULL;"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1 and rows[0]["status"] == "delivered"


def test_approve_dispatches_to_channels_and_writes_receipts(
    tmp_path, monkeypatch
) -> None:
    _db(tmp_path, monkeypatch)

    watch_id = _mk_watch()
    alert_id = _mk_alert(watch_id)
    _client().post(
        "/api/channels",
        json={"target": "https://hooks.example/global"},
    )
    _client().post(
        "/api/channels",
        json={"target": "https://hooks.example/watch", "watch_id": watch_id},
    )
    # A watch-scoped channel of ANOTHER watch must not receive this alert.
    other = _mk_watch()
    _client().post(
        "/api/channels",
        json={"target": "https://hooks.example/other", "watch_id": other},
    )
    delivered = []
    monkeypatch.setattr(
        webhook_client,
        "deliver",
        lambda target, secret, payload: (
            delivered.append((target, payload)),
            {"ok": True, "http_status": 200, "error": "", "attempts": 1},
        )[1],
    )
    resp = _client().post(f"/api/alerts/{alert_id}/approve")
    assert resp.json()["status"] == "approved"
    targets = [t for t, _ in delivered]
    assert "https://hooks.example/watch" in targets
    assert "https://hooks.example/global" in targets
    assert "https://hooks.example/other" not in targets
    payload = delivered[0][1]
    assert payload["type"] == "alert.approved"
    assert payload["alert_id"] == alert_id
    assert payload["report_id"] == alert_id
    from argus.store.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT tool FROM receipts WHERE watch_id = ? AND tool = 'alert_deliver';",
            (watch_id,),
        ).fetchall()
        ledger = conn.execute(
            "SELECT status FROM deliveries WHERE alert_id = ?;", (alert_id,)
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2, "one receipt per delivered channel"
    assert len(ledger) == 2 and all(r["status"] == "delivered" for r in ledger)


def test_delivery_failure_never_breaks_approval(tmp_path, monkeypatch) -> None:
    _db(tmp_path, monkeypatch)
    watch_id = _mk_watch()
    alert_id = _mk_alert(watch_id)
    _client().post("/api/channels", json={"target": "https://hooks.example/slow"})
    monkeypatch.setattr(
        webhook_client,
        "deliver",
        lambda *a, **k: {"ok": False, "http_status": None, "error": "boom", "attempts": 2},
    )
    resp = _client().post(f"/api/alerts/{alert_id}/approve")
    assert resp.json()["status"] == "approved"
    from argus.store.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT status FROM deliveries WHERE alert_id = ?;", (alert_id,)
        ).fetchall()
    finally:
        conn.close()
    assert rows and rows[0]["status"] == "failed"


def test_payload_carries_public_report_url(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_PUBLIC_URL", "https://argus.example")
    payload = webhook_client.alert_payload(
        {"id": "a1", "watch_id": "w1", "title": "t", "report_id": "a1",
         "decided_at": "now", "evidence": {}},
        {"id": "a1", "headline": "h", "confidence": 0.9, "hectares": 12.0,
         "data_hash": "abc"},
    )
    assert payload["report_url"].startswith("https://argus.example/reports?report=a1")
    assert payload["data_hash"] == "abc"
