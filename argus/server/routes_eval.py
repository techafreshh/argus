"""Eval probe status route: GET /api/eval/status."""

from fastapi import APIRouter

from argus.orchestrator.meta_client import spend_total
from argus.reports.ledger import get_precision
from argus.store.db import init_db

router = APIRouter()


@router.get("/api/eval/status")
def eval_status() -> dict:
    """Return ledger precision plus spend total and a probe stub (200, even when empty)."""
    init_db()
    precision = get_precision()
    return {
        "hits": precision["hits"],
        "misses": precision["misses"],
        "total": precision["total"],
        "precision": precision["precision"],
        "total_credits": spend_total(),
        "probes": {
            "replay": [],
            "false_positive": [],
            "novel_question": [],
            "status": "pending",
        },
    }
