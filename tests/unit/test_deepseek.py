"""Test del client DeepSeek contro un finto server locale."""

import asyncio
import json

import aiohttp
import pytest
from aiohttp import web

API_KEY = "sk-test"
PAYLOAD = {"model": "deepseek-flash", "messages": [], "stream": True}


def _sse(*events: object) -> bytes:
    """Compone il corpo di una risposta in streaming."""
    lines = []
    for event in events:
        data = event if isinstance(event, str) else json.dumps(event)
        lines.append(f"data: {data}\n\n")
    return "".join(lines).encode()


def _sse_handler(body: bytes):
    """Gestore che risponde con un flusso di eventi già pronto."""

    async def handler(request: web.Request) -> web.StreamResponse:
        return web.Response(body=body, content_type="text/event-stream")

    return handler


def _status_handler(status: int, message: str):
    """Gestore che risponde con un errore HTTP nel formato di DeepSeek."""

    async def handler(request: web.Request) -> web.StreamResponse:
        return web.json_response({"error": {"message": message}}, status=status)

    return handler


async def _collect(client, payload=PAYLOAD) -> list[dict]:
    return [chunk async for chunk in client.stream_chat(payload)]


ERROR_CASES = [
    (401, "DeepSeekAuthError"),
    (402, "DeepSeekBalanceError"),
    (429, "DeepSeekRateLimitError"),
    (500, "DeepSeekServerError"),
    (400, "DeepSeekServerError"),
]


async def test_list_models(deepseek, session, start_server) -> None:
    seen_headers = {}

    async def models(request: web.Request) -> web.StreamResponse:
        seen_headers.update(request.headers)
        return web.json_response(
            {
                "object": "list",
                "data": [
                    {"id": "deepseek-flash", "name": "DeepSeek-V4.1-Flash"},
                    {"id": "deepseek-v4-pro"},
                ],
            }
        )

    client = deepseek.DeepSeekClient(
        session, API_KEY, await start_server(models=models)
    )

    assert await client.list_models() == [
        deepseek.Model("deepseek-flash", "DeepSeek-V4.1-Flash"),
        deepseek.Model("deepseek-v4-pro", "deepseek-v4-pro"),
    ]
    assert seen_headers["Authorization"] == f"Bearer {API_KEY}"


@pytest.mark.parametrize(("status", "error_name"), ERROR_CASES)
async def test_list_models_http_errors(
    deepseek, session, start_server, status, error_name
) -> None:
    base_url = await start_server(models=_status_handler(status, "motivo"))
    client = deepseek.DeepSeekClient(session, API_KEY, base_url)

    with pytest.raises(getattr(deepseek, error_name), match="motivo"):
        await client.list_models()


async def test_list_models_unexpected_body(deepseek, session, start_server) -> None:
    async def models(request: web.Request) -> web.StreamResponse:
        return web.Response(text="<html>non sono JSON</html>")

    client = deepseek.DeepSeekClient(
        session, API_KEY, await start_server(models=models)
    )

    with pytest.raises(deepseek.DeepSeekServerError):
        await client.list_models()


async def test_connection_refused(deepseek, session, start_server) -> None:
    base_url = await start_server()
    # Una porta su cui non risponde nessuno.
    closed_url = base_url.rsplit(":", 1)[0] + ":1"
    client = deepseek.DeepSeekClient(session, API_KEY, closed_url)

    with pytest.raises(deepseek.DeepSeekConnectionError):
        await client.list_models()
    with pytest.raises(deepseek.DeepSeekConnectionError):
        await _collect(client)


async def test_stream_yields_chunks(deepseek, session, start_server) -> None:
    received = {}
    first = {"choices": [{"delta": {"role": "assistant", "content": "Buona"}}]}
    second = {"choices": [{"delta": {"content": "sera"}, "finish_reason": "stop"}]}

    async def chat(request: web.Request) -> web.StreamResponse:
        received["payload"] = await request.json()
        received["auth"] = request.headers["Authorization"]
        return web.Response(
            body=_sse(first, second, "[DONE]"), content_type="text/event-stream"
        )

    client = deepseek.DeepSeekClient(session, API_KEY, await start_server(chat=chat))

    assert await _collect(client) == [first, second]
    assert received["payload"] == PAYLOAD
    assert received["auth"] == f"Bearer {API_KEY}"


async def test_stream_ignores_comments_and_stops_at_done(
    deepseek, session, start_server
) -> None:
    chunk = {"choices": [{"delta": {"content": "ok"}}]}
    body = (
        b": keep-alive\n\n"
        + _sse(chunk, "[DONE]")
        + _sse({"choices": [{"delta": {"content": "dopo la fine"}}]})
    )
    base_url = await start_server(chat=_sse_handler(body))
    client = deepseek.DeepSeekClient(session, API_KEY, base_url)

    assert await _collect(client) == [chunk]


