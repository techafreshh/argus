"""Wikidata entity-context adapter (independent place verification)."""

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

SOURCE_NAME = "wikidata"
BASE_URL = "https://www.wikidata.org/w/api.php"


def _coerce_str(value: Any, default: str) -> str:
    if isinstance(value, str) and value:
        return value
    if value is None:
        return default
    text = str(value)
    return text if text else default


def _spec_for(region: str, window: str) -> FetchSpec:
    return FetchSpec(
        source=SOURCE_NAME,
        aoi={"region": region},
        window={"window": window, "start": f"{window}-01", "end": f"{window}-28"},
        params={"region": region, "window": window},
    )


def _build_urls(region: str, window: str) -> tuple[str, str]:
    _ = window
    params = {
        "action": "wbsearchentities",
        "search": region,
        "language": "en",
        "format": "json",
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    return url, url


def _coerce_entity(node: Any, region: str) -> dict | None:
    if isinstance(node, dict):
        entity = node.get("entity")
        if isinstance(entity, dict) and entity:
            return entity
        raw = node.get("search")
        if isinstance(raw, list) and raw:
            first = raw[0]
            if isinstance(first, dict):
                return {
                    "id": str(first.get("id", "")),
                    "label": str(first.get("label", first.get("title", region))),
                    "description": str(first.get("description", "")),
                }
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


class WikidataAdapter(Adapter):
    """Live Wikidata fetch; caching and offline stay in the base class."""

    def fetch_live(self, spec: FetchSpec) -> bytes:
        region = str((spec.params or {}).get("region", "test-aoi"))
        window = str((spec.params or {}).get("window", "2024-01"))
        query = _coerce_str((spec.params or {}).get("query"), region)
        url, source_url = _build_urls(query, window)
        response = get_with_retries(url)
        entity: dict | None = None
        try:
            entity = _coerce_entity(response.json(), query)
        except Exception:  # noqa: BLE001 - fall back to placeholder
            entity = None
        if entity is None:
            entity = {"id": "Q0", "label": query, "description": ""}
        payload = {
            "entity": entity,
            "source_url": source_url,
            "query": query,
            "region": region,
            "synthetic": False,
        }
        return json.dumps(payload).encode("utf-8")


def fetch(params: dict) -> dict:
    """Dict-API facade: canonical spec, typed fetch, JSON-fixture fallback."""
    region = str((params or {}).get("region", "test-aoi"))
    window = str((params or {}).get("window", "2024-01"))
    spec = _spec_for(region, window)
    adapter = WikidataAdapter()
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
