"""Test dell'agente conversazionale."""

from collections.abc import AsyncGenerator, Generator
import copy
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent, llm

from custom_components.jarvis.const import MAX_TOOL_ITERATIONS
from custom_components.jarvis.deepseek import (
    DeepSeekAuthError,
    DeepSeekBalanceError,
    DeepSeekConnectionError,
    DeepSeekRateLimitError,
    DeepSeekServerError,
)
from custom_components.jarvis.texts import error_message

AGENT_ID = "conversation.jarvis"
API_ID = "prova"


class FakeDeepSeek:
    """Finto DeepSeek: restituisce risposte preparate e ricorda le richieste.

    Ogni risposta è una lista di frammenti; un'eccezione nella lista viene
    sollevata in quel punto. Finite le risposte, l'ultima si ripete.
    """

    def __init__(self) -> None:
        """Parte senza risposte."""
        self.responses: list[list[Any]] = []
        self.payloads: list[dict[str, Any]] = []

    def stream_chat(self, payload: dict[str, Any]) -> AsyncGenerator[dict[str, Any]]:
        """Sostituisce `DeepSeekClient.stream_chat`."""
        self.payloads.append(copy.deepcopy(payload))
        index = min(len(self.payloads), len(self.responses)) - 1
        return self._generate(self.responses[index])

    @staticmethod
    async def _generate(response: list[Any]) -> AsyncGenerator[dict[str, Any]]:
        for item in response:
            if isinstance(item, Exception):
                raise item
            yield item


class LightTool(llm.Tool):
    """Strumento di prova che ricorda come è stato chiamato."""

    name = "accendi_luce"
    description = "Accende la luce di una stanza"
    parameters = vol.Schema({vol.Required("stanza"): str})

    def __init__(self) -> None:
        """Parte senza chiamate."""
        self.calls: list[dict[str, Any]] = []

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Registra la chiamata e conferma."""
        self.calls.append(tool_input.tool_args)
        return {"esito": "luce accesa"}


class FakeAPI(llm.API):
    """API LLM di prova con un solo strumento."""

    def __init__(self, hass: HomeAssistant, tool: llm.Tool) -> None:
        """Registra lo strumento da offrire."""
        super().__init__(hass=hass, id=API_ID, name="Prova")
        self.tool = tool

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Offre lo strumento di prova."""
        return llm.APIInstance(
            api=self,
            api_prompt="Usa gli strumenti di prova.",
            llm_context=llm_context,
            tools=[self.tool],
        )


@pytest.fixture
def fake_deepseek() -> Generator[FakeDeepSeek]:
    """Sostituisce le chiamate di chat a DeepSeek."""
    fake = FakeDeepSeek()
    with patch(
        "custom_components.jarvis.deepseek.DeepSeekClient.stream_chat",
        fake.stream_chat,
    ):
        yield fake


@pytest.fixture
def light_tool(hass: HomeAssistant) -> Generator[LightTool]:
    """Registra in HA un'API LLM di prova e ne restituisce lo strumento."""
    tool = LightTool()
    unregister = llm.async_register_api(hass, FakeAPI(hass, tool))
    yield tool
    unregister()


