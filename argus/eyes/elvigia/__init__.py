"""El Vigia: the ENSO watchman computing its own ONI."""

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

__all__ = [
    "classify_intensity",
    "classify_phase",
    "classify_trajectory",
    "compute_oni",
    "load_noaa_table",
    "pearson_corr",
    "phase_agreement_pct",
    "validate_against_noaa",
]
