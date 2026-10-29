"""Watches CRUD plus manual Plan -> acquire -> receipt run."""

from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from argus.analysis.ndvi import fetch_ndvi
from argus.analysis.sam_client import segment_concept
from argus.eyes.fireline.alert import file_fire_alert
from argus.eyes.fireline.anomaly import anomaly as fire_anomaly
from argus.orchestrator.loop import run_watch as loop_run_watch
from argus.orchestrator.meta_client import plan as make_plan
from argus.orchestrator.planner import match_template
from argus.orchestrator.router import route as route_question
from argus.store.db import get_connection, init_db

router = APIRouter()

_VEGETATION_HINTS = ("vegetation", "ndvi", "crop", "deforest", "forest")

_SHIP_HINTS = ("ship", "vessel", "boat", "tanker", "cargo", "harbor", "port")

_FIRE_HINTS = ("fire", "burn", "wildfire")

_CADENCES = ("daily", "weekly")

_OFFLINE_TRUTHY = {"1", "true", "yes", "on"}


def _is_offline() -> bool:
    """True when ARGUS_OFFLINE requests fixture-only behaviour."""
    return os.environ.get("ARGUS_OFFLINE", "").strip().lower() in _OFFLINE_TRUTHY


class RegionIn(BaseModel):
    type: str
    coords: list[float] = Field(min_length=4, max_length=4)

    @field_validator("type")
    @classmethod
    def _bbox_only(cls, value: str) -> str:
        if value != "bbox":
            raise ValueError("region.type must be 'bbox'")
        return value

    @field_validator("coords")
    @classmethod
    def _finite_coords(cls, value: list[float]) -> list[float]:
        checked = [float(item) for item in value]
        if not all(math.isfinite(item) for item in checked):
            raise ValueError("region.coords must be 4 finite floats")
        return checked


class WatchIn(BaseModel):
    name: str = Field(min_length=1)
    region: RegionIn | None = None
    aoi: dict[str, Any] | None = None
    question: str = Field(min_length=1)
    template: str | None = None
    cadence: str = "daily"

    model_config = {"extra": "allow"}

    @field_validator("name", "question")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("must not be empty")
        return str(value)

    @field_validator("cadence")
    @classmethod
    def _known_cadence(cls, value: str) -> str:
        if value not in _CADENCES:
            raise ValueError(f"cadence must be one of {list(_CADENCES)}")
        return value


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _is_vegetation(template: str, question: str) -> bool:
    text = f"{template} {question}".lower()
    if not text.strip():
        return True
    return any(hint in text for hint in _VEGETATION_HINTS)


def _is_ship_presence(template: str, question: str) -> bool:
    text = f"{template} {question}".lower()
    if not text.strip():
        return False
    return any(hint in text for hint in _SHIP_HINTS)


def _is_fire(template: str, question: str) -> bool:
    text = f"{template} {question}".lower()
    if "fire_anomaly" in text or "fire_watch" in text:
        return True
    if not text.strip():
        return False
    return any(hint in text for hint in _FIRE_HINTS)


def _region_window(row: Any) -> tuple[str, str]:
    region = "test-aoi"
    window = "2024-01"
    try:
        stored = json.loads(row["region_json"] or "{}")
    except (TypeError, ValueError):
        stored = {}
    if isinstance(stored, dict):
        for key in ("region", "name"):
            if isinstance(stored.get(key), str) and stored[key]:
                region = stored[key]
                break
        aoi = stored.get("aoi")
        if isinstance(aoi, dict):
            for key in ("region", "name"):
                if isinstance(aoi.get(key), str) and aoi[key]:
                    region = aoi[key]
                    break
        raw_window = stored.get("window", stored.get("month"))
        if isinstance(raw_window, dict):
            raw_window = (
                raw_window.get("window") or raw_window.get("month") or raw_window.get("start")
            )
        if isinstance(raw_window, str) and raw_window:
            window = raw_window[:7] if len(raw_window) >= 7 and raw_window[4] == "-" else raw_window
    return region, window


