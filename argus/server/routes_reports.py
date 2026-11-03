"""Filed graded report cards: serves the stable artifact written at approve time."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from argus.cookbook import recipe_for
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


@router.get("/api/reports/{report_id}/trace")
def get_report_trace(report_id: str) -> dict:
    """The decision log: how the agent got from question to graded report.

    Assembles the routed recipe, the watch the run created, every receipt
    (tool calls with params/hashes/sources), the approval decision, the
    webhook deliveries, and the hit/miss ledger entry — in one replayable
    timeline.
    """
    init_db()
    conn = get_connection()
    try:
        alert_row = conn.execute(
            "SELECT id, watch_id, report_id, title, confidence, status,"
            " evidence_json, created_at, decided_at FROM alerts WHERE id = ?;",
            (report_id,),
        ).fetchone()
        if alert_row is None or str(alert_row["status"]) != "approved":
            raise HTTPException(status_code=404, detail="report not found")
        watch_row = conn.execute(
            "SELECT id, name, region_json, question, template, cadence, status,"
            " created_at FROM watches WHERE id = ?;",
            (str(alert_row["watch_id"]),),
        ).fetchone()
        receipts = [
            _receipt_dict(row)
            for row in conn.execute(
                "SELECT id, watch_id, acquisition_id, tool, params_json,"
                " source_url, data_hash, plot_path, token_usage, created_at"
                " FROM receipts WHERE watch_id = ? ORDER BY created_at, rowid;",
                (str(alert_row["watch_id"]),),
            ).fetchall()
        ]
        deliveries = [
            {key: row[key] for key in row.keys()}  # noqa: SIM118 - sqlite3.Row
            for row in conn.execute(
                "SELECT id, alert_id, channel_id, status, http_status, error,"
                " attempts, created_at FROM deliveries WHERE alert_id = ?"
                " ORDER BY created_at, rowid;",
                (report_id,),
            ).fetchall()
        ]
        predictions = [
            {key: row[key] for key in row.keys()}  # noqa: SIM118 - sqlite3.Row
            for row in conn.execute(
                "SELECT * FROM predictions WHERE watch_id = ?"
                " ORDER BY created_at, rowid;",
                (str(alert_row["watch_id"]),),
            ).fetchall()
        ]
    finally:
        conn.close()

    watch = (
        {key: watch_row[key] for key in watch_row.keys()}  # noqa: SIM118 - sqlite3.Row
        if watch_row is not None
        else None
    )
    template = str((watch or {}).get("template", "")) if watch else ""
    recipe = recipe_for(template)
    if watch is not None and "region_json" in watch:
        try:
            watch["region"] = json.loads(watch.pop("region_json") or "{}")
        except (TypeError, ValueError):
            watch["region"] = {}
    return {
        "report_id": report_id,
        "route": {
            "template": template or None,
            "recipe_id": template if recipe else None,
            "recipe_title": str(recipe["title"]) if recipe else None,
            "recipe_blurb": str(recipe["blurb"]) if recipe else None,
            "question": (watch or {}).get("question") if watch else None,
        },
        "watch": watch,
        "alert": {
            "id": alert_row["id"],
            "title": alert_row["title"],
            "confidence": float(alert_row["confidence"]),
            "status": alert_row["status"],
            "evidence": json.loads(alert_row["evidence_json"] or "{}"),
            "created_at": alert_row["created_at"],
            "decided_at": alert_row["decided_at"],
        },
        "steps": receipts,
        "deliveries": deliveries,
        "predictions": predictions,
    }
