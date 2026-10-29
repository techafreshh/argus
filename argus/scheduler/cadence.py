"""Cadence tiers plus threshold heat-up and the in-process APScheduler."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from argus.store.db import get_connection, init_db

CADENCE_INTERVALS = {"daily": 86400, "weekly": 604800}
HEATUP_THRESHOLD = 2.0
HEATUP_FACTOR = 0.5
TICK_SECONDS = 60

_SCHEDULER: Any = None


def interval_for(cadence: str) -> int:
    """Return the base interval in seconds for a tier; raise on unknown tiers."""
    try:
        return CADENCE_INTERVALS[cadence]
    except KeyError:
        raise ValueError(f"cadence must be one of {sorted(CADENCE_INTERVALS)}") from None


def should_heat_up(z_score: float) -> bool:
    """Decide heat-up from a signal z-score; unparseable input never heats."""
    try:
        z = float(z_score)
    except (TypeError, ValueError):
        return False
    return math.isfinite(z) and abs(z) >= HEATUP_THRESHOLD


def effective_interval(cadence: str, z_score: float = 0.0) -> int:
    """Return the tier interval, halved while the signal breaches the threshold."""
    base = interval_for(cadence)
    if should_heat_up(z_score):
        return int(base * HEATUP_FACTOR)
    return base


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        try:
            parsed = datetime.fromtimestamp(float(value), UTC)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _signal_params(watch_row: Any) -> dict:
    params: dict[str, Any] = {"region": "test-aoi", "window": "2024-01"}
    try:
        stored = json.loads(watch_row["region_json"] or "{}")
    except (TypeError, ValueError):
        return params
    if not isinstance(stored, dict):
        return params
    region = stored.get("region", stored.get("name"))
    if isinstance(region, str) and region:
        params["region"] = region
    aoi = stored.get("aoi")
    if isinstance(aoi, dict):
        for key in ("region", "name"):
            if isinstance(aoi.get(key), str) and aoi[key]:
                params["region"] = aoi[key]
                break
    window = stored.get("window", stored.get("month"))
    if isinstance(window, dict):
        window = window.get("window") or window.get("month") or window.get("start")
    if isinstance(window, str) and window:
        params["window"] = window[:7] if len(window) >= 7 and window[4] == "-" else window
    return params


def _heat_z(watch_row: Any) -> float:
    """Best-effort heat-up signal for a watch row; 0.0 when unavailable."""
    try:
        from argus.analysis.ndvi import fetch_ndvi

        z = float(fetch_ndvi(_signal_params(watch_row)).get("z_score", 0.0))
    except Exception:  # noqa: BLE001 - scan degrades to the base interval
        return 0.0
    return z if math.isfinite(z) else 0.0


def _scan_dict(row: Any) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "question": row["question"],
        "template": row["template"],
        "cadence": row["cadence"],
        "status": row["status"],
        "updated_at": row["updated_at"],
    }


def due_watches(now: datetime | str | float | None = None) -> list[dict]:
    """Return active watches due for a run, stalest first.

    A watch with a missing (or unparseable) ``updated_at`` is always due;
    otherwise it is due once the heat-up-adjusted tier interval has elapsed
    since the last run.
    """
    init_db()
    moment = _parse_time(now) or datetime.now(UTC)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, region_json, question, template, cadence, status,"
            " created_at, updated_at FROM watches WHERE status = 'active'"
            " ORDER BY CASE WHEN updated_at IS NULL OR updated_at = ''"
            " THEN 0 ELSE 1 END, updated_at ASC, rowid ASC;"
        ).fetchall()
    finally:
        conn.close()
    due: list[dict] = []
    for row in rows:
        last = _parse_time(row["updated_at"])
        if last is None:
            due.append(_scan_dict(row))
            continue
        try:
            interval = effective_interval(str(row["cadence"] or "daily"), _heat_z(row))
        except ValueError:
            due.append(_scan_dict(row))
            continue
        if (moment - last).total_seconds() >= interval:
            due.append(_scan_dict(row))
    return due


def tick() -> int:
    """Run every due watch once in-process; never raises into the scheduler."""
    try:
        watches = due_watches()
    except Exception:  # noqa: BLE001 - a failed scan is an empty tick, not a crash
        return 0
    # Local import: the run path lives in the route layer and must stay
    # importable without pulling the scheduler into the server modules.
    from argus.server.routes_watches import run_watch as _run_watch

    ran = 0
    for watch in watches:
        watch_id = str(watch["id"])
        try:
            _run_watch(watch_id)
            ran += 1
        except Exception:  # noqa: BLE001, S112 - one failing watch never blocks the rest
            continue
        finally:
            try:
                conn = get_connection()
                try:
                    conn.execute(
                        "UPDATE watches SET updated_at = ? WHERE id = ?;",
                        (_utcnow(), watch_id),
                    )
                    conn.commit()
                finally:
                    conn.close()
            except Exception:  # noqa: BLE001, S110 - bookkeeping never fails the tick
                pass
    return ran


def start_scheduler(interval_seconds: int = TICK_SECONDS) -> Any:
    """Start the single in-process interval job; double-start returns the first."""
    global _SCHEDULER
    if _SCHEDULER is not None:
        return _SCHEDULER
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError as exc:
        raise RuntimeError("apscheduler is not installed") from exc
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        tick,
        "interval",
        seconds=int(interval_seconds),
        id="argus-tick",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _SCHEDULER = scheduler
    return scheduler


def stop_scheduler() -> None:
    """Shut the scheduler down; safe to call twice or before any start."""
    global _SCHEDULER
    scheduler, _SCHEDULER = _SCHEDULER, None
    if scheduler is None:
        return
    try:
        scheduler.shutdown(wait=False)
    except Exception:  # noqa: BLE001, S110 - shutdown is best-effort
        pass
