"""Issue #47: real OISST SST frames 1982->now for the globe demo beat."""

import json
import math
import struct
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from argus.analysis.sst_frames import (
    DEFAULT_OUT_DIR,
    anomaly_to_index,
    build_palette,
    kernel,
    render_frame,
)
from argus.eyes.elvigia.oni import classify_phase, compute_oni, load_noaa_table
from argus.server.app import app

STATIC_SST = Path("argus/server/static/sst")

EXPECTED_FIRST = "1982-01"
EXPECTED_LAST = "2025-12"

# Leak words must not reach the shipped UI. The built JS bundle also vendors
# third-party syntax grammars (via the chat panel) that contain the generic
# words "fixture"/"synthetic", so those two are asserted on first-party
# sources and the served manifest instead of the whole bundle.
LEAK_WORDS = ("ENSO_FIXTURE",)


def _expected_months() -> list[str]:
    months = []
    year, month = 1982, 1
    while (year, month) <= (2025, 12):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def _manifest() -> dict:
    return json.loads((DEFAULT_OUT_DIR / "manifest.json").read_text(encoding="utf-8"))


def _decode_png(raw: bytes) -> tuple[int, int, bytes]:
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    pos, width, height, ctype, idat = 8, 0, 0, 0, b""
    while pos < len(raw):
        (length,) = struct.unpack(">I", raw[pos : pos + 4])
        tag = raw[pos + 4 : pos + 8]
        data = raw[pos + 8 : pos + 8 + length]
        if tag == b"IHDR":
            width, height, _depth, ctype, _, _, _ = struct.unpack(">IIBBBBB", data)
        elif tag == b"IDAT":
            idat += data
        pos += 12 + length
    assert ctype == 3, "frames must be indexed-color PNGs"
    return width, height, zlib.decompress(idat)


def _center_mean(month: str, out_dir: Path = DEFAULT_OUT_DIR) -> float:
    width, height, px = _decode_png((out_dir / f"frame-{month}.png").read_bytes())
    stride = width + 1
    vals = []
    for y in range(35, 65):
        vals.extend(px[y * stride + 1 : (y + 1) * stride][200:300])
    assert (width, height) == (500, 100)
    return sum(vals) / len(vals)


def test_manifest_covers_every_month_with_valid_values():
    manifest = _manifest()
    frames = manifest["frames"]
    assert [f["month"] for f in frames] == _expected_months()
    assert len(frames) == 528
    for frame in frames:
        assert set(frame) == {"month", "anomaly", "phase"}
        assert isinstance(frame["anomaly"], (int, float))
        assert math.isfinite(frame["anomaly"])
        assert frame["phase"] in ("El Nino", "La Nina", "Neutral")


def test_manifest_phases_match_oni_engine_thresholds():
    rows = load_noaa_table()
    by_month = {row["month"]: row["noaa_oni"] for row in rows}
    for frame in _manifest()["frames"]:
        assert frame["phase"] == classify_phase(by_month[frame["month"]])


def test_manifest_anomalies_match_compute_oni():
    rows = load_noaa_table()
    result = compute_oni(rows)
    computed = dict(zip(result["months"], result["anomaly"]))
    for frame in _manifest()["frames"]:
        assert abs(frame["anomaly"] - computed[frame["month"]]) < 1e-6


def test_frames_are_real_indexed_pngs_matching_manifest():
    manifest = _manifest()
    files = sorted(DEFAULT_OUT_DIR.glob("frame-*.png"))
    assert len(files) == len(manifest["frames"]) == 528
    width, height, _ = _decode_png(files[0].read_bytes())
    assert (width, height) == (500, 100)


def test_strong_events_show_opposite_colors():
    assert _center_mean("1997-12") > 200
    assert _center_mean("2015-12") > 200
    assert _center_mean("1988-12") < 100
    assert _center_mean("2010-12") < 100


def test_kernel_peaks_at_center_and_ramps_diverge():
    assert kernel(0.5, 0.5) > kernel(0.0, 0.5) > 0
    assert kernel(0.5, 0.5) > kernel(0.5, 0.0) > 0
    palette = build_palette()
    assert palette[0] == (0x22, 0xD3, 0xEE)
    assert palette[255] == (0xFB, 0xBF, 0x24)
    assert anomaly_to_index(0.0) == 128
    assert anomaly_to_index(99.0) == 255
    assert anomaly_to_index(-99.0) == 0
    assert render_frame(1.5) != render_frame(-1.5)


def test_frames_serve_offline_same_origin(monkeypatch: pytest.MonkeyPatch):
    import httpx

    monkeypatch.setenv("ARGUS_OFFLINE", "1")

    def _blocked(*_args, **_kwargs):
        raise AssertionError("network egress attempted")

    monkeypatch.setattr(httpx, "get", _blocked)
    monkeypatch.setattr(httpx, "post", _blocked)
    client = TestClient(app)
    resp = client.get("/sst/manifest.json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    body = resp.json()
    assert [f["month"] for f in body["frames"]] == _expected_months()
    for month in ("1982-01", "2023-01", "2025-12"):
        frame = client.get(f"/sst/frame-{month}.png")
        assert frame.status_code == 200
        assert "image/png" in frame.headers["content-type"]
        assert frame.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_built_bundle_serves_sst_from_static():
    assert (STATIC_SST / "manifest.json").is_file()
    assert (STATIC_SST / "frame-2023-01.png").is_file()
    static_manifest = json.loads((STATIC_SST / "manifest.json").read_text())
    assert [f["month"] for f in static_manifest["frames"]] == _expected_months()


def _bundle_js() -> str:
    chunks = []
    for asset in sorted(Path("argus/server/static/assets").glob("*.js")):
        chunks.append(asset.read_text(encoding="utf-8", errors="replace"))
    index = Path("argus/server/static/index.html").read_text(encoding="utf-8")
    return "\n".join([index, *chunks])


def test_bundle_hooks_and_no_fake_canvas_residual():
    bundle = _bundle_js()
    assert "sst-scrubber" in bundle
    assert "sst-month" in bundle
    assert "sst-play" in bundle
    assert "globe-map" in bundle
    for word in LEAK_WORDS:
        assert word not in bundle
    assert "Math.sin((x / W" not in bundle
    assert "SstCanvas" not in bundle


def test_no_leak_words_in_first_party_sources_or_manifest():
    sources = [
        Path("web/src/App.tsx"),
        Path("web/src/api.ts"),
        Path("web/src/panels/SstGlobe.tsx"),
        Path("web/src/index.css"),
        Path("argus/analysis/sst_frames.py"),
        Path("argus/server/app.py"),
        DEFAULT_OUT_DIR / "manifest.json",
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for word in (*LEAK_WORDS, "synthetic", "fixture", "Fixture"):
            assert word not in text, f"{word} leaks in {path}"
    src = Path("web/src/App.tsx").read_text(encoding="utf-8")
    assert "getEnsoStatus" in src
