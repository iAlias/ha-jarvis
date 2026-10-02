"""Test della creazione automatica dell'assistente vocale."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant

from custom_components.jarvis.const import CONF_ASSISTANT_CREATED


@pytest.fixture
def pending_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Voce per cui l'assistente non è ancora stato creato."""
    data = dict(mock_config_entry.data)
    del data[CONF_ASSISTANT_CREATED]
    hass.config_entries.async_update_entry(mock_config_entry, data=data)
    return mock_config_entry


@pytest.fixture
def notify() -> Generator[MagicMock]:
    """Intercetta la notifica con i passaggi manuali."""
    with patch("homeassistant.components.persistent_notification.async_create") as mock:
        yield mock


@pytest.fixture
def pipelines(hass: HomeAssistant) -> Generator[SimpleNamespace]:
    """Finge che HA abbia le pipeline e i motori vocali predefiniti."""
    hass.config.components.add("assist_pipeline")
    pipeline = MagicMock(name="pipeline")
    with (
        patch(
            "homeassistant.components.stt.async_default_engine",
            return_value="stt.finto",
        ) as stt_engine,
        patch(
            "homeassistant.components.tts.async_default_engine",
            return_value="tts.finto",
        ) as tts_engine,
        patch(
            "homeassistant.components.assist_pipeline.async_create_default_pipeline",
            AsyncMock(return_value=pipeline),
        ) as create,
        patch(
            "homeassistant.components.assist_pipeline.async_update_pipeline",
            AsyncMock(),
        ) as update,
    ):
        yield SimpleNamespace(
            pipeline=pipeline,
            stt_engine=stt_engine,
            tts_engine=tts_engine,
            create=create,
            update=update,
        )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_creates_the_assistant(
    hass: HomeAssistant,
    pending_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    pipelines: SimpleNamespace,
    notify: MagicMock,
) -> None:
    await _setup(hass, pending_entry)

    pipelines.create.assert_awaited_once_with(
        hass,
        stt_engine_id="stt.finto",
        tts_engine_id="tts.finto",
        pipeline_name="Jarvis",
    )
    pipelines.update.assert_awaited_once_with(
        hass,
        pipelines.pipeline,
        conversation_engine="conversation.jarvis",
        conversation_language="*",
    )
    notify.assert_not_called()
    assert pending_entry.data[CONF_ASSISTANT_CREATED] is True


async def test_without_voice_engines_explains_the_manual_steps(
    hass: HomeAssistant,
    pending_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    pipelines: SimpleNamespace,
    notify: MagicMock,
) -> None:
    pipelines.stt_engine.return_value = None

    await _setup(hass, pending_entry)

    pipelines.create.assert_not_awaited()
    notify.assert_called_once()
    assert pending_entry.data[CONF_ASSISTANT_CREATED] is True


async def test_pipeline_not_created_explains_the_manual_steps(
    hass: HomeAssistant,
    pending_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    pipelines: SimpleNamespace,
    notify: MagicMock,
) -> None:
    pipelines.create.return_value = None

    await _setup(hass, pending_entry)

    pipelines.update.assert_not_awaited()
    notify.assert_called_once()


async def test_pipeline_error_does_not_stop_jarvis(
    hass: HomeAssistant,
    pending_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    pipelines: SimpleNamespace,
    notify: MagicMock,
) -> None:
    pipelines.create.side_effect = RuntimeError("API cambiata")

    await _setup(hass, pending_entry)

    notify.assert_called_once()
    assert pending_entry.state is ConfigEntryState.LOADED
    assert pending_entry.data[CONF_ASSISTANT_CREATED] is True


async def test_without_pipelines_explains_the_manual_steps(
    hass: HomeAssistant,
    pending_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    notify: MagicMock,
) -> None:
    await _setup(hass, pending_entry)

    notify.assert_called_once()
    assert pending_entry.data[CONF_ASSISTANT_CREATED] is True


async def test_does_not_try_twice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    pipelines: SimpleNamespace,
    notify: MagicMock,
) -> None:
    await _setup(hass, mock_config_entry)

    pipelines.create.assert_not_awaited()
    notify.assert_not_called()


async def test_waits_for_home_assistant_to_start(
    hass: HomeAssistant,
    pending_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    pipelines: SimpleNamespace,
    notify: MagicMock,
) -> None:
    """All'avvio i motori vocali possono non essere pronti: si aspetta."""
    hass.set_state(CoreState.starting)

    await _setup(hass, pending_entry)

    pipelines.create.assert_not_awaited()
    assert CONF_ASSISTANT_CREATED not in pending_entry.data

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    pipelines.create.assert_awaited_once()
    assert pending_entry.data[CONF_ASSISTANT_CREATED] is True
