"""Adapter package: typed fetch contract with cache/offline support."""

from argus.adapters import (
    chirps,
    gdelt,
    imagery,
    oisst,
    openmeteo,
    overpass,
    s1,
    s2,
    wikidata,
)
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
from argus.adapters.gdelt import GDELTAdapter, search_news
from argus.adapters.imagery import fetch_imagery
from argus.adapters.oisst import OISSTAdapter, fetch_sst
from argus.adapters.openmeteo import OpenMeteoAdapter, fetch_wind
from argus.adapters.overpass import OverpassAdapter
from argus.adapters.s1 import S1Adapter
from argus.adapters.s2 import S2Adapter
from argus.adapters.wikidata import WikidataAdapter

__all__ = [
    "CACHE_DIR",
    "Adapter",
    "CHIRPSAdapter",
    "FetchSpec",
    "GDELTAdapter",
    "OISSTAdapter",
    "OfflineMissingFixture",
    "OpenMeteoAdapter",
    "OverpassAdapter",
    "S1Adapter",
    "S2Adapter",
    "TypedResult",
    "WikidataAdapter",
    "cache_key",
    "cache_path",
    "chirps",
    "fetch_imagery",
    "fetch_rainfall",
    "fetch_sst",
    "fetch_wind",
    "gdelt",
    "imagery",
    "is_offline",
    "make_receipt",
    "oisst",
    "openmeteo",
    "overpass",
    "read_fixture",
    "resolve_cache_dir",
    "s1",
    "s2",
    "search_news",
    "wikidata",
    "write_fixture",
]
