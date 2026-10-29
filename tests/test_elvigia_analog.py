"""Issue #8: analog kNN engine, phase-keyed sub-watchers, CHIRPS self-check."""

import pytest
from fastapi.testclient import TestClient

from argus.eyes.elvigia import analog, selfcheck, subwatchers
from argus.server.app import app


@pytest.fixture(autouse=True)
def _clean_env(tmp_path, monkeypatch):
    """Isolate DB path; keep fixture lookup on the repo tree by default."""
    from argus.store.db import init_db

    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "elvigia.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    monkeypatch.delenv("ARGUS_FIXTURE_DIR", raising=False)
    init_db()
    yield


def _client() -> TestClient:
    return TestClient(app)


def test_status_shape_analogs_and_subwatchers():
    resp = _client().get("/api/enso/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["analogs"], list) and len(body["analogs"]) == 3
    for hit in body["analogs"]:
        assert isinstance(hit["year"], int)
        assert isinstance(hit["similarity"], (int, float))
    assert isinstance(body["subwatchers"], list) and len(body["subwatchers"]) >= 2
    for watcher in body["subwatchers"]:
        assert "region" in watcher


def test_analog_recall_2023_returns_2015_or_1997():
    vector = analog.current_vector_for("2023-11")
    assert vector is not None and len(vector) == 5
    hits = analog.find_analogs(vector, k=3)
    assert len(hits) == 3
    years = [hit["year"] for hit in hits]
    assert 2015 in years or 1997 in years


def test_phase_flip_reconfigures_subwatchers():
    nino = subwatchers.for_phase("El Nino")
    nina = subwatchers.for_phase("La Nina")
    assert len(nino) >= 2 and len(nina) >= 2
    nino_ids = {w["region"] for w in nino}
    nina_ids = {w["region"] for w in nina}
    assert nino_ids != nina_ids
    assert subwatchers.for_phase("el_nino") == nino
    assert subwatchers.for_phase("NEUTRAL") == subwatchers.for_phase("Neutral")


def test_status_offline_no_egress(monkeypatch: pytest.MonkeyPatch):
    import httpx

    monkeypatch.setenv("ARGUS_OFFLINE", "1")

    def _blocked(*_args, **_kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)
    monkeypatch.setattr(httpx, "post", _blocked)
    resp = _client().get("/api/enso/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["analogs"]) == 3
    assert len(body["subwatchers"]) >= 2
    verdict = selfcheck.self_check(region="no-such-region", expected="dry")
    assert verdict["verdict"] == "inconclusive"
    assert verdict["divergence"] is False
