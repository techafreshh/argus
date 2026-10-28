"""Adapter package: typed fetch contract with cache/offline support."""

from argus.adapters.base import (
    CACHE_DIR,
    Adapter,
    FetchSpec,
    OfflineMissingFixture,
    TypedResult,
    cache_key,
    cache_path,
    is_offline,
    make_receipt,
    read_fixture,
    resolve_cache_dir,
    write_fixture,
)

__all__ = [
    "CACHE_DIR",
    "Adapter",
    "FetchSpec",
    "OfflineMissingFixture",
    "TypedResult",
    "cache_key",
    "cache_path",
    "is_offline",
    "make_receipt",
    "read_fixture",
    "resolve_cache_dir",
    "write_fixture",
]
