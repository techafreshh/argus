"""Deterministic keyword router over the fixed template catalog (issue #9).

Pure functions, stdlib only, no I/O: safe to call offline, keyless,
and over spend cap. ``keywords`` match as raw substrings (safe stems
and phrases); ``words`` match whole tokens only, so risky bare words
such as "fire" or "port" cannot misfire inside "ceasefire" or
"transport". Abstention strings are fixed digit-free constants, so an
unrouted answer can never carry a fabricated measurement.
"""

from __future__ import annotations

import re

from argus.orchestrator.templates import TEMPLATE_NAMES, TEMPLATES

ANSWER_UNROUTED = "No pipeline covers this."

MISSING_GAPS: tuple[str, ...] = (
    "No catalog pipeline measures the requested phenomenon.",
    "No sensor tasking is available for this question type.",
    "No baseline archive supports comparison for this request.",
)

ADJACENT_FALLBACK: tuple[str, ...] = (
    "drought",
    "flooding",
    "vegetation_decline",
)

_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(filter(None, _TOKEN_RE.sub(" ", text).split(" ")))


def route(question: object) -> dict:
    """Map a plain-English question to a catalog template (pure function)."""
    text = str(question or "").lower()
    tokens = _tokens(text)
    for name in TEMPLATE_NAMES:
        entry = TEMPLATES[name]
        keywords = entry["keywords"]
        assert isinstance(keywords, tuple)
        if any(hint in text for hint in keywords):
            adjacent = [other for other in TEMPLATE_NAMES if other != name]
            return {"template": name, "adjacent": adjacent, "missing": []}
        words = entry["words"]
        assert isinstance(words, tuple)
        if words and not tokens.isdisjoint(words):
            adjacent = [other for other in TEMPLATE_NAMES if other != name]
            return {"template": name, "adjacent": adjacent, "missing": []}
    return {
        "template": None,
        "adjacent": list(ADJACENT_FALLBACK),
        "missing": list(MISSING_GAPS),
    }


def abstain_receipt(question: object) -> dict:
    """Build the honest missing-data receipt (fixed digit-free strings)."""
    _ = question
    return {
        "answer": ANSWER_UNROUTED,
        "missing": list(MISSING_GAPS),
        "adjacent": list(ADJACENT_FALLBACK),
    }
