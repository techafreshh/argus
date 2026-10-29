"""Question router route: POST /api/ask (issue #9)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from argus.orchestrator.meta_client import plan as make_plan
from argus.orchestrator.router import abstain_receipt, route
from argus.store.db import get_connection, init_db

router = APIRouter()


class AskIn(BaseModel):
    question: str | None = ""
    region: dict[str, Any] | None = None
    cadence: str = "daily"

    model_config = {"extra": "allow"}

    @field_validator("question", mode="before")
    @classmethod
    def _coerce_question(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @field_validator("cadence", mode="before")
    @classmethod
    def _default_cadence(cls, value: Any) -> str:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "daily"
        return str(value)


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _insert_watch(question: str, template: str, region: dict, cadence: str) -> str:
    name = question.strip()[:200] or "untitled question"
    watch_id = uuid.uuid4().hex
    now = _utcnow()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO watches "
            "(id, name, region_json, question, template, cadence, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                watch_id,
                name,
                json.dumps(region, sort_keys=True, default=str),
                question,
                template,
                cadence,
                "active",
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return watch_id


def _insert_receipt(watch_id: str, tool: str, params: dict, payload: dict) -> dict:
    receipt = {
        "id": uuid.uuid4().hex,
        "watch_id": watch_id,
        "acquisition_id": None,
        "tool": tool,
        "params_json": json.dumps(params, sort_keys=True, default=str),
        "source_url": "",
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


def _abstain_response(watch_id: str, receipt_id: str) -> dict:
    info = abstain_receipt("")
    return {
        "answer": info["answer"],
        "missing": info["missing"],
        "adjacent": info["adjacent"],
        "receipt_id": receipt_id,
        "template": None,
        "watch_id": watch_id,
    }


@router.post("/api/ask")
def ask(payload: AskIn) -> dict:
    """Route a plain-English question to a pipeline or honestly abstain."""
    try:
        init_db()
        question = str(payload.question or "")
        region = dict(payload.region or {})
        cadence = str(payload.cadence or "daily")
        if not question.strip():
            watch_id = _insert_watch(question, "unrouted", region, cadence)
            receipt = _insert_receipt(
                watch_id,
                "ask_abstain",
                {"question": question, "template": "unrouted"},
                {"answer": abstain_receipt("")["answer"]},
            )
            return _abstain_response(watch_id, receipt["id"])
        result = route(question)
        template = result.get("template")
        if template is not None:
            plan_obj = make_plan(question, region, cadence)
            plan_dict = plan_obj.to_dict()
            watch_id = _insert_watch(question, str(template), region, cadence)
            receipt = _insert_receipt(
                watch_id,
                "ask_route",
                {"question": question, "template": str(template)},
                {"template": str(template), "plan": plan_dict},
            )
            return {
                "ok": True,
                "template": str(template),
                "plan": plan_dict,
                "watch_id": watch_id,
                "receipt_id": receipt["id"],
            }
        watch_id = _insert_watch(question, "unrouted", region, cadence)
        receipt = _insert_receipt(
            watch_id,
            "ask_abstain",
            {"question": question, "template": "unrouted"},
            {"answer": abstain_receipt(question)["answer"]},
        )
        return _abstain_response(watch_id, receipt["id"])
    except Exception:  # noqa: BLE001 - the ask path never raises into a 500
        return {
            "answer": abstain_receipt("")["answer"],
            "missing": list(abstain_receipt("")["missing"]),
            "adjacent": list(abstain_receipt("")["adjacent"]),
            "receipt_id": uuid.uuid4().hex,
            "template": None,
            "watch_id": "",
        }
