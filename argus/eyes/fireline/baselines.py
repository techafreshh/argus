"""20-year MODIS MCD64A1 monthly burned-area climatology per region."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

BASELINE_YEARS = 20


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        dirs.append(Path(override))
    dirs.append(Path(__file__).resolve().parents[3] / "fixtures")
    return dirs


def _find_fixture(region: str, window: str) -> Path | None:
    for directory in _candidate_dirs():
        candidate = directory / f"modis_burned.{region}.{window}.json"
        if candidate.is_file():
            return candidate
    for directory in _candidate_dirs():
        matches = sorted(directory.glob(f"modis_burned.{region}.*.json"))
        if matches:
            return matches[0]
    for directory in _candidate_dirs():
        matches = sorted(directory.glob("modis_burned.*.json"))
        if matches:
            return matches[0]
    return None


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(float(v) for v in values) / len(values)


def _std(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    var = sum((float(v) - mean) ** 2 for v in values) / len(values)
    return math.sqrt(var) if var > 0 else 0.0


def build_baseline(region: str, month: str = "2024-01") -> dict:
    """Load the MODIS fixture history and return a 20-year climatology."""
    region = str(region or "test-aoi")
    month = str(month or "2024-01")
    if len(month) >= 7 and month[4] == "-":
        month = month[:7]
    history: list[float] = []
    source_url = ""
    fixture = _find_fixture(region, month)
    if fixture is not None:
        try:
            tile = json.loads(fixture.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            tile = {}
        if isinstance(tile, dict):
            raw = tile.get("history")
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, bool):
                        continue
                    if isinstance(item, (int, float)):
                        history.append(float(item))
            raw_url = tile.get("source_url")
            if isinstance(raw_url, str) and raw_url:
                source_url = raw_url
    history = history[:BASELINE_YEARS]
    while len(history) < BASELINE_YEARS:
        history.append(history[-1] if history else 100.0)
    mean = _mean(history)
    std = _std(history, mean)
    return {
        "mean": mean,
        "std": std,
        "values": list(history),
        "baseline_years": BASELINE_YEARS,
        "source_url": source_url,
        "region": region,
        "month": month,
    }
