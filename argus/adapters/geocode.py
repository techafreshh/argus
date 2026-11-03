"""Free-text place resolution: question language -> a usable bbox.

``extract_place_candidates`` is pure and deterministic; ``resolve_place`` calls
the public Nominatim geocoder (no key, plain URL) and never raises. Offline
mode never egresses and yields no region, so a question without a resolvable
place degrades to the pre-freeform behavior instead of fabricating one.
"""

from __future__ import annotations

import math
import os
import re
import unicodedata
from typing import Any

import httpx

SOURCE_NAME = "geocode"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_UA = "ARGUS/1.0 (orbital analyst demo; +https://argus.techa.pro)"
_TIMEOUT = 3.0
_MAX_CANDIDATES = 2

# Sentence openers and generic question words never name a place on their own.
_UPPER = r"[A-Z][^\W\d_]{2,}"
_PLACE_RE = re.compile(
    r"\b(" + _UPPER + r"(?:(?:\s+(?:of|del|el|da|de|la|le|and))*\s+"
    r"(?:" + _UPPER + r"|delta|river|lake|gulf|bay|basin|valley|coast|desert"
    r"|sea|strait|island|range|depression))*)"
)
_STOPWORDS = frozenset(
    {
        "and",
        "any",
        "are",
        "can",
        "compare",
        "could",
        "did",
        "does",
        "has",
        "have",
        "here",
        "how",
        "is",
        "please",
        "show",
        "should",
        "tell",
        "the",
        "there",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "why",
        "will",
        "would",
    }
)


def is_offline() -> bool:
    """Offline gate shared by every egressing helper in this module."""
    return os.environ.get("ARGUS_OFFLINE", "") == "1"


def extract_place_candidates(question: str) -> list[str]:
    """Proper-noun runs (allowing geo connectors), longest first, deduped."""
    text = str(question or "")
    if not text.strip():
        return []
    candidates: list[str] = []
    for match in _PLACE_RE.finditer(text):
        candidate = " ".join(match.group(1).split())
        if not candidate:
            continue
        words = candidate.split(" ")
        while words and words[0].lower().strip(".") in _STOPWORDS:
            words = words[1:]
        if not words:
            continue
        candidate = " ".join(words)
        if candidate not in candidates:
            candidates.append(candidate)
    candidates.sort(key=len, reverse=True)
    return candidates[:_MAX_CANDIDATES]


def _bbox_from(raw: Any) -> list[float] | None:
    """Nominatim boundingbox is [south, north, west, east]; -> [w, s, e, n]."""
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        south, north, west, east = (float(v) for v in raw)
    except (TypeError, ValueError):
        return None
    coords = [west, south, east, north]
    if any(math.isnan(v) or math.isinf(v) for v in coords):
        return None
    if west >= east or south >= north:
        return None
    return coords


def resolve_place(name: str) -> dict | None:
    """Resolve one place name to {name, bbox, source_url}; None on any failure.

    Among the top hits the largest-area bbox wins: natural regions (deltas,
    lakes, valleys) should outrank coincidentally-named infrastructure.
    """
    if is_offline() or not name.strip():
        return None
    try:
        response = httpx.get(
            NOMINATIM_URL,
            params={"q": name.strip(), "format": "jsonv2", "limit": 5},
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            return None
        best: dict | None = None
        best_area = -1.0
        for row in rows:
            if not isinstance(row, dict):
                continue
            bbox = _bbox_from(row.get("boundingbox"))
            if bbox is None:
                continue
            area = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
            if area <= best_area:
                continue
            display = str(row.get("display_name", "") or name.strip())
            best_area = area
            best = {
                "name": display.split(",")[0].strip() or name.strip(),
                "display_name": display,
                "bbox": bbox,
                "source_url": str(response.url),
            }
        return best
    except Exception:  # noqa: BLE001 - place resolution must never break a run
        return None


def _fold(text: str) -> str:
    """Diacritic-fold + lowercase for gazetteer lookups (Bodélé -> bodele)."""
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )


def region_from_question(question: str) -> tuple[dict | None, dict | None]:
    """First resolvable place in the question -> (bbox region, geocode info).

    Cookbook gazetteer aliases (deltas, basins, depressions — natural regions
    generic geocoders rank poorly) resolve first; everything else goes to the
    Nominatim geocoder. The info dict names its source via ``source_url``.
    """
    from argus.cookbook import gazetteer

    known = gazetteer()
    for candidate in extract_place_candidates(question):
        hit = known.get(_fold(candidate))
        if hit is not None:
            region = {"type": "bbox", "coords": hit["bbox"], "place": hit["name"]}
            return region, hit
        resolved = resolve_place(candidate)
        if resolved is not None:
            region = {
                "type": "bbox",
                "coords": resolved["bbox"],
                "place": resolved["name"],
            }
            return region, resolved
    return None, None
