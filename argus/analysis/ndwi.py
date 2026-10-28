"""Pure-stdlib water-index analysis (NDWI), mirroring the NDVI layer."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BASELINE_MEAN = 0.2
BASELINE_STD = 0.1
SOURCE_URL = "https://catalogue.dataspace.copernicus.eu/odt/v1"


def compute_ndwi(green: list[float], nir: list[float]) -> list[float]:
    """Per-pixel (green - nir) / (green + nir); zero denominator yields 0.0."""
    out: list[float] = []
    for g, n in zip(green, nir):
        denom = float(g) + float(n)
        if denom == 0.0:
            out.append(0.0)
        else:
            out.append((float(g) - float(n)) / denom)
    return out


def z_score(values: list[float], mean: float, std: float) -> float:
    """Standardised anomaly of the sample mean against a baseline."""
    if not values or not std:
        return 0.0
    sample = sum(float(v) for v in values) / len(values)
    return (sample - float(mean)) / float(std)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(float(v) for v in values) / len(values)


def _coerce_floats(items: Any) -> list[float] | None:
    if not isinstance(items, list) or not items:
        return None
    out: list[float] = []
    for item in items:
        if isinstance(item, bool):
            return None
        if isinstance(item, (int, float)):
            out.append(float(item))
        else:
            return None
    return out or None


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        dirs.append(Path(override))
    dirs.append(Path(__file__).resolve().parents[2] / "fixtures")
    return dirs


def _find_fixture(region: str, window: str) -> Path | None:
    for directory in _candidate_dirs():
        candidate = directory / f"ndwi.{region}.{window}.json"
        if candidate.is_file():
            return candidate
    for directory in _candidate_dirs():
        matches = sorted(directory.glob(f"ndwi.{region}.*.json"))
        if matches:
            return matches[0]
    for directory in _candidate_dirs():
        matches = sorted(directory.glob("ndvi.*.json"))
        if matches:
            return matches[0]
    return None


def _baseline_from(params: dict, tile: dict | None) -> tuple[float, float]:
    override = (params or {}).get("baseline")
    if isinstance(override, dict):
        try:
            return float(override.get("mean", BASELINE_MEAN)), float(
                override.get("std", BASELINE_STD)
            )
        except (TypeError, ValueError):
            pass
    if isinstance(tile, dict):
        base = tile.get("baseline")
        if isinstance(base, dict):
            try:
                return float(base.get("mean", BASELINE_MEAN)), float(
                    base.get("std", BASELINE_STD)
                )
            except (TypeError, ValueError):
                pass
    return BASELINE_MEAN, BASELINE_STD


def fetch_ndwi(params: dict) -> dict:
    """Return NDWI values with baseline z-score anomaly (no network)."""
    params = params or {}
    green = _coerce_floats(params.get("green"))
    nir = _coerce_floats(params.get("nir"))
    explicit = _coerce_floats(params.get("values"))
    tile: dict | None = None
    source_url = SOURCE_URL
    synthetic = True
    if green is not None and nir is not None:
        values = compute_ndwi(green, nir)
    elif explicit is not None:
        values = explicit
    else:
        region = str(params.get("region", "test-aoi"))
        aoi = params.get("aoi", region)
        if isinstance(aoi, dict):
            region = str(aoi.get("region", aoi.get("name", region)))
        elif aoi is not None:
            region = str(aoi) or region
        window = str(params.get("window", "2024-01") or "2024-01")
        if len(window) >= 7 and window[4] == "-":
            window = window[:7]
        fixture = _find_fixture(region, window)
        if fixture is not None:
            tile = json.loads(fixture.read_text(encoding="utf-8"))
            found = _coerce_floats(tile.get("values"))
            values = found if found is not None else [BASELINE_MEAN]
            raw_url = tile.get("source_url")
            if isinstance(raw_url, str) and raw_url:
                source_url = raw_url
            synthetic = bool(tile.get("synthetic", True))
        else:
            values = [BASELINE_MEAN]
    mean, std = _baseline_from(params, tile)
    return {
        "values": values,
        "mean": _mean(values),
        "z_score": z_score(values, mean, std),
        "baseline": {"mean": mean, "std": std},
        "source_url": source_url,
        "synthetic": synthetic,
    }
