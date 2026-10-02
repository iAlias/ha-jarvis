"""Creazione automatica dell'assistente vocale «Jarvis»."""

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.start import async_at_started

from .const import CONF_ASSISTANT_CREATED, DEFAULT_NAME, DOMAIN, LOGGER
from .texts import assistant_help

NOTIFICATION_ID = "jarvis_assistant_setup"


@callback
def async_schedule_assistant_creation(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Programma la creazione dell'assistente: una sola volta, a HA avviato.

    Durante l'avvio i motori vocali possono non essere ancora carichi: per questo
    si aspetta che Home Assistant sia partito del tutto.
    """
    if entry.data.get(CONF_ASSISTANT_CREATED):
        return

    async def _create(hass: HomeAssistant) -> None:
        await async_create_assistant(hass, entry)

    entry.async_on_unload(async_at_started(hass, _create))


async def async_create_assistant(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Crea l'assistente oppure spiega come farlo a mano. Non riprova più."""
    created = False
    try:
        created = await _async_create_pipeline(hass, entry)
    except Exception:
        # Le API delle pipeline non sono di Jarvis: un loro errore non deve
        # impedirgli di funzionare. Resta la strada manuale.
        LOGGER.exception("Creazione automatica dell'assistente non riuscita")

    if not created:
        title, message = assistant_help(hass.config.language)
        persistent_notification.async_create(
            hass, message, title=title, notification_id=NOTIFICATION_ID
        )

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_ASSISTANT_CREATED: True}
    )
    return created


async def _async_create_pipeline(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Crea la pipeline «Jarvis» con i motori vocali predefiniti di HA."""
    if "assist_pipeline" not in hass.config.components:
        return False

    entity_id = er.async_get(hass).async_get_entity_id(
        "conversation", DOMAIN, entry.entry_id
    )
    if entity_id is None:
        return False

    # Importati qui: sono componenti facoltativi, presenti solo se caricati.
    from homeassistant.components import assist_pipeline, stt, tts

    stt_engine = stt.async_default_engine(hass)
    tts_engine = tts.async_default_engine(hass)
    if stt_engine is None or tts_engine is None:
        return False

    pipeline = await assist_pipeline.async_create_default_pipeline(
        hass,
        stt_engine_id=stt_engine,
        tts_engine_id=tts_engine,
        pipeline_name=DEFAULT_NAME,
    )
    if pipeline is None:
        return False

    await assist_pipeline.async_update_pipeline(
        hass,
        pipeline,
        conversation_engine=entity_id,
        conversation_language=MATCH_ALL,
    )
    return True
