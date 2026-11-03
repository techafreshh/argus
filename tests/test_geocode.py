"""Freeform place resolution: candidate extraction, offline gating, region shape."""

from __future__ import annotations

from argus.adapters import geocode


def test_extraction_finds_geo_runs() -> None:
    assert geocode.extract_place_candidates(
        "Is the Niger delta flooding worse than last month?"
    ) == ["Niger delta"]
    assert geocode.extract_place_candidates("What is happening with Lake Mead?") == [
        "Lake Mead"
    ]
    assert geocode.extract_place_candidates(
        "Is the Gulf of Guinea shipping traffic up?"
    ) == ["Gulf of Guinea"]


def test_extraction_strips_question_words() -> None:
    # Sentence openers never become candidates.
    assert geocode.extract_place_candidates("Is flooding worsening here?") == []
    assert geocode.extract_place_candidates("What happened in 2024?") == []


def test_extraction_empty_and_noise() -> None:
    assert geocode.extract_place_candidates("") == []
    assert geocode.extract_place_candidates("hi") == []
    assert geocode.extract_place_candidates(None) == []


def test_offline_never_egresses(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_OFFLINE", "1")
    called = []
    monkeypatch.setattr(
        geocode.httpx, "get", lambda *a, **k: called.append(a)
    )
    assert geocode.resolve_place("Niger delta") is None
    # The cookbook gazetteer is local data: it still resolves offline, with
    # zero egress, so freeform questions keep working in offline mode.
    region, geo = geocode.region_from_question("Is the Niger delta flooding?")
    assert region is not None and region["place"] == "Niger delta floodplain"
    assert geo["source_url"].startswith("cookbook://flooding")
    assert called == []


def test_region_from_question(monkeypatch) -> None:
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    monkeypatch.setattr(
        geocode,
        "resolve_place",
        lambda name: {
            "name": "Kalamazoo",
            "display_name": "Kalamazoo River, Michigan, USA",
            "bbox": [-85.7, 42.2, -85.5, 42.35],
            "source_url": "https://nominatim.openstreetmap.org/search?q=kalamazoo",
        }
        if name.startswith("Kalamazoo")
        else None,
    )
    region, geo = geocode.region_from_question("Is the Kalamazoo river flooding?")
    assert region == {
        "type": "bbox",
        "coords": [-85.7, 42.2, -85.5, 42.35],
        "place": "Kalamazoo",
    }
    assert geo["source_url"].startswith("https://nominatim.openstreetmap.org/")


def test_gazetteer_regions_resolve_from_cookbook() -> None:
    for question, expected in (
        ("Is the Niger delta flooding worse than last month?", "Niger delta floodplain"),
        ("What is happening with Lake Mead?", "Lake Mead"),
        ("Is the Gulf of Guinea shipping traffic up?", "Rotterdam port approaches"),
        ("Dust risk over the Bodélé Depression this week?", "Bodélé Depression"),
    ):
        region, geo = geocode.region_from_question(question)
        assert geo is not None, question
        assert geo["name"] == expected, question
        assert geo["source_url"].startswith("cookbook://")
        assert region is not None and region["type"] == "bbox"


def test_unresolvable_question_yields_no_region(monkeypatch) -> None:
    monkeypatch.delenv("ARGUS_OFFLINE", raising=False)
    monkeypatch.setattr(geocode, "resolve_place", lambda name: None)
    region, geo = geocode.region_from_question("Is flooding worsening here?")
    assert region is None and geo is None


def test_bbox_validation() -> None:
    assert geocode._bbox_from(["4.5", "6.5", "5.5", "8.5"]) == [5.5, 4.5, 8.5, 6.5]
    assert geocode._bbox_from(["bad"]) is None
    assert geocode._bbox_from(["9", "9", "1", "1"]) is None  # inverted is rejected
    assert geocode._bbox_from(None) is None
