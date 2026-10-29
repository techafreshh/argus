"""CHIRPS self-check: confirm or refute the rainfall expectation.

Reads CHIRPS through the existing fixture/offline path and compares the
window mean against a fixed climatology mean. Missing fixtures, offline
gaps, or any other failure yield ``inconclusive`` — this function never
raises and never performs live egress in tests.
"""

from __future__ import annotations

import math
from typing import Any

CLIMATOLOGY_MEAN = 3.0
CONFIRM_THRESHOLD = 0.5


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _fetch_values(region: str, window: str) -> list[float] | None:
    try:
        from argus.adapters import chirps
    except Exception:  # noqa: BLE001 - self-check never raises
        return None
    try:
        payload = chirps.fetch({"region": region, "window": window})
    except Exception:  # noqa: BLE001 - missing fixture means inconclusive
        return None
    if not isinstance(payload, dict):
        return None
    values = payload.get("values")
    if not isinstance(values, list) or not values:
        return None
    cleaned = [v for v in (_as_float(v) for v in values) if math.isfinite(v)]
    return cleaned or None


def self_check(
    region: str = "southern_africa",
    expected: str = "dry",
    window: str = "2023-01",
    analog_year: Any = None,
) -> dict:
    """Confirm/refute ``expected`` rainfall for ``region`` over ``window``."""
    region = str(region or "southern_africa")
    window = str(window or "2023-01")
    expectation = str(expected or "dry").strip().lower()
    if expectation not in ("dry", "wet"):
        expectation = "dry"
    try:
        year = int(analog_year) if analog_year is not None else None
    except (TypeError, ValueError):
        year = None
    values = _fetch_values(region, window)
    base = {
        "region": region,
        "window": window,
        "expected": expectation,
        "analog_year": year,
        "divergence": False,
    }
    if not values:
        return {
            **base,
            "verdict": "inconclusive",
            "observed_anomaly": 0.0,
            "observed_mean": None,
        }
    mean = sum(values) / len(values)
    anomaly = mean - CLIMATOLOGY_MEAN
    if expectation == "dry":
        if anomaly < -CONFIRM_THRESHOLD:
            verdict = "confirmed"
        elif anomaly > CONFIRM_THRESHOLD:
            verdict = "refuted"
        else:
            verdict = "inconclusive"
    else:
        if anomaly > CONFIRM_THRESHOLD:
            verdict = "confirmed"
        elif anomaly < -CONFIRM_THRESHOLD:
            verdict = "refuted"
        else:
            verdict = "inconclusive"
    return {
        **base,
        "verdict": verdict,
        "observed_anomaly": round(anomaly, 4),
        "observed_mean": round(mean, 4),
        "divergence": verdict == "refuted",
    }
