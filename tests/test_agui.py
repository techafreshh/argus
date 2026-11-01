"""Issue #18: CopilotKit AG-UI chat bridge additive probes."""

import json

import pytest
from fastapi.testclient import TestClient

from argus.server.app import app
from argus.store.db import init_db


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "agui.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    monkeypatch.delenv("ARGUS_CHAT_ENABLED", raising=False)
    init_db()
    yield


def _client() -> TestClient:
    return TestClient(app)


def test_ask_bbox_routes_to_flooding():
    resp = _client().post(
        "/api/ask", json={"question": "Is flooding worsening here?", "bbox": [3, 6, 4, 7]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["template"] == "flooding"


def test_ask_malformed_bbox_never_422_or_500():
    for bad in ({"bbox": [1, 2]}, {"bbox": ["a", "b", "c", "d"]}, {"bbox": "nope"}):
        resp = _client().post(
            "/api/ask", json={"question": "Is flooding worsening here?", **bad}
        )
        assert resp.status_code == 200, (bad, resp.text)
        assert resp.json()["template"] == "flooding"


def test_agui_descriptor_and_copilot_handshake_with_root():
    client = _client()
    descriptor = client.get("/api/ag-ui")
    assert descriptor.status_code == 200, descriptor.text
    body = descriptor.json()
    assert body["protocol"] == "ag-ui"
    assert body["agent"] == "argus"
    handshake = client.post("/api/copilot")
    assert handshake.status_code == 200, handshake.text
    assert handshake.json()["runtime"] == "copilot"
    root = client.get("/")
    assert root.status_code == 200
    assert "ARGUS" in root.text


def test_agui_sse_stream_runs_to_finished():
    resp = _client().post(
        "/api/ag-ui", json={"question": "Is flooding worsening here?", "bbox": [3, 6, 4, 7]}
    )
    assert resp.status_code == 200, resp.text
    assert "text/event-stream" in resp.headers["content-type"]
    frames = [line for line in resp.text.splitlines() if line.startswith("data:")]
    assert frames, resp.text[:500]
    assert any("run_started" in frame for frame in frames)
    assert any("tool_call" in frame for frame in frames)
    assert any("tool_result" in frame for frame in frames)
    assert any("run_finished" in frame for frame in frames)


def _sse_events(text: str) -> list[dict]:
    return [json.loads(line[len("data:"):]) for line in text.splitlines() if line.startswith("data:")]


def test_copilot_info_lists_argus_agent():
    resp = _client().get("/api/copilot/info")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    agent_ids = [agent.get("id") for agent in body["agents"]]
    assert "argus" in agent_ids


def _assert_copilot_stream(resp) -> list[dict]:
    assert resp.status_code == 200, resp.text
    assert "text/event-stream" in resp.headers["content-type"]
    events = _sse_events(resp.text)
    kinds = [event["type"] for event in events]
    assert kinds[0] == "RUN_STARTED"
    assert "TEXT_MESSAGE_START" in kinds
    assert "TEXT_MESSAGE_CONTENT" in kinds
    assert kinds[-1] == "RUN_FINISHED"
    started = events[0]
    assert started["threadId"]
    assert started["runId"]
    finished = events[-1]
    assert finished["threadId"] == started["threadId"]
    assert finished["runId"] == started["runId"]
    starts = [e for e in events if e["type"] == "TEXT_MESSAGE_START"]
    assert starts and starts[0]["role"] == "assistant"
    message_id = starts[0]["messageId"]
    deltas = [
        e["delta"] for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"
    ]
    assert deltas and all(delta for delta in deltas)
    assert all(
        e["messageId"] == message_id
        for e in events
        if e["type"] == "TEXT_MESSAGE_CONTENT"
    )
    assert "".join(deltas)
    return events


def test_copilot_post_run_input_streams_uppercase_frames():
    resp = _client().post(
        "/api/copilot",
        json={
            "threadId": "thread-1",
            "runId": "run-1",
            "messages": [
                {"role": "user", "content": "Is flooding worsening here?"}
            ],
            "bbox": [3, 6, 4, 7],
        },
    )
    events = _assert_copilot_stream(resp)
    assert events[0]["threadId"] == "thread-1"
    assert events[0]["runId"] == "run-1"
    transcript = "".join(
        e["delta"] for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"
    )
    assert "flooding" in transcript.lower()
    assert "receipt" in transcript.lower()


def test_copilot_agent_run_streams_uppercase_frames():
    resp = _client().post(
        "/api/copilot/agent/argus/run",
        json={
            "threadId": "thread-2",
            "runId": "run-2",
            "messages": [
                {"role": "user", "content": "Is flooding worsening here?"}
            ],
            "bbox": [3, 6, 4, 7],
        },
    )
    _assert_copilot_stream(resp)


def test_copilot_agent_run_content_parts_and_abstain():
    resp = _client().post(
        "/api/copilot/agent/argus/run",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Is flooding worsening here?"}],
                }
            ],
        },
    )
    events = _assert_copilot_stream(resp)
    transcript = "".join(
        e["delta"] for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"
    )
    assert "flooding" in transcript.lower()
    abstain = _client().post(
        "/api/copilot/agent/argus/run",
        json={"messages": [{"role": "user", "content": "quux zzz"}]},
    )
    abstain_events = _assert_copilot_stream(abstain)
    abstain_text = "".join(
        e["delta"] for e in abstain_events if e["type"] == "TEXT_MESSAGE_CONTENT"
    )
    assert "No pipeline covers this." in abstain_text


