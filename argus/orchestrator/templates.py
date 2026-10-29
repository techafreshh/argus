"""Fixed seven-pipeline template catalog (issue #9).

Single source of truth for plain-English question routing. Each entry
holds substring keyword hints, whole-word hints, the backing
sensor/tool name, and a one-line capability blurb. Matching order is
:const:`TEMPLATE_NAMES`; vegetation sits last so broad decline
language cannot shadow the more specific pipelines.
"""

from __future__ import annotations

TEMPLATES: dict[str, dict[str, object]] = {
    "ship_presence": {
        "keywords": (
            "vessel",
            "boat",
            "tanker",
            "harbor",
            "harbour",
            "seaport",
            "ferry",
            "port traffic",
            "port activity",
            "container ship",
        ),
        "words": ("ship", "ships", "shipping"),
        "sensor": "s1",
        "blurb": "Find vessels and port activity in coastal waters.",
    },
    "fire_anomaly": {
        "keywords": (
            "wildfire",
            "wild fire",
            "burn scar",
            "burned area",
            "active fire",
            "fire anomaly",
            "thermal anomaly",
        ),
        "words": ("fire", "fires", "burning"),
        "sensor": "s2",
        "blurb": "Spot burn scars and active thermal anomalies.",
    },
    "flooding": {
        "keywords": (
            "flood",
            "inundat",
            "waterlog",
            "deluge",
            "river overflow",
            "flash flood",
        ),
        "words": (),
        "sensor": "s1",
        "blurb": "Detect surface-water expansion after heavy rain.",
    },
    "drought": {
        "keywords": (
            "drought",
            "desertif",
            "dry spell",
            "rainfall deficit",
            "precipitation deficit",
            "soil moisture",
        ),
        "words": ("arid",),
        "sensor": "chirps",
        "blurb": "Watch rainfall deficits and soil drying.",
    },
    "reservoir_change": {
        "keywords": (
            "reservoir",
            "dam level",
            "lake level",
            "water storage",
            "impoundment",
            "dam storage",
        ),
        "words": ("dam",),
        "sensor": "s1",
        "blurb": "Measure reservoir and lake surface change.",
    },
    "dust_risk": {
        "keywords": (
            "dust storm",
            "sandstorm",
            "haboob",
            "dust plume",
            "aerosol optical",
            "dust risk",
        ),
        "words": ("dust", "dusty", "sandstorm", "pm10"),
        "sensor": "openmeteo",
        "blurb": "Flag dust plumes and hazy air intrusions.",
    },
    "vegetation_decline": {
        "keywords": (
            "vegetat",
            "ndvi",
            "deforest",
            "forest loss",
            "forest cover",
            "crop health",
            "crop loss",
            "crop failure",
            "yield loss",
            "yield decline",
            "chlorophyll",
            "leaf area",
            "greenness",
            "dieback",
            "defoliat",
        ),
        "words": (),
        "sensor": "s2",
        "blurb": "Track greenness loss across seasons.",
    },
}

# Deterministic matching order: specific pipelines first, vegetation last.
TEMPLATE_NAMES: tuple[str, ...] = (
    "ship_presence",
    "fire_anomaly",
    "flooding",
    "drought",
    "reservoir_change",
    "dust_risk",
    "vegetation_decline",
)
