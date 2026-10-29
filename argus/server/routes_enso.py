"""Read-only ENSO status: GET /api/enso/status."""

from fastapi import APIRouter

from argus.eval.oni import current_snapshot

router = APIRouter()


@router.get("/api/enso/status")
def enso_status() -> dict:
    """Return own ONI, NOAA comparison, phase, analogs, sub-watchers (200)."""
    return current_snapshot()
