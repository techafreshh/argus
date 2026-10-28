"""Cloud-aware imagery router: Sentinel-2 optical with Sentinel-1 SAR fallback."""

from __future__ import annotations

from typing import Any

from argus.adapters import s1, s2
from argus.adapters.s2 import CLOUD_FALLBACK_PCT

SOURCE_NAME = "imagery"


def _resolve(params: dict) -> tuple[str, str, float]:
    raw = params or {}
    aoi = raw.get("aoi", raw.get("region", "test-aoi"))
    if isinstance(aoi, dict):
        region = str(aoi.get("region", aoi.get("name", "test-aoi")))
    elif aoi is None:
        region = "test-aoi"
    else:
        region = str(aoi) or "test-aoi"
    window = raw.get("window", "2024-01")
    if isinstance(window, dict):
        window = (
            window.get("window") or window.get("month") or window.get("start") or "2024-01"
        )
    window = str(window or "2024-01")
    if len(window) >= 7 and window[4] == "-":
        window = window[:7]
    try:
        max_cloud = float(raw.get("max_cloud_pct", CLOUD_FALLBACK_PCT))
    except (TypeError, ValueError):
        max_cloud = CLOUD_FALLBACK_PCT
    return region, window, max_cloud


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def fetch_imagery(params: dict) -> dict:
    """Return S2 optical unless cloud exceeds threshold, then S1 SAR fallback."""
    region, window, max_cloud = _resolve(params or {})
    try:
        optical = s2.fetch({"region": region, "window": window})
    except Exception:  # noqa: BLE001 - optical miss falls through to SAR
        optical = None
    if optical is not None:
        cloud_pct = _as_float(optical.get("cloud_pct"), CLOUD_FALLBACK_PCT)
        optical["cloud_pct"] = cloud_pct
        optical.setdefault("scene_id", f"S2_{region}_{window}")
        optical.setdefault("sensor", "s2")
        if cloud_pct <= max_cloud:
            return optical
    try:
        sar = s1.fetch({"region": region, "window": window})
    except Exception:
        if optical is not None:
            return optical
        raise
    sar.setdefault("scene_id", f"S1_{region}_{window}")
    sar["sensor"] = "s1"
    sar["fallback_from"] = "s2"
    if optical is not None:
        sar["optical_scene_id"] = optical.get("scene_id")
        sar["cloud_pct"] = _as_float(
            optical.get("cloud_pct"), sar.get("cloud_pct", 0.0)
        )
    sar.setdefault("cloud_pct", 0.0)
    return sar


fetch = fetch_imagery
