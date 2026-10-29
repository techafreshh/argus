"""Issue #10: cadence tiers, heat-up threshold/halving, due-scan ordering."""

import json
import uuid
from datetime import UTC, datetime

import pytest

from argus.scheduler import cadence as cadence_mod
from argus.scheduler.cadence import (
    due_watches,
    effective_interval,
    interval_for,
    should_heat_up,
    start_scheduler,
    stop_scheduler,
    tick,
)
from argus.store.db import get_connection, init_db


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the SQLite store at a fresh temp file for every test."""
    monkeypatch.setenv("ARGUS_DB_PATH", str(tmp_path / "cadence.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    init_db()
    yield


def _insert_watch(name, updated_at, status="active", cadence_name="daily"):
    watch_id = uuid.uuid4().hex
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO watches "
            "(id, name, region_json, question, template, cadence, status,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                watch_id,
                name,
                json.dumps({"region": "test-aoi", "window": "2024-01"}),
                "Is vegetation declining?",
                "vegetation_decline",
                cadence_name,
                status,
                updated_at,
                updated_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return watch_id


def test_interval_for_tiers():
    assert interval_for("daily") == 86400
    assert interval_for("weekly") == 604800


def test_interval_for_unknown_raises():
    with pytest.raises(ValueError):
        interval_for("hourly")


def test_should_heat_up_threshold():
    assert should_heat_up(0.0) is False
    assert should_heat_up(1.99) is False
    assert should_heat_up(-1.99) is False
    assert should_heat_up(2.0) is True
    assert should_heat_up(-2.5) is True


def test_effective_interval_halves_when_hot():
    assert effective_interval("daily", 0.0) == 86400
    assert effective_interval("daily", 2.5) == 43200
    assert effective_interval("weekly", 0.0) == 604800
    assert effective_interval("weekly", -3.0) == 302400


def test_due_scan_returns_stalest_first():
    old = _insert_watch("old", "2020-01-01T00:00:00+00:00")
    older = _insert_watch("older", "2019-01-01T00:00:00+00:00")
    fresh = _insert_watch("fresh", datetime.now(UTC).isoformat())
    due = due_watches(datetime.now(UTC))
    ids = [w["id"] for w in due]
    assert older in ids and old in ids
    assert fresh not in ids
    assert ids.index(older) < ids.index(old)


def test_missing_updated_at_is_due():
    watch_id = _insert_watch("missing", "")
    due = due_watches(datetime.now(UTC))
    assert any(w["id"] == watch_id for w in due)


def test_inactive_watch_never_due():
    watch_id = _insert_watch("paused", "2019-01-01T00:00:00+00:00", status="paused")
    due = due_watches(datetime.now(UTC))
    assert all(w["id"] != watch_id for w in due)


def test_tick_runs_stale_watch_and_refreshes():
    watch_id = _insert_watch("stale", "2019-01-01T00:00:00+00:00")
    assert tick() >= 1
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT updated_at FROM watches WHERE id = ?;", (watch_id,)
        ).fetchone()
        alerts = conn.execute(
            "SELECT id, status FROM alerts WHERE watch_id = ?;", (watch_id,)
        ).fetchall()
    finally:
        conn.close()
    assert row["updated_at"] != "2019-01-01T00:00:00+00:00"
    assert len(alerts) >= 1
    assert all(a["status"] == "queued" for a in alerts)


def test_scheduler_start_stop_guards_double_start():
    try:
        first = start_scheduler()
        assert start_scheduler() is first
    finally:
        stop_scheduler()
        stop_scheduler()
    assert cadence_mod._SCHEDULER is None
