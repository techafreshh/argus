"""Queued-alert approval queue: list, approve/reject (reports live in routes_reports)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from argus.reports.ledger import log_prediction
from argus.reports.render import file_report
from argus.store.db import get_connection, init_db

router = APIRouter()


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _alert_dict(row: Any) -> dict:
    try:
        evidence = json.loads(row["evidence_json"] or "{}")
    except (TypeError, ValueError):
        evidence = {}
    eye = str(evidence.get("eye", "")) if isinstance(evidence, dict) else ""
    return {
        "id": row["id"],
        "watch_id": row["watch_id"],
        "report_id": row["report_id"],
        "title": row["title"],
        "confidence": float(row["confidence"]),
        "status": row["status"],
        "eye": eye,
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


def _receipts_for_watch(watch_id: str) -> list[dict]:
    """Load a watch's receipts in API shape (oldest-first), additive params/tokens."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, watch_id, acquisition_id, tool, params_json, source_url,"
            " data_hash, plot_path, token_usage, created_at FROM receipts"
            " WHERE watch_id = ? ORDER BY created_at, rowid;",
            (watch_id,),
        ).fetchall()
    finally:
        conn.close()
    out: list[dict] = []
    for row in rows:
        try:
            params = json.loads(row["params_json"] or "{}")
        except (TypeError, ValueError):
            params = {}
        if not isinstance(params, dict):
            params = {}
        try:
            tokens = int(row["token_usage"])
        except (TypeError, ValueError):
            tokens = 0
        out.append(
            {
                "id": row["id"],
                "watch_id": row["watch_id"],
                "acquisition_id": row["acquisition_id"],
                "tool": row["tool"],
                "params_json": row["params_json"],
                "params": params,
                "source_url": row["source_url"],
                "data_hash": row["data_hash"],
                "plot_path": row["plot_path"],
                "token_usage": int(row["token_usage"]),
                "tokens": tokens,
                "created_at": row["created_at"],
            }
        )
    return out


def _file_report_for_alert(alert: dict) -> None:
    """Render the graded card, upsert the reports row, and log a prediction."""
    receipts = _receipts_for_watch(str(alert["watch_id"]))
    card = file_report(alert, receipts)
    data_hash = hashlib.sha256(
        json.dumps(card, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    card["data_hash"] = data_hash
    now = _utcnow()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO reports "
            "(id, watch_id, alert_id, headline, card_json, data_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);",
            (
                str(alert["id"]),
                str(alert["watch_id"]),
                str(alert["id"]),
                str(card["headline"]),
                json.dumps(card, sort_keys=True, default=str),
                data_hash,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    evidence = alert.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
    try:
        z_score = float(evidence.get("z_score", 0.0))
    except (TypeError, ValueError):
        z_score = 0.0
    try:
        log_prediction(
            str(alert["watch_id"]),
            {
                "alert_id": str(alert["id"]),
                "z_score": z_score,
                "confidence": float(alert.get("confidence", 0.0)),
            },
        )
    except Exception:  # noqa: BLE001, S110 - ledger must never break approve
        pass


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
    alert = _alert_dict(row)
    alert["status"] = "approved"
    alert["report_id"] = alert_id
    alert["decided_at"] = now
    alert["alert_id"] = alert["id"]
    _file_report_for_alert(alert)
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

