"""Mem0 hosted memory (api.mem0.ai): long-lived chat memory over a URL.

The room works with memory disabled: no ``MEM0_API_KEY`` or
``ARGUS_OFFLINE=1`` turns every call into a no-op (the offline demo never
egresses — PRD §9). Memory informs conversation continuity only; it never
feeds phase claims, alerts, or the verification rail. Every live call
writes a receipt, like every other tool call.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from argus.store.db import get_connection

_BASE_URL_DEFAULT = "https://api.mem0.ai"
_OFFLINE_TRUTHY = {"1", "true", "yes", "on"}
_TIMEOUT = 6.0


def _api_key() -> str:
    return os.environ.get("MEM0_API_KEY", "").strip()


def _base_url() -> str:
    return os.environ.get("MEM0_BASE_URL", _BASE_URL_DEFAULT).rstrip("/")


def _user_id() -> str:
    return os.environ.get("MEM0_USER_ID", "operator").strip() or "operator"


def _is_offline() -> bool:
    return os.environ.get("ARGUS_OFFLINE", "").strip().lower() in _OFFLINE_TRUTHY


def enabled() -> bool:
    """True when memory can run: key present and not offline."""
    return bool(_api_key()) and not _is_offline()


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _insert_receipt(watch_id: str, tool: str, params: dict, source_url: str, payload: dict) -> dict:
    stamped = dict(params or {})
    stamped["offline"] = _is_offline()
    receipt = {
        "id": uuid.uuid4().hex,
        "watch_id": watch_id,
        "tool": tool,
        "params": stamped,
        "source_url": source_url,
        "data_hash": hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "token_usage": 0,
        "created_at": _utcnow(),
    }
    conn = get_connection()
    try:
        # Receipts are scoped to a real watch (FK on watches.id); a memory
        # call outside any watch skips the receipt rather than failing.
        known = conn.execute(
            "SELECT 1 FROM watches WHERE id = ?;", (watch_id,)
        ).fetchone()
        if known is None:
            return receipt
        conn.execute(
            "INSERT INTO receipts "
            "(id, watch_id, acquisition_id, tool, params_json, source_url, "
            "data_hash, plot_path, token_usage, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                receipt["id"],
                receipt["watch_id"],
                None,
                receipt["tool"],
                json.dumps(stamped, sort_keys=True, default=str),
                receipt["source_url"],
                receipt["data_hash"],
                "",
                receipt["token_usage"],
                receipt["created_at"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return receipt


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Token {_api_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def search_memories(query: str, limit: int = 5, watch_id: str = "") -> list[dict]:
    """Top-k durable memories for a query; [] when disabled or on any failure."""
    text = str(query or "").strip()
    if not enabled() or not text:
        return []
    url = f"{_base_url()}/v3/memories/search/"
    body = {
        "query": text[:800],
        "filters": {"user_id": _user_id()},
        "top_k": max(1, min(int(limit), 20)),
    }
    memories: list[dict] = []
    error = ""
    try:
        resp = httpx.post(url, json=body, headers=_headers(), timeout=_TIMEOUT)
        results = resp.json().get("results", [])
        if isinstance(results, list):
            for item in results[: body["top_k"]]:
                if not isinstance(item, dict):
                    continue
                memories.append(
                    {
                        "id": str(item.get("id", "")),
                        "memory": str(item.get("memory", "")),
                        "score": item.get("score"),
                    }
                )
    except Exception as exc:  # noqa: BLE001 - memory must never break a run
        error = str(exc)[:200]
    _insert_receipt(
        watch_id,
        "memory_search",
        {"query": body["query"], "top_k": body["top_k"]},
        url,
        {"count": len(memories), "error": error} if error else {"count": len(memories)},
    )
    return memories


def remember(
    messages: list[dict],
    *,
    metadata: dict | None = None,
    watch_id: str = "",
) -> bool:
    """Send a conversation excerpt to Mem0 for fact extraction; never raises.

    ``messages`` are ``{"role": ..., "content": ...}`` pairs. Mem0 extracts
    and dedupes durable facts asynchronously (``infer`` defaults on).
    """
    if not enabled() or not messages:
        return False
    url = f"{_base_url()}/v3/memories/add/"
    body: dict[str, Any] = {
        "messages": [
            {"role": str(m.get("role", "user")), "content": str(m.get("content", ""))[:2000]}
            for m in messages[:20]
        ],
        "user_id": _user_id(),
    }
    if metadata:
        body["metadata"] = metadata
    ok = False
    detail: dict[str, Any] = {}
    try:
        resp = httpx.post(url, json=body, headers=_headers(), timeout=_TIMEOUT)
        ok = resp.status_code in (200, 201)
        try:
            detail = resp.json() if isinstance(resp.json(), dict) else {}
        except ValueError:
            detail = {}
        if not ok:
            detail["http_status"] = resp.status_code
    except Exception as exc:  # noqa: BLE001 - memory must never break a run
        detail = {"error": str(exc)[:200]}
    _insert_receipt(
        watch_id,
        "memory_add",
        {"roles": [m.get("role") for m in body["messages"]], "kind": (metadata or {}).get("kind", "")},
        url,
        detail or {"ok": ok},
    )
    return ok
