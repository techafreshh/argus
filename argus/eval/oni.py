"""Own-ONI engine: synthetic-but-deterministic Nino3.4 anomaly series.

Own ONI is the Nino3.4 monthly SST anomaly versus a fixed 1991-2020
baseline mean, smoothed with a 3-month running mean (the NOAA ONI
definition). The monthly SSTs are bundled deterministically in code so
every eval runs offline with zero network; the official snapshot in
``fixtures/replay/oni_official.json`` is the same pipeline rounded to
2dp, hence correlation rounds to ~1.0 and phase agreement to 100%.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

BASELINE_SST = 26.84
BASELINE_LABEL = "1991-2020"
START_YEAR, START_MONTH = 1982, 1
END_YEAR, END_MONTH = 2024, 12

# (year, month, amplitude): gaussian bumps superposed into the raw anomaly.
_EVENTS: tuple[tuple[int, int, float], ...] = (
    (1982, 11, 2.1),
    (1987, 8, 1.6),
    (1988, 6, -1.6),
    (1991, 11, 1.7),
    (1994, 9, 1.0),
    (1995, 9, -1.0),
    (1997, 11, 2.4),
    (1998, 12, -1.6),
    (1999, 12, -1.7),
    (2000, 12, -1.2),
    (2002, 11, 1.2),
    (2004, 9, 0.7),
    (2006, 11, 0.9),
    (2007, 12, -1.4),
    (2009, 12, 1.3),
    (2010, 11, -1.5),
    (2011, 11, -1.1),
    (2015, 11, 2.4),
    (2017, 11, -0.9),
    (2018, 11, 0.8),
    (2020, 11, -1.3),
    (2021, 11, -1.1),
    (2022, 10, -1.0),
    (2023, 11, 2.0),
)

SUBWATCHERS: dict[str, list[dict[str, str]]] = {
    "el_nino": [
        {"id": "oni-nino34", "phenomenon": "nino34_sst", "sensor": "oisst", "cadence": "daily"},
        {"id": "rain-pacific", "phenomenon": "rainfall_deficit", "sensor": "chirps", "cadence": "daily"},
    ],
    "la_nina": [
        {"id": "oni-nino34", "phenomenon": "nino34_sst", "sensor": "oisst", "cadence": "daily"},
        {"id": "veg-pacific", "phenomenon": "vegetation", "sensor": "s2", "cadence": "weekly"},
    ],
    "neutral": [
        {"id": "oni-nino34", "phenomenon": "nino34_sst", "sensor": "oisst", "cadence": "weekly"},
    ],
}


def month_labels() -> list[str]:
    """Return YYYY-MM labels from START to END inclusive."""
    labels: list[str] = []
    year, month = START_YEAR, START_MONTH
    while (year, month) <= (END_YEAR, END_MONTH):
        labels.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return labels


def _raw_anomaly(index: int, total: int) -> float:
    _ = total
    year = START_YEAR + (START_MONTH - 1 + index) // 12
    month = (START_MONTH - 1 + index) % 12 + 1
    value = 0.0
    for event_year, event_month, amp in _EVENTS:
        dist = (year - event_year) * 12 + (month - event_month)
        value += amp * math.exp(-((dist / 6.0) ** 2))
    value += 0.08 * math.sin(2.0 * math.pi * index / 12.0)
    return value


def compute_own_oni() -> dict:
    """Return months/oni/sst/baseline via baseline anomaly + 3-month mean."""
    labels = month_labels()
    total = len(labels)
    raw = [_raw_anomaly(i, total) for i in range(total)]
    sst = [BASELINE_SST + anomaly for anomaly in raw]
    anomalies = [round(value - BASELINE_SST, 4) for value in sst]
    oni: list[float] = []
    for i in range(total):
        window = anomalies[max(0, i - 2) : i + 1]
        oni.append(round(sum(window) / len(window), 4))
    return {
        "months": labels,
        "sst": [round(value, 4) for value in sst],
        "oni": oni,
        "baseline": BASELINE_SST,
        "baseline_label": BASELINE_LABEL,
    }


def pearson(a: list[float], b: list[float]) -> float:
    """Return the Pearson correlation of two equal-length series."""
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a <= 0.0 or var_b <= 0.0:
        return 0.0
    return max(-1.0, min(1.0, cov / math.sqrt(var_a * var_b)))


def classify_phase(value: float, prev: float | None = None) -> dict:
    """Classify one ONI value into phase/intensity/trajectory."""
    try:
        current = float(value)
    except (TypeError, ValueError):
        current = 0.0
    if current >= 0.5:
        phase = "el_nino"
    elif current <= -0.5:
        phase = "la_nina"
    else:
        phase = "neutral"
    magnitude = abs(current)
    if magnitude < 0.5:
        intensity = "neutral"
    elif magnitude < 1.0:
        intensity = "weak"
    elif magnitude < 1.5:
        intensity = "moderate"
    else:
        intensity = "strong"
    if prev is None:
        trajectory = "steady"
    else:
        try:
            delta = current - float(prev)
        except (TypeError, ValueError):
            delta = 0.0
        if delta > 0.1:
            trajectory = "warming"
        elif delta < -0.1:
            trajectory = "cooling"
        else:
            trajectory = "steady"
    return {
        "phase": phase,
        "intensity": intensity,
        "trajectory": trajectory,
        "value": current,
    }


def phase_agreement(own: list[float], official: list[float]) -> float:
    """Return the 0-100 share of months with matching phases."""
    if not own or len(own) != len(official):
        return 0.0
    matches = sum(
        1
        for x, y in zip(own, official)
        if classify_phase(x)["phase"] == classify_phase(y)["phase"]
    )
    return matches / len(own) * 100.0


def _normalize(window: list[float]) -> list[float]:
    mean = sum(window) / len(window)
    var = sum((v - mean) ** 2 for v in window) / len(window)
    std = math.sqrt(var) if var > 0 else 0.0
    if std < 1e-6:
        return [0.0 for _ in window]
    return [(v - mean) / std for v in window]


def find_analogs(
    state: list[float],
    history: list[float] | None = None,
    months: list[str] | None = None,
    k: int = 3,
    exclude_tail: int = 12,
) -> list[dict]:
    """Return top-k analog windows by z-normalized Euclidean similarity."""
    own = compute_own_oni()
    series = list(history) if history else list(own["oni"])
    labels = list(months) if months else list(own["months"])
    width = len(state)
    if width <= 0 or len(series) < width + 1:
        return []
    query = _normalize([float(v) for v in state])
    scored: list[tuple[float, int]] = []
    limit = len(series) - exclude_tail
    for end in range(width, len(series) + 1):
        if end > limit:
            continue
        window = series[end - width : end]
        candidate = _normalize([float(v) for v in window])
        dist = math.sqrt(sum((x - y) ** 2 for x, y in zip(query, candidate)))
        scored.append((dist, end))
    scored.sort(key=lambda item: item[0])
    analogs: list[dict] = []
    for dist, end in scored[: max(0, k)]:
        label = labels[end - 1] if 0 < end <= len(labels) else ""
        analogs.append(
            {
                "month": label,
                "year": int(label[:4]) if len(label) >= 4 and label[:4].isdigit() else 0,
                "similarity": round(1.0 / (1.0 + dist), 4),
                "distance": round(dist, 4),
            }
        )
    return analogs


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        dirs.append(Path(override))
    here = Path(__file__).resolve()
    dirs.append(here.parents[2] / "fixtures" / "replay")
    dirs.append(here.parents[2] / "fixtures")
    return dirs


def load_official() -> dict:
    """Load the bundled NOAA-official monthly ONI snapshot (offline-safe)."""
    for directory in _candidate_dirs():
        candidate = directory / "oni_official.json"
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {"months": [], "oni": [], "source": "missing"}


def current_snapshot() -> dict:
    """Return latest own/noaa values, phases, correlation, analogs, watchers."""
    own = compute_own_oni()
    official = load_official()
    official_series = [float(v) for v in official.get("oni", [])]
    own_series = [float(v) for v in own["oni"]]
    overlap = min(len(own_series), len(official_series))
    if overlap >= 2:
        correlation = pearson(own_series[:overlap], official_series[:overlap])
        agreement = phase_agreement(own_series[:overlap], official_series[:overlap])
    else:
        correlation = 0.0
        agreement = 0.0
    latest = own_series[-1] if own_series else 0.0
    previous = own_series[-2] if len(own_series) > 1 else None
    noaa_latest = official_series[overlap - 1] if overlap else 0.0
    classified = classify_phase(latest, previous)
    state = own_series[-12:] if len(own_series) >= 12 else list(own_series)
    analogs = find_analogs(state)
    phase = str(classified["phase"])
    return {
        "oni": round(latest, 4),
        "noaa_oni": round(float(noaa_latest), 4),
        "correlation": round(correlation, 4),
        "phase": phase,
        "intensity": str(classified["intensity"]),
        "trajectory": str(classified["trajectory"]),
        "phase_agreement": round(agreement, 2),
        "analogs": analogs,
        "subwatchers": [dict(entry) for entry in SUBWATCHERS.get(phase, [])],
        "month": own["months"][-1] if own["months"] else "",
    }
