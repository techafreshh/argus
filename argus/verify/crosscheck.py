"""Pure-stdlib presence-gated verification scorer.

No alert may ship on imagery alone: confidence reaches the 85 queue
threshold only when at least two independent sources are present.
"""

from __future__ import annotations

from typing import Any

QUEUE_THRESHOLD = 85.0
SINGLE_SOURCE_CAP = 70.0

_NEGATION_TOKENS = ("no evidence", "refute", "refutes", "refuted", "disagree")


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("articles", "elements", "items", "results", "values"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
        return []
    return []


def _imagery_score(imagery: Any) -> tuple[float, bool]:
    if not isinstance(imagery, dict) or not imagery:
        return 0.0, False
    cloud_pct = _as_float(imagery.get("cloud_pct", 0.0), 0.0)
    if cloud_pct >= 80:
        base = 15.0
    elif cloud_pct >= 50:
        base = 35.0
    elif cloud_pct >= 20:
        base = 55.0
    else:
        base = 70.0
    boost = False
    if _as_float(imagery.get("z_score"), 0.0) >= 2 or _as_float(
        imagery.get("hectares"), 0.0
    ) > 0:
        boost = True
    else:
        for key in ("change", "anomaly", "event"):
            if key in imagery and imagery.get(key):
                boost = True
                break
    if boost:
        base = min(95.0, base + 15.0)
    return base, True


def _news_score(news: Any) -> tuple[float, bool]:
    articles: list = []
    if isinstance(news, list):
        articles = news
    elif isinstance(news, dict):
        raw = news.get("articles", news.get("items", news.get("results")))
        if isinstance(raw, list):
            articles = raw
        elif not news:
            return 0.0, False
        else:
            # Dict without an article list: treat non-empty as no articles.
            articles = []
    elif news:
        return 0.0, False
    else:
        return 0.0, False
    if not articles:
        return 0.0, False
    text = ""
    try:
        text = " ".join(str(a).lower() for a in articles)
    except Exception:  # noqa: BLE001 - scoring never raises
        text = ""
    if any(token in text for token in _NEGATION_TOKENS):
        return 20.0, True
    return min(95.0, 75.0 + 5.0 * len(articles)), True


def _context_score(context: Any) -> tuple[float, bool]:
    if not isinstance(context, dict) or not context:
        return 0.0, False
    elements = context.get("elements")
    has_osm = isinstance(elements, list) and len(elements) > 0
    entity = context.get("entity")
    has_wiki = isinstance(entity, dict) and len(entity) > 0
    if has_osm and has_wiki:
        return 90.0, True
    if has_osm or has_wiki:
        return 80.0, True
    # Any other non-empty context dict counts as weak presence.
    return 0.0, False


def cross_check(
    imagery: Any = None, news: Any = None, context: Any = None, **kwargs: Any
) -> dict:
    """Score imagery/news/context evidence into 0-100 confidence.

    Accepts ``cross_check(imagery, news, context)`` positionally or as a
    single ``evidence`` dict kwarg. Returns confidence, decision, sub-scores,
    sources present, agreement flag, and evidence echo.
    """
    if kwargs:
        if imagery is None and "imagery" in kwargs:
            imagery = kwargs["imagery"]
        if news is None and "news" in kwargs:
            news = kwargs["news"]
        if context is None and "context" in kwargs:
            context = kwargs["context"]
        if imagery is None and isinstance(kwargs.get("evidence"), dict):
            evidence_kw = kwargs["evidence"]
            imagery = evidence_kw.get("imagery")
            news = evidence_kw.get("news")
            context = evidence_kw.get("context")
    imagery = imagery if imagery is not None else {}
    news = news if news is not None else {}
    context = context if context is not None else {}

    imagery_score, imagery_present = _imagery_score(imagery)
    news_score, news_present = _news_score(news)
    context_score, context_present = _context_score(context)

    scores = {
        "imagery": imagery_score,
        "news": news_score,
        "context": context_score,
    }
    sources_present = sum(
        [imagery_present, news_present, context_present]
    )
    present_scores = [
        s
        for s, present in (
            (imagery_score, imagery_present),
            (news_score, news_present),
            (context_score, context_present),
        )
        if present
    ]
    if sources_present <= 1:
        best = max(present_scores) if present_scores else 0.0
        confidence = min(best, SINGLE_SOURCE_CAP)
    else:
        avg = sum(present_scores) / len(present_scores)
        if any(s < 30 for s in present_scores):
            confidence = min(avg, SINGLE_SOURCE_CAP)
        else:
            confidence = min(100.0, avg + 15.0)
    confidence = max(0.0, min(100.0, float(confidence)))
    agreement = sources_present >= 2 and all(
        s >= 30 for s in present_scores
    )
    decision = (
        "queued"
        if (confidence >= QUEUE_THRESHOLD and sources_present >= 2)
        else "ambiguity"
    )
    return {
        "confidence": confidence,
        "decision": decision,
        "scores": scores,
        "sources_present": sources_present,
        "agreement": agreement,
        "evidence": {
            "imagery": imagery,
            "news": news,
            "context": context,
        },
    }
