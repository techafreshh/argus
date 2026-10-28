"""Offline vision-tier proofs: imagery, NDVI/NDWI, change, watch run (issue #12)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from argus.adapters import imagery, s1, s2
from argus.analysis import change, ndvi, ndwi
from argus.server.app import app
from argus.store.db import init_db

REPO_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture()
def offline_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Seed an isolated fixture dir; block egress; isolate DB and changes."""
    for name in (
        "s2.test-aoi.2024-01.json",
        "s1.test-aoi.2024-01.json",
        "ndvi.test-aoi.2024-01.json",
        "ndvi.before.json",
        "ndvi.after.json",
    ):
        shutil.copy(REPO_FIXTURES / name, tmp_path / name)
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "vision.db"))
    init_db()
    return tmp_path


def _block_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def _blocked(*args, **kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)


def test_imagery_offline_returns_scene(
    offline_dirs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_egress(monkeypatch)
    payload = imagery.fetch_imagery({"aoi": "test-aoi", "window": "2024-01"})
    assert isinstance(payload["scene_id"], str) and payload["scene_id"]
    assert isinstance(payload["cloud_pct"], float)


def test_imagery_sar_fallback_on_cloud(
    offline_dirs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_egress(monkeypatch)
    payload = imagery.fetch_imagery(
        {"aoi": "test-aoi", "window": "2024-01", "max_cloud_pct": 0.0}
    )
    assert payload["sensor"] == "s1"
    assert payload["fallback_from"] == "s2"
    assert isinstance(payload["cloud_pct"], float)


def test_ndvi_zscore_shape(offline_dirs: Path) -> None:
    tile = json.loads((offline_dirs / "ndvi.test-aoi.2024-01.json").read_text())
    payload = ndvi.fetch_ndvi({"values": tile["values"]})
    assert isinstance(payload["values"], list) and payload["values"]
    assert isinstance(payload["mean"], float)
    assert isinstance(payload["z_score"], float)
    assert ndvi.compute_ndvi([0.6], [0.2])[0] == pytest.approx(0.5)
    assert ndvi.compute_ndvi([0.0], [0.0]) == [0.0]


def test_ndwi_compute_shape() -> None:
    assert ndwi.compute_ndwi([0.6], [0.2])[0] == pytest.approx(0.5)
    assert ndwi.compute_ndwi([0.0], [0.0]) == [0.0]
    payload = ndwi.fetch_ndwi({"green": [0.6], "nir": [0.2]})
    assert isinstance(payload["mean"], float)
    assert isinstance(payload["z_score"], float)


def test_detect_change_writes_raster(offline_dirs: Path) -> None:
    before = json.loads((offline_dirs / "ndvi.before.json").read_text())
    after = json.loads((offline_dirs / "ndvi.after.json").read_text())
    result = change.detect_change(before, after)
    assert isinstance(result["hectares"], float) and result["hectares"] > 0
    assert Path(result["change_path"]).is_file()


def test_watch_run_includes_fetch_ndvi_receipt(offline_dirs: Path) -> None:
    client = TestClient(app)
    created = client.post(
        "/api/watches",
        json={"name": "veg", "template": "vegetation", "question": "ndvi crop loss?"},
    )
    assert created.status_code == 200
    watch_id = created.json()["id"]
    resp = client.post(f"/api/watches/{watch_id}/run")
    assert resp.status_code == 200
    receipts = resp.json()["receipts"]
    assert any(r.get("tool") == "fetch_ndvi" for r in receipts)


def test_watch_run_unknown_is_404(offline_dirs: Path) -> None:
    resp = TestClient(app).post("/api/watches/does-not-exist/run")
    assert resp.status_code == 404


def test_s2_s1_facades_offline(
    offline_dirs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_egress(monkeypatch)
    s2_payload = s2.fetch({"region": "test-aoi", "window": "2024-01"})
    assert isinstance(s2_payload["scene_id"], str)
    assert isinstance(s2_payload["cloud_pct"], float)
    s1_payload = s1.fetch({"region": "test-aoi", "window": "2024-01"})
    assert s1_payload["sensor"] == "s1"
    assert isinstance(s1_payload["cloud_pct"], float)
