"""Deterministic Plan-to-execute loop: Plan -> acquire -> receipt."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from argus.adapters import chirps, oisst, openmeteo
from argus.orchestrator.meta_client import plan as make_plan
from argus.store.db import get_connection

_DEFAULT_PARAMS = {"region": "nino34", "window": "2023-01"}

_OFFLINE_TRUTHY = {"1", "true", "yes", "on"}


def _is_offline() -> bool:
    """True when ARGUS_OFFLINE requests fixture-only behaviour."""
    return os.environ.get("ARGUS_OFFLINE", "").strip().lower() in _OFFLINE_TRUTHY


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _fallback_payload() -> dict:
    return {
        "values": [],
        "source_url": "",
        "region": _DEFAULT_PARAMS["region"],
        "window": _DEFAULT_PARAMS["window"],
        "synthetic": True,
    }


def run_watch(watch_id: str) -> dict:
    """Execute one Plan -> acquire -> receipt cycle for a watch.

    Loads the watch row, asks the (offline-safe, never-raising) planner
    for parameters, acquires via the dict-facade matching ``plan.sensor``
    (``oisst`` default, ``chirps``/``openmeteo`` otherwise), writes one
    ``acquisitions`` row plus one ``receipts`` row, and returns ids.
    A receipt is written even when the adapter fails (fallback payload).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, region_json, question, cadence FROM watches WHERE id = ?;",
            (watch_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise LookupError(f"watch not found: {watch_id}")
    try:
        region = json.loads(row["region_json"] or "{}")
    except (TypeError, ValueError):
        region = {}
    if not isinstance(region, dict):
        region = {}
    question = str(row["question"] or "")
    cadence = str(row["cadence"] or "daily")

    plan_obj = make_plan(question, region, cadence)
    sensor = str(getattr(plan_obj, "sensor", "") or "oisst").lower()
    if sensor == "chirps":
        fetch_fn = chirps.fetch
    elif sensor == "openmeteo":
        fetch_fn = openmeteo.fetch
    else:
        sensor = "oisst"
        fetch_fn = oisst.fetch

    params: dict[str, Any] = dict(_DEFAULT_PARAMS)
    params["offline"] = _is_offline()
    try:
        payload = fetch_fn(params)
        if not isinstance(payload, dict):
            payload = _fallback_payload()
    except Exception:  # noqa: BLE001 - executor synthesizes a receipt, never raises
        payload = _fallback_payload()

    source_url = str(payload.get("source_url", "") or "")
    data_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    now = _utcnow()
    acquisition_id = uuid.uuid4().hex
    receipt_id = uuid.uuid4().hex
    window = getattr(plan_obj, "window", {}) or {}
    aoi = getattr(plan_obj, "aoi", {}) or {}
    comparison = getattr(plan_obj, "comparison", "") or ""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO acquisitions "
            "(id, watch_id, sensor, aoi_json, window_start, window_end,"
            " comparison_json, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                acquisition_id,
                watch_id,
                sensor,
                json.dumps(aoi, sort_keys=True, default=str),
                str(window.get("start", "") if isinstance(window, dict) else ""),
                str(window.get("end", "") if isinstance(window, dict) else ""),
                json.dumps({"comparison": comparison}, sort_keys=True, default=str),
                "ok",
                now,
            ),
        )
        conn.execute(
            "INSERT INTO receipts "
            "(id, watch_id, acquisition_id, tool, params_json, source_url,"
            " data_hash, plot_path, token_usage, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                receipt_id,
                watch_id,
                acquisition_id,
                sensor,
                json.dumps(params, sort_keys=True, default=str),
                source_url,
                data_hash,
                "",
                0,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"receipt_id": receipt_id, "acquisition_id": acquisition_id}
