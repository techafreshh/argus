"""Operator cookbook: auditable recipes mapping questions to geospatial pipelines.

Each entry in ``recipes.json`` declares the language triggers, backing sensor,
analysis and verification steps, alert threshold, demo region preset, and known
pitfalls for one pipeline. The router catalog (``orchestrator/templates.py``)
is compiled from this file, so every routed plan can cite the recipe it
followed — and a question matching no recipe abstains honestly.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

_REQUIRED_KEYS = ("id", "title", "blurb", "sensor", "region_preset")


@lru_cache(maxsize=1)
def load_recipes() -> tuple[dict[str, Any], ...]:
    """Load and validate the cookbook recipes (import-once, cached)."""
    raw = (
        resources.files("argus.cookbook").joinpath("recipes.json").read_text("utf-8")
    )
    data = json.loads(raw)
    recipes = data.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        raise ValueError("cookbook recipes.json must hold a non-empty recipes list")
    seen: set[str] = set()
    for recipe in recipes:
        if not isinstance(recipe, dict):
            raise ValueError("cookbook recipes must be objects")  # noqa: TRY004
        missing = [key for key in _REQUIRED_KEYS if not recipe.get(key)]
        if missing:
            raise ValueError(f"recipe missing keys {missing}: {recipe.get('id')}")
        if recipe["id"] in seen:
            raise ValueError(f"duplicate cookbook recipe id: {recipe['id']}")
        seen.add(str(recipe["id"]))
    return tuple(recipes)


def recipe_map() -> dict[str, dict[str, Any]]:
    """Recipe id -> recipe dict, in deterministic catalog order."""
    return {str(recipe["id"]): recipe for recipe in load_recipes()}


def recipe_for(template: str | None) -> dict[str, Any] | None:
    """The recipe backing a routed template name, or None."""
    if not template:
        return None
    return recipe_map().get(str(template))


def preset_catalog() -> list[dict[str, Any]]:
    """Public preset shape for onboarding/watchlist: one-click cookbook watches."""
    presets: list[dict[str, Any]] = []
    for recipe in load_recipes():
        region = recipe.get("region_preset")
        if not isinstance(region, dict):
            continue
        presets.append(
            {
                "id": str(recipe["id"]),
                "title": str(recipe["title"]),
                "blurb": str(recipe["blurb"]),
                "sensor": str(recipe["sensor"]),
                "question": str(recipe.get("question", "")),
                "cadence": str(recipe.get("cadence", "daily")),
                "region_label": str(region.get("label", "")),
                "bbox": [float(v) for v in region.get("bbox", [])],
            }
        )
    return presets


def gazetteer() -> dict[str, dict[str, Any]]:
    """Known-region aliases -> {name, bbox, source}: natural features the
    generic geocoders rank poorly (deltas, basins, depressions) resolve
    straight from the cookbook, so freeform questions land on the exact
    region the recipe analyses."""
    out: dict[str, dict[str, Any]] = {}
    for recipe in load_recipes():
        region = recipe.get("region_preset")
        if not isinstance(region, dict):
            continue
        entry = {
            "name": str(region.get("label", "")),
            "bbox": [float(v) for v in region.get("bbox", [])],
            "source_url": f"cookbook://{recipe['id']}",
        }
        for alias in recipe.get("region_aliases", ()):
            out[str(alias).strip().lower()] = dict(entry)
        label_key = str(region.get("label", "")).strip().lower()
        if label_key:
            out.setdefault(label_key, dict(entry))
    return out
