"""Deterministic question-to-template matcher (keyword placeholder, no I/O)."""

from __future__ import annotations

TEMPLATES = frozenset(
    {
        "vegetation_decline",
        "flood_watch",
        "fire_watch",
        "drought_watch",
        "generic_observation",
    }
)

_VEGETATION_HINTS = ("vegetat", "ndvi", "declin", "crop", "maize", "forest")

_FLOOD_HINTS = ("flood", "inundat", "waterlog", "deluge")

_FIRE_HINTS = ("fire", "burn", "wildfire", "smoke")

_DROUGHT_HINTS = ("drought", "desertif", "dry spell", "rainfall", "precip")


def match_template(question: str) -> str:
    """Map a plain-English question to a template name (pure function)."""
    text = str(question or "").lower()
    if any(hint in text for hint in _VEGETATION_HINTS):
        return "vegetation_decline"
    if any(hint in text for hint in _FLOOD_HINTS):
        return "flood_watch"
    if any(hint in text for hint in _FIRE_HINTS):
        return "fire_watch"
    if any(hint in text for hint in _DROUGHT_HINTS):
        return "drought_watch"
    return "generic_observation"
