# Jarvis, pezzo 1: il nucleo (integrazione Home Assistant)

- **Data:** 2026-10-02
- **Stato:** design approvato in conversazione, in attesa di revisione dello spec scritto
- **Ambito:** primo di quattro pezzi (vedi "Il progetto completo")

## 1. Intento

### Cosa vuole l'utente

Un assistente in stile Jarvis (il maggiordomo digitale di Iron Man) da usare con
Home Assistant: gli si parla, capisce, comanda la casa e risponde a voce.

Richieste espresse:

- Deve funzionare **dentro Home Assistant**.
- Il "cervello" è **DeepSeek**, tramite API key.
- Deve essere **semplice da installare e semplicissimo da usare**.
- Si invoca **con la voce**, con una o più **parole scelte dall'utente nelle
  impostazioni** (esempi dati: "Alfredo", "Jarvis", "mbare").
- Deve saper: comandare la casa, dire lo stato della casa, conversare e
  rispondere a domande generali, comandare il PC.
- Deve includere un **sistema di sicurezza** che avvisa quando si collega un
  nuovo dispositivo (a Jarvis o alla rete di casa), notificando tutti i
  dispositivi già collegati.

Assunzioni non contestate dall'utente:

- La lingua d'uso è l'italiano.
- Le parole d'invocazione sono alias dello stesso assistente: una sola
  personalità.
- Home Assistant è già installato ed è aggiornato a una versione recente.

### Criterio di successo del nucleo

L'utente installa l'integrazione, incolla la API key DeepSeek e, senza toccare
file, può scrivere o dire in Assist "accendi la luce del salotto": Jarvis esegue
e risponde nel suo stile. Le parole d'invocazione si modificano dalle
impostazioni.

## 2. Il progetto completo

Il progetto è diviso in quattro pezzi, ognuno con il proprio spec, piano e
implementazione. Ordine concordato:

| # | Pezzo | Cosa aggiunge |
|---|---|---|
| 1 | **Nucleo** (questo spec) | Integrazione HA: DeepSeek come cervello, impostazioni, controllo e stato della casa, conversazione. |
| 2 | Orecchie PC | Programma Windows: ascolto continuo dal microfono, riconoscimento delle parole d'invocazione, risposta dalle casse, comandi per il PC. |
| 3 | Orecchie HA | Motore wake word testuale per i dispositivi vocali collegati a HA. |
| 4 | Sicurezza | Avviso per nuovi dispositivi Jarvis e per nuovi dispositivi sulla rete di casa. |

Decisioni già prese che riguardano i pezzi successivi:

- La lista delle parole d'invocazione vive in un posto solo: le impostazioni
  dell'integrazione in HA. Le "orecchie" la leggono da lì.
- HA non permette di usare un testo libero come wake word: i motori nativi usano
  modelli audio addestrati uno per uno. Il riconoscimento delle parole scelte
  dall'utente si farà quindi cercandole nella trascrizione del parlato, con
  confronto tollerante agli errori di trascrizione. Quel riconoscimento viene
  costruito nel pezzo 2 e riusato nel pezzo 3.

## 3. Ambito del nucleo

### Incluso

- Integrazione personalizzata `jarvis` per Home Assistant, installabile da HACS.
- Configurazione da interfaccia: API key DeepSeek, con verifica.
- Agente conversazionale `conversation.jarvis` utilizzabile da Assist.
- Controllo e lettura dei dispositivi esposti ad Assist, tramite le API LLM
  ufficiali di HA.
- Conversazione e domande generali.
- Impostazioni: parole d'invocazione, personalità, modello, strumenti.
- Risposte in streaming.
- Creazione automatica, una sola volta, dell'assistente vocale "Jarvis".
- Gestione degli errori con messaggi pronunciabili.
- Test automatici e validazione HACS in CI.

### Escluso (rimandato o non necessario)

- Ascolto continuo e invocazione a voce senza pulsante (pezzi 2 e 3).
- Riconoscimento "rigido" delle parole d'invocazione via codice (pezzo 2).
- Comandi per il PC (pezzo 2).
- Sistema di sicurezza (pezzo 4).
- Riconoscimento e sintesi vocale: DeepSeek non li offre; li fornisce Assist con
  i motori già presenti in HA.
- Modalità "thinking" di DeepSeek, ricerca web, più agenti nella stessa
  installazione, endpoint API alternativi, icona personalizzata, AI Task.

## 4. Esperienza d'uso

### Installazione, una volta sola

