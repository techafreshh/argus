"""Offline behavior proofs for easy-tier adapters (issue #4)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from argus.adapters import chirps, oisst, openmeteo
from argus.server.app import app


def _assert_payload(payload: dict) -> None:
    assert isinstance(payload, dict)
    assert "values" in payload
    values = payload["values"]
    assert isinstance(values, list) and len(values) > 0
    assert all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)


def test_oisst_offline_canonical_query(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    start = time.monotonic()
    payload = oisst.fetch({"region": "nino34", "window": "2023-01"})
    elapsed = time.monotonic() - start
    _assert_payload(payload)
    assert "source_url" in payload
    assert isinstance(payload["source_url"], str)
    assert payload["source_url"].startswith("http")
    assert elapsed < 2.0


def test_chirps_offline_returns_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    payload = chirps.fetch({"region": "nino34", "window": "2023-01"})
    _assert_payload(payload)


def test_openmeteo_offline_returns_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    payload = openmeteo.fetch({"region": "nino34", "window": "2023-01"})
    _assert_payload(payload)


def test_offline_no_egress_with_blocked_http(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import httpx

    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")

    def _blocked(*args, **kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)
    for module in (oisst, chirps, openmeteo):
        payload = module.fetch({"region": "nino34", "window": "2023-01"})
        _assert_payload(payload)


def test_offline_unknown_window_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    for module in (oisst, chirps, openmeteo):
        payload = module.fetch({"region": "nino34", "window": "2024-06"})
        _assert_payload(payload)


def test_fixtures_match_offline_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    root = Path(__file__).resolve().parents[1] / "fixtures"
    cases = (
        (oisst, "oisst.nino34.2023-01.json"),
        (chirps, "chirps.nino34.2023-01.json"),
        (openmeteo, "openmeteo.nino34.2023-01.json"),
    )
    for module, name in cases:
        expected = json.loads((root / name).read_text(encoding="utf-8"))
        payload = module.fetch({"region": "nino34", "window": "2023-01"})
        assert payload["values"] == expected["values"]


def test_healthz_still_ok() -> None:
    resp = TestClient(app).get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
