"""FIRMS-correlated percentile anomaly over the MODIS climatology."""

from __future__ import annotations

from typing import Any

from argus.adapters import firms, modis_burned
from argus.analysis.change import detect_change
from argus.eyes.fireline.baselines import build_baseline

EXCEEDANCE_PERCENTILE = 90.0


def _normalize(region: Any) -> tuple[str, str]:
    if isinstance(region, dict):
        name = region.get("region", region.get("name", region.get("aoi", "test-aoi")))
        if isinstance(name, dict):
            name = name.get("region", name.get("name", "test-aoi"))
        window = region.get("window", region.get("month", "2024-01"))
        if isinstance(window, dict):
            window = window.get("window") or window.get("month") or window.get("start") or "2024-01"
        return str(name or "test-aoi"), str(window or "2024-01")
    if region is None:
        return "test-aoi", "2024-01"
    return str(region or "test-aoi"), "2024-01"


def _mean(values: list[Any]) -> float:
    nums = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return 0.0
    return sum(nums) / len(nums)


def anomaly(region: Any = "test-aoi") -> dict:
    """Compute the fire percentile anomaly for a region.

    Accepts a region string or a ``{"region": ..., "window": ...}`` dict and
    returns percentile, baseline years, hectares, confidence and map links.
    """
    name, window = _normalize(region)
    if len(window) >= 7 and window[4] == "-":
        window = window[:7]
    baseline = build_baseline(name, window)
    history = list(baseline["values"])

    burned = modis_burned.fetch({"region": name, "window": window})
    current_values = burned.get("values") if isinstance(burned, dict) else None
    if not isinstance(current_values, list) or not current_values:
        current_values = [baseline["mean"]]
    current = _mean(current_values)

    fires = firms.fetch({"region": name, "window": window})
    detections = 0
    if isinstance(fires, dict):
        counts = fires.get("counts")
        if isinstance(counts, dict):
            try:
                detections = int(counts.get("detections", 0))
            except (TypeError, ValueError):
                detections = 0
    detections = max(detections, 0)

    ranked = sum(1 for h in history if float(h) <= current)
    percentile = 100.0 * ranked / len(history) if history else 0.0

    boost = 1.0 + detections / 200.0
    burned_total = sum(
        float(v) for v in current_values if isinstance(v, (int, float)) and not isinstance(v, bool)
    )
    hectares = float(burned_total * boost)
    confidence = min(0.99, 0.5 + percentile / 200.0)

    before_url = str(burned.get("source_url", "") or baseline.get("source_url", ""))
    after_url = str((fires.get("source_url", "") if isinstance(fires, dict) else "") or "")
    try:
        change = detect_change([baseline["mean"]] * len(current_values), [float(v) for v in current_values if isinstance(v, (int, float)) and not isinstance(v, bool)])
        after_url = str(change.get("change_path", "") or after_url)
    except (ValueError, TypeError):
        pass

    decision = "queued" if percentile >= EXCEEDANCE_PERCENTILE else "normal"
    return {
        "region": name,
        "window": window,
        "percentile": float(percentile),
        "baseline_years": int(baseline["baseline_years"]),
        "baseline": {"mean": baseline["mean"], "std": baseline["std"]},
        "current": float(current),
        "detections": int(detections),
        "hectares": float(hectares),
        "confidence": float(confidence),
        "before_url": before_url,
        "after_url": after_url,
        "decision": decision,
        "eye": "fireline",
    }
