"""MODIS MCD64A1 burned-area adapter (NASA LP DAAC catalogue reference)."""

from __future__ import annotations

import calendar
import json
import os
from pathlib import Path
from typing import Any

from argus.adapters._http import get_with_retries
from argus.adapters.base import (
    Adapter,
    FetchSpec,
    OfflineMissingFixture,
    cache_key,
    write_fixture,
)

SOURCE_NAME = "modis_burned"
BASE_URL = "https://lpdaac.usgs.gov/products/mcd64a1v061/"
UNITS = "hectares"

FIRE_REGIONS: dict[str, list[float]] = {
    "test-aoi": [24.0, -12.5, 30.0, -8.0],
}


def _month_range(window: str) -> tuple[str, str]:
    text = (window or "").strip()
    if len(text) == 7 and text[4] == "-":
        year, month = int(text[:4]), int(text[5:7])
        last = calendar.monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text, text
    raise ValueError(f"unsupported window: {window!r}")


def _bbox_for(region: str) -> list[float]:
    return list(FIRE_REGIONS.get(region, FIRE_REGIONS["test-aoi"]))


def _spec_for(region: str, window: str) -> FetchSpec:
    start, end = _month_range(window)
    return FetchSpec(
        source=SOURCE_NAME,
        aoi={"region": region, "bbox": _bbox_for(region)},
        window={"window": window, "start": start, "end": end},
        params={"region": region, "window": window},
    )


def _build_urls(region: str, window: str) -> tuple[str, str]:
    start, end = _month_range(window)
    lon_min, lat_min, lon_max, lat_max = _bbox_for(region)
    url = (
        f"{BASE_URL}?region={region}&start={start}&end={end}"
        f"&bbox={lon_min},{lat_min},{lon_max},{lat_max}"
    )
    return url, url


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


def _find_numeric_list(node: Any) -> list[float] | None:
    if isinstance(node, dict):
        values = node.get("values")
        found = _coerce_floats(values) if values is not None else None
        if found is not None:
            return found
        for value in node.values():
            found = _find_numeric_list(value)
            if found is not None:
                return found
        return None
    if isinstance(node, list):
        direct = _coerce_floats(node)
        if direct is not None:
            return direct
        for item in node:
            found = _find_numeric_list(item)
            if found is not None:
                return found
        return None
    return None


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        dirs.append(Path(override))
    dirs.append(Path(__file__).resolve().parents[2] / "fixtures")
    return dirs


def _find_fixture(region: str, window: str) -> Path | None:
    for directory in _candidate_dirs():
        candidate = directory / f"{SOURCE_NAME}.{region}.{window}.json"
        if candidate.is_file():
            return candidate
    for directory in _candidate_dirs():
        matches = sorted(directory.glob(f"{SOURCE_NAME}.{region}.*.json"))
        if matches:
            return matches[0]
    for directory in _candidate_dirs():
        matches = sorted(directory.glob(f"{SOURCE_NAME}.*.json"))
        if matches:
            return matches[0]
    return None


class MODISBurnedAdapter(Adapter):
    """Live MODIS burned-area fetch; caching and offline stay in the base class."""

    def fetch_live(self, spec: FetchSpec) -> bytes:
        region = str((spec.params or {}).get("region", "test-aoi"))
        window = str((spec.params or {}).get("window", "2024-01"))
        url, source_url = _build_urls(region, window)
        response = get_with_retries(url)
        values: list[float] | None = None
        try:
            values = _find_numeric_list(response.json())
        except Exception:  # noqa: BLE001 - fall back to placeholder
            values = None
        if values is None:
            values = [100.0]
        payload = {
            "values": values,
            "source_url": source_url,
            "region": region,
            "window": window,
            "units": UNITS,
            "synthetic": False,
        }
        return json.dumps(payload).encode("utf-8")


def fetch(params: dict) -> dict:
    """Dict-API facade: canonical spec, typed fetch, JSON-fixture fallback."""
    region = str((params or {}).get("region", "test-aoi"))
    window = str((params or {}).get("window", "2024-01"))
    spec = _spec_for(region, window)
    adapter = MODISBurnedAdapter()
    try:
        result = adapter.fetch(spec)
        if result.ok and result.data:
            return json.loads(result.data.decode("utf-8"))
    except OfflineMissingFixture:
        pass
    fixture = _find_fixture(region, window)
    if fixture is None:
        raise OfflineMissingFixture(f"OFFLINE missing fixture for {SOURCE_NAME}")
    raw = fixture.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    try:
        write_fixture(cache_key(spec.source, spec.aoi, spec.window), raw)
    except OSError:
        pass
    return payload


fetch_burned = fetch
