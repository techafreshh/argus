"""El Vigia ENSO status route: GET /api/enso/status (fixture-only, no egress).

Serves the issue-#7 contract (own ONI from the El Vigia engine over the
bundled NOAA snapshot, keys ``own_oni``/``noaa_oni``/``phase``/``correlation``
with CPC-style ``El Nino``/``La Nina``/``Neutral`` phases) plus the later
eval-lap aliases (``oni``, snake_case ``phase_id``, ``analogs``,
``subwatchers``) so one endpoint satisfies both consumers.
"""

from fastapi import APIRouter

from argus.eval.oni import SUBWATCHERS, find_analogs
from argus.eyes.elvigia.oni import (
    compute_oni,
    load_noaa_table,
    validate_against_noaa,
)

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
    clean = [(m, float(v)) for m, v in zip(months, oni) if v is not None]
    if not clean:
        return []
    hist_months = [m for m, _ in clean]
    hist = [v for _, v in clean]
    state = hist[-12:] if len(hist) >= 12 else list(hist)
    return find_analogs(state, history=hist, months=hist_months)


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
        "subwatchers": [dict(entry) for entry in SUBWATCHERS.get(phase_id, [])],
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
            "subwatchers": [dict(entry) for entry in SUBWATCHERS.get("neutral", [])],
        }


@router.get("/api/enso/status")
def enso_status() -> dict:
    """Own ONI vs NOAA with agreement rail (200, never null fields)."""
    return _safe_status()
