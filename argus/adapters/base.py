"""Typed adapter contract with file-tile cache and offline replay."""

from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class OfflineMissingFixture(Exception):
    """Raised when ARGUS_OFFLINE=1 and no cached fixture tile exists."""


@dataclass
class FetchSpec:
    """What to fetch: source name, area of interest, time window, extra params."""

    source: str = ""
    aoi: dict = field(default_factory=dict)
    window: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)


@dataclass
class TypedResult:
    """Typed outcome of an adapter fetch."""

    ok: bool
    data: bytes | None = None
    error: str | None = None
    receipt: dict = field(default_factory=dict)
    from_cache: bool = False
    cache_key: str = ""


def _repo_root() -> Path:
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        # ARGUS_FIXTURE_DIR points at the fixture root (contains cache/).
        return Path(override)
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "fixtures").is_dir() or (parent / "fixtures").exists():
            return parent
        if (parent / "pyproject.toml").is_file() and (parent / "argus").is_dir():
            return parent
    # Fallback: <repo>/ from argus/adapters/base.py.
    return here.parents[2]


def _cache_dir() -> Path:
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        return Path(override) / "cache"
    return _repo_root() / "fixtures" / "cache"


CACHE_DIR: Path = _cache_dir()


def resolve_cache_dir() -> Path:
    """Return the active fixture cache directory (honours ARGUS_FIXTURE_DIR)."""
    return _cache_dir()


def cache_key(source: str, aoi: dict, window: dict) -> str:
    """Full sha256 hex of canonical JSON over (source, aoi, window)."""
    canonical = json.dumps(
        {"source": source, "aoi": aoi, "window": window},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_path(key: str) -> Path:
    """Filesystem path of the tile for a cache key."""
    return resolve_cache_dir() / f"{key}.bin"


def is_offline() -> bool:
    """True when ARGUS_OFFLINE requests fixture-only reads."""
    return os.environ.get("ARGUS_OFFLINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def read_fixture(key: str) -> bytes | None:
    """Return cached tile bytes, or None when absent. Never creates dirs."""
    path = cache_path(key)
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        return None


def write_fixture(key: str, data: bytes) -> Path:
    """Persist tile bytes, creating parent dirs. Returns the tile path."""
    path = cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def make_receipt(params: dict, data: bytes) -> dict:
    """Receipt hook: records params and sha256 data hash (no I/O)."""
    return {
        "params": dict(params or {}),
        "data_hash": hashlib.sha256(data).hexdigest(),
    }


class Adapter(ABC):
    """Base class for data-source adapters.

    Subclasses implement only :meth:`fetch_live`; this class owns
    cache-key computation, fixture lookup, ARGUS_OFFLINE enforcement,
    cache writes, and receipt building.
    """

    @abstractmethod
    def fetch_live(self, spec: FetchSpec) -> bytes:
        """Fetch fresh payload bytes from the live source."""
        raise NotImplementedError

    def fetch(self, spec: FetchSpec) -> TypedResult:
        """Fetch a tile, honouring the file cache and offline mode."""
        key = cache_key(spec.source, spec.aoi, spec.window)
        params = dict(spec.params or {})

        if is_offline():
            cached = read_fixture(key)
            if cached is None:
                raise OfflineMissingFixture(f"OFFLINE missing fixture for key {key}")
            return TypedResult(
                ok=True,
                data=cached,
                error=None,
                receipt=make_receipt(params, cached),
                from_cache=True,
                cache_key=key,
            )

        cached = read_fixture(key)
        if cached is not None:
            return TypedResult(
                ok=True,
                data=cached,
                error=None,
                receipt=make_receipt(params, cached),
                from_cache=True,
                cache_key=key,
            )

        try:
            data = self.fetch_live(spec)
        except OfflineMissingFixture:
            raise
        except Exception as exc:  # noqa: BLE001 - adapters surface errors as data
            message = f"{exc}"
            if "OFFLINE" not in message.upper():
                message = f"{message}"
            return TypedResult(
                ok=False,
                data=None,
                error=message or "fetch failed",
                receipt={"params": params, "data_hash": None},
                from_cache=False,
                cache_key=key,
            )
        if not isinstance(data, (bytes, bytearray)):
            return TypedResult(
                ok=False,
                data=None,
                error=f"fetch_live must return bytes, got {type(data).__name__}",
                receipt={"params": params, "data_hash": None},
                from_cache=False,
                cache_key=key,
            )
        payload = bytes(data)
        write_fixture(key, payload)
        return TypedResult(
            ok=True,
            data=payload,
            error=None,
            receipt=make_receipt(params, payload),
            from_cache=False,
            cache_key=key,
        )
