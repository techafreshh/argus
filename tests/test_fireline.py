"""Issue #15: Fireline eye queues graded fire alerts (MODIS baselines + FIRMS)."""

import pytest
from fastapi.testclient import TestClient

from argus.eyes.fireline import anomaly
from argus.server.app import app
from argus.store.db import init_db

CREATE_BODY = {
    "name": "fire watch",
    "region": {"type": "bbox", "coords": [24, -12.5, 30, -8]},
    "question": "Is fire anomaly worsening here?",
    "template": "fire_anomaly",
    "cadence": "daily",
}


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "fireline.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    init_db()
    yield


def _client() -> TestClient:
    return TestClient(app)


def test_anomaly_returns_percentile_and_baseline_years():
    result = anomaly("test-aoi")
    assert result["percentile"] >= 90.0
    assert result["baseline_years"] == 20
    assert isinstance(result["hectares"], float)
    assert isinstance(result["confidence"], float)


def test_anomaly_accepts_dict_region():
    result = anomaly({"region": "test-aoi", "window": "2024-01"})
    assert result["percentile"] >= 90.0
    assert result["baseline_years"] == 20


def test_fire_run_queues_fireline_alert():
    client = _client()
    watch_id = client.post("/api/watches", json=dict(CREATE_BODY)).json()["id"]
    run = client.post(f"/api/watches/{watch_id}/run")
    assert run.status_code == 200, run.text
    assert run.json()["ok"] is True
    assert run.json()["alert_status"] == "queued"
    alerts = client.get("/api/alerts").json()
    mine = [a for a in alerts if a["id"] == run.json()["alert_id"]]
    assert len(mine) == 1
    assert mine[0]["eye"] == "fireline"
    assert mine[0]["status"] == "queued"


def test_fire_report_carries_hectares_and_confidence():
    client = _client()
    watch_id = client.post("/api/watches", json=dict(CREATE_BODY)).json()["id"]
    alert_id = client.post(f"/api/watches/{watch_id}/run").json()["alert_id"]
    resp = client.post(f"/api/alerts/{alert_id}/approve")
    assert resp.status_code == 200, resp.text
    report = client.get(f"/api/reports/{alert_id}")
    assert report.status_code == 200, report.text
    card = report.json()
    assert isinstance(card["hectares"], float)
    assert isinstance(card["confidence"], float)
    assert card["hectares"] > 0


def test_fire_offline_no_egress(monkeypatch):
    import httpx

    from argus.adapters import era5, firms, modis_burned
    from argus.adapters.base import OfflineMissingFixture

    monkeypatch.setenv("ARGUS_OFFLINE", "1")

    def _blocked(*args, **kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)
    result = anomaly("test-aoi")
    assert result["baseline_years"] == 20
    assert result["percentile"] >= 90.0
    for module in (modis_burned, firms):
        payload = module.fetch({"region": "test-aoi", "window": "2024-01"})
        assert "values" in payload
        assert payload["values"]
    with pytest.raises(OfflineMissingFixture):
        era5.fetch({"region": "no-such-region", "window": "1999-01"})
