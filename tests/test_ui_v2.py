"""UI-v2 surfaces in the served bundle: FAB, freeform composer, wizard,
presets, decision log, toolbox. The minified bundle emits JSX attributes as
``"aria-label":"..."`` / ``"data-testid":"..."`` JSON-ish keys, so the greps
use those token forms."""

from pathlib import Path

STATIC = Path("argus/server/static")


def _bundle() -> str:
    chunks = [str((STATIC / "index.html").read_text(encoding="utf-8", errors="replace"))]
    for asset in sorted((STATIC / "assets").glob("*.js")):
        chunks.append(asset.read_text(encoding="utf-8", errors="replace"))
    for asset in sorted((STATIC / "assets").glob("*.css")):
        chunks.append(asset.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def test_floating_chat_launcher_ships() -> None:
    bundle = _bundle()
    assert 'aria-label":"open chat drawer"' in bundle
    assert "chat-fab" in bundle


def test_freeform_composer_ships() -> None:
    bundle = _bundle()
    # Single freeform textarea (no pre-filled fake question, no bbox field).
    assert 'aria-label":"chat question"' in bundle
    assert 'textarea",' in bundle
    assert 'aria-label":"chat bbox"' not in bundle
    assert "is the Niger delta flooding" in bundle


def test_onboarding_wizard_ships() -> None:
    bundle = _bundle()
    assert 'data-testid":"onboarding-wizard"' in bundle
    assert 'aria-label":"preset-list"' in bundle
    assert 'aria-label":"webhook url"' in bundle


def test_preset_gallery_on_watchlist_ships() -> None:
    bundle = _bundle()
    assert 'data-testid":"preset-gallery"' in bundle


def test_decision_log_ships() -> None:
    bundle = _bundle()
    assert 'data-testid":"decision-log"' in bundle
    assert 'aria-label":"decision-steps"' in bundle


def test_toolbox_page_ships() -> None:
    bundle = _bundle()
    assert 'aria-label":"toolbox-sources"' in bundle
    assert 'data-testid":"toolbox-summary"' in bundle
    # the nav entry is present
    assert "/toolbox" in bundle


def test_channels_page_ships() -> None:
    bundle = _bundle()
    assert "/channels" in bundle
    assert 'data-testid":"channels-page"' in bundle
    assert 'aria-label":"webhook channel target"' in bundle
