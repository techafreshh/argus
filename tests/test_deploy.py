"""Issue #19: docker compose deploy + offline demo contract."""

from pathlib import Path

from fastapi.testclient import TestClient

from argus.server.app import app
from argus.store.db import init_db

REPO = Path(__file__).resolve().parents[1]

CREATE_BODY = {
    "name": "t",
    "region": {"type": "bbox", "coords": [24, -12.5, 30, -8]},
    "question": "Is vegetation declining?",
    "cadence": "daily",
}


def _client() -> TestClient:
    return TestClient(app)


def test_compose_and_dockerfile_exist():
    assert (REPO / "docker-compose.yml").is_file()
    assert (REPO / "docker" / "Dockerfile").is_file()


def test_dockerfile_runs_uvicorn():
    text = (REPO / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert "uvicorn" in text


def test_compose_wires_port_offline_and_env_file():
    text = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "PORT" in text
    assert "ARGUS_OFFLINE" in text
    assert "env_file" in text


def test_offline_run_returns_receipt_with_offline_flag(tmp_path, monkeypatch):
    import httpx

    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "deploy.db"))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    monkeypatch.delenv("META_API_KEY", raising=False)
    init_db()

    def _blocked(*args, **kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)
    monkeypatch.setattr(httpx, "post", _blocked)

    client = _client()
    created = client.post("/api/watches", json=CREATE_BODY)
    assert created.status_code == 201, created.text
    watch_id = created.json()["id"]

    run = client.post(f"/api/watches/{watch_id}/run")
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["receipt_id"]
    assert body["offline"] is True
    for receipt in body["receipts"]:
        assert receipt["offline"] is True

    receipts = client.get(f"/api/watches/{watch_id}/receipts")
    assert receipts.status_code == 200
    rows = receipts.json()
    assert len(rows) >= 1
    for row in rows:
        assert row["offline"] is True