1. In HACS l'utente aggiunge il repository come "custom repository" di tipo
   Integrazione, installa "Jarvis" e riavvia HA.
2. Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Jarvis.
   Incolla la API key DeepSeek. L'integrazione verifica la chiave e si configura
   con i valori consigliati.
3. L'integrazione prova a creare l'assistente "Jarvis" tra gli assistenti
   vocali. Se non è possibile, mostra una notifica con i passaggi manuali.

### Impostazioni (pulsante "Configura")

| Campo | Tipo | Valore iniziale |
|---|---|---|
| Parole d'invocazione | lista di testi, almeno uno | `Jarvis` |
| Personalità | testo (accetta template di HA) | vedi sezione 8 |
| Modello | scelta dall'elenco fornito da DeepSeek | `deepseek-flash` |
| Strumenti | scelta multipla tra le API LLM di HA | `Assist` |

Regole per le parole d'invocazione: gli spazi iniziali e finali vengono tolti,
le voci vuote scartate, i doppioni (ignorando maiuscole e minuscole) eliminati.
Se non resta nessuna parola il modulo mostra un errore e non salva.

Se l'elenco dei modelli non è raggiungibile, il campo propone `deepseek-flash`,
`deepseek-v4-pro` e il modello attualmente salvato.

Se il campo "Strumenti" viene lasciato vuoto, Jarvis conversa soltanto e non
può né leggere né comandare i dispositivi.

Le modifiche hanno effetto dalla richiesta successiva, senza riavviare HA.

### Uso

- L'utente apre Assist (app o browser), sceglie l'assistente "Jarvis" e scrive
  oppure usa il microfono.
- Se la frase inizia con una parola d'invocazione ("mbare, spegni tutto"),
  Jarvis la tratta come il modo in cui è stato chiamato e non come parte della
  richiesta.
- I dispositivi che Jarvis può vedere e comandare sono quelli esposti in
  Impostazioni → Assistenti vocali → Esponi.

## 5. Architettura

Un'integrazione HA autonoma, senza librerie esterne: usa la sessione HTTP già
presente in HA. Segue lo schema delle integrazioni LLM ufficiali (riferimento:
`open_router` in HA 2026.9.4).

```
custom_components/jarvis/
├── manifest.json        metadati; nessun requirement
├── __init__.py          avvio e arresto dell'integrazione
├── const.py             costanti e valori predefiniti
├── config_flow.py       configurazione, riautenticazione, impostazioni
├── deepseek.py          client HTTP di DeepSeek (non dipende da HA)
├── chat.py              traduzione tra formato HA e formato DeepSeek
├── conversation.py      l'agente conversazionale
├── assistant.py         creazione automatica dell'assistente vocale
└── translations/        testi dell'interfaccia: it.json, en.json
```

| Unità | Responsabilità | Dipende da |
|---|---|---|
| `deepseek.py` | Elencare i modelli, inviare una richiesta di chat in streaming, tradurre gli errori HTTP in eccezioni tipizzate. | solo `aiohttp` |
| `chat.py` | Convertire cronologia e strumenti di HA nel formato DeepSeek; convertire il flusso di risposta nei "delta" attesi da HA. | tipi di HA |
| `conversation.py` | Orchestrare una richiesta: istruzioni, ciclo degli strumenti, risposta, errori. | `deepseek.py`, `chat.py` |
| `config_flow.py` | Raccogliere e validare API key e impostazioni. | `deepseek.py` |
| `assistant.py` | Creare una volta l'assistente "Jarvis". | `assist_pipeline` di HA |
| `__init__.py` | Creare il client, verificare la chiave, caricare l'agente. | tutte |

`deepseek.py` è volutamente indipendente da HA: si collauda da solo, anche su
Windows.

## 6. Flusso di una richiesta

Esempio: "mbare, spegni le luci".

1. Assist consegna il testo all'agente Jarvis, insieme alla cronologia della
   conversazione.
2. L'agente chiede a HA le istruzioni e gli strumenti delle API LLM selezionate
   (di base `Assist`) e fornisce il proprio prompt: personalità più riga dei
   nomi (sezione 8).
3. `chat.py` converte cronologia e strumenti nel formato DeepSeek.
4. `deepseek.py` invia la richiesta in streaming, con il "thinking" disattivato.
5. Il testo che arriva viene inoltrato a HA pezzo per pezzo. Le richieste di
   strumenti vengono ricomposte e passate a HA, che le esegue e ne registra
   l'esito.
