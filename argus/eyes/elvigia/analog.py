"""Analog kNN engine: closest-historical-year story over ocean_states.csv.

Pure-stdlib 5-feature (``[nino34, trend, nino4, atl3, iod]``) z-scored
Euclidean kNN. No numpy, no network; the fixture is resolved with the
same candidate-dirs + ``ARGUS_FIXTURE_DIR`` override idiom as the
fireline baselines. Nothing here ever raises on bad input.
"""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path
from typing import Any

FEATURES = ("nino34", "trend", "nino4", "atl3", "iod")
N_FEATURES = len(FEATURES)

# Exact (distance ~0) self-matches are the query itself, not an analog.
_SELF_TOLERANCE = 1e-9


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        dirs.append(Path(override))
    dirs.append(Path(__file__).resolve().parents[3] / "fixtures")
    return dirs


def _find_states_csv(path: str | Path | None = None) -> Path | None:
    if path is not None:
        candidate = Path(path)
        return candidate if candidate.is_file() else None
    for directory in _candidate_dirs():
        candidate = directory / "ocean_states.csv"
        if candidate.is_file():
            return candidate
    return None


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def load_states(path: str | Path | None = None) -> list[dict]:
    """Load monthly ocean states as ``{month, year, vector}`` dicts."""
    resolved = _find_states_csv(path)
    if resolved is None:
        return []
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError:
        return []
    states: list[dict] = []
    try:
        rows = csv.DictReader(text.splitlines())
        for record in rows:
            month = str((record or {}).get("month", "")).strip()
            if len(month) < 7 or month[4] != "-" or not month[:4].isdigit():
                continue
            vector = [_as_float((record or {}).get(name)) for name in FEATURES]
            states.append(
                {
                    "month": month[:7],
                    "year": int(month[:4]),
                    "vector": vector,
                }
            )
    except (csv.Error, ValueError):
        return states
    return states


def _stats(states: list[dict]) -> tuple[list[float], list[float]]:
    n = len(states)
    means = [
        sum(float(s["vector"][j]) for s in states) / n
        for j in range(N_FEATURES)
    ]
    stds: list[float] = []
    for j in range(N_FEATURES):
        var = sum((s["vector"][j] - means[j]) ** 2 for s in states) / n
        std = math.sqrt(var) if var > 0 else 0.0
        stds.append(std if std >= 1e-9 else 1.0)
    return means, stds


def _zscore(vector: list[float], means: list[float], stds: list[float]) -> list[float]:
    return [(vector[j] - means[j]) / stds[j] for j in range(N_FEATURES)]


def find_analogs(
    current_vector: Any,
    k: int = 3,
    states: list[dict] | None = None,
    exclude: Any = None,
) -> list[dict]:
    """Return top-k historical analogs for a 5-feature current vector.

    Each hit mirrors the eval ``find_analogs`` shape: ``month``/``year``/
    ``similarity=1/(1+dist)``/``distance``. The query month itself (distance
    ~0) and any ``exclude`` month labels are skipped. Never raises.
    """
    try:
        k = max(0, int(k))
    except (TypeError, ValueError):
        k = 3
    if k <= 0:
        return []
    try:
        query = [_as_float(v) for v in list(current_vector)[:N_FEATURES]]  # type: ignore[arg-type]
    except TypeError:
        return []
    if len(query) < N_FEATURES:
        return []
    history = list(states) if states is not None else load_states()
    usable = [
        s
        for s in history
        if isinstance(s, dict)
        and isinstance(s.get("vector"), list)
        and len(s["vector"]) >= N_FEATURES
        and isinstance(s.get("month"), str)
    ]
    if not usable:
        return []
    if isinstance(exclude, str):
        excluded = {exclude}
    elif isinstance(exclude, (list, tuple, set)):
        excluded = {str(m) for m in exclude}
    else:
        excluded = set()
    means, stds = _stats(usable)
    scored: list[tuple[float, dict]] = []
    for state in usable:
        if state["month"] in excluded:
            continue
        try:
            candidate = _zscore([_as_float(v) for v in state["vector"][:N_FEATURES]], means, stds)
            dist = math.sqrt(
                sum((x - y) ** 2 for x, y in zip(_zscore(query, means, stds), candidate))
            )
        except (TypeError, ValueError):
            continue
        if dist < _SELF_TOLERANCE:
            continue
        scored.append((dist, state))
    scored.sort(key=lambda item: item[0])
    analogs: list[dict] = []
    for dist, state in scored[:k]:
        label = str(state["month"])
        analogs.append(
            {
                "month": label,
                "year": int(label[:4]) if label[:4].isdigit() else 0,
                "similarity": round(1.0 / (1.0 + dist), 4),
                "distance": round(dist, 4),
            }
        )
    return analogs


def current_vector_for(month: str, path: str | Path | None = None) -> list[float] | None:
    """Return the 5-feature fixture vector for a YYYY-MM label, if present."""
    label = str(month or "").strip()[:7]
    for state in load_states(path):
        if state["month"] == label:
            return list(state["vector"])
    return None


def latest_state(path: str | Path | None = None) -> dict | None:
    """Return the most recent monthly state, or None when unavailable."""
    states = load_states(path)
    return states[-1] if states else None
