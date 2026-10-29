"""Queue graded fireline reports into the approval queue."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from argus.store.db import get_connection


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _insert_receipt(
    watch_id: str,
    tool: str,
    params: dict,
    source_url: str,
    payload: dict,
) -> dict:
    receipt = {
        "id": uuid.uuid4().hex,
        "watch_id": watch_id,
        "acquisition_id": None,
        "tool": tool,
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


def file_fire_alert(watch_id: str, result: dict, title: str) -> dict:
    """Insert modis/firms receipts plus a queued ``eye=fireline`` alert."""
    result = dict(result or {})
    region = str(result.get("region", "test-aoi"))
    window = str(result.get("window", "2024-01"))
    params = {"region": region, "window": window, "aoi": region}
    for tool in ("modis_burned", "firms"):
        _insert_receipt(
            watch_id,
            tool,
            params,
            str(result.get("before_url" if tool == "modis_burned" else "after_url", "") or ""),
            {k: result.get(k) for k in ("region", "window", "percentile", "hectares", "confidence")},
        )
    evidence: dict[str, Any] = {
        "eye": "fireline",
        "region": region,
        "window": window,
        "percentile": float(result.get("percentile", 0.0)),
        "baseline_years": int(result.get("baseline_years", 20)),
        "hectares": float(result.get("hectares", 0.0)),
        "confidence": float(result.get("confidence", 0.0)),
        "before_url": str(result.get("before_url", "") or ""),
        "after_url": str(result.get("after_url", "") or ""),
        "detections": int(result.get("detections", 0) or 0),
        "decision": str(result.get("decision", "queued")),
    }
    alert = {
        "id": uuid.uuid4().hex,
        "watch_id": watch_id,
        "report_id": None,
        "title": str(title),
        "confidence": float(result.get("confidence", 0.0)),
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
