# Jarvis, nucleo: piano di implementazione

> **Per chi esegue:** usare superpowers:executing-plans. Piano volutamente snello,
> su richiesta dell'utente: descrive file, interfacce e prove; il codice si
> scrive durante l'esecuzione, test compresi.

**Obiettivo:** integrazione Home Assistant `jarvis` con DeepSeek come cervello,
installabile da HACS e configurabile dalla sola API key.

**Architettura:** integrazione autonoma senza librerie esterne. Un client HTTP
indipendente da HA parla con DeepSeek in streaming; un traduttore converte tra
il formato di HA e quello di DeepSeek; un'entità conversazionale orchestra il
ciclo degli strumenti usando le API LLM ufficiali di HA.

**Tecnologie:** Python 3.14, Home Assistant 2026.9.4, `aiohttp`, `pytest`,
`pytest-homeassistant-custom-component` 0.13.367, `ruff`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-02-jarvis-nucleo-design.md`

## Vincoli globali

- Dominio `jarvis`; nessun `requirements` nel manifest; una sola installazione.
- Versione minima di HA 2026.9.0; versione dell'integrazione 0.1.0.
- Modello predefinito `deepseek-flash`; `thinking` sempre `{"type": "disabled"}`;
  `max_tokens` 1024; limite di 10 giri di strumenti.
- Tempi massimi: 60 s per chiamata, 30 s senza dati.
- Testi per l'utente in italiano e in inglese; italiano se la lingua è `it`.
- Commenti e documentazione in italiano; nomi nel codice in inglese.
- La API key non compare mai nei log né nel repository.
- Repository pubblico `iAlias/ha-jarvis`, licenza MIT.

## Dove girano i test

HA non si importa su Windows (manca `fcntl`, e il sistema blocca una libreria
compilata), quindi i test sono divisi in due gruppi:

| Gruppo | Cartella | Dove gira | Comando |
|---|---|---|---|
| Puri (senza HA) | `tests/unit` | su questo PC e in CI | `.venv\Scripts\python -m pytest tests/unit` |
| Con HA | `tests/ha` | solo in CI (Linux) | `pytest tests/ha` |

I moduli `deepseek.py` e `texts.py` non importano HA: i test puri li caricano
dal percorso del file, senza passare da `custom_components/jarvis/__init__.py`.

## Punti di attenzione

Casi che lo spec implica e che colpiscono chi usa il software. Ognuno ha il suo
test nel compito indicato.

1. Flusso interrotto a metà risposta: errore di connessione, non eccezione
   grezza (compito 2).
2. Argomenti di uno strumento spezzati su più frammenti, o JSON non valido: nel
   primo caso ricomposti, nel secondo esito d'errore senza eseguire (compiti 2
   e 3).
3. Parole d'invocazione con spazi, doppioni, maiuscole diverse o caratteri di
   template come `{{`: lista pulita e prompt che non si rompe (compito 2).
4. Risposta di DeepSeek senza alcun contenuto: messaggio a voce, non crash
   (compito 5).
5. Motori vocali non ancora caricati mentre HA si avvia: la creazione
   dell'assistente attende che HA sia avviato (compito 6).

---

## Compito 1: struttura, repository e CI

**File:** `.gitignore`, `.gitattributes`, `LICENSE`, `README.md`, `hacs.json`,
`pyproject.toml`, `requirements_local.txt`, `requirements_test.txt`,
`.github/workflows/tests.yml`, `.github/workflows/validate.yml`,
`custom_components/jarvis/manifest.json`, `custom_components/jarvis/const.py`.

- [ ] Creare i file di struttura e l'ambiente locale `.venv` con `uv`.
- [ ] `tests.yml`: un lavoro per `tests/unit` e uno per `tests/ha`, più `ruff check`.
- [ ] `validate.yml`: `hassfest` e validazione HACS.
- [ ] Creare il repository pubblico `iAlias/ha-jarvis` e fare il primo push.

## Compito 2: client DeepSeek e testi

**File:** `custom_components/jarvis/deepseek.py`,
`custom_components/jarvis/texts.py`, `tests/unit/conftest.py`,
`tests/unit/test_deepseek.py`, `tests/unit/test_texts.py`.

**Produce:**

- `DeepSeekClient(session, api_key, base_url=BASE_URL)` con
  `async list_models() -> list[Model]` e
  `stream_chat(payload: dict) -> AsyncGenerator[dict]`.
- `Model(id, name)`, `ToolCall(id, name, arguments)`,
  `ToolCallAccumulator.add(fragments)` e `.result() -> list[ToolCall]`.
- Eccezioni: `DeepSeekError` e le sottoclassi `DeepSeekAuthError`,
  `DeepSeekBalanceError`, `DeepSeekRateLimitError`, `DeepSeekServerError`,
  `DeepSeekConnectionError`.
- `texts.py`: `language_key(language) -> "it" | "en"`,
  `default_prompt(language)`, `build_prompt(prompt, words, language)`,
  `error_message(kind, language)`, `clean_invocation_words(words) -> list[str]`.

- [ ] Test contro un finto server locale: elenco modelli; flusso con testo;
  flusso con strumenti a frammenti; `[DONE]`; righe di commento; i cinque
  errori; flusso interrotto; riga non JSON.
- [ ] Test dei testi: scelta della lingua; pulizia delle parole; prompt con
  nomi contenenti `{{`.
- [ ] Implementare, far passare i test in locale, commit.

## Compito 3: traduttore

**File:** `custom_components/jarvis/chat.py`, `tests/ha/conftest.py`,
`tests/ha/test_chat.py`.

**Consuma:** `ToolCallAccumulator`, `ToolCall`.

**Produce:** `format_tool(tool, custom_serializer) -> dict`,
`build_messages(content) -> list[dict]`,
`async_transform_stream(chunks) -> AsyncGenerator[delta]`.

- [ ] Test: ogni tipo di messaggio; strumento convertito in JSON Schema; flusso
  di solo testo; flusso con strumento valido; argomenti non validi resi come
  richiesta esterna più esito d'errore; flusso vuoto.
- [ ] Implementare, push, CI verde, commit.

## Compito 4: configurazione

**File:** `custom_components/jarvis/__init__.py`, `config_flow.py`,
`translations/it.json`, `translations/en.json`, `tests/ha/test_config_flow.py`,
`tests/ha/test_init.py`.

**Produce:** voce di configurazione con `runtime_data: DeepSeekClient`; dati
`api_key`; opzioni `invocation_words`, `prompt`, `model`, `llm_hass_api`.

- [ ] Test: chiave valida; chiave sbagliata; rete assente; riautenticazione;
  salvataggio opzioni; parole vuote rifiutate; elenco modelli non raggiungibile;
  avvio con i vari errori.
- [ ] Implementare, push, CI verde, commit.

## Compito 5: agente

**File:** `custom_components/jarvis/conversation.py`,
`tests/ha/test_conversation.py`.

**Consuma:** tutto ciò che producono i compiti 2, 3 e 4.

- [ ] Test: risposta semplice; uno strumento; due giri; limite dei giri; ogni
  errore con il suo messaggio a voce; chiave revocata che avvia la
  riautenticazione; risposta vuota; riga dei nomi presente nel prompt.
- [ ] Implementare, push, CI verde, commit.

## Compito 6: assistente automatico

**File:** `custom_components/jarvis/assistant.py`, `tests/ha/test_assistant.py`.

- [ ] Test: creazione riuscita; motori assenti con notifica; errore con
  notifica; nessun secondo tentativo; attesa dell'avvio di HA.
- [ ] Implementare, push, CI verde, commit.

## Compito 7: rifinitura e rilascio

- [ ] README completo in italiano: installazione, impostazioni, uso, costi,
  riservatezza, risoluzione dei problemi.
- [ ] `hassfest` e validazione HACS verdi.
- [ ] Rilascio `v0.1.0` su GitHub.
- [ ] Consegnare all'utente la lista di collaudo della sezione 14 dello spec.
