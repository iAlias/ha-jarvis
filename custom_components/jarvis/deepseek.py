"""Client HTTP di DeepSeek.

Questo modulo non importa Home Assistant: dipende solo da aiohttp, così si
collauda da solo.
"""

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import aiohttp

BASE_URL = "https://api.deepseek.com"

MODELS_TIMEOUT = aiohttp.ClientTimeout(total=10)
# 60 secondi per l'intera chiamata, 30 senza ricevere dati.
CHAT_TIMEOUT = aiohttp.ClientTimeout(total=60, sock_read=30)


class DeepSeekError(Exception):
    """Errore nel parlare con DeepSeek.

    `kind` indica quale messaggio pronunciare all'utente.
    """

    kind = "server"


class DeepSeekAuthError(DeepSeekError):
    """La API key è sbagliata o revocata."""

    kind = "auth"


class DeepSeekBalanceError(DeepSeekError):
    """Il credito è esaurito."""

    kind = "balance"


class DeepSeekRateLimitError(DeepSeekError):
    """Troppe richieste."""

    kind = "rate_limit"


class DeepSeekServerError(DeepSeekError):
    """DeepSeek ha risposto con un errore o con dati non validi."""

    kind = "server"


class DeepSeekConnectionError(DeepSeekError):
    """Rete assente, connessione caduta o tempo scaduto."""

    kind = "connection"


@dataclass(frozen=True, slots=True)
class Model:
    """Un modello offerto da DeepSeek."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Una richiesta di strumento ricomposta; `arguments` è ancora testo JSON."""

    id: str
    name: str
    arguments: str


class ToolCallAccumulator:
    """Ricompone le richieste di strumenti che in streaming arrivano a frammenti."""

    def __init__(self) -> None:
        """Parte senza richieste."""
        self._calls: dict[int, dict[str, str]] = {}

    def add(self, fragments: list[dict[str, Any]]) -> None:
        """Aggiunge i frammenti di un evento, distinguendo le richieste per indice."""
        for fragment in fragments:
            index = fragment.get("index") or 0
            call = self._calls.setdefault(
                index, {"id": "", "name": "", "arguments": ""}
            )
            if fragment.get("id"):
                call["id"] = fragment["id"]
            function = fragment.get("function") or {}
            # Il nome arriva intero; alcuni servizi lo ripetono a ogni frammento.
            if function.get("name") and not call["name"]:
                call["name"] = function["name"]
            if function.get("arguments"):
                call["arguments"] += function["arguments"]

    def result(self) -> list[ToolCall]:
        """Le richieste ricomposte, nell'ordine in cui il modello le ha emesse."""
        return [ToolCall(**self._calls[index]) for index in sorted(self._calls)]


def _message_from(body: Any) -> str:
    """Estrae il messaggio d'errore dal corpo di una risposta, se c'è."""
    if not isinstance(body, dict):
        return ""
    error = body.get("error", body)
    if isinstance(error, str):
        return error
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    return ""


def _describe(err: Exception) -> str:
    return str(err) or type(err).__name__


async def _raise_for_status(response: aiohttp.ClientResponse) -> None:
    """Traduce uno stato HTTP d'errore nell'eccezione corrispondente."""
    if response.status < 400:
        return
    try:
        message = _message_from(await response.json(content_type=None))
    except ValueError:
        message = ""
    message = message or f"HTTP {response.status}"
    if response.status == 401:
        raise DeepSeekAuthError(message)
    if response.status == 402:
        raise DeepSeekBalanceError(message)
    if response.status == 429:
        raise DeepSeekRateLimitError(message)
    raise DeepSeekServerError(message)


class DeepSeekClient:
    """Parla con le API di DeepSeek nel formato compatibile OpenAI."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        base_url: str = BASE_URL,
    ) -> None:
        """Prepara il client; la sessione HTTP resta di chi la fornisce."""
        self._session = session
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._base_url = base_url.rstrip("/")

    async def list_models(self) -> list[Model]:
        """Elenca i modelli. Serve anche a verificare la API key."""
        try:
            async with self._session.get(
                f"{self._base_url}/models",
                headers=self._headers,
                timeout=MODELS_TIMEOUT,
            ) as response:
                await _raise_for_status(response)
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DeepSeekConnectionError(_describe(err)) from err
        except ValueError as err:
            raise DeepSeekServerError("Risposta non valida da DeepSeek") from err

        entries = body.get("data") if isinstance(body, dict) else None
        if not isinstance(entries, list):
            raise DeepSeekServerError("Risposta inattesa da DeepSeek")
        return [
            Model(id=entry["id"], name=entry.get("name") or entry["id"])
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        ]

    async def stream_chat(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[dict[str, Any]]:
        """Invia una richiesta di chat e restituisce i frammenti della risposta."""
        try:
            async with self._session.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers,
                json=payload,
                timeout=CHAT_TIMEOUT,
            ) as response:
                await _raise_for_status(response)
                async for raw_line in response.content:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    # Le righe vuote e i commenti (": keep-alive") non contano.
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        return
                    chunk = json.loads(data)
                    if isinstance(chunk, dict) and "error" in chunk:
                        raise DeepSeekServerError(
                            _message_from(chunk) or "Errore di DeepSeek"
                        )
                    yield chunk
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DeepSeekConnectionError(_describe(err)) from err
        except ValueError as err:
            raise DeepSeekServerError("Risposta non valida da DeepSeek") from err
