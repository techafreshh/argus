"""El Vigia ONI engine: own Nino3.4 ONI plus the NOAA validation rail."""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path

EL_NINO_THRESHOLD = 0.5
LA_NINA_THRESHOLD = -0.5

CLIMATOLOGY_START_YEAR = 1991
CLIMATOLOGY_END_YEAR = 2020
DEFAULT_START = "1982-01"

PHASE_EL_NINO = "El Nino"
PHASE_LA_NINA = "La Nina"
PHASE_NEUTRAL = "Neutral"


def _parse_month(label: str) -> tuple[int, int]:
    text = str(label).strip()[:7]
    year, month = int(text[:4]), int(text[5:7])
    if not 1 <= month <= 12:
        raise ValueError(f"bad month label: {label!r}")
    return year, month


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + delta
    return total // 12, total % 12 + 1


def _month_label(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _coerce_value(row: object) -> float | None:
    if isinstance(row, bool):
        return None
    if isinstance(row, (int, float)):
        value = float(row)
        return None if math.isnan(value) else value
    if isinstance(row, dict):
        for key in ("sst", "value", "temp", "temperature", "oni", "noaa_oni"):
            if (
                key in row
                and isinstance(row[key], (int, float))
                and not isinstance(row[key], bool)
            ):
                value = float(row[key])  # type: ignore[arg-type]
                return None if math.isnan(value) else value
        return None
    if isinstance(row, (list, tuple)):
        for item in row:
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                value = float(item)
                return None if math.isnan(value) else value
        return None
    return None


def _coerce_month(row: object) -> str | None:
    if isinstance(row, dict):
        for key in ("month", "date", "time"):
            if key in row and isinstance(row[key], str):
                try:
                    year, month = _parse_month(row[key])
                    return _month_label(year, month)
                except (ValueError, IndexError):
                    continue
        if "year" in row:
            try:
                year = int(row["year"])  # type: ignore[arg-type]
                month = int(row.get("month_num", row.get("mon", row.get("month", 1))))  # type: ignore[arg-type]
                if 1 <= month <= 12:
                    return _month_label(year, month)
            except (TypeError, ValueError):
                pass
        return None
    if isinstance(row, (list, tuple)) and len(row) >= 2:
        for item in row:
            if isinstance(item, str):
                try:
                    year, month = _parse_month(item)
                    return _month_label(year, month)
                except (ValueError, IndexError):
                    continue
    return None


def _normalize_series(
    series: object, start: str = DEFAULT_START
) -> tuple[list[str], list[float | None]]:
    if isinstance(series, dict):
        raise TypeError("compute_oni expects a sequence of rows, not a single dict")
    try:
        rows = list(series)  # type: ignore[arg-type]
    except TypeError:
        raise TypeError(
            "compute_oni expects a sequence of monthly SST values"
        ) from None
    if not rows:
        raise ValueError("compute_oni needs at least one monthly value")
    start_year, start_month = _parse_month(start)
    months: list[str] = []
    values: list[float | None] = []
    cursor_year, cursor_month = start_year, start_month
    for row in rows:
        label = _coerce_month(row)
        if label is None:
            label = _month_label(cursor_year, cursor_month)
        months.append(label)
        values.append(_coerce_value(row))
        year, month = _parse_month(label)
        cursor_year, cursor_month = _add_months(year, month, 1)
    return months, values


def classify_phase(oni_value: float | None) -> str:
    """CPC-style phase on a single ONI value (None is Neutral)."""
    if oni_value is None or math.isnan(oni_value):
        return PHASE_NEUTRAL
    if oni_value >= EL_NINO_THRESHOLD:
        return PHASE_EL_NINO
    if oni_value <= LA_NINA_THRESHOLD:
        return PHASE_LA_NINA
    return PHASE_NEUTRAL


def classify_intensity(oni_value: float | None) -> str:
    """CPC-style strength bucket on a single ONI value."""
    if oni_value is None or math.isnan(oni_value):
        return PHASE_NEUTRAL
    magnitude = abs(oni_value)
    if magnitude < EL_NINO_THRESHOLD:
        return PHASE_NEUTRAL
    if magnitude < 1.0:
        return "Weak"
    if magnitude < 1.5:
        return "Moderate"
    if magnitude < 2.0:
        return "Strong"
    return "Very strong"


def classify_trajectory(recent_oni: list[float | None]) -> str:
    """Warming/Cooling/Steady from the slope over recent ONI values."""
    clean = [v for v in recent_oni if v is not None and not math.isnan(v)][-6:]
    if len(clean) < 2:
        return "Steady"
    slope = clean[-1] - clean[0]
    if slope > 0.2:
        return "Warming"
    if slope < -0.2:
        return "Cooling"
    return "Steady"


def pearson_corr(xs: list[float | None], ys: list[float | None]) -> float:
    """Pearson r over pairwise-complete entries; never None or NaN."""
    pairs = [
        (x, y)
        for x, y in zip(xs, ys)
        if (x is not None and y is not None and not math.isnan(x) and not math.isnan(y))
    ]
    if len(pairs) < 2:
        return 0.0
    n = len(pairs)
    mean_x = sum(p[0] for p in pairs) / n
    mean_y = sum(p[1] for p in pairs) / n
    cov = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pairs)
    var_x = sum((p[0] - mean_x) ** 2 for p in pairs)
    var_y = sum((p[1] - mean_y) ** 2 for p in pairs)
    if var_x <= 0.0 or var_y <= 0.0:
        identical = all(p[0] == p[1] for p in pairs)
        return 1.0 if identical else 0.0
    return cov / (var_x**0.5 * var_y**0.5)


