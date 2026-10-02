"""Test del traduttore tra il formato di HA e quello di DeepSeek."""

from collections.abc import AsyncGenerator
import json
from typing import Any

import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from custom_components.jarvis.chat import (
    async_transform_stream,
    build_messages,
    format_tool,
)

AGENT_ID = "conversation.jarvis"


class LightTool(llm.Tool):
    """Strumento di prova."""

    name = "accendi_luce"
    description = "Accende la luce di una stanza"
    parameters = vol.Schema(
        {vol.Required("stanza"): str, vol.Optional("luminosita"): int}
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Non usato in questi test."""
        return {}


async def _stream(*chunks: dict[str, Any]) -> AsyncGenerator[dict[str, Any]]:
    for chunk in chunks:
        yield chunk


async def _transform(*chunks: dict[str, Any]) -> list[Any]:
    return [delta async for delta in async_transform_stream(_stream(*chunks))]


def _text(text: str) -> dict[str, Any]:
    return {"choices": [{"delta": {"content": text}}]}


def _tool(**fragment: Any) -> dict[str, Any]:
    return {"choices": [{"delta": {"tool_calls": [fragment]}}]}


def test_build_messages_covers_every_kind() -> None:
    contents = [
        conversation.SystemContent(content="Sei Jarvis."),
        conversation.UserContent(content="accendi la luce"),
        conversation.AssistantContent(
            agent_id=AGENT_ID,
            content=None,
            tool_calls=[
                llm.ToolInput(
                    id="call_1", tool_name="accendi_luce", tool_args={"stanza": "sala"}
                )
            ],
        ),
        conversation.ToolResultContent(
            agent_id=AGENT_ID,
            tool_call_id="call_1",
            tool_name="accendi_luce",
            tool_result={"esito": "ok"},
        ),
        conversation.AssistantContent(agent_id=AGENT_ID, content="Fatto."),
    ]

    system, user, request, result, answer = build_messages(contents)

    assert system == {"role": "system", "content": "Sei Jarvis."}
    assert user == {"role": "user", "content": "accendi la luce"}
    assert request["role"] == "assistant"
    assert request["content"] is None
    (tool_call,) = request["tool_calls"]
    assert tool_call["id"] == "call_1"
    assert tool_call["type"] == "function"
    assert tool_call["function"]["name"] == "accendi_luce"
    assert json.loads(tool_call["function"]["arguments"]) == {"stanza": "sala"}
    assert result["role"] == "tool"
    assert result["tool_call_id"] == "call_1"
    assert json.loads(result["content"]) == {"esito": "ok"}
    assert answer == {"role": "assistant", "content": "Fatto."}


def test_build_messages_skips_empty_content() -> None:
    contents = [
        conversation.SystemContent(content=""),
        conversation.AssistantContent(agent_id=AGENT_ID, content=None),
        conversation.UserContent(content="ciao"),
    ]

    assert build_messages(contents) == [{"role": "user", "content": "ciao"}]


def test_format_tool() -> None:
    result = format_tool(LightTool(), None)

    assert result["type"] == "function"
    function = result["function"]
    assert function["name"] == "accendi_luce"
    assert function["description"] == "Accende la luce di una stanza"
    assert function["parameters"]["type"] == "object"
    assert function["parameters"]["properties"]["stanza"]["type"] == "string"
    assert function["parameters"]["properties"]["luminosita"]["type"] == "integer"
    assert function["parameters"]["required"] == ["stanza"]


def test_format_tool_without_description() -> None:
    tool = LightTool()
    tool.description = None

    assert "description" not in format_tool(tool, None)["function"]


async def test_stream_of_text() -> None:
    assert await _transform(_text("Buona"), _text("sera")) == [
        {"role": "assistant"},
        {"content": "Buona"},
        {"content": "sera"},
    ]


async def test_stream_ignores_chunks_without_choices() -> None:
    deltas = await _transform(
        {"choices": []}, _text("ok"), {"usage": {"total_tokens": 3}}
    )

    assert deltas == [{"role": "assistant"}, {"content": "ok"}]


async def test_empty_stream_yields_nothing() -> None:
    assert await _transform() == []


async def test_tool_call_in_fragments_is_reassembled() -> None:
    """Gli argomenti spezzati su più frammenti vanno ricomposti."""
    deltas = await _transform(
        _text("Subito."),
        _tool(index=0, id="call_1", function={"name": "accendi_luce", "arguments": ""}),
        _tool(index=0, function={"arguments": '{"stanza": "sa'}),
        _tool(index=0, function={"arguments": 'la"}'}),
    )

    assert deltas == [
        {"role": "assistant"},
        {"content": "Subito."},
        {
            "tool_calls": [
                llm.ToolInput(
                    id="call_1", tool_name="accendi_luce", tool_args={"stanza": "sala"}
                )
            ]
        },
    ]


async def test_tool_call_without_arguments() -> None:
    deltas = await _transform(
        _tool(index=0, id="call_1", function={"name": "ora_esatta", "arguments": ""})
    )

    assert deltas[1] == {
        "tool_calls": [llm.ToolInput(id="call_1", tool_name="ora_esatta", tool_args={})]
    }


async def test_tool_call_without_id_gets_one() -> None:
    deltas = await _transform(_tool(function={"name": "ora_esatta", "arguments": "{}"}))

    (tool_input,) = deltas[1]["tool_calls"]
    assert tool_input.id


async def test_invalid_arguments_are_reported_not_executed() -> None:
    """Con argomenti non validi lo strumento non parte: torna un esito d'errore."""
    for arguments in ('{"stanza": ', "[1, 2]"):
        deltas = await _transform(
            _tool(
                index=0,
                id="call_1",
                function={"name": "accendi_luce", "arguments": arguments},
            )
        )

        assert deltas[:2] == [
            {"role": "assistant"},
            {
                "tool_calls": [
                    llm.ToolInput(
                        id="call_1",
                        tool_name="accendi_luce",
                        tool_args={},
                        external=True,
                    )
                ]
            },
        ]
        (failure,) = deltas[2:]
        assert failure["role"] == "tool_result"
        assert failure["tool_call_id"] == "call_1"
        assert failure["tool_name"] == "accendi_luce"
        assert failure["tool_result"]["error"] == "invalid_arguments"