def _insert_receipt(
    watch_id: str,
    tool: str,
    params: dict,
    source_url: str,
    payload: dict,
    plot_path: str = "",
) -> dict:
    stamped = dict(params or {})
    stamped["offline"] = _is_offline()
    receipt = {
        "id": uuid.uuid4().hex,
        "watch_id": watch_id,
        "acquisition_id": None,
        "tool": tool,
        "offline": stamped["offline"],
        "params_json": json.dumps(stamped, sort_keys=True, default=str),
        "source_url": source_url,
        "data_hash": hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "plot_path": plot_path,
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


def _insert_alert(
    watch_id: str,
    title: str,
    confidence: float,
    evidence: dict,
) -> dict:
    alert = {
        "id": uuid.uuid4().hex,
        "watch_id": watch_id,
        "report_id": None,
        "title": title,
        "confidence": confidence,
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


def _watch_dict(row: Any) -> dict:
    try:
        region = json.loads(row["region_json"] or "{}")
    except (TypeError, ValueError):
        region = {}
    return {
        "id": row["id"],
        "name": row["name"],
        "region": region,
        "question": row["question"],
        "template": row["template"],
        "cadence": row["cadence"],
        "status": row["status"],
    }


def _receipt_dict(row: Any) -> dict:
    try:
        params = json.loads(row["params_json"] or "{}")
    except (TypeError, ValueError):
        params = {}
    if not isinstance(params, dict):
        params = {}
    try:
        tokens = int(row["token_usage"])
    except (TypeError, ValueError):
        tokens = 0
    return {
        "id": row["id"],
        "watch_id": row["watch_id"],
        "acquisition_id": row["acquisition_id"],
        "tool": row["tool"],
        "params_json": row["params_json"],
        "params": params,
        "offline": bool(params.get("offline", False)),
        "source_url": row["source_url"],
        "data_hash": row["data_hash"],
        "plot_path": row["plot_path"],
        "token_usage": int(row["token_usage"]),
        "tokens": tokens,
        "created_at": row["created_at"],
    }


def _get_watch_or_404(watch_id: str) -> Any:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, region_json, question, template, cadence, status"
            " FROM watches WHERE id = ?;",
            (watch_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return row


@router.post("/api/watches")
def create_watch(payload: WatchIn, response: Response) -> dict:
    """Create a watch; stores the matched template plus the initial Plan."""
    init_db()
    template = (payload.template or "").strip() or (
        route_question(payload.question).get("template")
        or match_template(payload.question)
    )
    if payload.region is not None:
        region: dict[str, Any] = {
            "type": payload.region.type,
            "coords": list(payload.region.coords),
        }
    else:
        region = dict(payload.aoi or {})
        extra = payload.model_dump()
        for key, value in extra.items():
            if key not in {"name", "region", "aoi", "question", "template", "cadence"}:
                region.setdefault(key, value)
    plan_obj = make_plan(payload.question, region, payload.cadence)
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
                str(payload.name),
                json.dumps(region, sort_keys=True, default=str),
                str(payload.question),
                str(template),
                str(payload.cadence),
                "active",
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    if payload.region is not None:
        response.status_code = 201
    return {
        "ok": True,
        "id": watch_id,
        "template": str(template),
        "plan": plan_obj.to_dict(),
        "name": str(payload.name),
        "region": region,
        "question": str(payload.question),
        "cadence": str(payload.cadence),
    }


@router.get("/api/watches")
def list_watches() -> list[dict]:
    """List watches newest-first."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, region_json, question, template, cadence, status"
            " FROM watches ORDER BY created_at DESC, rowid DESC;"
        ).fetchall()
    finally:
        conn.close()
    return [_watch_dict(row) for row in rows]


@router.get("/api/watches/{watch_id}")
def get_watch(watch_id: str) -> dict:
    """Return one watch; 404 when absent."""
    init_db()
    return _watch_dict(_get_watch_or_404(watch_id))


@router.delete("/api/watches/{watch_id}")
def delete_watch(watch_id: str) -> dict:
    """Remove a watch and its acquisitions/receipts; 404 when absent."""
    init_db()
    _get_watch_or_404(watch_id)
    conn = get_connection()
    try:
        conn.execute("DELETE FROM receipts WHERE watch_id = ?;", (watch_id,))
        conn.execute("DELETE FROM acquisitions WHERE watch_id = ?;", (watch_id,))
        conn.execute("DELETE FROM alerts WHERE watch_id = ?;", (watch_id,))
        conn.execute("DELETE FROM predictions WHERE watch_id = ?;", (watch_id,))
        conn.execute("DELETE FROM watches WHERE id = ?;", (watch_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.post("/api/watches/{watch_id}/run")
def run_watch(watch_id: str) -> dict:
    """Run the Plan -> acquire -> receipt loop for a watch (manual demo beat)."""
    init_db()
    row = _get_watch_or_404(watch_id)
    template = str(row["template"] or "")
    question = str(row["question"] or "")
    region, window = _region_window(row)
    offline = _is_offline()
    try:
        loop_result = loop_run_watch(watch_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="watch not found")
    except Exception as exc:  # noqa: BLE001 - run never 500s into the route layer
        fallback: dict[str, Any] = {"error": str(exc) or "run failed"}
        receipt = _insert_receipt(watch_id, "oisst", {"region": region}, "", fallback)
        return {
            "ok": False,
            "error": fallback["error"],
            "offline": offline,
            "receipt_id": receipt["id"],
            "acquisition_id": receipt["acquisition_id"],
            "receipts": [receipt],
        }
    receipts: list[dict] = []
    conn = get_connection()
    try:
        loop_row = conn.execute(
            "SELECT id, tool, source_url, data_hash, plot_path, token_usage"
            " FROM receipts WHERE id = ?;",
            (loop_result["receipt_id"],),
        ).fetchone()
    finally:
        conn.close()
    if loop_row is not None:
        receipts.append(
            {
                "id": loop_row["id"],
                "tool": loop_row["tool"],
                "offline": offline,
                "source_url": loop_row["source_url"],
                "data_hash": loop_row["data_hash"],
                "plot_path": loop_row["plot_path"],
                "token_usage": int(loop_row["token_usage"]),
            }
        )
    if _is_fire(template, question):
        fire_params: dict[str, Any] = {"region": region, "window": window}
        try:
            fire_result = fire_anomaly(fire_params)
        except Exception as exc:  # noqa: BLE001 - run never raises into the route layer
            error: dict[str, Any] = {"error": str(exc) or "fire anomaly failed"}
            receipt = _insert_receipt(watch_id, "fire_anomaly", fire_params, "", error)
            receipts.append(
                {
                    "id": receipt["id"],
                    "tool": "fire_anomaly",
                    "offline": offline,
                    "source_url": receipt["source_url"],
                    "data_hash": receipt["data_hash"],
                    "plot_path": receipt["plot_path"],
                    "token_usage": receipt["token_usage"],
                }
            )
            return {
                "ok": False,
                "error": error["error"],
                "offline": offline,
                "receipt_id": loop_result["receipt_id"],
                "acquisition_id": loop_result["acquisition_id"],
                "receipts": receipts,
            }
        summary = _insert_receipt(
            watch_id,
            "fire_anomaly",
            fire_params,
            str(fire_result.get("before_url", "")),
            fire_result,
        )
        receipts.append(
            {
                "id": summary["id"],
                "tool": "fire_anomaly",
                "offline": offline,
                "source_url": summary["source_url"],
                "data_hash": summary["data_hash"],
                "plot_path": summary["plot_path"],
                "token_usage": summary["token_usage"],
            }
        )
        title = str(row["name"] or row["question"] or "watch alert")
        alert = file_fire_alert(watch_id, fire_result, title)
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE watches SET updated_at = ? WHERE id = ?;",
                (_utcnow(), watch_id),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": True,
            "offline": offline,
            "receipt_id": loop_result["receipt_id"],
            "acquisition_id": loop_result["acquisition_id"],
            "receipts": receipts,
            "alert_id": alert["id"],
            "alert_status": alert["status"],
        }
    params: dict[str, Any] = {"region": region, "window": window, "aoi": region}
    if not _is_vegetation(template, question):
        params["template"] = "vegetation"
    try:
        result = fetch_ndvi(params)
    except Exception as exc:  # noqa: BLE001 - run never raises into the route layer
        error: dict[str, Any] = {"error": str(exc) or "fetch_ndvi failed"}
        receipt = _insert_receipt(watch_id, "fetch_ndvi", params, "", error)
        receipts.append(
            {
                "id": receipt["id"],
                "tool": "fetch_ndvi",
                "offline": offline,
                "source_url": receipt["source_url"],
                "data_hash": receipt["data_hash"],
                "plot_path": receipt["plot_path"],
                "token_usage": receipt["token_usage"],
            }
        )
        return {
            "ok": False,
            "error": error["error"],
            "offline": offline,
            "receipt_id": loop_result["receipt_id"],
            "acquisition_id": loop_result["acquisition_id"],
            "receipts": receipts,
        }
    receipt = _insert_receipt(
        watch_id,
        "fetch_ndvi",
        params,
        str(result.get("source_url", "")),
        result,
        plot_path="",
    )
    receipts.append(
        {
            "id": receipt["id"],
            "tool": "fetch_ndvi",
            "offline": offline,
            "source_url": receipt["source_url"],
            "data_hash": receipt["data_hash"],
            "plot_path": receipt["plot_path"],
            "token_usage": receipt["token_usage"],
        }
    )
    if _is_ship_presence(template, question):
        sam_params: dict[str, Any] = {
            "noun_phrase": "ship",
            "region": region,
            "window": window,
        }
        try:
            sam_result = segment_concept(
                "ship",
                {"region": region, "window": window, "width": 1024, "height": 1024},
            )
        except Exception as exc:  # noqa: BLE001 - run never raises
            sam_result = {
                "boxes": [],
                "masks_path": "",
                "source_url": "",
                "error": str(exc) or "segment_concept failed",
            }
        sam_receipt = _insert_receipt(
            watch_id,
            "segment_concept",
            sam_params,
            str(sam_result.get("source_url", "")),
            sam_result,
            plot_path=str(sam_result.get("masks_path", "")),
        )
        receipts.append(
            {
                "id": sam_receipt["id"],
                "tool": "segment_concept",
                "offline": offline,
                "source_url": sam_receipt["source_url"],
                "data_hash": sam_receipt["data_hash"],
                "plot_path": sam_receipt["plot_path"],
                "token_usage": sam_receipt["token_usage"],
            }
        )
    try:
        z = float(result.get("z_score", 0.0))
    except (TypeError, ValueError):
        z = 0.0
    if not math.isfinite(z):
        z = 0.0
    title = str(row["name"] or row["question"] or "watch alert")
    alert = _insert_alert(
        watch_id,
        title,
        min(0.99, abs(z) / 5.0),
        {"receipt_id": receipt["id"], "z_score": z},
    )
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE watches SET updated_at = ? WHERE id = ?;",
            (_utcnow(), watch_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "ok": True,
        "offline": offline,
        "receipt_id": loop_result["receipt_id"],
        "acquisition_id": loop_result["acquisition_id"],
        "receipts": receipts,
        "alert_id": alert["id"],
        "alert_status": alert["status"],
    }


@router.get("/api/watches/{watch_id}/receipts")
def list_receipts(watch_id: str) -> list[dict]:
    """Return the bare receipt trail for a watch; 404 when the watch is absent."""
    init_db()
    _get_watch_or_404(watch_id)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, watch_id, acquisition_id, tool, params_json, source_url,"
            " data_hash, plot_path, token_usage, created_at FROM receipts"
            " WHERE watch_id = ? ORDER BY created_at, rowid;",
            (watch_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_receipt_dict(row) for row in rows]
