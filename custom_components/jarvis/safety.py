"""Cosa Jarvis non comanda mai a voce e cosa comanda solo dopo un sì.

Modulo senza dipendenze da Home Assistant: lavora su oggetti con gli attributi
di uno State (entity_id, domain, name, attributes).
"""

import re
from typing import Any

# Mai a voce: basta una voce da fuori la finestra per aprire casa.
BLOCKED_DOMAINS = {"lock", "alarm_control_panel"}
BLOCKED_COVER_CLASSES = {"gate", "garage", "door"}
# Solo dopo un sì: si muovono, e un equivoco può fare danni.
CONFIRM_DOMAINS = {"cover", "valve"}

# Argomenti degli strumenti di Assist che indicano su cosa agire.
TARGET_ARGS = ("name", "area", "floor", "domain", "device_class")

_YES = re.compile(
    r"\b(s[iì]|yes|sure|ok|okay|certo|confermo|procedi|vai|esatto|fallo|do it)\b",
    re.IGNORECASE,
)
_NO = re.compile(
    r"\b(no|non|annulla|lascia|aspetta|stop|cancel|don't)\b", re.IGNORECASE
)


def is_read_only(tool_name: str) -> bool:
    """Gli strumenti che leggono soltanto non vanno controllati."""
    # Gli strumenti di Assist possono avere un prefisso: homeassistant__GetLiveContext.
    return tool_name.rpartition("__")[2].startswith(("Get", "HassGet"))


def is_yes(text: str) -> bool:
    """La frase è una conferma (e non contiene un rifiuto)."""
    return bool(_YES.search(text)) and not _NO.search(text)


def _is_blocked(state: Any) -> bool:
    return state.domain in BLOCKED_DOMAINS or (
        state.domain == "cover"
        and state.attributes.get("device_class") in BLOCKED_COVER_CLASSES
    )


def _names(states: list[Any]) -> str:
    return ", ".join(sorted({state.name for state in states}))


class Guard:
    """Decide, per una frase dell'utente, quali comandi possono partire."""

    def __init__(
        self, pending: dict[str, set[str]], conversation_id: str, user_text: str
    ) -> None:
        """Una conferma vale solo per ciò che era stato chiesto al giro prima."""
        asked = pending.pop(conversation_id, set())
        self._approved = asked if is_yes(user_text) else set()
        self._pending = pending
        self._conversation_id = conversation_id

    def check(self, states: list[Any]) -> dict[str, str] | None:
        """None se il comando può partire, altrimenti l'esito da dare al modello."""
        if blocked := [state for state in states if _is_blocked(state)]:
            return {
                "error": "not_allowed_by_voice",
                "error_text": (
                    f"For safety, {_names(blocked)} cannot be controlled by voice. "
                    "Do not retry. Tell the user to use the Home Assistant app."
                ),
            }
        to_confirm = [
            state
            for state in states
            if state.domain in CONFIRM_DOMAINS and state.entity_id not in self._approved
        ]
        if to_confirm:
            self._pending.setdefault(self._conversation_id, set()).update(
                state.entity_id for state in to_confirm
            )
            return {
                "error": "confirmation_required",
                "error_text": (
                    f"Nothing moved yet. Ask the user to confirm moving "
                    f"{_names(to_confirm)}, with a short question ending in '?'. "
                    "Call the tool again only after they answer yes."
                ),
            }
        return None