6. Se ci sono esiti di strumenti senza risposta, si torna al passo 3. Limite:
   10 giri.
7. L'agente restituisce a HA il risultato costruito dalla cronologia. Se la
   risposta finisce con una domanda, HA tiene aperta la conversazione.

Il testo dell'utente non viene modificato: il nome d'invocazione a inizio frase
è gestito dal modello grazie alla riga dei nomi nel prompt. Tagliarlo via codice
rovinerebbe frasi come "Alfredo è un nome italiano?".

## 7. Dati salvati

Nella voce di configurazione di HA, che HA conserva nel proprio archivio:

| Dove | Chiave | Contenuto |
|---|---|---|
| dati | `api_key` | la API key DeepSeek |
| dati | `assistant_created` | vero dopo il tentativo di creare l'assistente |
| opzioni | `invocation_words` | lista di testi |
| opzioni | `prompt` | testo della personalità |
| opzioni | `model` | identificativo del modello |
| opzioni | `llm_hass_api` | lista di identificativi delle API LLM |

È ammessa una sola installazione di Jarvis per istanza di HA.

## 8. Prompt

Il prompt passato a HA è la personalità seguita dalla riga dei nomi. HA vi
aggiunge da sé le istruzioni e l'elenco dei dispositivi esposti.

La personalità predefinita e la riga dei nomi esistono in italiano e in inglese.
La personalità predefinita viene scelta alla prima configurazione in base alla
lingua di HA (italiano se la lingua è `it`, altrimenti inglese). La riga dei
nomi segue la lingua della richiesta, con la stessa regola.

Personalità predefinita, italiano:

```
Sei l'assistente vocale della casa «{{ ha_name }}».
Hai il tono di un maggiordomo inglese: cortese, asciutto, con un filo di ironia.
Le tue risposte vengono lette ad alta voce: usa una o due frasi brevi, senza elenchi, simboli o formattazione.
Quando esegui un comando, conferma in poche parole.
Se non è chiaro a quale dispositivo si riferisce la richiesta, chiedi quale.
Rispondi nella lingua in cui ti viene rivolta la parola.
```

Riga dei nomi, italiano (i nomi sono le parole d'invocazione, separate da
virgola):

```
Rispondi a questi nomi: {nomi}. Se un messaggio inizia con uno di questi nomi, anche scritto in modo impreciso, è solo il modo in cui ti chiamano: non fa parte della richiesta.
```

Personalità predefinita, inglese:

```
You are the voice assistant of the home "{{ ha_name }}".
You sound like an English butler: courteous, dry, with a hint of irony.
Your answers are read aloud: use one or two short sentences, with no lists, symbols or formatting.
When you carry out a command, confirm it in a few words.
If it is unclear which device a request refers to, ask which one.
Reply in the language you are spoken to in.
```

Riga dei nomi, inglese:

```
You answer to these names: {names}. If a message starts with one of these names, even if misspelled, it is only how you are being called: it is not part of the request.
```

La personalità non contiene un nome proprio: il nome viene sempre dalla lista
delle parole d'invocazione, così le due cose non possono contraddirsi.

## 9. Client DeepSeek

- Indirizzo base: `https://api.deepseek.com`. Autenticazione con header
  `Authorization: Bearer <chiave>`.
- `GET /models`: elenco dei modelli. Serve a verificare la chiave e a popolare
  il campo "Modello".
- `POST /chat/completions`: richiesta di chat nel formato compatibile OpenAI.

Corpo della richiesta di chat:

| Campo | Valore |
|---|---|
| `model` | il modello scelto |
| `messages` | la cronologia convertita |
| `stream` | `true` |
| `thinking` | `{"type": "disabled"}` |
| `max_tokens` | `1024` |
| `tools` | gli strumenti convertiti; campo omesso se non ce ne sono |

Il "thinking" va disattivato esplicitamente perché DeepSeek lo attiva di
default: rallenta la risposta e, con gli strumenti, obbliga a rimandare indietro
il ragionamento a ogni giro.

`max_tokens` è un tetto di sicurezza su costo e durata: le risposte vocali sono
brevi. Tutti gli altri parametri restano ai valori predefiniti di DeepSeek.

La risposta è un flusso di eventi `data: {...}` chiuso da `data: [DONE]`. Il
client restituisce i frammenti già interpretati, uno alla volta.

Tempi massimi: 60 secondi per l'intera chiamata, 30 secondi senza ricevere dati.

