"""Behavior proofs for verification cross-check plus GDELT/OSM context (issue #14)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from argus.adapters import gdelt, overpass, wikidata
from argus.server.app import app
from argus.store.db import get_connection, init_db
from argus.verify.crosscheck import cross_check

REPO_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture()
def offline_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Seed an isolated fixture dir; block egress; isolate the database."""
    for name in (
        "gdelt.test-aoi.2024-01.json",
        "overpass.test-aoi.2024-01.json",
        "wikidata.test-aoi.2024-01.json",
    ):
        shutil.copy(REPO_FIXTURES / name, tmp_path / name)
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "verify.db"))
    init_db()
    return tmp_path


def _block_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def _blocked(*args, **kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)


def _high_agreement() -> dict:
    return {
        "imagery": {"cloud_pct": 10.0, "z_score": 3.0},
        "news": {
            "articles": [
                {"title": "Anomaly seen", "url": "https://example.com/a"},
                {"title": "Confirmed", "url": "https://example.com/b"},
            ]
        },
        "context": {
            "elements": [{"type": "node", "id": 1}],
            "entity": {"id": "Q1", "label": "test-aoi", "description": "d"},
        },
    }


def test_cross_check_high_agreement_queued() -> None:
    result = cross_check(**_high_agreement())
    assert result["confidence"] >= 85
    assert result["decision"] == "queued"
    assert result["sources_present"] >= 2


def test_cross_check_cloud_only_ambiguity() -> None:
    result = cross_check(
        {"cloud_pct": 90.0},
        {},
        {},
    )
    assert result["decision"] == "ambiguity"
    assert result["confidence"] < 85


def test_cross_check_single_source_capped() -> None:
    result = cross_check({"cloud_pct": 5.0, "z_score": 9.0}, {}, {})
    assert result["confidence"] < 85
    assert result["decision"] == "ambiguity"


def test_verify_high_agreement_queues_alert(offline_dirs: Path) -> None:
    client = TestClient(app)
    resp = client.post("/api/verify", json=_high_agreement())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["confidence"] >= 85
    assert body["decision"] == "queued"
    assert body["alert"]["status"] == "queued"
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT status FROM alerts WHERE id = ?;", (body["alert"]["id"],)
        ).fetchall()
    finally:
        conn.close()
    assert rows and rows[0]["status"] == "queued"


def test_verify_cloud_only_no_queued_alert(offline_dirs: Path) -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/verify",
        json={"imagery": {"cloud_pct": 95.0}, "news": {}, "context": {}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["decision"] == "ambiguity" or body["confidence"] < 85
    assert body.get("alert") is None
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT COUNT(*) AS n FROM alerts WHERE status = 'queued';"
        ).fetchone()
    finally:
        conn.close()
    assert int(rows["n"]) == 0


def test_verify_watch_alias_queues_and_404s(offline_dirs: Path) -> None:
    client = TestClient(app)
    watch = client.post(
        "/api/watches",
        json={"name": "v", "question": "Is there change?", "cadence": "daily"},
    ).json()
    watch_id = watch["id"]
    resp = client.post(f"/api/watches/{watch_id}/verify", json=_high_agreement())
    assert resp.status_code == 200
    assert resp.json()["alert"]["status"] == "queued"
    missing = client.post("/api/watches/nope/verify", json=_high_agreement())
    assert missing.status_code == 404


@pytest.mark.parametrize("module", [gdelt, overpass, wikidata])
def test_offline_adapters_fixture_source_url_fast(
    offline_dirs: Path, monkeypatch: pytest.MonkeyPatch, module
) -> None:
    _block_egress(monkeypatch)
    start = time.monotonic()
    payload = module.fetch({"region": "test-aoi", "window": "2024-01"})
    elapsed = time.monotonic() - start
    assert isinstance(payload, dict)
    assert isinstance(payload.get("source_url"), str)
    assert payload["source_url"].startswith("http")
    assert elapsed < 2.0


def test_healthz_still_ok(offline_dirs: Path) -> None:
    resp = TestClient(app).get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
