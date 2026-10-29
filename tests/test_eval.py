"""Issue #20: eval honesty gates + ENSO status + full-system 200s."""

import pytest
from fastapi.testclient import TestClient

from argus.server.app import app
from argus.store.db import init_db


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "eval.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    init_db()
    yield


def _client() -> TestClient:
    return TestClient(app)


def test_eval_run_flow():
    client = _client()
    started = client.post("/api/eval/run")
    assert started.status_code == 200, started.text
    run_id = started.json()["run_id"]
    assert run_id

    status = client.get("/api/eval/status", params={"run_id": run_id})
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["oni_correlation"] >= 0.99
    assert body["phase_agreement"] >= 95
    assert body["replay_pass"] == 5
    assert body["false_positive_pass"] == 4
    assert body["novel_question_pass"] == 10
    assert isinstance(body["precision"], float)
    assert len(body["receipts"]) == 4


def test_eval_offline_no_egress(monkeypatch):
    import httpx

    monkeypatch.setenv("ARGUS_OFFLINE", "1")

    def _blocked(*args, **kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)
    monkeypatch.setattr(httpx, "post", _blocked)

    client = _client()
    run_id = client.post("/api/eval/run").json()["run_id"]
    body = client.get("/api/eval/status", params={"run_id": run_id}).json()
    assert body["oni_correlation"] >= 0.99
    assert body["replay_pass"] == 5
    assert body["false_positive_pass"] == 4
    assert body["novel_question_pass"] == 10


def test_enso_status_shape():
    body = _client().get("/api/enso/status").json()
    for key in (
        "oni",
        "own_oni",
        "noaa_oni",
        "correlation",
        "phase",
        "phase_id",
        "intensity",
        "trajectory",
        "analogs",
        "subwatchers",
    ):
        assert key in body, key
    assert body["correlation"] >= 0.99
    assert body["phase"] in ("El Nino", "La Nina", "Neutral")
    assert body["phase_id"] in ("el_nino", "la_nina", "neutral")
    assert body["oni"] == body["own_oni"]
    assert len(body["analogs"]) == 3


def test_full_system_200s():
    client = _client()
    assert client.get("/").status_code == 200
    assert client.get("/api/watches").status_code == 200
    assert client.get("/api/alerts").status_code == 200
    assert client.get("/api/enso/status").status_code == 200
    assert client.get("/api/spend").status_code == 200
