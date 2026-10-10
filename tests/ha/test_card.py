"""Test della registrazione della card nel frontend."""

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from custom_components.jarvis.card import CARD_PATH, CARD_URL
from custom_components.jarvis.const import DOMAIN


@pytest.fixture
async def frontend(hass: HomeAssistant) -> AsyncGenerator[SimpleNamespace]:
    """Finge che il frontend di HA sia caricato."""
    assert await async_setup_component(hass, "http", {})
    hass.config.components.add("frontend")
    with (
        patch("homeassistant.components.frontend.add_extra_js_url") as add_url,
        patch.object(hass.http, "async_register_static_paths", AsyncMock()) as register,
    ):
        yield SimpleNamespace(add_url=add_url, register=register)


def test_card_file_is_shipped() -> None:
    assert CARD_PATH.is_file()


async def test_card_is_registered_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    frontend: SimpleNamespace,
) -> None:
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    version = (await async_get_integration(hass, DOMAIN)).version
    frontend.register.assert_awaited_once_with(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), True)]
    )
    frontend.add_url.assert_called_once_with(hass, f"{CARD_URL}?v={version}")

    # Ricaricare l'integrazione non deve registrare la card una seconda volta.
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    frontend.register.assert_awaited_once()
    frontend.add_url.assert_called_once()


async def test_without_frontend_jarvis_still_starts(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    assert init_integration.state is ConfigEntryState.LOADED
