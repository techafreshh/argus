"""CopilotKit AG-UI chat bridge: JSON handshake plus SSE run stream (issue #18).

Additive only: reuses the existing ``route()`` + ``plan()`` + watch/receipt
helpers, adds no DB tables, and never raises into a 500. When the
``ARGUS_CHAT_ENABLED=0`` kill-switch is set, the chat routes return 200 JSON
``{disabled: True}`` while panels and alerts keep working untouched.

Wire shape is our own documented SSE ``data: {json}`` frames
(``run_started`` / ``tool_call`` / ``tool_result`` / ``message`` /
``run_finished``); no ``ag-ui``/``copilotkit`` Python dependency is added.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from starlette.responses import StreamingResponse

from argus.orchestrator.meta_client import plan as make_plan
from argus.orchestrator.router import abstain_receipt, route
from argus.store.db import get_connection, init_db

router = APIRouter()

AGUI_EVENTS = ("run_started", "tool_call", "tool_result", "message", "run_finished")


def _chat_disabled() -> bool:
    return os.environ.get("ARGUS_CHAT_ENABLED", "1") == "0"


def _disabled_payload() -> dict:
    return {"ok": False, "disabled": True}


class AguiIn(BaseModel):
    question: str | None = ""
    region: dict[str, Any] | None = None
    bbox: list[Any] | None = None
    cadence: str = "daily"
    threadId: str | None = None

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

    @field_validator("bbox", mode="before")
    @classmethod
    def _coerce_bbox(cls, value: Any) -> list[float] | None:
        # Malformed bboxes are ignored, never a 422/500.
        if value is None:
            return None
        try:
            coords = [float(v) for v in list(value)]
        except (TypeError, ValueError):
            return None
        if len(coords) != 4 or any(not math.isfinite(v) for v in coords):
            return None
        return coords


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _effective_region(payload: AguiIn) -> dict:
    region = dict(payload.region or {})
    if not region and payload.bbox:
        region = {"type": "bbox", "coords": list(payload.bbox)}
    return region


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
        "params": params,
        "params_json": json.dumps(params, sort_keys=True, default=str),
        "source_url": "",
        "data_hash": hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "plot_path": "",
        "token_usage": 0,
        "tokens": 0,
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


def _frame(event: dict) -> str:
    return "data: " + json.dumps(event, sort_keys=True, default=str) + "\n\n"


def _run_frames(
    question: str, region: dict, cadence: str, thread_id: str
) -> Iterator[str]:
    """Yield the run stream; the route path never raises into a 500."""
    try:
        init_db()
        yield _frame(
            {
                "type": "run_started",
                "threadId": thread_id,
                "question": question,
                "agent": "argus",
            }
        )
        if not question.strip():
            info = abstain_receipt("")
            watch_id = _insert_watch(question, "unrouted", region, cadence)
            receipt = _insert_receipt(
                watch_id,
                "ask_abstain",
                {"question": question, "template": "unrouted"},
                {"answer": info["answer"]},
            )
            yield _frame(
                {
                    "type": "tool_call",
                    "tool": "plan",
                    "input": {"question": question, "region": region},
                }
            )
            yield _frame(
                {
                    "type": "tool_result",
                    "tool": "plan",
                    "receipt": {
                        "id": receipt["id"],
                        "tool": receipt["tool"],
                        "params": receipt["params"],
                        "source_url": receipt["source_url"],
                        "data_hash": receipt["data_hash"],
                        "tokens": receipt["tokens"],
                    },
                }
            )
            yield _frame(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": info["answer"],
                    "template": None,
                    "watch_id": watch_id,
                    "receipt_id": receipt["id"],
                    "citations": [],
                }
            )
            yield _frame({"type": "run_finished", "ok": True, "abstained": True})
            return
        result = route(question)
        template = result.get("template")
        if template is None:
            info = abstain_receipt(question)
            watch_id = _insert_watch(question, "unrouted", region, cadence)
            receipt = _insert_receipt(
                watch_id,
                "ask_abstain",
                {"question": question, "template": "unrouted"},
                {"answer": info["answer"]},
            )
            yield _frame(
                {
                    "type": "tool_call",
                    "tool": "plan",
                    "input": {"question": question, "region": region},
                }
            )
            yield _frame(
                {
                    "type": "tool_result",
                    "tool": "plan",
                    "receipt": {
                        "id": receipt["id"],
                        "tool": receipt["tool"],
                        "params": receipt["params"],
                        "source_url": receipt["source_url"],
                        "data_hash": receipt["data_hash"],
                        "tokens": receipt["tokens"],
                    },
                }
            )
            yield _frame(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": info["answer"],
                    "template": None,
                    "missing": info["missing"],
                    "adjacent": info["adjacent"],
                    "watch_id": watch_id,
                    "receipt_id": receipt["id"],
                    "citations": [],
                }
            )
            yield _frame({"type": "run_finished", "ok": True, "abstained": True})
            return
        plan_obj = make_plan(question, region, cadence)
        plan_dict = plan_obj.to_dict()
        yield _frame(
            {
                "type": "tool_call",
                "tool": "plan",
                "input": {"question": question, "region": region, "cadence": cadence},
            }
        )
        watch_id = _insert_watch(question, str(template), region, cadence)
        receipt = _insert_receipt(
            watch_id,
            "ask_route",
            {"question": question, "template": str(template)},
            {"template": str(template), "plan": plan_dict},
        )
        yield _frame(
            {
                "type": "tool_result",
                "tool": "plan",
                "receipt": {
                    "id": receipt["id"],
                    "tool": receipt["tool"],
                    "params": receipt["params"],
                    "source_url": receipt["source_url"],
                    "data_hash": receipt["data_hash"],
                    "tokens": receipt["tokens"],
                },
            }
        )
        yield _frame(
            {
                "type": "message",
                "role": "assistant",
                "content": f"Template {template}: plan ready.",
                "template": str(template),
                "plan": plan_dict,
                "watch_id": watch_id,
                "receipt_id": receipt["id"],
                "citations": [
                    {
                        "receipt_id": receipt["id"],
                        "data_hash": receipt["data_hash"],
                        "source_url": receipt["source_url"],
                    }
                ],
            }
        )
        yield _frame(
            {
                "type": "run_finished",
                "ok": True,
                "template": str(template),
                "watch_id": watch_id,
                "receipt_id": receipt["id"],
            }
        )
    except Exception as exc:  # noqa: BLE001 - streaming must never 500
        yield _frame({"type": "run_finished", "ok": False, "error": str(exc)[:200]})


@router.get("/api/ag-ui")
def agui_descriptor():
    """Describe the AG-UI bridge (JSON handshake)."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    try:
        init_db()
    except Exception:  # noqa: BLE001, S110 - descriptor must stay 200
        pass
    return {
        "ok": True,
        "protocol": "ag-ui",
        "agent": "argus",
        "events": list(AGUI_EVENTS),
    }


@router.post("/api/ag-ui")
def agui_run(payload: AguiIn):
    """Stream an orchestrator run as SSE ``data: {json}`` frames."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    try:
        question = str(payload.question or "")
        region = _effective_region(payload)
        cadence = str(payload.cadence or "daily")
        thread_id = str(payload.threadId or uuid.uuid4().hex)
    except Exception:  # noqa: BLE001 - malformed input degrades, never 500
        question, region, cadence, thread_id = "", {}, "daily", uuid.uuid4().hex
    return StreamingResponse(
        _run_frames(question, region, cadence, thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _copilot_handshake() -> dict:
    return {"ok": True, "runtime": "copilot", "agent": "argus"}


@router.get("/api/copilot")
def copilot_handshake_get():
    """CopilotKit handshake alias (GET)."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    return _copilot_handshake()


@router.post("/api/copilot")
def copilot_handshake_post():
    """CopilotKit handshake alias (POST)."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    return _copilot_handshake()
