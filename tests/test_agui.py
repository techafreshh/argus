"""Issue #18: CopilotKit AG-UI chat bridge additive probes."""

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
