"""Mem0 long-memory client: URL-based, offline no-op, receipts on live calls."""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from argus.adapters import mem0_client
from argus.server.app import app
from argus.store.db import get_connection, init_db

SEARCH_URL = "https://api.mem0.ai/v3/memories/search/"
ADD_URL = "https://api.mem0.ai/v3/memories/add/"

UI_WATCH_BODY = {
    "name": "Memory watch",
    "region": {"type": "bbox", "coords": [24, -12.5, 30, -8]},
    "question": "Is vegetation declining?",
    "cadence": "daily",
}


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


@pytest.fixture()
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "mem.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    init_db()
    yield


def _receipt_count(tool: str) -> int:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM receipts WHERE tool = ?;", (tool,)
        ).fetchone()
    finally:
        conn.close()
    return int(row[0])


def _mk_watch() -> str:
    """Receipts are FK-scoped to real watches; make one for unit tests."""
    watch_id = uuid.uuid4().hex
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO watches (id, name, region_json, question, template, "
            "cadence, status, created_at, updated_at) "
            "VALUES (?, 'w', '{}', 'q', 'unrouted', 'daily', 'active', '2026-01-01', '2026-01-01');",
            (watch_id,),
        )
        conn.commit()
    finally:
        conn.close()
    return watch_id


def test_disabled_without_key_is_full_noop(_db):
    assert mem0_client.enabled() is False
    assert mem0_client.search_memories("anything") == []
    assert mem0_client.remember([{"role": "user", "content": "hi"}]) is False
    assert _receipt_count("memory_search") == 0
    assert _receipt_count("memory_add") == 0


def test_offline_never_egresses_even_with_key(_db, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-key")
    monkeypatch.setenv("ARGUS_OFFLINE", "1")

    def _boom(*args, **kwargs):
        raise AssertionError("offline mode must not call the memory API")

    monkeypatch.setattr(mem0_client.httpx, "post", _boom)
    assert mem0_client.enabled() is False
    assert mem0_client.search_memories("Is flooding worsening here?") == []
    assert mem0_client.remember([{"role": "user", "content": "hi"}]) is False


def test_search_posts_v3_shape_and_writes_receipt(_db, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-key")
    seen: dict = {}

    def _fake_post(url, *, json=None, headers=None, timeout=None):
        seen["url"] = url
        seen["body"] = json
        seen["auth"] = (headers or {}).get("Authorization", "")
        return _FakeResponse(
            {
                "results": [
                    {"id": "m1", "memory": "watches Gulf of Guinea", "score": 0.91},
                    {"id": "m2", "memory": "prefers daily cadence", "score": 0.55},
                ]
            }
        )

    monkeypatch.setattr(mem0_client.httpx, "post", _fake_post)
    out = mem0_client.search_memories(
        "Is flooding worsening here?", watch_id=_mk_watch()
    )
    assert seen["url"] == SEARCH_URL
    assert seen["auth"] == "Token m0-test-key"
    assert seen["body"]["filters"] == {"user_id": "operator"}
    assert [m["memory"] for m in out] == [
        "watches Gulf of Guinea",
        "prefers daily cadence",
    ]
    assert _receipt_count("memory_search") == 1


def test_remember_posts_messages_and_writes_receipt(_db, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-key")
    seen: dict = {}

    def _fake_post(url, *, json=None, headers=None, timeout=None):
        seen["url"] = url
        seen["body"] = json
        return _FakeResponse({"event_id": "evt1", "status": "PENDING"}, status_code=201)

    monkeypatch.setattr(mem0_client.httpx, "post", _fake_post)
    ok = mem0_client.remember(
        [
            {"role": "user", "content": "watch the maize belt"},
            {"role": "assistant", "content": "Template vegetation_decline: plan ready."},
        ],
        metadata={"kind": "chat_run"},
        watch_id=_mk_watch(),
    )
    assert ok is True
    assert seen["url"] == ADD_URL
    assert [m["role"] for m in seen["body"]["messages"]] == ["user", "assistant"]
    assert seen["body"]["user_id"] == "operator"
    assert seen["body"]["metadata"] == {"kind": "chat_run"}
    assert _receipt_count("memory_add") == 1


def test_memory_failure_never_raises(_db, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-key")

    def _explode(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(mem0_client.httpx, "post", _explode)
    watch_id = _mk_watch()
    assert mem0_client.search_memories("question", watch_id=watch_id) == []
    assert (
        mem0_client.remember(
            [{"role": "user", "content": "hi"}], watch_id=watch_id
        )
        is False
    )
    # Failures still land as receipts: the trail shows the attempt.
    assert _receipt_count("memory_search") == 1
    assert _receipt_count("memory_add") == 1


def _frames(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            out.append(json.loads(line[5:].strip()))
    return out


def test_agui_run_carries_and_stores_memories(_db, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-key")
    stored: list[dict] = []
    monkeypatch.setattr(
        mem0_client,
        "search_memories",
        lambda query, limit=5, watch_id="": [
            {"id": "m1", "memory": "watches Gulf of Guinea", "score": 0.9}
        ],
    )
    monkeypatch.setattr(
        mem0_client,
        "remember",
        lambda messages, *, metadata=None, watch_id="": stored.append(
            {"messages": messages, "metadata": metadata, "watch_id": watch_id}
        )
        or True,
    )
    resp = TestClient(app).post(
        "/api/ag-ui",
        json={"question": "Is flooding worsening here?", "threadId": "t1"},
    )
    assert resp.status_code == 200
    events = _frames(resp.text)
    kinds = [e["type"] for e in events]
    assert "run_started" in kinds and "run_finished" in kinds
    message = next(e for e in events if e["type"] == "message")
    assert message["memories"] == [
        {"id": "m1", "memory": "watches Gulf of Guinea", "score": 0.9}
    ]
    assert len(stored) == 1
    assert stored[0]["metadata"]["kind"] == "chat_run"
    assert stored[0]["messages"][0]["content"] == "Is flooding worsening here?"


def test_watch_create_and_approval_decisions_are_remembered(_db, monkeypatch):
    monkeypatch.setenv("MEM0_API_KEY", "m0-test-key")
    kinds: list[str] = []

    def _spy(messages, *, metadata=None, watch_id=""):
        # Pure recorder: no egress, no receipts — the route seams are the contract.
        kinds.append((metadata or {}).get("kind", ""))
        return True

    monkeypatch.setattr(mem0_client, "remember", _spy)
    client = TestClient(app)
    created = client.post("/api/watches", json=dict(UI_WATCH_BODY))
    assert created.status_code == 201
    watch_id = created.json()["id"]
    run = client.post(f"/api/watches/{watch_id}/run")
    assert run.status_code == 200
    alerts = client.get("/api/alerts").json()
    queued = [a for a in alerts if a["status"] == "queued"]
    assert queued, "run should queue an alert"
    decided = client.post(f"/api/alerts/{queued[0]['id']}/approve")
    assert decided.status_code == 200
    assert "watch_created" in kinds
    assert "alert_approved" in kinds
