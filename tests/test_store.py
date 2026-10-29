import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from argus.server.app import app
from argus.store.db import get_connection, init_db
from argus.store.schema import SCHEMA_VERSION

EXPECTED_TABLES = {
    "watches",
    "acquisitions",
    "receipts",
    "alerts",
    "predictions",
    "meta_spend",
    "reports",
}


def _client() -> TestClient:
    return TestClient(app)


def _tables(path: Path) -> set[str]:
    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def test_schema_version_is_two() -> None:
    assert SCHEMA_VERSION == 2


def test_init_creates_all_tables(tmp_path: Path) -> None:
    db = tmp_path / "argus.db"
    init_db(db)
    assert EXPECTED_TABLES <= _tables(db)


def test_wal_mode(tmp_path: Path) -> None:
    db = tmp_path / "argus.db"
    init_db(db)
    conn = get_connection(db)
    try:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert str(mode).lower() == "wal"
    finally:
        conn.close()


def test_init_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "argus.db"
    init_db(db)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO watches (id, name, region_json, question, template,"
        " cadence, status, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("w1", "n", "{}", "q", "t", "daily", "active", "2026-01-01T00:00:00Z",
         "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    init_db(db)
    assert EXPECTED_TABLES <= _tables(db)
    conn = sqlite3.connect(str(db))
    try:
        count = conn.execute("SELECT COUNT(*) FROM watches").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def test_healthz_still_ok() -> None:
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
