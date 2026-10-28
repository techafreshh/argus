"""El Vigia ONI engine contract: correlation, agreement, timing, units."""

from __future__ import annotations

import math
import time

from argus.eyes.elvigia.oni import (
    classify_phase,
    compute_oni,
    load_noaa_table,
    validate_against_noaa,
)


def _fixture_series():
    table = load_noaa_table()
    rows = [{"month": row["month"], "sst": row["sst"]} for row in table]
    noaa = [row["noaa_oni"] for row in table]
    return table, rows, noaa


def test_compute_oni_matches_noaa_table():
    table, rows, noaa = _fixture_series()
    assert len(table) >= 480
    start = time.monotonic()
    result = compute_oni(rows)
    elapsed = time.monotonic() - start
    assert elapsed < 10.0
    rail = validate_against_noaa(result["oni"], noaa)
    assert rail["correlation"] >= 0.99
    assert rail["phase_agreement_pct"] >= 95.0


def test_compute_oni_accepts_bare_floats_with_default_start():
    _, rows, noaa = _fixture_series()
    result = compute_oni([row["sst"] for row in rows])
    assert result["months"][0] == "1982-01"
    rail = validate_against_noaa(result["oni"], noaa)
    assert rail["correlation"] >= 0.99


def test_first_two_oni_entries_are_none():
    result = compute_oni([27.0, 27.1, 27.2, 27.3])
    assert result["oni"][0] is None
    assert result["oni"][1] is None
    assert result["oni"][2] is not None


def test_classify_phase_thresholds():
    assert classify_phase(0.6) == "El Nino"
    assert classify_phase(-0.6) == "La Nina"
    assert classify_phase(0.0) == "Neutral"
    assert classify_phase(0.5) == "El Nino"
    assert classify_phase(-0.5) == "La Nina"
    assert classify_phase(0.49) == "Neutral"
    assert classify_phase(None) == "Neutral"


def test_rail_never_returns_nan_or_none():
    rail = validate_against_noaa([None, None], [None, None])
    assert isinstance(rail["correlation"], float) and math.isfinite(rail["correlation"])
    assert isinstance(rail["phase_agreement_pct"], float)
    rail = validate_against_noaa([1.0, 1.0], [1.0, 1.0])
    assert rail["correlation"] == 1.0
