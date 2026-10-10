"""Test della registrazione della card nel frontend."""

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from custom_components.jarvis.card import CARD_PATH, CARD_URL
from custom_components.jarvis.const import DOMAIN

OTHER_RESOURCE = {"id": "altra", "url": "/hacsfiles/altra-card.js", "type": "module"}


class FakeResources:
    """Finte risorse delle dashboard, con la stessa interfaccia di quelle di HA."""

    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        """Parte con le risorse indicate."""
        self.items = {item["id"]: dict(item) for item in items or []}
        self.broken = False

    async def async_get_info(self) -> dict[str, int]:
        """Carica l'elenco."""
        if self.broken:
            raise RuntimeError("interfaccia cambiata")
        return {"resources": len(self.items)}

    def async_items(self) -> list[dict[str, Any]]:
        """Elenca le risorse."""
        return list(self.items.values())

    async def async_create_item(self, data: dict[str, Any]) -> dict[str, Any]:
        """Aggiunge una risorsa."""
        item = {"id": f"nuova{len(self.items)}", "url": data["url"]}
        item["type"] = data["res_type"]
        self.items[item["id"]] = item
        return item

    async def async_update_item(
        self, item_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Modifica una risorsa."""
        self.items[item_id].update(url=updates["url"], type=updates["res_type"])
        return self.items[item_id]

    async def async_delete_item(self, item_id: str) -> None:
        """Toglie una risorsa."""
        del self.items[item_id]

    def jarvis(self) -> list[dict[str, Any]]:
        """Le risorse che puntano alla card di Jarvis."""
        return [
            item for item in self.items.values() if item["url"].startswith(CARD_URL)
        ]


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


@pytest.fixture
def resources(hass: HomeAssistant) -> FakeResources:
    """Finge che le dashboard abbiano risorse modificabili."""
    fake = FakeResources([OTHER_RESOURCE])
    hass.config.components.add("lovelace")
    hass.data[LOVELACE_DATA] = SimpleNamespace(resource_mode="storage", resources=fake)
    return fake


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Avvia Jarvis e restituisce l'indirizzo atteso della card."""
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    version = (await async_get_integration(hass, DOMAIN)).version
    return f"{CARD_URL}?v={version}"


def test_card_file_is_shipped() -> None:
    assert CARD_PATH.is_file()


async def test_card_is_registered_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    frontend: SimpleNamespace,
) -> None:
    url = await _setup(hass, mock_config_entry)

    frontend.register.assert_awaited_once_with(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), True)]
    )
    frontend.add_url.assert_called_once_with(hass, url)

    # Ricaricare l'integrazione non deve registrare la card una seconda volta.
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    frontend.register.assert_awaited_once()
    frontend.add_url.assert_called_once()


async def test_card_is_added_to_the_dashboard_resources(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    frontend: SimpleNamespace,
    resources: FakeResources,
) -> None:
    """Le risorse si leggono a ogni apertura: la card non dipende dalla cache."""
    url = await _setup(hass, mock_config_entry)

    (item,) = resources.jarvis()
    assert item["url"] == url
    assert item["type"] == "module"
    assert resources.items["altra"] == OTHER_RESOURCE
    frontend.add_url.assert_not_called()


async def test_resource_follows_the_installed_version(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    frontend: SimpleNamespace,
    resources: FakeResources,
) -> None:
    resources.items["vecchia"] = {
        "id": "vecchia",
        "url": f"{CARD_URL}?v=0.0.1",
        "type": "module",
    }

    url = await _setup(hass, mock_config_entry)

    (item,) = resources.jarvis()
    assert item == {"id": "vecchia", "url": url, "type": "module"}


async def test_yaml_resources_fall_back_to_the_extra_module(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    frontend: SimpleNamespace,
    resources: FakeResources,
) -> None:
    hass.data[LOVELACE_DATA].resource_mode = "yaml"

    url = await _setup(hass, mock_config_entry)

    assert resources.jarvis() == []
    frontend.add_url.assert_called_once_with(hass, url)


async def test_broken_resources_fall_back_to_the_extra_module(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    frontend: SimpleNamespace,
    resources: FakeResources,
) -> None:
    resources.broken = True

    url = await _setup(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    frontend.add_url.assert_called_once_with(hass, url)


async def test_removing_jarvis_removes_only_its_resource(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    frontend: SimpleNamespace,
    resources: FakeResources,
) -> None:
    await _setup(hass, mock_config_entry)
    assert resources.jarvis()

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert resources.jarvis() == []
    assert resources.items == {"altra": OTHER_RESOURCE}


async def test_without_frontend_jarvis_still_starts(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    assert init_integration.state is ConfigEntryState.LOADED
