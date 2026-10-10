"""Card «Jarvis» per le dashboard: un pulsante che avvia l'ascolto."""

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

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

    # Importato qui: il frontend è facoltativo, presente solo se caricato.
    from homeassistant.components.frontend import add_extra_js_url

    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), True)]
    )
    # La versione nell'indirizzo fa ricaricare il file dopo un aggiornamento.
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
    hass.data[_REGISTERED] = True
    return True
