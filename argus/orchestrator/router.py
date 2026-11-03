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

from argus.cookbook import recipe_for
from argus.orchestrator.templates import TEMPLATE_NAMES, TEMPLATES

ANSWER_UNROUTED = "No pipeline covers this."

# Conversational replies for non-measurement turns: greetings, app questions,
# thanks. Fixed digit-free constants describing the app itself — they never
# claim a measurement, so the never-fabricate gate holds by construction.
SMALLTALK_GREETING = (
    "Hey! I'm ARGUS, an autonomous analyst watching the planet from orbit. "
    "Tell me a place and a worry — 'is the Niger delta flooding?', 'is vegetation "
    "declining in the maize belt?'. I'll run the pipeline, verify against "
    "baselines, and queue an alert for your approval. Or ask 'what can you do' "
    "for the full tour."
)

SMALLTALK_CAPABILITIES = (
    "I'm ARGUS — I measure the Earth instead of taking headlines at face value. "
    "Today I can: compute the El Nino / La Nina index myself from NOAA OISST and "
    "find the closest analog years in the historical record; watch African fire "
    "regimes against long MODIS baselines; and route plain-English questions "
    "through cookbook recipes — flooding, vegetation decline, drought, fire, "
    "dust, water change. Every run leaves receipts: source, parameters, data "
    "hashes. Outbound alerts always wait for your approval. Ask me about any "
    "region — e.g. 'is the Niger delta flooding?' — and anything I cannot "
    "measure, I say so instead of guessing."
)

SMALLTALK_THANKS = (
    "Anytime. I keep watching while you're away — anything that crosses a "
    "threshold waits in the approval queue with its receipts."
)

_CAPABILITY_PHRASES: tuple[str, ...] = (
    "what can you do",
    "what can i do",
    "who are you",
    "what are you",
    "what is this app",
    "what is argus",
    "what do you do",
    "how do you work",
    "how does this work",
    "what do you measure",
    "what can i ask",
    "dashboard",
    "sections of",
    "this app",
    "this site",
    "this chat",
    "this room",
    "this tool",
)

_GREETING_WORDS = frozenset(
    {
        "hi",
        "hey",
        "hello",
        "yo",
        "hola",
        "sup",
        "greetings",
        "morning",
        "afternoon",
        "evening",
        "there",
        "bot",
        "agent",
        "argus",
        "team",
        "folks",
    }
)

_THANKS_WORDS = frozenset(
    {
        "thanks",
        "thank",
        "thx",
        "ty",
        "cheers",
        "nice",
        "cool",
        "awesome",
        "great",
    }
)


def smalltalk_reply(question: object) -> str | None:
    """Conversational reply for non-measurement turns, else None (pure function).

    Consulted only after the template catalog fails to route, so a greeting
    piggybacked on a real question never hijacks the pipeline.
    """
    text = str(question or "").strip().lower()
    if not text:
        return None
    if any(phrase in text for phrase in _CAPABILITY_PHRASES):
        return SMALLTALK_CAPABILITIES
    tokens = _tokens(text)
    if not tokens:
        return None
    if "help" in tokens and len(tokens) <= 2:
        return SMALLTALK_CAPABILITIES
    if any(f"good {part}" in text for part in ("morning", "afternoon", "evening")):
        return SMALLTALK_GREETING
    if tokens <= _GREETING_WORDS:
        return SMALLTALK_GREETING
    if tokens <= _THANKS_WORDS:
        return SMALLTALK_THANKS
    return None

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
            return _routed(name, tokens)
        words = entry["words"]
        assert isinstance(words, tuple)
        if words and not tokens.isdisjoint(words):
            return _routed(name, tokens)
    return {
        "template": None,
        "adjacent": list(ADJACENT_FALLBACK),
        "missing": list(MISSING_GAPS),
        "recipe_id": None,
        "recipe_title": None,
    }


def _routed(name: str, tokens: set[str]) -> dict:
    """Routed result citing the cookbook recipe that backs the template."""
    recipe = recipe_for(name)
    return {
        "template": name,
        "adjacent": [other for other in TEMPLATE_NAMES if other != name],
        "missing": [],
        "recipe_id": name if recipe else None,
        "recipe_title": str(recipe["title"]) if recipe else None,
    }


def abstain_receipt(question: object) -> dict:
    """Build the honest missing-data receipt (fixed digit-free strings)."""
    _ = question
    return {
        "answer": ANSWER_UNROUTED,
        "missing": list(MISSING_GAPS),
        "adjacent": list(ADJACENT_FALLBACK),
    }
