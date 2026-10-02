"""Traduzione tra il formato di Home Assistant e quello di DeepSeek."""

from collections.abc import AsyncGenerator, AsyncIterable, Callable
import json
from typing import Any

from probatio import to_openapi

from homeassistant.components import conversation
from homeassistant.helpers import llm
from homeassistant.helpers.json import json_dumps

from .deepseek import ToolCallAccumulator

# Chiavi di primo livello dello schema che l'API non accetta.
_UNSUPPORTED_SCHEMA_KEYS = {"oneOf", "anyOf", "allOf"}

type Delta = (
    conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
)


def format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> dict[str, Any]:
    """Converte uno strumento di HA nella definizione attesa da DeepSeek."""
    schema = to_openapi(tool.parameters, custom_serializer=custom_serializer)
    function: dict[str, Any] = {
        "name": tool.name,
        "parameters": {
            key: value
            for key, value in schema.items()
            if key not in _UNSUPPORTED_SCHEMA_KEYS
        },
    }
    if tool.description:
        function["description"] = tool.description
    return {"type": "function", "function": function}


def _convert_content(content: conversation.Content) -> dict[str, Any] | None:
    """Converte una voce della cronologia di HA in un messaggio per DeepSeek."""
    if isinstance(content, conversation.ToolResultContent):
        return {
            "role": "tool",
            "tool_call_id": content.tool_call_id,
            "content": json_dumps(content.tool_result),
        }

    if isinstance(content, conversation.AssistantContent):
        if not content.content and not content.tool_calls:
            return None
        # Stringa vuota e non null: è la forma che DeepSeek stesso restituisce
        # per i messaggi che contengono solo richieste di strumenti.
        message: dict[str, Any] = {
            "role": "assistant",
            "content": content.content or "",
        }
        if content.tool_calls:
            message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.tool_name,
                        "arguments": json_dumps(tool_call.tool_args),
                    },
                }
                for tool_call in content.tool_calls
            ]
        return message

    if content.content:
        return {"role": content.role, "content": content.content}
    return None


def build_messages(contents: list[conversation.Content]) -> list[dict[str, Any]]:
    """Converte la cronologia di HA nella lista di messaggi per DeepSeek."""
    return [
        message
        for content in contents
        if (message := _convert_content(content)) is not None
    ]


def _parse_arguments(arguments: str) -> dict[str, Any] | None:
    """Interpreta gli argomenti di uno strumento; None se non sono validi."""
    if not arguments.strip():
        return {}
    try:
        parsed = json.loads(arguments)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def async_transform_stream(
    chunks: AsyncIterable[dict[str, Any]],
) -> AsyncGenerator[Delta]:
    """Converte i frammenti di DeepSeek nei delta attesi dalla cronologia di HA.

    Il testo viene inoltrato subito. Le richieste di strumenti arrivano a pezzi:
    vengono ricomposte e passate a HA solo a flusso concluso.
    """
    accumulator = ToolCallAccumulator()
    started = False

    async for chunk in chunks:
        choices = chunk.get("choices")
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        if not started:
            # Il ruolo apre un nuovo messaggio nella cronologia.
            started = True
            yield {"role": "assistant"}
        if text := delta.get("content"):
            yield {"content": text}
        if fragments := delta.get("tool_calls"):
            accumulator.add(fragments)

    tool_inputs: list[llm.ToolInput] = []
    failures: list[conversation.ToolResultContentDeltaDict] = []
    for call in accumulator.result():
        arguments = _parse_arguments(call.arguments)
        # Con argomenti non validi lo strumento non va eseguito: lo si segna
        # come esterno e si restituisce al modello un esito d'errore.
        tool_input = llm.ToolInput(
            tool_name=call.name,
            tool_args=arguments or {},
            external=arguments is None,
        )
        if call.id:
            tool_input.id = call.id
        tool_inputs.append(tool_input)
        if arguments is None:
            failures.append(
                {
                    "role": "tool_result",
                    "tool_call_id": tool_input.id,
                    "tool_name": call.name,
                    "tool_result": {
                        "error": "invalid_arguments",
                        "error_text": "Tool arguments are not valid JSON",
                    },
                }
            )

    if tool_inputs:
        if not started:
            yield {"role": "assistant"}
        yield {"tool_calls": tool_inputs}
    for failure in failures:
        yield failure
