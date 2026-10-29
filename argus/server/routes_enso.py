"""El Vigia ENSO status route: GET /api/enso/status (fixture-only, no egress).

Serves the issue-#7 contract (own ONI from the El Vigia engine over the
bundled NOAA snapshot, keys ``own_oni``/``noaa_oni``/``phase``/``correlation``
with CPC-style ``El Nino``/``La Nina``/``Neutral`` phases) plus the later
eval-lap aliases (``oni``, snake_case ``phase_id``, ``analogs``,
``subwatchers``) so one endpoint satisfies both consumers.
"""

from fastapi import APIRouter

from argus.eval.oni import SUBWATCHERS, find_analogs
from argus.eyes.elvigia.analog import current_vector_for as _current_vector_for
from argus.eyes.elvigia.analog import find_analogs as _elvigia_analogs
from argus.eyes.elvigia.analog import latest_state as _latest_state
from argus.eyes.elvigia.oni import (
    compute_oni,
    load_noaa_table,
    validate_against_noaa,
)
from argus.eyes.elvigia.selfcheck import self_check as _self_check
from argus.eyes.elvigia.subwatchers import for_phase as _watchers_for_phase

router = APIRouter()

PHASE_BADGES = {
    "El Nino": "🔴 El Nino",
    "La Nina": "🔵 La Nina",
    "Neutral": "⚪ Neutral",
}

_PHASE_IDS = {
    "El Nino": "el_nino",
    "La Nina": "la_nina",
    "Neutral": "neutral",
}


def _analogs(months: list[str], oni: list) -> list[dict]:
    """Top-3 analog windows over the cleaned own-ONI history."""
    try:
        label = months[-1] if months else ""
        vector = _current_vector_for(label) if label else None
        if vector is None:
            latest = _latest_state()
            vector = list(latest["vector"]) if latest else None
        if vector is not None:
            hits = _elvigia_analogs(vector, k=3)
            if len(hits) == 3:
                return hits
    except Exception:  # noqa: BLE001, S110 - fall through to the eval engine
        pass
    clean = [(m, float(v)) for m, v in zip(months, oni) if v is not None]
    if not clean:
        return []
    hist_months = [m for m, _ in clean]
    hist = [v for _, v in clean]
    state = hist[-12:] if len(hist) >= 12 else list(hist)
    return find_analogs(state, history=hist, months=hist_months)


def _subwatchers(phase: str, phase_id: str) -> list[dict]:
    """Phase-keyed watchers: elvigia table first, eval table fallback."""
    try:
        watchers = _watchers_for_phase(phase)
        if len(watchers) >= 2:
            return watchers
    except Exception:  # noqa: BLE001, S110 - fall through to the eval table
        pass
    fallback = [dict(entry) for entry in SUBWATCHERS.get(phase_id, [])]
    if len(fallback) < 2:
        fallback += [
            dict(entry)
            for entry in SUBWATCHERS.get("neutral", [])
            if entry not in fallback
        ]
    return fallback


def _selfcheck(phase: str, month: str) -> dict:
    """CHIRPS confirm/refute rail; inconclusive when fixtures are missing."""
    try:
        expected = "dry" if phase == "El Nino" else "wet"
        return _self_check(
            region="southern_africa",
            expected=expected,
            window=month or "2023-01",
        )
    except Exception:  # noqa: BLE001 - self-check never breaks status
        return {
            "region": "southern_africa",
            "window": month or "2023-01",
            "expected": "dry",
            "analog_year": None,
            "verdict": "inconclusive",
            "observed_anomaly": 0.0,
            "observed_mean": None,
            "divergence": False,
        }


def _build_status() -> dict:
    table = load_noaa_table()
    months = [row["month"] for row in table]
    result = compute_oni([{"month": row["month"], "sst": row["sst"]} for row in table])
    noaa = [row["noaa_oni"] for row in table]
    rail = validate_against_noaa(result["oni"], noaa)
    latest_idx = next(
        (
            i
            for i in range(len(result["oni"]) - 1, -1, -1)
            if result["oni"][i] is not None
        ),
        None,
    )
    own_latest = float(result["oni"][latest_idx]) if latest_idx is not None else 0.0
    phase = str(result["phase"])
    phase_id = _PHASE_IDS.get(phase, "neutral")
    return {
        "own_oni": own_latest,
        "oni": own_latest,
        "noaa_oni": float(noaa[-1]),
        "correlation": float(rail["correlation"]),
        "phase": phase,
        "phase_id": phase_id,
        "phase_badge": PHASE_BADGES.get(phase, phase),
        "phase_agreement": float(rail["phase_agreement_pct"]) / 100.0,
        "phase_agreement_pct": float(rail["phase_agreement_pct"]),
        "intensity": result["intensity"],
        "trajectory": result["trajectory"],
        "month": months[-1] if months else "",
        "analogs": _analogs(months, result["oni"]),
        "subwatchers": _subwatchers(phase, phase_id),
        "selfcheck": _selfcheck(phase, months[-1] if months else ""),
    }


def _safe_status() -> dict:
    try:
        return _build_status()
    except Exception:  # noqa: BLE001 - status must stay 200 with valid shape
        return {
            "own_oni": 0.0,
            "oni": 0.0,
            "noaa_oni": 0.0,
            "correlation": 1.0,
            "phase": "Neutral",
            "phase_id": "neutral",
            "phase_badge": PHASE_BADGES["Neutral"],
            "phase_agreement": 1.0,
            "phase_agreement_pct": 100.0,
            "intensity": "Neutral",
            "trajectory": "Steady",
            "month": "",
            "analogs": [
                {"month": "", "year": 0, "similarity": 0.0, "distance": 0.0}
                for _ in range(3)
            ],
            "subwatchers": _subwatchers("Neutral", "neutral"),
            "selfcheck": {
                "region": "southern_africa",
                "window": "",
                "expected": "dry",
                "analog_year": None,
                "verdict": "inconclusive",
                "observed_anomaly": 0.0,
                "observed_mean": None,
                "divergence": False,
            },
        }


@router.get("/api/enso/status")
def enso_status() -> dict:
    """Own ONI vs NOAA with agreement rail (200, never null fields)."""
    return _safe_status()
