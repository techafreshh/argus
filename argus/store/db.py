"""SQLite connection and migration helpers (stdlib sqlite3 only)."""

import os
import sqlite3
from pathlib import Path

from argus.store.schema import SCHEMA_VERSION, get_migrations

DEFAULT_DB_PATH = Path("data/argus.db")
ENV_VAR = "ARGUS_DB_PATH"


def resolve_db_path(path: str | Path | None = None) -> Path:
    """Resolve the database file path, creating parent dirs as needed."""
    if path is not None:
        resolved = Path(path)
    else:
        override = os.environ.get(ENV_VAR)
        resolved = Path(override) if override else DEFAULT_DB_PATH
    if str(resolved) != ":memory:":
        resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def get_connection(path: str | Path | None = None) -> sqlite3.Connection:
    """Open a short-lived connection with WAL mode and FK enforcement."""
    resolved = resolve_db_path(path)
    conn = sqlite3.connect(str(resolved), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version;").fetchone()
    return int(row[0]) if row else 0


def init_db(path: str | Path | None = None) -> Path:
    """Apply pending migrations idempotently; safe to call twice."""
    resolved = resolve_db_path(path)
    conn = get_connection(resolved)
    try:
        current = _current_version(conn)
        for version, mig_path in get_migrations():
            if version > current:
                conn.executescript(mig_path.read_text(encoding="utf-8"))
                conn.execute(f"PRAGMA user_version = {version};")
        # Clamp user_version forward even if no migration files matched.
        if _current_version(conn) < SCHEMA_VERSION:
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
        conn.commit()
    finally:
        conn.close()
    return resolved
