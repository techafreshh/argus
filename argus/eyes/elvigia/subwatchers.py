"""Phase-keyed sub-watcher reconfiguration for El Vigia.

Each ocean phase visibly re-targets the watcher fleet: El Nino watches
Southern-Africa drought plus East-African short rains, La Nina flips to
Southern-Africa flood/vegetation plus West-Pacific rains, Neutral keeps a
generic pair. El Nino and La Nina region-id sets are disjoint so a phase
flip is always observable. Never raises.
"""

from __future__ import annotations

from typing import Any

_PHASE_ALIASES = {
    "elnino": "el_nino",
    "elnina": "la_nina",
    "lanina": "la_nina",
    "el_nino": "el_nino",
    "la_nina": "la_nina",
    "neutral": "neutral",
    "neutro": "neutral",
}

_WATCHERS: dict[str, list[dict[str, str]]] = {
    "el_nino": [
        {
            "id": "drought-southern-africa",
            "region": "southern_africa",
            "phenomenon": "rainfall_deficit",
            "sensor": "chirps",
            "cadence": "daily",
        },
        {
            "id": "short-rains-east-africa",
            "region": "east_africa",
            "phenomenon": "short_rains",
            "sensor": "chirps",
            "cadence": "daily",
        },
    ],
    "la_nina": [
        {
            "id": "flood-southern-africa",
            "region": "southern_africa",
            "phenomenon": "vegetation",
            "sensor": "s2",
            "cadence": "weekly",
        },
        {
            "id": "rain-west-pacific",
            "region": "west_pacific",
            "phenomenon": "rainfall_surplus",
            "sensor": "chirps",
            "cadence": "daily",
        },
    ],
    "neutral": [
        {
            "id": "oni-nino34",
            "region": "nino34",
            "phenomenon": "nino34_sst",
            "sensor": "oisst",
            "cadence": "weekly",
        },
        {
            "id": "seasonal-outlook-tropics",
            "region": "tropics",
            "phenomenon": "seasonal_outlook",
            "sensor": "openmeteo",
            "cadence": "weekly",
        },
    ],
}


def normalize_phase(phase: Any) -> str:
    """Map CPC display/alias forms to the canonical ``el_nino`` key."""
    text = str(phase or "").strip().lower().replace("_", " ").replace("-", " ")
    squashed = text.replace(" ", "")
    if squashed in _PHASE_ALIASES:
        return _PHASE_ALIASES[squashed]
    # CPC display forms ("El Nino", "La Nina") squash to the same keys.
    return _PHASE_ALIASES.get(squashed, "neutral")


def for_phase(phase: Any) -> list[dict]:
    """Return the >=2 watcher dicts armed for the given ocean phase."""
    key = normalize_phase(phase)
    return [dict(entry) for entry in _WATCHERS.get(key, _WATCHERS["neutral"])]


def active_watchers(phase: Any = "Neutral") -> list[dict]:
    """Return the watcher set for the current (or given) phase."""
    return for_phase(phase)
