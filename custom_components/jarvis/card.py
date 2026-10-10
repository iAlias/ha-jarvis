"""Card «Jarvis» per le dashboard: un pulsante che avvia l'ascolto."""

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN, LOGGER

CARD_FILENAME = "jarvis-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
CARD_PATH = Path(__file__).parent / "www" / CARD_FILENAME

_REGISTERED = f"{DOMAIN}_card_registered"


async def async_register_card(hass: HomeAssistant) -> bool:
    """Rende disponibile la card nelle dashboard.

    Va fatto una sola volta per avvio di Home Assistant: un percorso statico non
    si può registrare due volte, e l'integrazione può essere ricaricata.
    """
    if hass.data.get(_REGISTERED):
        return True
    if "frontend" not in hass.config.components:
        return False

    integration = await async_get_integration(hass, DOMAIN)
    # La versione nell'indirizzo fa ricaricare il file dopo un aggiornamento.
    url = f"{CARD_URL}?v={integration.version}"

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), True)]
    )

    # Le risorse delle dashboard vengono lette a ogni apertura. Il modulo extra
    # del frontend invece finisce nella pagina iniziale, che browser e app
    # tengono in memoria: lì una card nuova non compare finché la cache non
    # viene svuotata. Si usa quindi solo come ripiego.
    if not await _async_ensure_resource(hass, url):
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, url)

    hass.data[_REGISTERED] = True
    return True


async def async_unregister_card(hass: HomeAssistant) -> None:
    """Toglie la card dalle risorse delle dashboard quando Jarvis viene rimosso."""
    resources = _storage_resources(hass)
    if resources is None:
        return
    try:
        await resources.async_get_info()
        for item in list(resources.async_items()):
            if _is_card(item):
                await resources.async_delete_item(item["id"])
    except Exception:
        LOGGER.exception("Rimozione della card dalle risorse non riuscita")


def _storage_resources(hass: HomeAssistant):
    """Le risorse delle dashboard, se sono modificabili (non definite in YAML)."""
    if "lovelace" not in hass.config.components:
        return None

    # Importato qui: le dashboard sono un componente facoltativo.
    from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE

    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None or lovelace.resource_mode != MODE_STORAGE:
        return None
    return lovelace.resources


def _is_card(item: dict) -> bool:
    return item.get("url", "").split("?")[0] == CARD_URL


async def _async_ensure_resource(hass: HomeAssistant, url: str) -> bool:
    """Registra la card tra le risorse delle dashboard, o ne aggiorna la versione."""
    resources = _storage_resources(hass)
    if resources is None:
        return False

    try:
        # Carica l'elenco, se non è ancora stato letto.
        await resources.async_get_info()
        for item in resources.async_items():
            if _is_card(item):
                if item["url"] != url:
                    await resources.async_update_item(
                        item["id"], {"res_type": "module", "url": url}
                    )
                return True
        await resources.async_create_item({"res_type": "module", "url": url})
    except Exception:
        # Le risorse delle dashboard non sono di Jarvis: se la loro
        # interfaccia cambia resta il ripiego sul modulo extra.
        LOGGER.exception("Registrazione della card tra le risorse non riuscita")
        return False
    return True
