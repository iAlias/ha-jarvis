"""Fixture dei test che usano Home Assistant."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL, CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.jarvis.const import (
    CONF_ASSISTANT_CREATED,
    CONF_INVOCATION_WORDS,
    DOMAIN,
)
from custom_components.jarvis.deepseek import Model

MODELS = [
    Model("deepseek-flash", "DeepSeek-V4.1-Flash"),
    Model("deepseek-v4-pro", "DeepSeek-V4-Pro"),
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Permette a HA di caricare l'integrazione dalla cartella custom_components."""


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant) -> None:
    """Il componente di base di HA: in un'installazione vera c'è sempre."""
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def mock_list_models() -> Generator[AsyncMock]:
    """Finge l'elenco dei modelli di DeepSeek, cioè una API key valida."""
    with patch(
        "custom_components.jarvis.deepseek.DeepSeekClient.list_models",
        AsyncMock(return_value=MODELS),
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Voce di configurazione di Jarvis, con l'assistente già creato."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Jarvis",
        data={CONF_API_KEY: "sk-test", CONF_ASSISTANT_CREATED: True},
        options={
            CONF_INVOCATION_WORDS: ["Jarvis", "mbare"],
            CONF_PROMPT: "Sei un assistente di prova.",
            CONF_MODEL: "deepseek-flash",
            CONF_LLM_HASS_API: [],
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_list_models: AsyncMock
) -> MockConfigEntry:
    """Jarvis caricato in Home Assistant."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