@pytest.mark.parametrize(("status", "error_name"), ERROR_CASES)
async def test_stream_http_errors(
    deepseek, session, start_server, status, error_name
) -> None:
    base_url = await start_server(chat=_status_handler(status, "motivo"))
    client = deepseek.DeepSeekClient(session, API_KEY, base_url)

    with pytest.raises(getattr(deepseek, error_name), match="motivo"):
        await _collect(client)


async def test_stream_invalid_json(deepseek, session, start_server) -> None:
    base_url = await start_server(chat=_sse_handler(_sse("{non json")))
    client = deepseek.DeepSeekClient(session, API_KEY, base_url)

    with pytest.raises(deepseek.DeepSeekServerError):
        await _collect(client)


async def test_stream_error_event(deepseek, session, start_server) -> None:
    body = _sse({"error": {"message": "sovraccarico"}})
    base_url = await start_server(chat=_sse_handler(body))
    client = deepseek.DeepSeekClient(session, API_KEY, base_url)

    with pytest.raises(deepseek.DeepSeekServerError, match="sovraccarico"):
        await _collect(client)


async def test_stream_interrupted(deepseek, session, start_server) -> None:
    """Se la connessione cade a metà risposta l'errore è di connessione."""
    chunk = {"choices": [{"delta": {"content": "Stavo dicendo"}}]}

    async def chat(request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse()
        response.content_type = "text/event-stream"
        await response.prepare(request)
        await response.write(_sse(chunk))
        assert request.transport is not None
        request.transport.close()
        return response

    client = deepseek.DeepSeekClient(session, API_KEY, await start_server(chat=chat))
    chunks = []

    with pytest.raises(deepseek.DeepSeekConnectionError):
        async for item in client.stream_chat(PAYLOAD):
            chunks.append(item)

    assert chunks == [chunk]


async def test_stream_timeout(deepseek, session, start_server, monkeypatch) -> None:
    async def chat(request: web.Request) -> web.StreamResponse:
        await asyncio.sleep(5)
        return web.Response(body=_sse("[DONE]"))

    monkeypatch.setattr(deepseek, "CHAT_TIMEOUT", aiohttp.ClientTimeout(total=0.2))
    client = deepseek.DeepSeekClient(session, API_KEY, await start_server(chat=chat))

    with pytest.raises(deepseek.DeepSeekConnectionError):
        await _collect(client)


def test_error_kinds(deepseek) -> None:
    """Ogni errore dichiara il tipo di messaggio da pronunciare."""
    assert deepseek.DeepSeekAuthError("x").kind == "auth"
    assert deepseek.DeepSeekBalanceError("x").kind == "balance"
    assert deepseek.DeepSeekRateLimitError("x").kind == "rate_limit"
    assert deepseek.DeepSeekServerError("x").kind == "server"
    assert deepseek.DeepSeekConnectionError("x").kind == "connection"


def test_accumulator_joins_fragments(deepseek) -> None:
    """Gli argomenti arrivano a pezzi: vanno ricomposti nell'ordine giusto."""
    accumulator = deepseek.ToolCallAccumulator()
    accumulator.add(
        [
            {
                "index": 0,
                "id": "call_1",
                "function": {"name": "HassTurnOn", "arguments": ""},
            }
        ]
    )
    accumulator.add([{"index": 0, "function": {"arguments": '{"name": "lu'}}])
    accumulator.add([{"index": 0, "function": {"arguments": 'ce"}'}}])

    assert accumulator.result() == [
        deepseek.ToolCall("call_1", "HassTurnOn", '{"name": "luce"}')
    ]


def test_accumulator_keeps_parallel_calls_apart(deepseek) -> None:
    accumulator = deepseek.ToolCallAccumulator()
    accumulator.add(
        [
            {"index": 1, "id": "b", "function": {"name": "Due", "arguments": "{"}},
            {"index": 0, "id": "a", "function": {"name": "Uno", "arguments": "{"}},
        ]
    )
    accumulator.add(
        [
            {"index": 0, "function": {"arguments": "}"}},
            {"index": 1, "function": {"arguments": "}"}},
        ]
    )

    assert accumulator.result() == [
        deepseek.ToolCall("a", "Uno", "{}"),
        deepseek.ToolCall("b", "Due", "{}"),
    ]


def test_accumulator_tolerates_repeated_names_and_missing_fields(deepseek) -> None:
    accumulator = deepseek.ToolCallAccumulator()
    accumulator.add([{"function": {"name": "Uno"}}])
    accumulator.add([{"function": {"name": "Uno", "arguments": None}}])

    assert accumulator.result() == [deepseek.ToolCall("", "Uno", "")]


def test_accumulator_empty(deepseek) -> None:
    assert deepseek.ToolCallAccumulator().result() == []
