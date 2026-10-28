"""Muse Spark 1.3 client with typed Plan output and a spend ledger.

OpenAI-compatible wire call (``POST {base}/chat/completions``) over the
repo's ``httpx`` stack -- no extra SDK dependency, so the offline path
(``ARGUS_OFFLINE=1`` or ``META_API_KEY`` unset) never imports anything
beyond ``fastapi + httpx + sqlite3``. Every billable call is logged to the
``meta_spend`` table via :func:`log_spend`.

The ``META_API_KEY`` value is only ever sent as an ``Authorization``
header; it is never written to the database, never returned in a
response, and never logged.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from argus.store.db import get_connection, init_db

DEFAULT_BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL_ID = "muse-spark-1.3-contributor"
DEFAULT_SPEND_CAP = 150.0

META_BASE_URL = os.environ.get("META_BASE_URL", DEFAULT_BASE_URL)
MODEL_ID = os.environ.get("ARGUS_MODEL", DEFAULT_MODEL_ID)

_PLAN_FIELDS = ("sensor", "aoi", "window", "comparison", "cadence")

_PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sensor": {"type": "string"},
        "aoi": {"type": "object"},
        "window": {"type": "object"},
        "comparison": {"type": "string"},
        "cadence": {"type": "string"},
    },
    "required": ["sensor", "aoi", "window", "comparison", "cadence"],
    "additionalProperties": False,
}

_OFFLINE_TRUTHY = {"1", "true", "yes", "on"}


@dataclass
class Plan:
    """Constrained planner output: what to observe, where, when, how."""

    sensor: str
    aoi: dict
    window: dict
    comparison: str
    cadence: str
    capped: bool = field(default=False, compare=False)

    def to_dict(self) -> dict:
        return {
            "sensor": self.sensor,
            "aoi": dict(self.aoi),
            "window": dict(self.window),
            "comparison": self.comparison,
            "cadence": self.cadence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Plan:
        if not isinstance(data, dict):
            raise TypeError(f"Plan must be a dict, got {type(data).__name__}")
        missing = [key for key in _PLAN_FIELDS if key not in data]
        if missing:
            raise ValueError(f"Plan missing required keys: {missing}")
        if not isinstance(data["sensor"], str):
            raise TypeError("Plan.sensor must be a string")
        if not isinstance(data["aoi"], dict):
            raise TypeError("Plan.aoi must be a dict")
        if not isinstance(data["window"], dict):
            raise TypeError("Plan.window must be a dict")
        if not isinstance(data["comparison"], str):
            raise TypeError("Plan.comparison must be a string")
        if not isinstance(data["cadence"], str):
            raise TypeError("Plan.cadence must be a string")
        return cls(
            sensor=data["sensor"],
            aoi=dict(data["aoi"]),
            window=dict(data["window"]),
            comparison=data["comparison"],
            cadence=data["cadence"],
        )


CANNED_PLAN = Plan(
    sensor="oisst",
    aoi={"bbox": [-5, -170, 5, -120]},
    window={"start": "2023-01-01", "end": "2023-01-31"},
    comparison="climatology",
    cadence="daily",
)


def _canned(capped: bool = False) -> Plan:
    """Return a fresh copy of the offline Plan (never the shared instance)."""
    return Plan(
        sensor=CANNED_PLAN.sensor,
        aoi=dict(CANNED_PLAN.aoi),
        window=dict(CANNED_PLAN.window),
        comparison=CANNED_PLAN.comparison,
        cadence=CANNED_PLAN.cadence,
        capped=capped,
    )


def is_offline() -> bool:
    """True when ARGUS_OFFLINE requests fixture-only behaviour."""
    return os.environ.get("ARGUS_OFFLINE", "").strip().lower() in _OFFLINE_TRUTHY


def _base_url() -> str:
    return os.environ.get("META_BASE_URL", META_BASE_URL or DEFAULT_BASE_URL)


def _model_id() -> str:
    return os.environ.get("ARGUS_MODEL", MODEL_ID or DEFAULT_MODEL_ID)


def _api_key() -> str:
    return os.environ.get("META_API_KEY", "")


def _spend_cap() -> float:
    try:
        return float(os.environ.get("ARGUS_SPEND_CAP", DEFAULT_SPEND_CAP))
    except (TypeError, ValueError):
        return DEFAULT_SPEND_CAP


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def spend_total() -> float:
    """Return SUM(cost_credits) over meta_spend (0.0 on an empty ledger)."""
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_credits), 0) FROM meta_spend;"
        ).fetchone()
        return float(row[0]) if row else 0.0
    finally:
        conn.close()


def log_spend(
    operation: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_credits: float = 0.0,
) -> dict:
    """Insert one usage row into meta_spend and return it as a dict.

    Never reads ``META_API_KEY``; the key cannot leak through this path.
    """
    init_db()
    entry = {
        "id": uuid.uuid4().hex,
        "operation": str(operation),
        "model": str(model),
        "tokens_in": int(tokens_in),
        "tokens_out": int(tokens_out),
        "cost_credits": float(cost_credits),
        "created_at": _utcnow(),
    }
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO meta_spend "
            "(id, operation, model, tokens_in, tokens_out, cost_credits, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);",
            (
                entry["id"],
                entry["operation"],
                entry["model"],
                entry["tokens_in"],
                entry["tokens_out"],
                entry["cost_credits"],
                entry["created_at"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return entry


def get_spend() -> dict:
    """Return the spend ledger as {"total_credits": float, "calls": [...]}."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, operation, model, tokens_in, tokens_out, cost_credits, created_at "
            "FROM meta_spend ORDER BY created_at, rowid;"
        ).fetchall()
    finally:
        conn.close()
    calls = [
        {
            "id": row["id"],
            "operation": row["operation"],
            "model": row["model"],
            "tokens_in": int(row["tokens_in"]),
            "tokens_out": int(row["tokens_out"]),
            "cost_credits": float(row["cost_credits"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"total_credits": float(sum(call["cost_credits"] for call in calls)), "calls": calls}


def _default_cost(tokens_in: int, tokens_out: int) -> float:
    return (int(tokens_in) + int(tokens_out)) / 1000.0 * 0.001


def _live_plan(question: str, region: dict | None, cadence: str) -> Plan:
    model = _model_id()
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are ARGUS, an orbital-watch planner. "
                "Reply with exactly one JSON Plan object.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "region": region or {},
                        "cadence": cadence,
                    },
                    sort_keys=True,
                    default=str,
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "Plan",
                "schema": _PLAN_JSON_SCHEMA,
                "strict": True,
            },
        },
    }
    headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
    response = httpx.post(
        f"{_base_url().rstrip('/')}/chat/completions",
        json=payload,
        headers=headers,
        timeout=20.0,
    )
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    if isinstance(content, str):
        content = json.loads(content)
    plan_obj = Plan.from_dict(content)
    usage = body.get("usage") or {}
    tokens_in = int(usage.get("prompt_tokens", 0))
    tokens_out = int(usage.get("completion_tokens", 0))
    log_spend("plan", model, tokens_in, tokens_out, _default_cost(tokens_in, tokens_out))
    return plan_obj


def plan(
    question: str = "",
    region: dict | None = None,
    cadence: str = "daily",
    **_kwargs: Any,
) -> Plan:
    """Plan an observation; offline, keyless, capped, or failing live calls
    all fall back to the canned Plan instead of raising (never HTTP 500)."""
    cadence = cadence or "daily"
    if is_offline() or not _api_key():
        return _canned()
    try:
        if spend_total() >= _spend_cap():
            return _canned(capped=True)
        return _live_plan(question, region, cadence)
    except Exception:  # noqa: BLE001 - planner must never raise into the route layer
        return _canned()