@pytest.fixture
async def init_with_tools(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    light_tool: LightTool,
) -> MockConfigEntry:
    """Jarvis caricato con l'API LLM di prova tra gli strumenti."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, CONF_LLM_HASS_API: [API_ID]},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


def _text(*parts: str) -> list[dict[str, Any]]:
    return [{"choices": [{"delta": {"content": part}}]} for part in parts]


def _tool_call(
    arguments: str, name: str = "accendi_luce", call_id: str = "call_1"
) -> list[dict[str, Any]]:
    fragment = {
        "index": 0,
        "id": call_id,
        "function": {"name": name, "arguments": arguments},
    }
    return [{"choices": [{"delta": {"tool_calls": [fragment]}}]}]


async def _converse(
    hass: HomeAssistant,
    text: str = "accendi la luce del salotto",
    *,
    language: str = "it",
    conversation_id: str | None = None,
) -> conversation.ConversationResult:
    return await conversation.async_converse(
        hass, text, conversation_id, Context(), language=language, agent_id=AGENT_ID
    )


def _speech(result: conversation.ConversationResult) -> str:
    return result.response.speech["plain"]["speech"]


async def test_simple_answer(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_deepseek: FakeDeepSeek
) -> None:
    fake_deepseek.responses = [_text("Buonasera, ", "signore.")]

    result = await _converse(hass, "ciao")

    assert _speech(result) == "Buonasera, signore."
    assert result.response.error_code is None

    (payload,) = fake_deepseek.payloads
    assert payload["model"] == "deepseek-flash"
    assert payload["stream"] is True
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["max_tokens"] == 1024
    assert "tools" not in payload
    system = payload["messages"][0]
    assert system["role"] == "system"
    assert "Sei un assistente di prova." in system["content"]
    assert "Rispondi a questi nomi: Jarvis, mbare." in system["content"]
    assert payload["messages"][-1] == {"role": "user", "content": "ciao"}


async def test_names_line_follows_the_request_language(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_deepseek: FakeDeepSeek
) -> None:
    fake_deepseek.responses = [_text("Good evening.")]

    await _converse(hass, "hello", language="en")

    system = fake_deepseek.payloads[0]["messages"][0]["content"]
    assert "You answer to these names: Jarvis, mbare." in system


async def test_conversation_keeps_its_history(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_deepseek: FakeDeepSeek
) -> None:
    fake_deepseek.responses = [_text("Buonasera."), _text("Bene, grazie.")]

    first = await _converse(hass, "ciao")
    await _converse(hass, "come va", conversation_id=first.conversation_id)

    roles = [message["role"] for message in fake_deepseek.payloads[1]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


async def test_tool_call(
    hass: HomeAssistant,
    init_with_tools: MockConfigEntry,
    fake_deepseek: FakeDeepSeek,
    light_tool: LightTool,
) -> None:
    fake_deepseek.responses = [_tool_call('{"stanza": "salotto"}'), _text("Fatto.")]

    result = await _converse(hass)

    assert _speech(result) == "Fatto."
    assert light_tool.calls == [{"stanza": "salotto"}]

    first, second = fake_deepseek.payloads
    (tool,) = first["tools"]
    assert tool["function"]["name"] == "accendi_luce"
    assert "Usa gli strumenti di prova." in first["messages"][0]["content"]
    request, outcome = second["messages"][-2:]
    assert request["role"] == "assistant"
    assert request["tool_calls"][0]["id"] == "call_1"
    assert outcome["role"] == "tool"
    assert outcome["tool_call_id"] == "call_1"
    assert json.loads(outcome["content"]) == {"esito": "luce accesa"}


async def test_tool_arguments_split_in_fragments(
    hass: HomeAssistant,
    init_with_tools: MockConfigEntry,
    fake_deepseek: FakeDeepSeek,
    light_tool: LightTool,
) -> None:
    pieces = [
        {"index": 0, "id": "call_1", "function": {"name": "accendi_luce"}},
        {"index": 0, "function": {"arguments": '{"stanza": "ca'}},
        {"index": 0, "function": {"arguments": 'mera"}'}},
    ]
    fake_deepseek.responses = [
        [{"choices": [{"delta": {"tool_calls": [piece]}}]} for piece in pieces],
        _text("Fatto."),
    ]

    await _converse(hass)

    assert light_tool.calls == [{"stanza": "camera"}]


async def test_several_rounds_of_tools(
    hass: HomeAssistant,
    init_with_tools: MockConfigEntry,
    fake_deepseek: FakeDeepSeek,
    light_tool: LightTool,
) -> None:
    fake_deepseek.responses = [
        _tool_call('{"stanza": "salotto"}', call_id="call_1"),
        _tool_call('{"stanza": "cucina"}', call_id="call_2"),
        _text("Accese entrambe."),
    ]

    result = await _converse(hass, "accendi salotto e cucina")

    assert _speech(result) == "Accese entrambe."
    assert light_tool.calls == [{"stanza": "salotto"}, {"stanza": "cucina"}]
    assert len(fake_deepseek.payloads) == 3


async def test_invalid_tool_arguments_are_not_executed(
    hass: HomeAssistant,
    init_with_tools: MockConfigEntry,
    fake_deepseek: FakeDeepSeek,
    light_tool: LightTool,
) -> None:
    fake_deepseek.responses = [
        _tool_call('{"stanza": '),
        _text("Non ci sono riuscito."),
    ]

    result = await _converse(hass)

    assert _speech(result) == "Non ci sono riuscito."
    assert light_tool.calls == []
    outcome = fake_deepseek.payloads[1]["messages"][-1]
    assert outcome["role"] == "tool"
    assert json.loads(outcome["content"])["error"] == "invalid_arguments"


async def test_stops_after_too_many_rounds(
    hass: HomeAssistant,
    init_with_tools: MockConfigEntry,
    fake_deepseek: FakeDeepSeek,
    light_tool: LightTool,
) -> None:
    fake_deepseek.responses = [_tool_call('{"stanza": "salotto"}')]

    result = await _converse(hass)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert _speech(result) == error_message("too_many_steps", "it")
    assert len(fake_deepseek.payloads) == MAX_TOOL_ITERATIONS


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (DeepSeekAuthError("no"), "auth"),
        (DeepSeekBalanceError("no"), "balance"),
        (DeepSeekRateLimitError("no"), "rate_limit"),
        (DeepSeekServerError("no"), "server"),
        (DeepSeekConnectionError("no"), "connection"),
    ],
)
@pytest.mark.parametrize("language", ["it", "en"])
async def test_errors_are_spoken(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_deepseek: FakeDeepSeek,
    error: Exception,
    kind: str,
    language: str,
) -> None:
    fake_deepseek.responses = [[error]]

    result = await _converse(hass, language=language)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert _speech(result) == error_message(kind, language)


async def test_revoked_key_asks_to_reauthenticate(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_deepseek: FakeDeepSeek
) -> None:
    fake_deepseek.responses = [[DeepSeekAuthError("chiave revocata")]]

    await _converse(hass)
    await hass.async_block_till_done()

    assert any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_empty_response_is_an_error(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_deepseek: FakeDeepSeek
) -> None:
    fake_deepseek.responses = [[]]

    result = await _converse(hass)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert _speech(result) == error_message("server", "it")


async def test_connection_lost_mid_answer(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_deepseek: FakeDeepSeek
) -> None:
    fake_deepseek.responses = [
        [*_text("Stavo dicendo"), DeepSeekConnectionError("caduta")]
    ]

    result = await _converse(hass)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert _speech(result) == error_message("connection", "it")


async def test_unknown_tools_api_is_reported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_models: AsyncMock,
    fake_deepseek: FakeDeepSeek,
) -> None:
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, CONF_LLM_HASS_API: ["non_esiste"]},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await _converse(hass)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert fake_deepseek.payloads == []


async def test_agent_can_control_only_with_tools(
    hass: HomeAssistant, init_with_tools: MockConfigEntry
) -> None:
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert (
        state.attributes["supported_features"]
        == conversation.ConversationEntityFeature.CONTROL
    )


async def test_agent_without_tools_only_chats(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.attributes["supported_features"] == 0

    agent_info = conversation.async_get_agent_info(hass, AGENT_ID)
    assert agent_info is not None
    assert agent_info.supports_streaming is True
