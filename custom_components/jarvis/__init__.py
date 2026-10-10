"""Jarvis: assistente vocale per Home Assistant con DeepSeek come cervello."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .assistant import async_schedule_assistant_creation
from .card import async_register_card, async_unregister_card
from .const import LOGGER
from .deepseek import (
    DeepSeekAuthError,
    DeepSeekBalanceError,
    DeepSeekClient,
    DeepSeekError,
)

PLATFORMS = [Platform.CONVERSATION]

type JarvisConfigEntry = ConfigEntry[DeepSeekClient]


async def async_setup_entry(hass: HomeAssistant, entry: JarvisConfigEntry) -> bool:
    """Avvia Jarvis: verifica la API key e carica l'agente."""
    client = DeepSeekClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])

    try:
        await client.list_models()
    except DeepSeekAuthError as err:
        raise ConfigEntryAuthFailed("La API key DeepSeek non è valida") from err
    except DeepSeekBalanceError:
        # La chiave è valida: Jarvis parte e dirà a voce che il credito è finito.
        LOGGER.warning("Il credito DeepSeek risulta esaurito")
    except DeepSeekError as err:
        raise ConfigEntryNotReady(f"DeepSeek non raggiungibile: {err}") from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_card(hass)
    async_schedule_assistant_creation(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: JarvisConfigEntry) -> bool:
    """Ferma Jarvis."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: JarvisConfigEntry) -> None:
    """Pulisce ciò che Jarvis ha aggiunto fuori dalla propria configurazione."""
    await async_unregister_card(hass)
