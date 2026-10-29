"""Verification endpoint: cross-check imagery/news/context before queueing."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from argus.store.db import get_connection, init_db
from argus.verify.crosscheck import cross_check

router = APIRouter()


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _watch_exists(watch_id: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM watches WHERE id = ?;", (watch_id,)
        ).fetchone()
    finally:
        conn.close()
    return row is not None


def _ensure_watch(watch_id: str | None, title: str) -> str:
    if watch_id and _watch_exists(watch_id):
        return watch_id
    new_id = watch_id or uuid.uuid4().hex
    if _watch_exists(new_id):
        return new_id
    now = _utcnow()
    name = (title or "verification").strip() or "verification"
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO watches "
            "(id, name, region_json, question, template, cadence, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                new_id,
                name,
                json.dumps({"region": "test-aoi"}, sort_keys=True),
                name,
                "verification",
                "daily",
                "active",
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return new_id


def _insert_receipt(
    watch_id: str, params: dict, source_url: str, payload: dict
) -> dict:
    receipt = {
        "id": uuid.uuid4().hex,
        "watch_id": watch_id,
        "acquisition_id": None,
        "tool": "cross_check",
        "params_json": json.dumps(params, sort_keys=True, default=str),
        "source_url": source_url,
        "data_hash": hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "plot_path": "",
        "token_usage": 0,
        "created_at": _utcnow(),
    }
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO receipts "
            "(id, watch_id, acquisition_id, tool, params_json, source_url, "
            "data_hash, plot_path, token_usage, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                receipt["id"],
                receipt["watch_id"],
                receipt["acquisition_id"],
                receipt["tool"],
                receipt["params_json"],
                receipt["source_url"],
                receipt["data_hash"],
                receipt["plot_path"],
                receipt["token_usage"],
                receipt["created_at"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return receipt


def _insert_alert(
    watch_id: str, title: str, confidence: float, evidence: dict
) -> dict:
    alert = {
        "id": uuid.uuid4().hex,
        "watch_id": watch_id,
        "report_id": None,
        "title": title,
        "confidence": confidence,
        "status": "queued",
        "evidence_json": json.dumps(evidence, sort_keys=True, default=str),
        "created_at": _utcnow(),
        "decided_at": None,
    }
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO alerts "
            "(id, watch_id, report_id, title, confidence, status, "
            "evidence_json, created_at, decided_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                alert["id"],
                alert["watch_id"],
                alert["report_id"],
                alert["title"],
                alert["confidence"],
                alert["status"],
                alert["evidence_json"],
                alert["created_at"],
                alert["decided_at"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return alert


def _verify(watch_id_or_none: str | None, body: Any) -> dict:
    payload = body if isinstance(body, dict) else {}
    imagery = payload.get("imagery", {})
    news = payload.get("news", {})
    context = payload.get("context", {})
    if imagery is None:
        imagery = {}
    if news is None:
        news = {}
    if context is None:
        context = {}
    title = payload.get("title", "verification")
    if not isinstance(title, str) or not title.strip():
        title = "verification"
    requested_watch = payload.get("watch_id", watch_id_or_none)
    if not isinstance(requested_watch, str):
        requested_watch = watch_id_or_none
    result = cross_check(imagery, news, context)
    confidence = float(result["confidence"])
    decision = str(result["decision"])
    if decision == "queued":
        watch_id = _ensure_watch(requested_watch, title)
        evidence = {
            "imagery": imagery,
            "news": news,
            "context": context,
            "scores": result["scores"],
            "sources_present": result["sources_present"],
        }
        alert = _insert_alert(watch_id, title, confidence, evidence)
        _insert_receipt(
            watch_id,
            {"watch_id": watch_id, "decision": decision},
            "",
            result,
        )
        return {
            "ok": True,
            "confidence": confidence,
            "decision": "queued",
            "status": "queued",
            "watch_id": watch_id,
            "alert": {
                "id": alert["id"],
                "watch_id": watch_id,
                "title": title,
                "confidence": confidence,
                "status": "queued",
            },
            "alert_id": alert["id"],
            "alert_status": "queued",
            "evidence": evidence,
            "scores": result["scores"],
            "sources_present": result["sources_present"],
            "agreement": result["agreement"],
        }
    watch_id = requested_watch if requested_watch else None
    if watch_id and not _watch_exists(watch_id):
        watch_id = _ensure_watch(requested_watch, title)
    elif not watch_id:
        watch_id = _ensure_watch(None, title)
    _insert_receipt(
        str(watch_id),
        {"watch_id": str(watch_id), "decision": decision},
        "",
        result,
    )
    return {
        "ok": True,
        "confidence": confidence,
        "decision": "ambiguity",
        "status": "ambiguity",
        "watch_id": watch_id,
        "alert": None,
        "alert_id": None,
        "alert_status": "ambiguity",
        "card": {
            "title": title,
            "confidence": confidence,
            "explanation": (
                "Independent sources do not agree; "
                "manual review required before queueing."
            ),
            "scores": result["scores"],
            "sources_present": result["sources_present"],
        },
        "evidence": result["evidence"],
        "scores": result["scores"],
        "sources_present": result["sources_present"],
        "agreement": result["agreement"],
    }


@router.post("/api/verify")
async def verify(request: Request) -> dict:
    """Cross-check posted evidence; queue an alert only on multi-source agreement."""
    init_db()
    try:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 - malformed body verifies as empty
            body = {}
        return _verify(None, body)
    except Exception as exc:  # noqa: BLE001 - verify never 500s
        return {"ok": False, "error": str(exc) or "verify failed"}


@router.post("/api/watches/{watch_id}/verify")
async def verify_watch(watch_id: str, request: Request) -> dict:
    """Alias verify scoped to a watch; 404 when the watch is unknown."""
    init_db()
    if not _watch_exists(watch_id):
        raise HTTPException(status_code=404, detail="watch not found")
    try:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 - malformed body verifies as empty
            body = {}
        if isinstance(body, dict):
            body = dict(body)
            body.setdefault("watch_id", watch_id)
        else:
            body = {"watch_id": watch_id}
        return _verify(watch_id, body)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - verify never 500s
        return {"ok": False, "error": str(exc) or "verify failed"}
