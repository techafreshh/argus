"""Fixed seven-pipeline template catalog (issue #9), compiled from the cookbook.

The operator cookbook (``argus/cookbook/recipes.json``) is the single source of
truth for language triggers, sensor pairing, and capability blurbs; this module
compiles it into the plain dict/tuple shape the deterministic router has always
consumed. Matching order is the cookbook order: specific pipelines first,
vegetation last, so broad decline language cannot shadow the more specific
pipelines.
"""

from __future__ import annotations

from argus.cookbook import load_recipes


def _compile() -> tuple[dict[str, dict[str, object]], tuple[str, ...]]:
    templates: dict[str, dict[str, object]] = {}
    names: list[str] = []
    for recipe in load_recipes():
        name = str(recipe["id"])
        templates[name] = {
            "keywords": tuple(str(k) for k in recipe.get("keywords", ())),
            "words": tuple(str(w) for w in recipe.get("words", ())),
            "sensor": str(recipe.get("sensor", "")),
            "blurb": str(recipe.get("blurb", "")),
        }
        names.append(name)
    return templates, tuple(names)


TEMPLATES, TEMPLATE_NAMES = _compile()
