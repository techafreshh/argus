"""Eval honesty gates: POST /api/eval/run + GET /api/eval/status.

The POST handler executes the synchronous fixture-driven ``run_eval()``
(no threads, no persistence) and stores the result in a module-level
dict keyed by ``run_id``. ``GET /api/eval/status`` without a ``run_id``
keeps the legacy pending shape (200, even when empty); with a known
``run_id`` it returns the stored gate result; unknown ids 404. The
routes never 500: malformed queries fall back to empty-safe JSON.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from argus.eval.probes import run_eval
from argus.orchestrator.meta_client import spend_total
from argus.reports.ledger import get_precision
from argus.store.db import init_db

router = APIRouter()

_RUNS: dict[str, dict] = {}


def _legacy_status() -> dict:
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


@router.post("/api/eval/run")
def run_eval_route() -> dict:
    """Execute all honesty-gate probes synchronously; return run_id."""
    init_db()
    try:
        result = run_eval()
    except Exception as exc:  # noqa: BLE001 - eval run never 500s
        return {"ok": False, "error": str(exc) or "eval run failed"}
    _RUNS[str(result["run_id"])] = result
    return {"run_id": result["run_id"], "status": "complete"}


@router.get("/api/eval/status")
def eval_status(request: Request) -> Any:
    """Return the stored gate result for ?run_id=, else the legacy shape."""
    init_db()
    try:
        run_id = request.query_params.get("run_id", "")
    except Exception:  # noqa: BLE001 - malformed query falls back safely
        run_id = ""
    if not run_id:
        return _legacy_status()
    result = _RUNS.get(str(run_id))
    if result is None:
        raise HTTPException(status_code=404, detail="eval run not found")
    return result
