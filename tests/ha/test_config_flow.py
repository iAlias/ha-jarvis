"""Test della configurazione e delle impostazioni."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL, CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.jarvis.const import CONF_INVOCATION_WORDS, DOMAIN
from custom_components.jarvis.deepseek import (
    DeepSeekAuthError,
    DeepSeekBalanceError,
    DeepSeekConnectionError,
    DeepSeekServerError,
)
from custom_components.jarvis.texts import default_prompt


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Evita di avviare davvero l'integrazione a fine configurazione."""
    with patch(
        "custom_components.jarvis.async_setup_entry", AsyncMock(return_value=True)
    ) as mock:
        yield mock


def _model_options(result: dict[str, Any]) -> list[str]:
    """I modelli proposti dal modulo delle impostazioni."""
    for key, selector in result["data_schema"].schema.items():
        if key == CONF_MODEL:
            return [option["value"] for option in selector.config["options"]]
    raise AssertionError("campo del modello non trovato")


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_list_models: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "  sk-valida  "}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jarvis"
    assert result["data"] == {CONF_API_KEY: "sk-valida"}
    assert result["options"] == {
        CONF_INVOCATION_WORDS: ["Jarvis"],
        CONF_PROMPT: default_prompt("en"),
        CONF_MODEL: "deepseek-flash",
        CONF_LLM_HASS_API: ["assist"],
    }


async def test_default_personality_follows_home_assistant_language(
    hass: HomeAssistant, mock_list_models: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    hass.config.language = "it"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk-valida"}
    )

    assert result["options"][CONF_PROMPT] == default_prompt("it")


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (DeepSeekAuthError("no"), "invalid_auth"),
        (DeepSeekConnectionError("no"), "cannot_connect"),
        (DeepSeekServerError("no"), "cannot_connect"),
    ],
)
async def test_user_flow_reports_errors_and_recovers(
    hass: HomeAssistant,
    mock_list_models: AsyncMock,
    mock_setup_entry: AsyncMock,
    error: Exception,
    code: str,
) -> None:
    mock_list_models.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk-sbagliata"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": code}
    assert not hass.config_entries.async_entries(DOMAIN)

    mock_list_models.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk-valida"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_accepts_key_without_credit(
    hass: HomeAssistant, mock_list_models: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Il credito esaurito non rende la chiave sbagliata."""
    mock_list_models.side_effect = DeepSeekBalanceError("credito finito")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk-valida"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_only_one_jarvis(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reauth_replaces_the_key(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_list_models: AsyncMock
) -> None:
    result = await init_integration.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_list_models.side_effect = DeepSeekAuthError("no")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk-ancora-sbagliata"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    assert init_integration.data[CONF_API_KEY] == "sk-test"

    mock_list_models.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk-nuova"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert init_integration.data[CONF_API_KEY] == "sk-nuova"


async def test_options_save_cleaned_words(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_INVOCATION_WORDS: [" Alfredo ", "alfredo", "mbare"],
            CONF_PROMPT: "Sei Alfredo.",
            CONF_MODEL: "deepseek-v4-pro",
            CONF_LLM_HASS_API: [],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options == {
        CONF_INVOCATION_WORDS: ["Alfredo", "mbare"],
        CONF_PROMPT: "Sei Alfredo.",
        CONF_MODEL: "deepseek-v4-pro",
        CONF_LLM_HASS_API: [],
    }


async def test_options_reject_empty_words(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    before = dict(init_integration.options)
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_INVOCATION_WORDS: ["  ", ""], CONF_MODEL: "deepseek-flash"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_INVOCATION_WORDS: "no_invocation_words"}
    assert init_integration.options == before


async def test_options_without_personality_restore_the_default(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_INVOCATION_WORDS: ["Jarvis"], CONF_MODEL: "deepseek-flash"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options[CONF_PROMPT] == default_prompt("en")
    assert init_integration.options[CONF_LLM_HASS_API] == []


async def test_options_list_models_from_deepseek(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert _model_options(result) == ["deepseek-flash", "deepseek-v4-pro"]


async def test_options_keep_a_saved_model_that_is_no_longer_listed(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    hass.config_entries.async_update_entry(
        init_integration,
        options={**init_integration.options, CONF_MODEL: "modello-ritirato"},
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert _model_options(result) == [
        "deepseek-flash",
        "deepseek-v4-pro",
        "modello-ritirato",
    ]


async def test_options_fall_back_when_models_are_unreachable(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_list_models: AsyncMock
) -> None:
    mock_list_models.side_effect = DeepSeekConnectionError("rete assente")

    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert _model_options(result) == ["deepseek-flash", "deepseek-v4-pro"]
