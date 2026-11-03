"""Geospatial toolbox (curated source registry with live/stale probes) and the
cookbook-derived preset catalog the onboarding wizard and watchlist consume."""

from __future__ import annotations

import json
import time
from importlib import resources
from typing import Any

import httpx
from fastapi import APIRouter

from argus.adapters import geocode
from argus.cookbook import preset_catalog

router = APIRouter()

_PROBE_TTL_SECONDS = 300
_probe_cache: dict[str, tuple[str, str]] = {}


def _load_catalog() -> list[dict[str, Any]]:
    raw = resources.files("argus.toolbox").joinpath("catalog.json").read_text("utf-8")
    data = json.loads(raw)
    sources = data.get("sources")
    return sources if isinstance(sources, list) else []


def _probe(url: str) -> str:
    """Cheap HEAD reachability probe, cached for _PROBE_TTL_SECONDS."""
    if geocode.is_offline():
        return "offline"
    cached = _probe_cache.get(url)
    if cached and time.monotonic() - float(cached[1]) < _PROBE_TTL_SECONDS:
        return cached[0]
    status = "stale"
    try:
        response = httpx.head(url, timeout=4.0, follow_redirects=True)
        if response.status_code < 500:
            status = "live"
    except Exception:  # noqa: BLE001 - an unreachable source is just stale
        status = "stale"
    _probe_cache[url] = (status, str(time.monotonic()))
    return status


@router.get("/api/toolbox")
def list_sources() -> dict:
    """The capability registry: what ARGUS can reach right now."""
    sources = []
    for source in _load_catalog():
        sources.append(
            {
                **source,
                "status": _probe(str(source.get("url", ""))),
            }
        )
    return {"sources": sources}


@router.get("/api/presets")
def list_presets() -> dict:
    """One-click cookbook watches for onboarding and the watchlist."""
    return {"presets": preset_catalog()}