def test_copilot_connect_and_stop_stubs():
    client = _client()
    connect = client.post(
        "/api/copilot/agent/argus/connect", json={"threadId": "thread-9"}
    )
    assert connect.status_code == 200, connect.text
    assert "text/event-stream" in connect.headers["content-type"]
    kinds = [event["type"] for event in _sse_events(connect.text)]
    assert kinds[0] == "RUN_STARTED"
    assert kinds[-1] == "RUN_FINISHED"
    stop = client.post("/api/copilot/agent/argus/stop/thread-9")
    assert stop.status_code == 200, stop.text
    assert stop.json() == {"ok": True}
    missing_connect = client.post("/api/copilot/agent/nope/connect", json={})
    assert missing_connect.status_code == 404, missing_connect.text


def test_copilot_unknown_agent_404s_and_empty_post_handshakes():
    client = _client()
    missing = client.post(
        "/api/copilot/agent/nope/run",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert missing.status_code == 404, missing.text
    assert missing.json()["error"] == "Agent not found"
    empty = client.post("/api/copilot")
    assert empty.status_code == 200, empty.text
    assert empty.json()["runtime"] == "copilot"
    legacy = client.post("/api/copilot", json={"question": "hi"})
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["runtime"] == "copilot"
    malformed = client.post("/api/copilot/agent/argus/run", json={"bbox": [1, 2]})
    assert malformed.status_code == 200, malformed.text
    assert "text/event-stream" in malformed.headers["content-type"]


def test_copilot_disabled_parity(monkeypatch):
    monkeypatch.setenv("ARGUS_CHAT_ENABLED", "0")
    client = _client()
    info = client.get("/api/copilot/info")
    assert info.status_code == 200
    assert info.json()["disabled"] is True
    run = client.post(
        "/api/copilot/agent/argus/run",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert run.status_code == 200
    assert run.json()["disabled"] is True
    dual = client.post(
        "/api/copilot",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert dual.status_code == 200
    assert dual.json()["disabled"] is True
    stop = client.post("/api/copilot/agent/argus/stop/thread-1")
    assert stop.status_code == 200
    assert stop.json()["disabled"] is True


def test_chat_disabled_panels_and_alerts_still_work(monkeypatch):
    monkeypatch.setenv("ARGUS_CHAT_ENABLED", "0")
    client = _client()
    root = client.get("/")
    assert root.status_code == 200
    assert "ARGUS" in root.text
    assert "globe" in root.text.lower()
    alerts = client.get("/api/alerts")
    assert alerts.status_code == 200, alerts.text
    disabled = client.get("/api/ag-ui")
    assert disabled.status_code == 200
    assert disabled.json()["disabled"] is True
