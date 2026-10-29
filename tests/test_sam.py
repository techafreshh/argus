"""Issue #13: SAM 3.1 tiling/stitching segmentation proofs."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from argus.analysis import sam_client, stitch, tiling
from argus.server.app import app
from argus.store.db import init_db


def _isolate(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("ARGUS_FIXTURE_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "sam.db"))
    init_db()
    return tmp_path


def test_offline_segment_concept_shape(tmp_path: Path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    result = sam_client.segment_concept("solar farm", str(tmp_path / "scene.tif"))
    assert isinstance(result["boxes"], list) and len(result["boxes"]) >= 1
    assert Path(result["masks_path"]).is_file()
    assert result["concept"] == "solar farm"
    assert result["source_url"].startswith("fixture://")


def test_tiling_covers_scene_with_overlap() -> None:
    windows = tiling.tile_windows(2500, 1800)
    assert len(windows) > 1
    xs = sorted({w["x0"] for w in windows})
    assert xs[0] == 0
    assert max(w["x1"] for w in windows) == 2500
    assert max(w["y1"] for w in windows) == 1800
    # Overlap: second column starts before the first tile ends.
    first_row = sorted([w for w in windows if w["row"] == 0], key=lambda w: w["x0"])
    assert len(first_row) >= 2
    assert first_row[1]["x0"] < first_row[0]["x1"]
    # Edge clamping: last tile touches the scene edge exactly.
    assert first_row[-1]["x1"] == 2500


def test_cap_dimensions_scales_oversize() -> None:
    w, h, scale = tiling.cap_dimensions(8192, 8192)
    assert w * h <= tiling.MAX_PIXELS
    assert scale < 1.0
    w2, h2, scale2 = tiling.cap_dimensions(1024, 1024)
    assert (w2, h2, scale2) == (1024, 1024, 1.0)


def test_nms_drops_duplicate() -> None:
    boxes = [
        {"x1": 0, "y1": 0, "x2": 100, "y2": 100, "score": 0.9},
        {"x1": 5, "y1": 5, "x2": 100, "y2": 100, "score": 0.5},
        {"x1": 500, "y1": 500, "x2": 600, "y2": 600, "score": 0.7},
    ]
    kept = stitch.nms(boxes, iou_threshold=0.5)
    assert len(kept) == 2
    assert kept[0]["score"] == 0.9


def test_stitch_offsets_tile_origins() -> None:
    per_tile = [
        {
            "tile": {"x0": 0, "y0": 0, "column": 0, "row": 0},
            "boxes": [{"x1": 10, "y1": 10, "x2": 50, "y2": 50, "score": 0.9}],
        },
        {
            "tile": {"x0": 896, "y0": 0, "column": 1, "row": 0},
            "boxes": [{"x1": 10, "y1": 10, "x2": 50, "y2": 50, "score": 0.8}],
        },
    ]
    merged = stitch.stitch_detections(per_tile)
    assert len(merged) == 2
    assert any(b["x1"] == 906 for b in merged)


def test_watch_run_ship_presence_receipt(tmp_path: Path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    client = TestClient(app)
    created = client.post(
        "/api/watches",
        json={"name": "ships", "template": "ship_presence", "question": "ships?"},
    )
    assert created.status_code == 200
    resp = client.post(f"/api/watches/{created.json()['id']}/run")
    assert resp.status_code == 200
    receipts = resp.json()["receipts"]
    sam_entries = [r for r in receipts if r.get("tool") == "segment_concept"]
    assert sam_entries
    assert "fixture" in sam_entries[0]["source_url"] or "meta.ai" in sam_entries[0][
        "source_url"
    ]


def test_missing_key_offline_no_500(tmp_path: Path, monkeypatch) -> None:
    _isolate(tmp_path, monkeypatch)
    result = sam_client.segment_concept("ship", {"width": 1024, "height": 1024})
    assert isinstance(result["boxes"], list) and len(result["boxes"]) >= 1
    assert result["source_url"].startswith("fixture://")
    client = TestClient(app)
    created = client.post(
        "/api/watches",
        json={"name": "ships", "template": "ship_presence", "question": "ships?"},
    )
    resp = client.post(f"/api/watches/{created.json()['id']}/run")
    assert resp.status_code == 200
