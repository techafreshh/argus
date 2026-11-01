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

from fastapi import APIRouter, Request
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


class CopilotRunIn(BaseModel):
    """Permissive RunAgentInput shape for the CopilotKit-facing routes."""

    question: str | None = ""
    region: dict[str, Any] | None = None
    bbox: list[Any] | None = None
    cadence: str = "daily"
    threadId: str | None = None
    runId: str | None = None
    messages: list[Any] | None = None
    state: dict[str, Any] | None = None

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


def _last_user_text(messages: Any, fallback: str = "") -> str:
    """Return the last user message text, handling plain or ContentPart[] content."""
    if not isinstance(messages, list):
        return fallback
    for entry in reversed(messages):
        if not isinstance(entry, dict):
            continue
        if entry.get("role") != "user":
            continue
        content = entry.get("content")
        if isinstance(content, str):
            if content.strip():
                return content
        elif isinstance(content, list):
            parts = [
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict)
                and part.get("type") == "text"
                and str(part.get("text", "")).strip()
            ]
            if parts:
                return "".join(parts)
    return fallback


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


COPILOT_AGENT_IDS = ("argus", "default")


def _copilot_handshake() -> dict:
    return {"ok": True, "runtime": "copilot", "agent": "argus"}


def _copilot_info() -> dict:
    return {
        "agents": [
            {
                "id": "argus",
                "name": "argus",
                "description": "ARGUS orbital-watch planner.",
            }
        ],
        "actions": [],
        "sdkVersion": "0.0.0",
    }


def _copilot_answer_text(
    template: str | None,
    plan_dict: dict | None,
    receipt: dict,
    fallback: str,
) -> str:
    """Assistant text embedding plan todos plus the tool receipt id/hash."""
    receipt_bits = f"receipt {receipt['id']} hash {receipt['data_hash']}."
    if template is None or not plan_dict:
        return f"{fallback} {receipt_bits}"
    todos = ", ".join(
        f"{key}={json.dumps(plan_dict.get(key), sort_keys=True, default=str)}"
        for key in ("sensor", "aoi", "window", "comparison", "cadence")
    )
    return f"Template {template}: plan ready. todos: {todos}. {receipt_bits}"