def phase_agreement_pct(own: list[float | None], ref: list[float | None]) -> float:
    """Share (0-100) of pairwise-complete months with matching phase."""
    pairs = [
        (a, b)
        for a, b in zip(own, ref)
        if (a is not None and b is not None and not math.isnan(a) and not math.isnan(b))
    ]
    if not pairs:
        return 0.0
    hits = sum(1 for a, b in pairs if classify_phase(a) == classify_phase(b))
    return 100.0 * hits / len(pairs)


def validate_against_noaa(
    own_oni: list[float | None], noaa_oni: list[float | None]
) -> dict:
    """Validation rail: correlation and phase agreement vs NOAA."""
    correlation = pearson_corr(own_oni, noaa_oni)
    agreement = phase_agreement_pct(own_oni, noaa_oni)
    n = sum(
        1
        for a, b in zip(own_oni, noaa_oni)
        if (a is not None and b is not None and not math.isnan(a) and not math.isnan(b))
    )
    return {"correlation": correlation, "phase_agreement_pct": agreement, "n": n}


def compute_oni(series: object, start: str = DEFAULT_START) -> dict:
    """Build 1991-2020 climatology, monthly anomalies, trailing 3-month ONI.

    Accepts bare monthly-SST floats (contiguous from ``start``) or
    dict/tuple rows carrying their own month labels.
    """
    months, values = _normalize_series(series, start=start)
    buckets: dict[int, list[float]] = {}
    for label, value in zip(months, values):
        if value is None:
            continue
        year, month = _parse_month(label)
        if CLIMATOLOGY_START_YEAR <= year <= CLIMATOLOGY_END_YEAR:
            buckets.setdefault(month, []).append(value)
    overall = [v for v in values if v is not None]
    fallback = sum(overall) / len(overall) if overall else 0.0
    climatology = {
        month: (sum(vals) / len(vals) if vals else fallback)
        for month, vals in ((m, buckets.get(m, [])) for m in range(1, 13))
    }
    anomaly: list[float | None] = []
    for label, value in zip(months, values):
        if value is None:
            anomaly.append(None)
            continue
        _, month = _parse_month(label)
        anomaly.append(value - climatology[month])
    oni: list[float | None] = []
    for i, _ in enumerate(anomaly):
        window = anomaly[max(0, i - 2) : i + 1]
        if len(window) < 3 or any(v is None for v in window):
            oni.append(None)
        else:
            oni.append(sum(window) / 3.0)  # type: ignore[arg-type]
    latest_idx = next(
        (i for i in range(len(oni) - 1, -1, -1) if oni[i] is not None), None
    )
    latest = oni[latest_idx] if latest_idx is not None else None
    return {
        "oni": oni,
        "anomaly": anomaly,
        "climatology": climatology,
        "months": months,
        "phase": classify_phase(latest),
        "intensity": classify_intensity(latest),
        "trajectory": classify_trajectory(oni),
    }


def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        dirs.append(Path(override))
    dirs.append(Path(__file__).resolve().parents[3] / "fixtures")
    return dirs


def _find_noaa_csv() -> Path | None:
    for directory in _candidate_dirs():
        candidate = directory / "noaa_oni.csv"
        if candidate.is_file():
            return candidate
    return None


def load_noaa_table(path: str | Path | None = None) -> list[dict]:
    """Load the bundled NOAA ONI snapshot (tolerates `#` comment lines)."""
    resolved = Path(path) if path is not None else _find_noaa_csv()
    if resolved is None or not resolved.is_file():
        raise FileNotFoundError("noaa_oni.csv fixture not found")
    rows: list[dict] = []
    with resolved.open(encoding="utf-8") as fh:
        filtered = (line for line in fh if not line.lstrip().startswith("#"))
        for record in csv.DictReader(filtered):
            try:
                rows.append(
                    {
                        "month": str(record["month"]).strip(),
                        "sst": float(record["sst"]),
                        "noaa_oni": float(record["noaa_oni"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
    if not rows:
        raise ValueError("noaa_oni.csv fixture holds no data rows")
    return rows
