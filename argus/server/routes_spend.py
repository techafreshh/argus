"""Read-only spend ledger route: GET /api/spend."""

from fastapi import APIRouter

from argus.orchestrator.meta_client import get_spend

router = APIRouter()


@router.get("/api/spend")
def read_spend() -> dict:
    """Return {"total_credits": float, "calls": [...]} (200, even when empty)."""
    return get_spend()