def _agui_copilot_frames(
    question: str, region: dict, cadence: str, thread_id: str, run_id: str
) -> Iterator[str]:
    """Yield the CopilotKit-facing run stream; never raises into a 500."""
    try:
        init_db()
        message_id = uuid.uuid4().hex
        tool_call_id = uuid.uuid4().hex
        yield _frame(
            {"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id}
        )
        args_delta = json.dumps(
            {"question": question, "region": region, "cadence": cadence},
            sort_keys=True,
            default=str,
        )
        yield _frame(
            {
                "type": "TOOL_CALL_START",
                "toolCallId": tool_call_id,
                "toolCallName": "plan",
            }
        )
        yield _frame(
            {
                "type": "TOOL_CALL_ARGS",
                "toolCallId": tool_call_id,
                "delta": args_delta,
            }
        )
        yield _frame({"type": "TOOL_CALL_END", "toolCallId": tool_call_id})
        if not question.strip():
            info = abstain_receipt("")
            watch_id = _insert_watch(question, "unrouted", region, cadence)
            receipt = _insert_receipt(
                watch_id,
                "ask_abstain",
                {"question": question, "template": "unrouted"},
                {"answer": info["answer"]},
            )
            answer = _copilot_answer_text(None, None, receipt, info["answer"])
        else:
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
                answer = _copilot_answer_text(None, None, receipt, info["answer"])
            else:
                plan_obj = make_plan(question, region, cadence)
                plan_dict = plan_obj.to_dict()
                watch_id = _insert_watch(question, str(template), region, cadence)
                receipt = _insert_receipt(
                    watch_id,
                    "ask_route",
                    {"question": question, "template": str(template)},
                    {"template": str(template), "plan": plan_dict},
                )
                answer = _copilot_answer_text(
                    str(template),
                    plan_dict,
                    receipt,
                    f"Template {template}: plan ready.",
                )
        yield _frame(
            {
                "type": "TEXT_MESSAGE_START",
                "messageId": message_id,
                "role": "assistant",
            }
        )
        for offset in range(0, len(answer), 400):
            yield _frame(
                {
                    "type": "TEXT_MESSAGE_CONTENT",
                    "messageId": message_id,
                    "delta": answer[offset : offset + 400],
                }
            )
        yield _frame({"type": "TEXT_MESSAGE_END", "messageId": message_id})
        yield _frame(
            {"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id}
        )
    except Exception as exc:  # noqa: BLE001 - streaming must never 500
        yield _frame({"type": "RUN_ERROR", "message": str(exc)[:200]})


def _copilot_body_to_run(body: Any) -> tuple[str, dict, str, str, str]:
    """Parse a tolerant CopilotKit/RunAgentInput body into run arguments."""
    try:
        payload = (
            CopilotRunIn.model_validate(body) if isinstance(body, dict) else CopilotRunIn()
        )
    except Exception:  # noqa: BLE001 - malformed input degrades, never 500
        payload = CopilotRunIn()
    try:
        raw = body if isinstance(body, dict) else {}
        messages = payload.messages
        if messages is None:
            nested = raw.get("input") or raw.get("data")
            if isinstance(nested, dict):
                nested_messages = nested.get("messages")
                if isinstance(nested_messages, list):
                    messages = nested_messages
        question = _last_user_text(messages, str(payload.question or ""))
        region = _effective_region(payload)
        cadence = str(payload.cadence or "daily")
        thread_id = str(
            payload.threadId
            or raw.get("thread_id")
            or raw.get("threadId")
            or uuid.uuid4().hex
        )
        run_id = str(
            payload.runId or raw.get("run_id") or raw.get("runId") or uuid.uuid4().hex
        )
    except Exception:  # noqa: BLE001 - malformed input degrades, never 500
        question, region, cadence = "", {}, "daily"
        thread_id, run_id = uuid.uuid4().hex, uuid.uuid4().hex
    return question, region, cadence, thread_id, run_id


def _copilot_stream(body: Any) -> StreamingResponse:
    question, region, cadence, thread_id, run_id = _copilot_body_to_run(body)
    return StreamingResponse(
        _agui_copilot_frames(question, region, cadence, thread_id, run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _looks_like_run_body(body: Any) -> bool:
    """True when the posted JSON carries a RunAgentInput ``messages`` array."""
    if not isinstance(body, dict):
        return False
    messages = body.get("messages")
    if isinstance(messages, list):
        return True
    for key in ("input", "data"):
        nested = body.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("messages"), list):
            return True
    return False


@router.get("/api/copilot")
def copilot_handshake_get():
    """CopilotKit handshake alias (GET)."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    return _copilot_handshake()


@router.post("/api/copilot")
async def copilot_handshake_post(request: Request):
    """CopilotKit alias: RunAgentInput bodies stream, anything else handshakes."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - empty/invalid JSON keeps the handshake
        body = None
    if _looks_like_run_body(body):
        return _copilot_stream(body)
    return _copilot_handshake()


@router.get("/api/copilot/info")
def copilot_info():
    """CopilotKit discovery: list the registered agents."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    return _copilot_info()


def _unknown_copilot_agent(agent_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "Agent not found",
            "message": f"Agent '{agent_id}' does not exist",
        },
    )


@router.post("/api/copilot/agent/{agent_id}/run")
async def copilot_agent_run(agent_id: str, request: Request):
    """Start a CopilotKit agent run as an SSE stream of AG-UI events."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    if agent_id not in COPILOT_AGENT_IDS:
        return _unknown_copilot_agent(agent_id)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - missing/invalid JSON degrades to abstain
        body = None
    return _copilot_stream(body)


@router.post("/api/copilot/agent/{agent_id}/connect")
async def copilot_agent_connect(agent_id: str, request: Request):
    """Reconnect stub: a short valid SSE run ending in RUN_FINISHED."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    if agent_id not in COPILOT_AGENT_IDS:
        return _unknown_copilot_agent(agent_id)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - missing/invalid JSON is fine here
        body = None
    _, _, _, thread_id, run_id = _copilot_body_to_run(body)

    def _connect_frames() -> Iterator[str]:
        yield _frame(
            {"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id}
        )
        yield _frame(
            {"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id}
        )

    return StreamingResponse(
        _connect_frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/copilot/agent/{agent_id}/stop/{thread_id}")
def copilot_agent_stop(agent_id: str, thread_id: str):
    """Stop stub: nothing runs in the background, so stopping is trivially ok."""
    if _chat_disabled():
        return JSONResponse(status_code=200, content=_disabled_payload())
    _ = (agent_id, thread_id)
    return {"ok": True}
