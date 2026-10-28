"""Stitch per-tile detections into global boxes with greedy NMS."""

from __future__ import annotations

from typing import Any


def _coords(box: dict) -> tuple[float, float, float, float]:
    return (
        float(box.get("x1", 0)),
        float(box.get("y1", 0)),
        float(box.get("x2", 0)),
        float(box.get("y2", 0)),
    )


def iou(a: dict, b: dict) -> float:
    """Intersection-over-union of two {"x1","y1","x2","y2"} boxes."""
    try:
        ax1, ay1, ax2, ay2 = _coords(a)
        bx1, by1, bx2, by2 = _coords(b)
    except (TypeError, ValueError):
        return 0.0
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = ix2 - ix1
    ih = iy2 - iy1
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def _score(box: dict) -> float:
    try:
        return float(box.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def nms(boxes: list[dict], iou_threshold: float = 0.5) -> list[dict]:
    """Greedy score-descending suppression of overlapping boxes."""
    try:
        threshold = float(iou_threshold)
    except (TypeError, ValueError):
        threshold = 0.5
    ordered = sorted(boxes, key=_score, reverse=True)
    kept: list[dict] = []
    for box in ordered:
        if not isinstance(box, dict):
            continue
        if any(iou(box, other) > threshold for other in kept):
            continue
        kept.append(box)
    return kept


def _tile_origin(entry: dict) -> tuple[float, float]:
    tile: Any = entry.get("tile", entry.get("window", entry))
    if isinstance(tile, dict) and isinstance(tile.get("x0"), (int, float)):
        try:
            return float(tile.get("x0", 0)), float(tile.get("y0", 0))
        except (TypeError, ValueError):
            return 0.0, 0.0
    origin = entry.get("origin")
    if isinstance(origin, dict):
        try:
            return float(origin.get("x", origin.get("x0", 0))), float(
                origin.get("y", origin.get("y0", 0))
            )
        except (TypeError, ValueError):
            return 0.0, 0.0
    return 0.0, 0.0


def stitch_detections(
    per_tile: list[dict], iou_threshold: float = 0.5
) -> list[dict]:
    """Offset tile-local boxes into global pixels, then merge with NMS."""
    if not isinstance(per_tile, list) or not per_tile:
        return []
    merged: list[dict] = []
    for entry in per_tile:
        if not isinstance(entry, dict):
            continue
        boxes = entry.get("boxes", [])
        if not isinstance(boxes, list):
            continue
        ox, oy = _tile_origin(entry)
        for box in boxes:
            if not isinstance(box, dict):
                continue
            try:
                x1, y1, x2, y2 = _coords(box)
            except (TypeError, ValueError):
                continue
            shifted = dict(box)
            shifted["x1"] = x1 + ox
            shifted["y1"] = y1 + oy
            shifted["x2"] = x2 + ox
            shifted["y2"] = y2 + oy
            merged.append(shifted)
    return nms(merged, iou_threshold=iou_threshold)
