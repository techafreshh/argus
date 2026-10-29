"""GET /api/enso/status contract: keys, offline numeric correlation, valid phase."""

import math

import pytest
from fastapi.testclient import TestClient

from argus.server.app import app


def test_get_enso_status_shape():
    resp = TestClient(app).get("/api/enso/status")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("own_oni", "noaa_oni", "phase", "correlation"):
        assert key in body
    assert isinstance(body["own_oni"], (int, float))
    assert isinstance(body["noaa_oni"], (int, float))
    assert isinstance(body["correlation"], (int, float))
    assert body["phase"] in ("El Nino", "La Nina", "Neutral")


def test_get_enso_status_offline_no_egress(monkeypatch: pytest.MonkeyPatch):
    import httpx

    monkeypatch.setenv("ARGUS_OFFLINE", "1")

    def _blocked(*_args, **_kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)
    monkeypatch.setattr(httpx, "post", _blocked)
    resp = TestClient(app).get("/api/enso/status")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["correlation"], (int, float))
    assert math.isfinite(body["correlation"])
    assert body["phase"] in ("El Nino", "La Nina", "Neutral")
