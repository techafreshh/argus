"""Planner-visible tool registry (name -> spec)."""

from __future__ import annotations

TOOL_REGISTRY: dict[str, dict] = {
    "fetch_sst": {
        "source": "oisst",
        "description": "Fetch sea-surface temperature tiles for an AOI and window.",
        "params": {"aoi": "dict", "window": "dict"},
    },
    "compute_oni": {
        "source": "oni",
        "description": "Compute the Oceanic Nino Index anomaly for a window.",
        "params": {"window": "dict", "region": "dict"},
    },
    "fetch_rainfall": {
        "source": "chirps",
        "description": "Fetch CHIRPS rainfall tiles for an AOI and window.",
        "params": {"aoi": "dict", "window": "dict"},
    },
    "fetch_ndvi": {
        "source": "ndvi",
        "description": "Fetch vegetation-index tiles for an AOI and window.",
        "params": {"aoi": "dict", "window": "dict"},
    },
    "fetch_burned_area": {
        "source": "burned-area",
        "description": "Fetch burned-area tiles for an AOI and window.",
        "params": {"aoi": "dict", "window": "dict"},
    },
    "fetch_active_fires": {
        "source": "active-fires",
        "description": "Fetch active-fire detections for an AOI and window.",
        "params": {"aoi": "dict", "window": "dict"},
    },
    "fetch_imagery": {
        "source": "imagery",
        "description": "Fetch optical imagery tiles for an AOI and window.",
        "params": {"aoi": "dict", "window": "dict"},
    },
    "cross_check": {
        "source": "cross-check",
        "description": "Cross-check independent sources before reporting.",
        "params": {"evidence": "dict"},
    },
    "segment_concept": {
        "source": "sam-3.1",
        "description": "Segment a noun-phrase concept into boxes plus masks.",
        "params": {"noun_phrase": "str", "image": "str|dict"},
    },
    "file_report": {
        "source": "report",
        "description": "File the final analyst report for a watch.",
        "params": {"watch_id": "str", "summary": "str"},
    },
}


def tool_names() -> list[str]:
    """Return the sorted names of all planner-visible tools."""
    return sorted(TOOL_REGISTRY)
