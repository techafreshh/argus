"""Adapter package: typed fetch contract with cache/offline support."""

from argus.adapters import chirps, oisst, openmeteo
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
from argus.adapters.chirps import CHIRPSAdapter, fetch_rainfall
from argus.adapters.oisst import OISSTAdapter, fetch_sst
from argus.adapters.openmeteo import OpenMeteoAdapter, fetch_wind

__all__ = [
    "CACHE_DIR",
    "Adapter",
    "CHIRPSAdapter",
    "FetchSpec",
    "OISSTAdapter",
    "OfflineMissingFixture",
    "OpenMeteoAdapter",
    "TypedResult",
    "cache_key",
    "cache_path",
    "chirps",
    "fetch_rainfall",
    "fetch_sst",
    "fetch_wind",
    "is_offline",
    "make_receipt",
    "oisst",
    "openmeteo",
    "read_fixture",
    "resolve_cache_dir",
    "write_fixture",
]
