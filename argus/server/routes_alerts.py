"""Queued-alert approval queue: list, approve/reject, approved-alert reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from argus.store.db import get_connection, init_db

router = APIRouter()


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _alert_dict(row: Any) -> dict:
    try:
        evidence = json.loads(row["evidence_json"] or "{}")
    except (TypeError, ValueError):
        evidence = {}
    return {
        "id": row["id"],
        "watch_id": row["watch_id"],
        "report_id": row["report_id"],
        "title": row["title"],
        "confidence": float(row["confidence"]),
        "status": row["status"],
        "evidence": evidence,
        "created_at": row["created_at"],
        "decided_at": row["decided_at"],
    }


def _get_alert_or_404(alert_id: str) -> Any:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, watch_id, report_id, title, confidence, status,"
            " evidence_json, created_at, decided_at FROM alerts WHERE id = ?;",
            (alert_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return row


@router.get("/api/alerts")
def list_alerts() -> list[dict]:
    """List queued/decided alerts newest-first."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, watch_id, report_id, title, confidence, status,"
            " evidence_json, created_at, decided_at FROM alerts"
            " ORDER BY created_at DESC, rowid DESC;"
        ).fetchall()
    finally:
        conn.close()
    return [_alert_dict(row) for row in rows]


@router.post("/api/alerts/{alert_id}/approve")
def approve_alert(alert_id: str) -> dict:
    """Approve a queued alert; it becomes its own report (report_id = alert id)."""
    init_db()
    row = _get_alert_or_404(alert_id)
    if str(row["status"]) != "queued":
        raise HTTPException(status_code=409, detail="alert already decided")
    now = _utcnow()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE alerts SET status = 'approved', decided_at = ?, report_id = ?"
            " WHERE id = ?;",
            (now, alert_id, alert_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "id": alert_id, "status": "approved", "report_id": alert_id}


@router.post("/api/alerts/{alert_id}/reject")
def reject_alert(alert_id: str) -> dict:
    """Reject a queued alert; rejected alerts never become reports."""
    init_db()
    row = _get_alert_or_404(alert_id)
    if str(row["status"]) != "queued":
        raise HTTPException(status_code=409, detail="alert already decided")
    now = _utcnow()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE alerts SET status = 'rejected', decided_at = ? WHERE id = ?;",
            (now, alert_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "id": alert_id, "status": "rejected"}


@router.get("/api/reports/{report_id}")
def get_report(report_id: str) -> dict:
    """Render an approved alert as its report; 404 unless approved."""
    init_db()
    row = _get_alert_or_404(report_id)
    if str(row["status"]) != "approved":
        raise HTTPException(status_code=404, detail="report not found")
    body = _alert_dict(row)
    body["alert_id"] = body["id"]
    return body
