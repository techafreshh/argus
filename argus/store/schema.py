"""Canonical schema definition for the ARGUS SQLite store."""

from pathlib import Path

SCHEMA_VERSION = 1

_MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def get_migrations() -> list[tuple[int, Path]]:
    """Return sorted (version, path) pairs for versioned migration files."""
    out: list[tuple[int, Path]] = []
    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        try:
            version = int(path.stem.split("_")[0])
        except (ValueError, IndexError):
            continue
        out.append((version, path))
    return sorted(out)


def _load_initial_ddl() -> str:
    path = _MIGRATIONS_DIR / "0001_initial.sql"
    return path.read_text(encoding="utf-8")


INITIAL_DDL = _load_initial_ddl()
