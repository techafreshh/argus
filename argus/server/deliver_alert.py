"""Alert delivery: fan a decided alert out to the operator's webhook channels.

Every attempt lands in the ``deliveries`` ledger and in the watch's receipts
(``alert_deliver``), so "what happened after approval" is auditable end to end.
Delivery failures never break the approval path.
"""

from __future__ import annotations

import json

from argus.adapters import webhook_client
from argus.store.db import get_connection, init_db


def _insert_receipt(watch_id: str, params: dict, payload: dict, source: str) -> str | None:
    """A delivery receipt, FK-scoped to a real watch (skipped when unknown)."""
    import hashlib
    import uuid

    conn = get_connection()
    try:
        known = conn.execute(
            "SELECT 1 FROM watches WHERE id = ?;", (watch_id,)
        ).fetchone()
        if known is None:
            return None
        receipt_id = uuid.uuid4().hex
        data_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        conn.execute(
            "INSERT INTO receipts "
            "(id, watch_id, acquisition_id, tool, params_json, source_url, "
            "data_hash, plot_path, token_usage, created_at) "
            "VALUES (?, ?, NULL, ?, ?, ?, ?, '', 0, ?);",
            (
                receipt_id,
                watch_id,
                "alert_deliver",
                json.dumps(params, sort_keys=True, default=str),
                source,
                data_hash,
                webhook_client.utcnow(),
            ),
        )
        conn.commit()
        return receipt_id
    finally:
        conn.close()


def channels_for(watch_id: str) -> list[dict]:
    """Active channels: watch-scoped plus global, global last."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, kind, target, secret, watch_id, status, created_at "
            "FROM channels WHERE status = 'active' "
            "AND (watch_id IS NULL OR watch_id = ?) "
            "ORDER BY (watch_id IS NULL), created_at, rowid;",
            (watch_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": row["id"],
            "kind": row["kind"],
            "target": row["target"],
            "secret": row["secret"],
            "watch_id": row["watch_id"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _record_delivery(
    alert_id: str, channel_id: str, result: dict, watch_id: str, target: str
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO deliveries "
            "(id, alert_id, channel_id, status, http_status, error, attempts, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            (
                webhook_client.new_delivery_id(),
                alert_id,
                channel_id,
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
    _insert_receipt(
        watch_id,
        {
            "channel_id": channel_id,
            "target": target,
            "alert_id": alert_id,
            "status": "delivered" if result.get("ok") else "failed",
            "http_status": result.get("http_status"),
        },
        {"alert_id": alert_id, "result": {k: v for k, v in result.items() if k != "signature"}},
        source=target,
    )


def dispatch_alert(alert: dict, card: dict) -> list[dict]:
    """Deliver to every matching channel; never raises."""
    watch_id = str(alert.get("watch_id", ""))
    payload = webhook_client.alert_payload(alert, card)
    results: list[dict] = []
    try:
        channels = channels_for(watch_id)
    except Exception:  # noqa: BLE001 - channel lookup must never break approve
        return results
    for channel in channels:
        if str(channel.get("kind")) != "webhook":
            continue
        try:
            result = webhook_client.deliver(
                str(channel["target"]), str(channel["secret"] or ""), payload
            )
        except Exception as exc:  # noqa: BLE001 - one bad channel never blocks the rest
            result = {"ok": False, "http_status": None, "error": str(exc)[:200]}
        try:
            _record_delivery(
                str(alert.get("id", "")),
                str(channel["id"]),
                {**result, "attempts": result.get("attempts", 1)},
                watch_id,
                str(channel["target"]),
            )
        except Exception:  # noqa: BLE001, S110 - ledger failure never breaks approve
            pass
        results.append(
            {
                "channel_id": str(channel["id"]),
                "target": str(channel["target"]),
                "ok": bool(result.get("ok")),
                "http_status": result.get("http_status"),
                "error": str(result.get("error", "")),
            }
        )
    return results
