"""Cookbook recipes: validation, router citation, and preset catalog shape."""

from __future__ import annotations

from argus.cookbook import load_recipes, preset_catalog, recipe_for, recipe_map
from argus.orchestrator.router import route
from argus.orchestrator.templates import TEMPLATE_NAMES, TEMPLATES


def test_recipes_load_and_are_valid() -> None:
    recipes = load_recipes()
    assert len(recipes) == 7
    ids = [r["id"] for r in recipes]
    assert len(ids) == len(set(ids))
    for recipe in recipes:
        assert recipe["title"] and recipe["blurb"] and recipe["sensor"]
        assert isinstance(recipe["analysis"], list) and recipe["analysis"]
        assert isinstance(recipe["verification"], list) and recipe["verification"]
        assert recipe["alert_threshold"]
        assert isinstance(recipe["pitfalls"], list) and recipe["pitfalls"]


def test_templates_compile_from_cookbook() -> None:
    # The router catalog is compiled from recipes.json — same ids, same order.
    assert TEMPLATE_NAMES == tuple(r["id"] for r in load_recipes())
    for name in TEMPLATE_NAMES:
        entry = TEMPLATES[name]
        recipe = recipe_map()[name]
        assert entry["keywords"] == tuple(recipe["keywords"])
        assert entry["words"] == tuple(recipe["words"])
        assert entry["sensor"] == recipe["sensor"]
        assert entry["blurb"] == recipe["blurb"]


def test_router_still_routes_and_cites_recipe() -> None:
    result = route("Are there new burn scars near the arc of deforestation?")
    assert result["template"] == "fire_anomaly"
    assert result["recipe_id"] == "fire_anomaly"
    assert result["recipe_title"] == "Fire anomaly"


def test_router_abstains_without_recipe() -> None:
    result = route("How many penguins live in Antarctica?")
    assert result["template"] is None
    assert result["recipe_id"] is None
    assert result["missing"]


def test_recipe_for_unknown_is_none() -> None:
    assert recipe_for("nope") is None
    assert recipe_for(None) is None


def test_preset_catalog_shape() -> None:
    presets = preset_catalog()
    assert len(presets) == 7
    for preset in presets:
        assert preset["id"] and preset["title"] and preset["question"]
        assert len(preset["bbox"]) == 4
        assert preset["bbox"][0] < preset["bbox"][2]
        assert preset["bbox"][1] < preset["bbox"][3]
        assert preset["cadence"] in ("daily", "weekly")


def test_route_result_shape_is_stable() -> None:
    # abstain_receipt must stay digit-free so unrouted answers carry no numbers.
    result = route("Is flooding worsening here?")
    assert result["template"] == "flooding"
    assert set(result) >= {"template", "adjacent", "missing", "recipe_id", "recipe_title"}
