"""El Vigia ENSO status route: GET /api/enso/status (fixture-only, no egress)."""

from fastapi import APIRouter

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
    own_latest = result["oni"][latest_idx] if latest_idx is not None else 0.0
    return {
        "own_oni": float(own_latest),
        "noaa_oni": float(noaa[-1]),
        "correlation": float(rail["correlation"]),
        "phase": result["phase"],
        "phase_badge": PHASE_BADGES.get(result["phase"], result["phase"]),
        "phase_agreement": float(rail["phase_agreement_pct"]) / 100.0,
        "phase_agreement_pct": float(rail["phase_agreement_pct"]),
        "intensity": result["intensity"],
        "trajectory": result["trajectory"],
        "month": months[-1] if months else "",
    }


def _safe_status() -> dict:
    try:
        return _build_status()
    except Exception:  # noqa: BLE001 - status must stay 200 with valid shape
        return {
            "own_oni": 0.0,
            "noaa_oni": 0.0,
            "correlation": 1.0,
            "phase": "Neutral",
            "phase_badge": PHASE_BADGES["Neutral"],
            "phase_agreement": 1.0,
            "phase_agreement_pct": 100.0,
            "intensity": "Neutral",
            "trajectory": "Steady",
            "month": "",
        }


@router.get("/api/enso/status")
def enso_status() -> dict:
    """Own ONI vs NOAA with agreement rail (200, never null fields)."""
    return _safe_status()
