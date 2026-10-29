"""Filed graded report cards: serves the stable artifact written at approve time."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from argus.reports.render import file_report
from argus.store.db import get_connection, init_db

router = APIRouter()


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


def _receipt_dict(row: Any) -> dict:
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
    return {
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


def _load_receipts(watch_id: str) -> list[dict]:
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
    return [_receipt_dict(row) for row in rows]


@router.get("/api/reports/{report_id}")
def get_report(report_id: str) -> dict:
    """Return the filed report card; 404 unless the alert is approved."""
    init_db()
    conn = get_connection()
    try:
        alert_row = conn.execute(
            "SELECT id, watch_id, report_id, title, confidence, status,"
            " evidence_json, created_at, decided_at FROM alerts WHERE id = ?;",
            (report_id,),
        ).fetchone()
    finally:
        conn.close()
    if alert_row is None or str(alert_row["status"]) != "approved":
        raise HTTPException(status_code=404, detail="report not found")
    conn = get_connection()
    try:
        report_row = conn.execute(
            "SELECT id, watch_id, alert_id, headline, card_json, data_hash,"
            " created_at FROM reports WHERE id = ?;",
            (report_id,),
        ).fetchone()
    finally:
        conn.close()
    if report_row is not None:
        try:
            card = json.loads(report_row["card_json"] or "{}")
        except (TypeError, ValueError):
            card = {}
        if isinstance(card, dict) and card:
            return _with_live_linkage(card, alert_row)
    # Fallback for alerts approved before the reports table existed.
    alert = _alert_dict(alert_row)
    alert["alert_id"] = alert["id"]
    card = file_report(alert, _load_receipts(str(alert_row["watch_id"])))
    return _with_live_linkage(card, alert_row)


def _with_live_linkage(card: dict, alert_row: Any) -> dict:
    """Overlay live decide-state onto the stable filed card (never stored)."""
    alert = _alert_dict(alert_row)
    card["status"] = alert["status"]
    card["title"] = alert["title"]
    card["report_id"] = alert["report_id"]
    card["evidence"] = alert["evidence"]
    card["decided_at"] = alert["decided_at"]
    return card
