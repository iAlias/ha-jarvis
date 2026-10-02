"""Fixture dei test puri: caricano i moduli senza importare Home Assistant."""

import importlib.util
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path
from types import ModuleType

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

COMPONENT_DIR = Path(__file__).parents[2] / "custom_components" / "jarvis"

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]
StartServer = Callable[..., Awaitable[str]]


def _load(name: str) -> ModuleType:
    """Carica un modulo dal suo file, saltando il pacchetto che importa HA."""
    module_name = f"jarvis_pure_{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name, COMPONENT_DIR / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def deepseek() -> ModuleType:
    """Il modulo del client DeepSeek."""
    return _load("deepseek")


@pytest.fixture(scope="session")
def texts() -> ModuleType:
    """Il modulo dei testi."""
    return _load("texts")


@pytest.fixture
async def session() -> AsyncGenerator[aiohttp.ClientSession]:
    """Una sessione HTTP vera, chiusa a fine test."""
    async with aiohttp.ClientSession() as client_session:
        yield client_session


@pytest.fixture
async def start_server() -> AsyncGenerator[StartServer]:
    """Avvia un finto DeepSeek locale e ne restituisce l'indirizzo base."""
    servers: list[TestServer] = []

    async def _start(
        *, models: Handler | None = None, chat: Handler | None = None
    ) -> str:
        app = web.Application()
        if models is not None:
            app.router.add_get("/models", models)
        if chat is not None:
            app.router.add_post("/chat/completions", chat)
        server = TestServer(app)
        await server.start_server()
        servers.append(server)
        return str(server.make_url("")).rstrip("/")

    yield _start

    for server in servers:
        await server.close()
