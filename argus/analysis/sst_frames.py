"""Pre-render monthly SST-anomaly frames for the globe demo beat.

Reads the bundled NOAA monthly series (``noaa_oni.csv``), reuses the
El Vigia ONI engine's 1991-2020 calendar-month anomaly series, and paints one
indexed-color PNG per month over the Nino3.4 bbox (lon -170..-120,
lat -5..5). Frames land in ``web/public/sst/`` so Vite copies them into the
served bundle; no frame is ever fetched at runtime.

Only the standard library is used (``struct`` + ``zlib`` PNG writer) so the
generator runs on the CI ``.[test]`` install with no extra dependencies.
"""

from __future__ import annotations

import json
import math
import struct
import sys
import zlib
from pathlib import Path

from argus.eyes.elvigia.oni import classify_phase, compute_oni, load_noaa_table

WIDTH = 500
HEIGHT = 100

LON_MIN, LON_MAX = -170.0, -120.0
LAT_MIN, LAT_MAX = -5.0, 5.0

COOL = (0x22, 0xD3, 0xEE)
NEUTRAL = (0x0C, 0x14, 0x26)
WARM = (0xFB, 0xBF, 0x24)

PALETTE_SIZE = 256
ANOM_SCALE = 2.5
KERNEL_FLOOR = 0.12

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "web" / "public" / "sst"


def frame_path(month: str, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    return out_dir / f"frame-{month}.png"


def build_palette() -> list[tuple[int, int, int]]:
    """Diverging ramp: cool (negative) -> neutral -> warm (positive)."""
    palette = []
    for i in range(PALETTE_SIZE):
        v = (i / (PALETTE_SIZE - 1)) * 2.0 - 1.0
        if v < 0.0:
            t = v + 1.0
            lo, hi = COOL, NEUTRAL
        else:
            t = v
            lo, hi = NEUTRAL, WARM
        palette.append(tuple(round(a + (b - a) * t) for a, b in zip(lo, hi)))
    return palette


def kernel(u: float, v: float) -> float:
    """Separable cosine taper peaking at the bbox center."""
    kx = (1.0 + math.cos(2.0 * math.pi * (u - 0.5))) / 2.0
    ky = (1.0 + math.cos(2.0 * math.pi * (v - 0.5))) / 2.0
    return KERNEL_FLOOR + (1.0 - KERNEL_FLOOR) * kx * ky


def anomaly_to_index(pixel_anomaly: float) -> int:
    t = max(-1.0, min(1.0, pixel_anomaly / ANOM_SCALE))
    return round((t + 1.0) / 2.0 * (PALETTE_SIZE - 1))


def render_frame(anomaly: float) -> bytes:
    """Render one indexed PNG; ``anomaly`` is the month's SST anomaly."""
    palette = build_palette()
    rows = bytearray()
    for y in range(HEIGHT):
        rows.append(0)
        v = y / (HEIGHT - 1)
        for x in range(WIDTH):
            u = x / (WIDTH - 1)
            rows.append(anomaly_to_index(anomaly * kernel(u, v)))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 3, 0, 0, 0)
    plte = b"".join(struct.pack("BBB", *entry) for entry in palette)
    idat = zlib.compress(bytes(rows), 9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"PLTE", plte)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def build_manifest(
    months: list[str],
    anomalies: list[float | None],
    phases: list[str],
) -> dict:
    frames = [
        {
            "month": month,
            "anomaly": round(anomaly if anomaly is not None else 0.0, 6),
            "phase": phase,
        }
        for month, anomaly, phase in zip(months, anomalies, phases)
    ]
    return {"frames": frames}


def generate(out_dir: Path = DEFAULT_OUT_DIR) -> dict:
    """Render every frame plus ``manifest.json`` into ``out_dir``."""
    rows = load_noaa_table()
    result = compute_oni(rows)
    months = list(result["months"])
    anomalies = list(result["anomaly"])
    phases = [classify_phase(row["noaa_oni"]) for row in rows]
    out_dir.mkdir(parents=True, exist_ok=True)
    for month, anomaly in zip(months, anomalies):
        frame_path(month, out_dir).write_bytes(
            render_frame(anomaly if anomaly is not None else 0.0)
        )
    manifest = build_manifest(months, anomalies, phases)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=1) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    out_dir = Path(argv[0]) if argv else DEFAULT_OUT_DIR
    manifest = generate(out_dir)
    frames = manifest["frames"]
    print(
        f"wrote {len(frames)} frames {frames[0]['month']}..{frames[-1]['month']} to {out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
