"""El Vigia: the ENSO watchman computing its own ONI."""

from argus.eyes.elvigia.analog import (
    current_vector_for,
    find_analogs,
    latest_state,
    load_states,
)
from argus.eyes.elvigia.oni import (
    classify_intensity,
    classify_phase,
    classify_trajectory,
    compute_oni,
    load_noaa_table,
    pearson_corr,
    phase_agreement_pct,
    validate_against_noaa,
)
from argus.eyes.elvigia.selfcheck import self_check
from argus.eyes.elvigia.subwatchers import active_watchers, for_phase

__all__ = [
    "active_watchers",
    "classify_intensity",
    "classify_phase",
    "classify_trajectory",
    "compute_oni",
    "current_vector_for",
    "find_analogs",
    "for_phase",
    "latest_state",
    "load_noaa_table",
    "load_states",
    "pearson_corr",
    "phase_agreement_pct",
    "self_check",
    "validate_against_noaa",
]
