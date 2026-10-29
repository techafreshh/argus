"""Tile-window math for large-scene segmentation (stdlib only)."""

from __future__ import annotations

TILE_SIZE = 1024
OVERLAP = 128
MAX_PIXELS = 4096 * 4096


def _coerce_dim(value: object, default: int = 1024) -> int:
    try:
        number = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if number <= 0:
        return default
    return number


def cap_dimensions(width: object, height: object) -> tuple[int, int, float]:
    """Scale dimensions down to fit MAX_PIXELS; return (width, height, scale)."""
    w = _coerce_dim(width)
    h = _coerce_dim(height)
    try:
        area = w * h
    except (TypeError, OverflowError):
        return 1024, 1024, 1.0
    if area <= MAX_PIXELS:
        return w, h, 1.0
    import math

    scale = math.sqrt(MAX_PIXELS / float(area))
    w = max(1, int(w * scale))
    h = max(1, int(h * scale))
    return w, h, scale


def tile_windows(
    width: object,
    height: object,
    tile_size: int = TILE_SIZE,
    overlap: int = OVERLAP,
) -> list[dict]:
    """Cover the scene with overlapping tiles; clamp the last row/column."""
    w = _coerce_dim(width)
    h = _coerce_dim(height)
    try:
        tile = int(tile_size)
    except (TypeError, ValueError):
        tile = TILE_SIZE
    try:
        ov = int(overlap)
    except (TypeError, ValueError):
        ov = OVERLAP
    if tile <= 0:
        tile = TILE_SIZE
    ov = max(ov, 0)
    if ov >= tile:
        ov = tile // 2
    step = max(1, tile - ov)
    windows: list[dict] = []
    row = 0
    y0 = 0
    while True:
        y1 = min(y0 + tile, h)
        # Clamp a short trailing strip back so tiles keep full size.
        if y1 == h and h > tile and y0 + tile > h:
            y0 = h - tile
            y1 = h
        col = 0
        x0 = 0
        while True:
            x1 = min(x0 + tile, w)
            if x1 == w and w > tile and x0 + tile > w:
                x0 = w - tile
                x1 = w
            windows.append(
                {
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "column": col,
                    "row": row,
                }
            )
            if x1 >= w:
                break
            x0 += step
            if x0 >= w:
                break
            col += 1
        if y1 >= h:
            break
        y0 += step
        if y0 >= h:
            break
        row += 1
    return windows