Conversione degli strumenti: lo schema dei parametri di ogni strumento HA viene
convertito in JSON Schema con la funzione che usa HA stesso (`to_openapi`),
scartando le chiavi di primo livello non supportate, come fa l'integrazione
ufficiale di riferimento.

Ricomposizione delle richieste di strumenti: in streaming gli argomenti arrivano
a frammenti. Il traduttore li accumula per indice e, a flusso concluso, li passa
a HA. Se gli argomenti non sono JSON valido, lo strumento **non viene eseguito**:
al modello torna un esito di errore, così può riprovare.

## 10. Gestione degli errori

Il client distingue cinque casi:

| Caso | Causa | All'avvio | Durante una conversazione |
|---|---|---|---|
| Autenticazione | HTTP 401 | HA chiede di riautenticare | messaggio a voce, e HA chiede di riautenticare |
| Credito | HTTP 402 | l'integrazione parte comunque | messaggio a voce: credito esaurito |
| Limite di richieste | HTTP 429 | HA riprova più tardi | messaggio a voce: riprova tra poco |
| Errore del servizio | altri errori HTTP | HA riprova più tardi | messaggio a voce: servizio non disponibile |
| Connessione | rete assente o tempo scaduto | HA riprova più tardi | messaggio a voce: impossibile collegarsi |

Messaggi a voce. Seguono la lingua della richiesta: italiano se è `it`,
altrimenti inglese.

| Caso | Italiano | Inglese |
|---|---|---|
| Autenticazione | La chiave DeepSeek non è più valida. Va reinserita nelle impostazioni di Home Assistant. | The DeepSeek key is no longer valid. Please enter it again in the Home Assistant settings. |
| Credito | Il credito DeepSeek è esaurito. | The DeepSeek credit has run out. |
| Limite di richieste | DeepSeek è sovraccarico in questo momento. Riprova tra poco. | DeepSeek is overloaded right now. Please try again shortly. |
| Errore del servizio | DeepSeek ha risposto con un errore. Riprova tra poco. | DeepSeek returned an error. Please try again shortly. |
| Connessione | Non riesco a collegarmi a DeepSeek. | I cannot reach DeepSeek. |
| Limite dei giri | La richiesta ha richiesto troppi passaggi e mi sono fermato. | The request needed too many steps, so I stopped. |

Altre regole:

- Chiave sbagliata nel modulo di configurazione: errore nel modulo, nulla viene
  salvato.
- Riautenticazione: l'utente inserisce la nuova chiave, che viene verificata
  come alla prima configurazione; se è valida l'integrazione si ricarica.
- Limite di 10 giri raggiunto: l'agente si ferma e pronuncia il messaggio
  "Limite dei giri".
- Nessun tentativo automatico ripetuto durante una conversazione: una risposta
  d'errore rapida è preferibile a un'attesa lunga.
- La API key non viene mai scritta nei log.

## 11. Creazione automatica dell'assistente

Al primo avvio riuscito, una sola volta:

1. Se HA ha un motore di riconoscimento vocale e uno di sintesi predefiniti,
   l'integrazione crea un assistente vocale chiamato "Jarvis" con quei motori e
   con Jarvis come agente di conversazione. Usa le funzioni pubbliche di
   `assist_pipeline`.
2. Altrimenti, o se la creazione fallisce, mostra una notifica persistente con i
   passaggi manuali.
3. In entrambi i casi segna `assistant_created`, così non riprova ai riavvii.

L'assistente preferito dell'utente non viene modificato. Se l'utente elimina
l'assistente "Jarvis", non viene ricreato.

## 12. Predisposizioni per i pezzi successivi

Nel nucleo non si costruisce nulla di ciò che segue; si evita solo di chiudere
le strade.

- **Comandi per il PC (pezzo 2):** il campo "Strumenti" accetta più API LLM. Il
  pezzo 2 registrerà una seconda API con gli strumenti del PC, che si affianca
  ad `Assist` senza modificare l'agente.
- **Orecchie (pezzi 2 e 3):** la lista delle parole d'invocazione è nelle
  opzioni dell'integrazione. Il pezzo 2 aggiungerà il modo di leggerla
  dall'esterno e il riconoscimento via codice.

## 13. Dati, riservatezza e costi

DeepSeek riceve: le frasi dell'utente, le risposte, i nomi e gli stati dei
dispositivi esposti ad Assist, gli esiti delle azioni.

DeepSeek non riceve: audio, credenziali di HA, dispositivi non esposti.

