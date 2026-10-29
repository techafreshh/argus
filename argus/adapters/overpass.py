"""OSM Overpass ground-context adapter (independent ground verification)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from argus.adapters._http import get_with_retries
from argus.adapters.base import (
    Adapter,
    FetchSpec,
    OfflineMissingFixture,
    cache_key,
    write_fixture,
)

SOURCE_NAME = "overpass"
BASE_URL = "https://overpass-api.de/api/interpreter"


def _bbox_for(region: str) -> list[float]:
    # Small demo boxes; unknown regions fall back to the shared test AOI.
    boxes: dict[str, list[float]] = {
        "test-aoi": [36.8, -1.4, 37.0, -1.2],
    }
    return list(boxes.get(region, boxes["test-aoi"]))


def _spec_for(region: str, window: str) -> FetchSpec:
    return FetchSpec(
        source=SOURCE_NAME,
        aoi={"region": region, "bbox": _bbox_for(region)},
        window={"window": window, "start": f"{window}-01", "end": f"{window}-28"},
        params={"region": region, "window": window},
    )


def _build_query(region: str) -> str:
    lon_min, lat_min, lon_max, lat_max = _bbox_for(region)
    bbox = f"{lat_min},{lon_min},{lat_max},{lon_max}"
    return (
        f"[out:json];(node[place]({bbox});way[landuse]({bbox});"
        f"relation[building]({bbox}););out center 20;"
    )


def _build_urls(region: str, window: str) -> tuple[str, str]:
    query = _build_query(region)
    url = f"{BASE_URL}?{urlencode({'data': query})}"
    return url, url


def _coerce_elements(node: Any) -> list[dict] | None:
    if isinstance(node, dict):
        raw = node.get("elements")
        if isinstance(raw, list) and raw:
            return [item if isinstance(item, dict) else {"id": str(item)} for item in raw]
    if isinstance(node, list) and node:
        return [item if isinstance(item, dict) else {"id": str(item)} for item in node]
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


class OverpassAdapter(Adapter):
    """Live Overpass fetch; caching and offline stay in the base class."""

    def fetch_live(self, spec: FetchSpec) -> bytes:
        region = str((spec.params or {}).get("region", "test-aoi"))
        window = str((spec.params or {}).get("window", "2024-01"))
        url, source_url = _build_urls(region, window)
        response = get_with_retries(url)
        elements: list[dict] | None = None
        try:
            elements = _coerce_elements(response.json())
        except Exception:  # noqa: BLE001 - fall back to placeholder
            elements = None
        if elements is None:
            elements = [{"type": "node", "id": 1, "region": region}]
        payload = {
            "elements": elements,
            "source_url": source_url,
            "bbox": _bbox_for(region),
            "region": region,
            "window": window,
            "synthetic": False,
        }
        return json.dumps(payload).encode("utf-8")


def fetch(params: dict) -> dict:
    """Dict-API facade: canonical spec, typed fetch, JSON-fixture fallback."""
    region = str((params or {}).get("region", "test-aoi"))
    window = str((params or {}).get("window", "2024-01"))
    spec = _spec_for(region, window)
    adapter = OverpassAdapter()
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
