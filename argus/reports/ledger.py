"""Hit/miss precision ledger over the existing ``predictions`` table."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from argus.store.db import get_connection, init_db

_OUTCOMES = ("hit", "miss")


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def log_prediction(
    watch_id: str,
    expectation: dict,
    expires_at: str | None = None,
) -> dict:
    """Insert an open prediction row and return it as a dict."""
    init_db()
    now = _utcnow()
    expiry = expires_at or (datetime.now(UTC) + timedelta(days=30)).isoformat()
    row = {
        "id": uuid.uuid4().hex,
        "watch_id": str(watch_id),
        "analog_json": None,
        "expectation_json": json.dumps(dict(expectation or {}), sort_keys=True, default=str),
        "expectation": dict(expectation or {}),
        "outcome": None,
        "status": "open",
        "expires_at": expiry,
        "evaluated_at": None,
        "created_at": now,
    }
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO predictions "
            "(id, watch_id, analog_json, expectation_json, outcome, status, "
            "expires_at, evaluated_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                row["id"],
                row["watch_id"],
                row["analog_json"],
                row["expectation_json"],
                row["outcome"],
                row["status"],
                row["expires_at"],
                row["evaluated_at"],
                row["created_at"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return row


def _prediction_dict(row: Any) -> dict:
    try:
        expectation: Any = json.loads(row["expectation_json"] or "{}")
    except (TypeError, ValueError):
        expectation = {}
    return {
        "id": row["id"],
        "watch_id": row["watch_id"],
        "expectation": expectation,
        "expectation_json": row["expectation_json"],
        "outcome": row["outcome"],
        "status": row["status"],
        "expires_at": row["expires_at"],
        "evaluated_at": row["evaluated_at"],
        "created_at": row["created_at"],
    }


def evaluate_prediction(pred_id: str, outcome: str) -> dict:
    """Grade an open prediction as ``hit`` or ``miss``; else ValueError."""
    if outcome not in _OUTCOMES:
        raise ValueError(f"outcome must be one of {list(_OUTCOMES)}")
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, watch_id, expectation_json, outcome, status,"
            " expires_at, evaluated_at, created_at FROM predictions WHERE id = ?;",
            (pred_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"prediction not found: {pred_id}")
        now = _utcnow()
        conn.execute(
            "UPDATE predictions SET outcome = ?, status = 'evaluated',"
            " evaluated_at = ? WHERE id = ?;",
            (outcome, now, pred_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT id, watch_id, expectation_json, outcome, status,"
            " expires_at, evaluated_at, created_at FROM predictions WHERE id = ?;",
            (pred_id,),
        ).fetchone()
    finally:
        conn.close()
    return _prediction_dict(updated)


def get_precision() -> dict:
    """Return {"hits", "misses", "total", "precision"} over evaluated rows."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute("SELECT outcome FROM predictions WHERE outcome IS NOT NULL;").fetchall()
    finally:
        conn.close()
    hits = sum(1 for row in rows if str(row["outcome"]) == "hit")
    misses = sum(1 for row in rows if str(row["outcome"]) == "miss")
    total = hits + misses
    precision = (hits / total) if total else 0.0
    return {"hits": hits, "misses": misses, "total": total, "precision": precision}
