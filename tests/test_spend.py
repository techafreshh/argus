"""Issue #5: Meta client Plan + meta_spend ledger + GET /api/spend."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from argus.orchestrator.tools import TOOL_REGISTRY, tool_names
from argus.server.app import app
from argus.store.db import init_db


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "spend.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    init_db()
    yield


def _raw_rows():
    import os

    conn = sqlite3.connect(os.environ["ARGUS_DB_PATH"])
    try:
        return conn.execute("SELECT * FROM meta_spend;").fetchall()
    finally:
        conn.close()


def test_get_spend_shape():
    resp = TestClient(app).get("/api/spend")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_credits" in body and "calls" in body
    assert isinstance(body["total_credits"], (int, float))
    assert isinstance(body["calls"], list)


def test_get_spend_empty_db_is_zero():
    body = TestClient(app).get("/api/spend").json()
    assert body == {"total_credits": 0.0, "calls": []}


def test_meta_client_importables():
    from argus.orchestrator import meta_client

    assert callable(meta_client.plan)
    assert callable(meta_client.log_spend)


def test_tool_registry_covers_planner_sources():
    assert set(TOOL_REGISTRY) >= {"fetch_sst", "compute_oni", "cross_check"}
    assert set(tool_names()) == set(TOOL_REGISTRY)
    for spec in TOOL_REGISTRY.values():
        assert {"source", "description", "params"} <= set(spec)


def test_offline_canned_plan_no_500(monkeypatch):
    from argus.orchestrator import meta_client

    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    monkeypatch.delenv("META_API_KEY", raising=False)
    got = meta_client.plan("anything")
    assert got.sensor == "oisst"
    assert got.to_dict() == {
        "sensor": "oisst",
        "aoi": {"bbox": [-5, -170, 5, -120]},
        "window": {"start": "2023-01-01", "end": "2023-01-31"},
        "comparison": "climatology",
        "cadence": "daily",
    }
    resp = TestClient(app).get("/api/spend")
    assert resp.status_code == 200


def test_plan_from_dict_rejects_missing_keys():
    from argus.orchestrator import meta_client

    with pytest.raises(ValueError):
        meta_client.Plan.from_dict({"sensor": "oisst"})
    with pytest.raises(TypeError):
        meta_client.Plan.from_dict("not-a-dict")  # type: ignore[arg-type]


def test_log_spend_roundtrip():
    from argus.orchestrator import meta_client

    meta_client.log_spend("plan", "muse-spark-1.3-contributor", 100, 50, 0.5)
    meta_client.log_spend("plan", "muse-spark-1.3-contributor", 200, 100, 1.5)
    body = TestClient(app).get("/api/spend").json()
    assert len(body["calls"]) == 2
    assert body["total_credits"] == pytest.approx(2.0)
    first = body["calls"][0]
    assert {"id", "operation", "model", "tokens_in", "tokens_out", "cost_credits", "created_at"} <= set(first)


def test_post_spend_is_404():
    resp = TestClient(app).post("/api/spend", json={})
    assert resp.status_code == 404


def test_spend_cap_skips_live_call(monkeypatch):
    import httpx

    from argus.orchestrator import meta_client

    monkeypatch.setenv("META_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_SPEND_CAP", "150.0")
    meta_client.log_spend("plan", "muse-spark-1.3-contributor", 10, 10, 200.0)

    def _fail(*_args, **_kwargs):
        raise AssertionError("live call must be skipped when over cap")

    monkeypatch.setattr(httpx, "post", _fail)
    got = meta_client.plan("anything")
    assert got.sensor == "oisst"
    assert got.capped is True


def test_live_plan_logs_usage(monkeypatch):
    import httpx

    from argus.orchestrator import meta_client

    monkeypatch.setenv("META_API_KEY", "test-key")

    canned = {
        "sensor": "oisst",
        "aoi": {"bbox": [-5, -170, 5, -120]},
        "window": {"start": "2023-01-01", "end": "2023-01-31"},
        "comparison": "climatology",
        "cadence": "daily",
    }

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": json.dumps(canned)}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            }

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse())
    got = meta_client.plan("watch the pacific")
    assert got.sensor == "oisst"
    body = TestClient(app).get("/api/spend").json()
    assert len(body["calls"]) == 1
    assert body["total_credits"] == pytest.approx((1000 + 500) / 1000.0 * 0.001)


def test_key_never_logged(monkeypatch):
    from argus.orchestrator import meta_client

    secret = "sk-test-secret-9f8e7d6c5b"
    monkeypatch.setenv("META_API_KEY", secret)
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    meta_client.plan("anything")
    meta_client.log_spend("plan", "muse-spark-1.3-contributor", 1, 1, 0.01)
    for row in _raw_rows():
        assert secret not in " ".join(str(col) for col in row)
    body = TestClient(app).get("/api/spend").json()
    assert secret not in json.dumps(body)
