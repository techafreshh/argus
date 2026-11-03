"""Operator notification channels: register, list, remove, test-fire (webhooks)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from argus.adapters import webhook_client
from argus.store.db import get_connection, init_db

router = APIRouter()


class ChannelIn(BaseModel):
    target: str
    secret: str = ""
    watch_id: str | None = None

    @field_validator("target", mode="before")
    @classmethod
    def _http_url(cls, value: object) -> str:
        target = str(value or "").strip()
        if not target.startswith(("http://", "https://")) or len(target) > 2048:
            raise ValueError("target must be an http(s) URL")
        return target

    @field_validator("secret", mode="before")
    @classmethod
    def _cap_secret(cls, value: object) -> str:
        return str(value or "")[:256]

    @field_validator("watch_id", mode="before")
    @classmethod
    def _empty_watch_is_global(cls, value: object) -> str | None:
        text = str(value or "").strip()
        return text or None


def _channel_dict(row) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "target": row["target"],
        "watch_id": row["watch_id"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@router.get("/api/channels")
def list_channels() -> list[dict]:
    """Registered channels, oldest first (never exposes the signing secret)."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, kind, target, watch_id, status, created_at FROM channels "
            "ORDER BY created_at, rowid;"
        ).fetchall()
    finally:
        conn.close()
    return [_channel_dict(row) for row in rows]


@router.post("/api/channels")
def create_channel(payload: ChannelIn) -> dict:
    """Register a webhook channel; watch_id omitted = global."""
    init_db()
    channel_id = uuid.uuid4().hex
    conn = get_connection()
    try:
        if payload.watch_id is not None:
            known = conn.execute(
                "SELECT 1 FROM watches WHERE id = ?;", (payload.watch_id,)
            ).fetchone()
            if known is None:
                raise HTTPException(status_code=404, detail="watch not found")
        conn.execute(
            "INSERT INTO channels (id, kind, target, secret, watch_id, status, created_at) "
            "VALUES (?, 'webhook', ?, ?, ?, 'active', datetime('now'));",
            (channel_id, payload.target, payload.secret, payload.watch_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, kind, target, watch_id, status, created_at FROM channels "
            "WHERE id = ?;",
            (channel_id,),
        ).fetchone()
    finally:
        conn.close()
    return _channel_dict(row)


@router.delete("/api/channels/{channel_id}")
def delete_channel(channel_id: str) -> dict:
    """Deactivate-and-remove a channel; past deliveries stay in the ledger."""
    init_db()
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM channels WHERE id = ?;", (channel_id,))
        conn.commit()
    finally:
        conn.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="channel not found")
    return {"ok": True, "id": channel_id}


@router.post("/api/channels/{channel_id}/test")
def test_channel(channel_id: str) -> dict:
    """Fire a signed test payload at one channel; records the delivery."""
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, target, secret, watch_id FROM channels WHERE id = ?;",
            (channel_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="channel not found")
    payload = {
        "type": "channel.test",
        "channel_id": row["id"],
        "message": "ARGUS webhook channel verified.",
        "at": webhook_client.utcnow(),
    }
    result = webhook_client.deliver(str(row["target"]), str(row["secret"] or ""), payload)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO deliveries "
            "(id, alert_id, channel_id, status, http_status, error, attempts, created_at) "
            "VALUES (?, NULL, ?, ?, ?, ?, ?, ?);",
            (
                webhook_client.new_delivery_id(),
                row["id"],
                "delivered" if result.get("ok") else "failed",
                result.get("http_status"),
                str(result.get("error", "")),
                int(result.get("attempts", 1)),
                webhook_client.utcnow(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": bool(result.get("ok")), "http_status": result.get("http_status"),
            "error": str(result.get("error", ""))}