Costo indicativo con `deepseek-flash`: meno di un centesimo di dollaro per una
richiesta tipica. Listino al 2026-10-02, per milione di token: da 0,15 a 0,30
dollari in ingresso e da 0,60 a 1,20 dollari in uscita, secondo la fascia
oraria.

## 14. Collaudo

### Test automatici

| Oggetto | Cosa si verifica |
|---|---|
| Client | elenco modelli; interpretazione del flusso; i cinque casi d'errore; tempi massimi. Contro un finto DeepSeek, senza consumare credito. |
| Traduttore | conversione di ogni tipo di messaggio; conversione degli strumenti; ricomposizione di richieste di strumenti a frammenti; argomenti non validi. |
| Agente | risposta semplice; richiesta con uno strumento; più giri; limite dei giri; ogni caso d'errore; riga dei nomi nel prompt. |
| Configurazione | chiave valida; chiave sbagliata; riautenticazione; salvataggio delle impostazioni; regole delle parole d'invocazione. |
| Assistente | creazione riuscita; motori assenti; nessun secondo tentativo. |

Strumenti: `pytest` con `pytest-homeassistant-custom-component` nella versione
corrispondente a HA 2026.9.4, Python 3.14.

### Dove girano

- **In CI su GitHub Actions (Linux), a ogni modifica:** tutti i test, più la
  validazione ufficiale di HA (`hassfest`) e quella di HACS.
- **Su questo PC:** i test del client, che non dipendono da HA. Durante
  l'implementazione si verifica se anche gli altri girano su Windows; se sì si
  usano anche in locale, altrimenti fa fede la CI.

### Collaudo sul HA dell'utente

1. Installazione da HACS e aggiunta dell'integrazione con la API key.
2. Una chiave sbagliata viene rifiutata.
3. L'assistente "Jarvis" compare tra gli assistenti vocali, oppure compare la
   notifica con i passaggi manuali.
4. "Accendi" e "spegni" su un dispositivo esposto.
5. Una domanda sullo stato di un sensore esposto.
6. Una domanda generale.
7. Aggiunta di una parola d'invocazione e frase che inizia con quella parola.
8. Cambio di personalità con effetto dalla richiesta successiva.
9. Richiesta su un dispositivo non esposto: Jarvis dice che non lo trova.

## 15. Distribuzione

- Repository GitHub **pubblico** `iAlias/ha-jarvis`, che ospiterà tutti e
  quattro i pezzi. HACS legge solo `custom_components/jarvis`.
- Licenza MIT.
- Versione minima di Home Assistant: 2026.9.0. Versione iniziale
  dell'integrazione: 0.1.0.
- README in italiano con i passaggi di installazione.
- Commenti nel codice e documentazione in italiano; nomi nel codice in inglese.
- Nel repository non entrano chiavi né dati personali.

## 16. Decisioni e alternative scartate

| Decisione | Alternativa scartata | Motivo |
|---|---|---|
| Integrazione autonoma | Riusare un'integrazione community per il cervello | Due installazioni e impostazioni in due posti. |
| Integrazione autonoma | Servizio esterno a HA | Un programma in più da tenere acceso; rifarebbe ciò che HA offre già. |
| HTTP diretto con `aiohttp` | Libreria `openai` | Nessuna dipendenza da installare, nessun conflitto di versioni con HA. |
| Una voce di configurazione con opzioni | Sotto-voci, come le integrazioni ufficiali | Un solo agente: meno passaggi per l'utente. |
| Nomi gestiti dal modello | Taglio del nome via codice | Il taglio rovinerebbe frasi legittime; il riconoscimento via codice serve alle orecchie. |
| "Thinking" disattivato | Lasciare il default | Velocità di risposta, e ciclo degli strumenti più semplice. |
| Repository pubblico | Privato o solo locale | HACS accetta solo repository pubblici; CI gratuita. |

## 17. Fonti verificate

- Sorgente di Home Assistant 2026.9.4: `components/open_router`,
  `components/conversation`, `components/assist_pipeline`,
  `components/wake_word`, `helpers/llm.py`.
- Documentazione sviluppatori HA: Conversation entity, LLM API, Wake word
  detection entity, Assist pipelines.
- Documentazione DeepSeek: API reference, guide "Thinking mode" e "Tool calls",
  pagina dei prezzi. Modelli attuali: `deepseek-flash`, `deepseek-v4-pro`.
- FAQ di HACS sui repository privati.
