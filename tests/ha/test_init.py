"""Test dell'avvio e dell'arresto dell'integrazione."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.jarvis.deepseek import (
    DeepSeekAuthError,
    DeepSeekBalanceError,
    DeepSeekConnectionError,
    DeepSeekRateLimitError,
    DeepSeekServerError,
)


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    assert init_integration.state is ConfigEntryState.LOADED
    assert hass.states.get("conversation.jarvis") is not None

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_invalid_key_asks_to_reauthenticate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_list_models: AsyncMock
) -> None:
    mock_list_models.side_effect = DeepSeekAuthError("chiave revocata")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )


@pytest.mark.parametrize(
    "error",
    [
        DeepSeekConnectionError("rete assente"),
        DeepSeekServerError("errore 500"),
        DeepSeekRateLimitError("troppe richieste"),
    ],
)
async def test_temporary_errors_are_retried(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    error: Exception,
) -> None:
    mock_list_models.side_effect = error

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_no_credit_still_starts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_list_models: AsyncMock
) -> None:
    """Senza credito Jarvis parte comunque: lo dirà a voce alla prima richiesta."""
    mock_list_models.side_effect = DeepSeekBalanceError("credito finito")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
