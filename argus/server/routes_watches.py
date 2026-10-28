"""Minimal watches routes: create a watch and run its vegetation check."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from argus.analysis.ndvi import fetch_ndvi
from argus.store.db import get_connection, init_db

router = APIRouter()

_VEGETATION_HINTS = ("vegetation", "ndvi", "crop", "deforest", "forest")


class WatchCreate(BaseModel):
    name: str = "watch"
    region: dict[str, Any] | None = None
    aoi: dict[str, Any] | None = None
    question: str = ""
    template: str = "vegetation"
    cadence: str = "daily"

    model_config = {"extra": "allow"}


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _is_vegetation(template: str, question: str) -> bool:
    text = f"{template} {question}".lower()
    if not text.strip():
        return True
    return any(hint in text for hint in _VEGETATION_HINTS)


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
    receipt = {
        "id": uuid.uuid4().hex,
        "watch_id": watch_id,
        "acquisition_id": None,
        "tool": tool,
        "params_json": json.dumps(params, sort_keys=True, default=str),
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


@router.post("/api/watches")
def create_watch(payload: WatchCreate | None = None) -> dict:
    """Insert a watch row; all fields optional with vegetation-friendly defaults."""
    init_db()
    body = payload or WatchCreate()
    extra = body.model_dump()
    region = dict(body.region or body.aoi or {})
    for key, value in extra.items():
        if key not in {"name", "region", "aoi", "question", "template", "cadence"}:
            region.setdefault(key, value)
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
                str(body.name or "watch"),
                json.dumps(region, sort_keys=True, default=str),
                str(body.question or ""),
                str(body.template or "vegetation"),
                str(body.cadence or "daily"),
                "active",
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "id": watch_id}


@router.post("/api/watches/{watch_id}/run")
def run_watch(watch_id: str) -> dict:
    """Run a watch: vegetation watches execute fetch_ndvi and log a receipt."""
    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, region_json, question, template FROM watches WHERE id = ?;",
            (watch_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="watch not found")
    template = str(row["template"] or "")
    question = str(row["question"] or "")
    region, window = _region_window(row)
    params: dict[str, Any] = {"region": region, "window": window, "aoi": region}
    if not _is_vegetation(template, question):
        params["template"] = "vegetation"
    try:
        result = fetch_ndvi(params)
    except Exception as exc:  # noqa: BLE001 - run never raises into the route layer
        error: dict[str, Any] = {"error": str(exc) or "fetch_ndvi failed"}
        receipt = _insert_receipt(watch_id, "fetch_ndvi", params, "", error)
        return {"ok": False, "error": error["error"], "receipts": [receipt]}
    receipt = _insert_receipt(
        watch_id,
        "fetch_ndvi",
        params,
        str(result.get("source_url", "")),
        result,
        plot_path="",
    )
    entry = {
        "tool": "fetch_ndvi",
        "source_url": receipt["source_url"],
        "data_hash": receipt["data_hash"],
        "plot_path": receipt["plot_path"],
        "token_usage": receipt["token_usage"],
        "id": receipt["id"],
    }
    return {"ok": True, "receipts": [entry]}
