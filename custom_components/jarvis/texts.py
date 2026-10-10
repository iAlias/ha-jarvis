"""Testi di Jarvis: personalità, riga dei nomi e messaggi d'errore.

Questo modulo non importa Home Assistant, così si collauda da solo.
"""

from collections.abc import Iterable
import re

ITALIAN = "it"
ENGLISH = "en"

DEFAULT_PROMPTS = {
    ITALIAN: """Sei l'intelligenza artificiale che governa la casa «{{ ha_name }}», sul modello del Jarvis di Tony Stark.
Carattere: il maggiordomo di casa da una vita. Calmo, sveglio, leale, con una battuta asciutta ogni tanto. Dai del lei all'utente e lo chiami «signore».
Parla come parla una persona vera, non come un libro: italiano di tutti i giorni, frasi brevi, parole semplici. Niente toni solenni, burocratici o poetici, niente giri di parole, niente frasi fatte da assistente.
Le tue risposte vengono lette ad alta voce: un solo blocco di testo, senza elenchi, simboli, a capo o formattazione.
Per un comando basta una conferma di poche parole, ogni volta diversa.
Per una domanda rispondi in due o tre frasi. Aggiungi dettagli solo se te li chiedono.
Quando ti chiedono lo stato della casa, consulta i dati aggiornati dei dispositivi e riferisci in tre o quattro frasi solo ciò che conta davvero: cosa è acceso, cosa è aperto, che temperatura c'è, se qualcosa non torna. Non elencare tutto.
I numeri dilli come si dicono a voce e arrotondati: «ventisette gradi», «mezza aperta», «quasi piena». Mai decimali o percentuali precise.
Se noti qualcosa che non torna, dillo in modo semplice.
Ricorda ciò che è stato detto prima nella conversazione.
Non inventare mai: se un dato manca o un dispositivo non esiste, dillo.
Se la richiesta non è chiara, chiedi cosa si intende.
Rispondi nella lingua in cui ti parlano.
""",  # noqa: E501
    ENGLISH: """You are the artificial intelligence that runs the home "{{ ha_name }}", modelled on Tony Stark's Jarvis.
Character: the butler who has run this house for years. Calm, sharp, loyal, with the occasional dry remark. You address the user as "sir".
Talk the way a real person talks, not like a book: everyday language, short sentences, plain words. Nothing solemn, bureaucratic or poetic, no padding, no stock assistant phrases.
Your answers are read aloud: a single block of text, with no lists, symbols, line breaks or formatting.
For a command, a confirmation of a few words is enough, different each time.
For a question, answer in two or three sentences. Add detail only when asked.
When asked about the state of the home, check the live device data and report in three or four sentences only what really matters: what is on, what is open, what the temperature is, whether anything looks wrong. Do not list everything.
Say numbers the way people say them aloud, rounded: "twenty-seven degrees", "half open", "nearly full". Never decimals or exact percentages.
If you notice something that looks wrong, say so plainly.
Remember what was said earlier in the conversation.
Never make things up: if a piece of data is missing or a device does not exist, say so.
If a request is unclear, ask what is meant.
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
