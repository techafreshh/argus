"""Signed webhook delivery for approved alerts (URL-based, no self-hosting).

The payload is canonical JSON; the ``X-ARGUS-Signature`` header carries the
HMAC-SHA256 hex over the exact body bytes, keyed by the channel secret, so a
receiver can verify authenticity without trusting the network. Offline mode
never egresses. ``deliver`` never raises — the caller records the outcome.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import UTC, datetime

import httpx

_TIMEOUT = 6.0
_ATTEMPTS = 2


def is_offline() -> bool:
    return os.environ.get("ARGUS_OFFLINE", "") == "1"


def sign(body: bytes, secret: str) -> str:
    """HMAC-SHA256 hex over the exact body bytes, keyed by the channel secret."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def deliver(target: str, secret: str, payload: dict) -> dict:
    """POST the signed payload; returns {ok, http_status, error, signature}."""
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    signature = sign(body, secret)
    if is_offline():
        return {"ok": False, "http_status": None, "error": "offline", "signature": signature}
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ARGUS/1.0 (alert delivery)",
        "X-ARGUS-Signature": f"sha256={signature}",
    }
    last_error = ""
    for attempt in range(_ATTEMPTS):
        try:
            response = httpx.post(target, content=body, headers=headers, timeout=_TIMEOUT)
            ok = 200 <= response.status_code < 300
            return {
                "ok": ok,
                "http_status": response.status_code,
                "error": "" if ok else f"HTTP {response.status_code}",
                "signature": signature,
                "attempts": attempt + 1,
            }
        except Exception as exc:  # noqa: BLE001 - delivery must never raise
            last_error = str(exc)[:200]
    return {"ok": False, "http_status": None, "error": last_error, "signature": signature, "attempts": _ATTEMPTS}


def alert_payload(alert: dict, card: dict) -> dict:
    """The delivered envelope: alert decision + graded card summary + links."""
    public_base = os.environ.get("ARGUS_PUBLIC_URL", "https://argus.techa.pro").rstrip("/")
    report_id = str(card.get("id", "") or alert.get("report_id", ""))
    evidence = alert.get("evidence")
    return {
        "type": "alert.approved",
        "alert_id": str(alert.get("id", "")),
        "watch_id": str(alert.get("watch_id", "")),
        "report_id": report_id,
        "title": str(alert.get("title", "")),
        "headline": str(card.get("headline", "")),
        "confidence": float(card.get("confidence", alert.get("confidence", 0.0)) or 0.0),
        "hectares": float(card.get("hectares", 0.0) or 0.0),
        "evidence": evidence if isinstance(evidence, dict) else {},
        "data_hash": str(card.get("data_hash", "")),
        "report_url": f"{public_base}/reports?report={report_id}" if report_id else f"{public_base}/reports",
        "decided_at": str(alert.get("decided_at", "")),
    }


def new_delivery_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> str:
    return datetime.now(UTC).isoformat()
