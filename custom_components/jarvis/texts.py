"""Testi di Jarvis: personalità, riga dei nomi e messaggi d'errore.

Questo modulo non importa Home Assistant, così si collauda da solo.
"""

from collections.abc import Iterable
import re

ITALIAN = "it"
ENGLISH = "en"

DEFAULT_PROMPTS = {
    ITALIAN: """Sei l'assistente vocale della casa «{{ ha_name }}».
Hai il tono di un maggiordomo inglese: cortese, asciutto, con un filo di ironia.
Le tue risposte vengono lette ad alta voce: usa una o due frasi brevi, senza elenchi, simboli o formattazione.
Quando esegui un comando, conferma in poche parole.
Se non è chiaro a quale dispositivo si riferisce la richiesta, chiedi quale.
Rispondi nella lingua in cui ti viene rivolta la parola.
""",  # noqa: E501
    ENGLISH: """You are the voice assistant of the home "{{ ha_name }}".
You sound like an English butler: courteous, dry, with a hint of irony.
Your answers are read aloud: use one or two short sentences, with no lists, symbols or formatting.
When you carry out a command, confirm it in a few words.
If it is unclear which device a request refers to, ask which one.
Reply in the language you are spoken to in.
""",  # noqa: E501
}

NAMES_LINES = {
    ITALIAN: (
        "Rispondi a questi nomi: {names}. Se un messaggio inizia con uno di questi"
        " nomi, anche scritto in modo impreciso, è solo il modo in cui ti chiamano:"
        " non fa parte della richiesta."
    ),
    ENGLISH: (
        "You answer to these names: {names}. If a message starts with one of these"
        " names, even if misspelled, it is only how you are being called: it is not"
        " part of the request."
    ),
}

ERROR_MESSAGES = {
    "auth": {
        ITALIAN: (
            "La chiave DeepSeek non è più valida. Va reinserita nelle impostazioni"
            " di Home Assistant."
        ),
        ENGLISH: (
            "The DeepSeek key is no longer valid. Please enter it again in the"
            " Home Assistant settings."
        ),
    },
    "balance": {
        ITALIAN: "Il credito DeepSeek è esaurito.",
        ENGLISH: "The DeepSeek credit has run out.",
    },
    "rate_limit": {
        ITALIAN: "DeepSeek è sovraccarico in questo momento. Riprova tra poco.",
        ENGLISH: "DeepSeek is overloaded right now. Please try again shortly.",
    },
    "server": {
        ITALIAN: "DeepSeek ha risposto con un errore. Riprova tra poco.",
        ENGLISH: "DeepSeek returned an error. Please try again shortly.",
    },
    "connection": {
        ITALIAN: "Non riesco a collegarmi a DeepSeek.",
        ENGLISH: "I cannot reach DeepSeek.",
    },
    "too_many_steps": {
        ITALIAN: "La richiesta ha richiesto troppi passaggi e mi sono fermato.",
        ENGLISH: "The request needed too many steps, so I stopped.",
    },
}

# Titolo e testo della notifica mostrata quando l'assistente vocale non si è
# potuto creare in automatico.
ASSISTANT_HELP = {
    ITALIAN: (
        "Jarvis: aggiungi l'assistente vocale",
        "Non ho potuto creare da solo l'assistente vocale «Jarvis». Per farlo a"
        " mano: apri Impostazioni → Assistenti vocali, premi «Aggiungi"
        " assistente», dagli un nome e scegli «Jarvis» come agente di"
        " conversazione.",
    ),
    ENGLISH: (
        "Jarvis: add the voice assistant",
        'I could not create the "Jarvis" voice assistant on my own. To do it by'
        ' hand: open Settings → Voice assistants, press "Add assistant", give'
        ' it a name and pick "Jarvis" as the conversation agent.',
    ),
}

_ENDRAW = re.compile(r"\{%-?\s*endraw\s*-?%\}")


def language_key(language: str | None) -> str:
    """Italiano se la lingua è `it` (anche `it-IT`), altrimenti inglese."""
    if language and language.replace("_", "-").split("-")[0].lower() == ITALIAN:
        return ITALIAN
    return ENGLISH


def default_prompt(language: str | None) -> str:
    """Personalità predefinita nella lingua indicata."""
    return DEFAULT_PROMPTS[language_key(language)]


def error_message(kind: str, language: str | None) -> str:
    """Messaggio da pronunciare per un tipo di errore."""
    messages = ERROR_MESSAGES.get(kind, ERROR_MESSAGES["server"])
    return messages[language_key(language)]


def assistant_help(language: str | None) -> tuple[str, str]:
    """Titolo e testo con i passaggi manuali per aggiungere l'assistente."""
    return ASSISTANT_HELP[language_key(language)]


def clean_invocation_words(words: Iterable[str]) -> list[str]:
    """Toglie spazi superflui, voci vuote e doppioni (ignorando le maiuscole)."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for word in words:
        word = " ".join(str(word).split())
        key = word.casefold()
        if not word or key in seen:
            continue
        seen.add(key)
        cleaned.append(word)
    return cleaned


def build_prompt(prompt: str, words: Iterable[str], language: str | None) -> str:
    """Personalità seguita dalla riga con i nomi a cui Jarvis risponde."""
    names = ", ".join(clean_invocation_words(words))
    if not names:
        return prompt
    line = NAMES_LINES[language_key(language)].format(names=names)
    # HA tratta il prompt come un template. Le parole d'invocazione sono testo
    # libero dell'utente: dentro `raw` restano testo, e va tolta l'unica
    # sequenza che chiuderebbe il blocco.
    line = _ENDRAW.sub("", line)
    return f"{prompt.rstrip()}\n{{% raw %}}{line}{{% endraw %}}"
