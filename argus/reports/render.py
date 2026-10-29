"""Pure graded-card renderer: alert + receipts -> filed report card (no DB I/O)."""

from __future__ import annotations

import math
from typing import Any

_HECTARE_KEYS = ("hectares", "area_ha", "hectare", "area_hectares", "ha")


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _hectares_from(evidence: dict) -> float:
    if not isinstance(evidence, dict):
        return 0.0
    for key in _HECTARE_KEYS:
        if key in evidence:
            return _to_float(evidence[key], 0.0)
    nested = evidence.get("numbers")
    if isinstance(nested, dict):
        for key in _HECTARE_KEYS:
            if key in nested:
                return _to_float(nested[key], 0.0)
    return 0.0


def _counts_from(evidence: dict) -> dict:
    if not isinstance(evidence, dict):
        return {}
    counts = evidence.get("counts")
    if isinstance(counts, dict):
        return dict(counts)
    return {}


def file_report(alert: dict, receipts: list[dict]) -> dict:
    """Render a graded report card from an alert dict and receipt dicts.

    Inputs are plain dicts in API shape; no database access is performed.
    The returned card is JSON-serializable.
    """
    alert = dict(alert or {})
    receipts = list(receipts or [])
    alert_id = str(alert.get("id", ""))
    watch_id = str(alert.get("watch_id", ""))
    title = str(alert.get("title", "") or "report")
    confidence = _to_float(alert.get("confidence", 0.0), 0.0)
    evidence = alert.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    hectares = _hectares_from(evidence)
    counts = _counts_from(evidence)
    before_url = str(evidence.get("before_url", "") or "")
    after_url = str(
        evidence.get("after_url", "") or evidence.get("change_path", "") or ""
    )
    sources = sorted(
        {
            str(r.get("source_url", ""))
            for r in receipts
            if isinstance(r, dict) and str(r.get("source_url", ""))
        }
    )
    pct = confidence * 100.0
    card = {
        "id": alert_id,
        "watch_id": watch_id,
        "alert_id": alert_id,
        "headline": f"{title} \u2014 {hectares:g} ha @ {pct:g}%",
        "hectares": hectares,
        "counts": counts,
        "confidence": confidence,
        "before_url": before_url,
        "after_url": after_url,
        "sources": sources,
        "receipts": receipts,
    }
    return card
