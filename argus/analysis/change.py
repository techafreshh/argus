"""Bi-temporal change detection over index vectors (stdlib only)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

PIXEL_HA = 0.01
DEFAULT_THRESHOLD = 0.15


def _repo_root() -> Path:
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "pyproject.toml").is_file() and (parent / "argus").is_dir():
            return parent
    return here.parents[2]


def _changes_dir(out_dir: str | Path | None = None) -> Path:
    if out_dir is not None:
        return Path(out_dir)
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        return Path(override) / "changes"
    return _repo_root() / "data" / "changes"


def _as_values(obj: Any) -> list[float]:
    if isinstance(obj, dict):
        raw = obj.get("values", obj.get("diff"))
        if raw is None:
            raise ValueError("change input dict has no 'values' key")
        obj = raw
    if not isinstance(obj, list) or not obj:
        raise ValueError("change input must be a non-empty float list")
    out: list[float] = []
    for item in obj:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError("change input must be a non-empty float list")
        out.append(float(item))
    return out


def detect_change(
    before: list[float] | dict,
    after: list[float] | dict,
    threshold: float = DEFAULT_THRESHOLD,
    pixel_ha: float = PIXEL_HA,
    out_dir: str | Path | None = None,
) -> dict:
    """Difference two index vectors; write a JSON raster; return hectares."""
    before_v = _as_values(before)
    after_v = _as_values(after)
    total = min(len(before_v), len(after_v))
    if total == 0:
        raise ValueError("change input must be a non-empty float list")
    before_v = before_v[:total]
    after_v = after_v[:total]
    diff = [after_v[i] - before_v[i] for i in range(total)]
    mask = [abs(d) >= float(threshold) for d in diff]
    changed = sum(1 for m in mask if m)
    hectares = float(changed * float(pixel_ha))
    directory = _changes_dir(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"change-{uuid.uuid4().hex[:8]}.json"
    path = directory / name
    path.write_text(
        json.dumps(
            {"width": total, "threshold": float(threshold), "diff": diff, "mask": mask}
        ),
        encoding="utf-8",
    )
    return {
        "hectares": hectares,
        "change_path": str(path),
        "changed_pixels": changed,
        "total_pixels": total,
        "threshold": float(threshold),
    }
