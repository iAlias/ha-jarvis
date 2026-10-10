"""Test del file della card: c'è, e usa l'azione ufficiale per l'ascolto."""

from pathlib import Path

CARD = (
    Path(__file__).parents[2]
    / "custom_components"
    / "jarvis"
    / "www"
    / "jarvis-card.js"
)


def test_card_defines_the_element_and_starts_listening() -> None:
    source = CARD.read_text(encoding="utf-8")

    assert 'customElements.define("jarvis-card"' in source
    assert 'new Event("hass-action"' in source
    assert 'action: "assist"' in source
    assert "start_listening: true" in source


def test_card_is_listed_in_the_card_picker() -> None:
    source = CARD.read_text(encoding="utf-8")

    assert "window.customCards" in source
    assert 'type: "jarvis-card"' in source
