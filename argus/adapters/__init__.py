"""Adapter package: typed fetch contract with cache/offline support."""

from argus.adapters import (
    chirps,
    era5,
    firms,
    gdelt,
    geocode,
    imagery,
    mem0_client,
    modis_burned,
    oisst,
    openmeteo,
    overpass,
    s1,
    s2,
    s5p,
    viirs,
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
from argus.adapters.era5 import ERA5Adapter, fetch_wind_era5
from argus.adapters.firms import FIRMSAdapter, fetch_fires
from argus.adapters.gdelt import GDELTAdapter, search_news
from argus.adapters.imagery import fetch_imagery
from argus.adapters.mem0_client import remember, search_memories
from argus.adapters.modis_burned import MODISBurnedAdapter, fetch_burned
from argus.adapters.oisst import OISSTAdapter, fetch_sst
from argus.adapters.openmeteo import OpenMeteoAdapter, fetch_wind
from argus.adapters.overpass import OverpassAdapter
from argus.adapters.s1 import S1Adapter
from argus.adapters.s2 import S2Adapter
from argus.adapters.s5p import S5PAdapter, fetch_aerosol
from argus.adapters.viirs import VIIRSAdapter, fetch_lights
from argus.adapters.webhook_client import deliver as deliver_webhook
from argus.adapters.wikidata import WikidataAdapter

__all__ = [
    "CACHE_DIR",
    "Adapter",
    "CHIRPSAdapter",
    "ERA5Adapter",
    "FIRMSAdapter",
    "FetchSpec",
    "GDELTAdapter",
    "MODISBurnedAdapter",
    "OISSTAdapter",
    "OfflineMissingFixture",
    "OpenMeteoAdapter",
    "OverpassAdapter",
    "S1Adapter",
    "S2Adapter",
    "S5PAdapter",
    "TypedResult",
    "VIIRSAdapter",
    "WikidataAdapter",
    "cache_key",
    "cache_path",
    "chirps",
    "deliver_webhook",
    "era5",
    "fetch_aerosol",
    "fetch_burned",
    "fetch_fires",
    "fetch_imagery",
    "fetch_lights",
    "fetch_rainfall",
    "fetch_sst",
    "fetch_wind",
    "fetch_wind_era5",
    "firms",
    "gdelt",
    "geocode",
    "imagery",
    "is_offline",
    "make_receipt",
    "mem0_client",
    "modis_burned",
    "oisst",
    "openmeteo",
    "overpass",
    "read_fixture",
    "remember",
    "resolve_cache_dir",
    "s1",
    "s2",
    "s5p",
    "search_memories",
    "search_news",
    "viirs",
    "webhook_client",
    "wikidata",
    "write_fixture",
]
