"""Eval package: fixture-driven honesty gates."""

from argus.eval.oni import (
    SUBWATCHERS,
    classify_phase,
    compute_own_oni,
    current_snapshot,
    find_analogs,
    load_official,
    pearson,
    phase_agreement,
)
from argus.eval.probes import run_eval

__all__ = [
    "SUBWATCHERS",
    "classify_phase",
    "compute_own_oni",
    "current_snapshot",
    "find_analogs",
    "load_official",
    "pearson",
    "phase_agreement",
    "run_eval",
]
