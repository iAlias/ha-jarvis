# Jarvis per Home Assistant

Un assistente in stile Jarvis per [Home Assistant](https://www.home-assistant.io/),
con [DeepSeek](https://platform.deepseek.com/) come cervello. Gli scrivi o gli
parli da Assist: comanda la casa, ti dice in che stato è e risponde alle domande
con il tono di un maggiordomo inglese.

Stato: versione 0.1.0, primo dei quattro pezzi previsti (vedi
[Cosa arriverà](#cosa-arriverà)).

## Cosa fa

- **Comanda la casa:** luci, clima, tapparelle, prese, scene e script che esponi
  ad Assist.
- **Dice lo stato della casa:** temperature, porte, consumi, presenze.
- **Conversa:** domande generali, spiegazioni, calcoli.
- **Risponde a più nomi:** scegli tu le parole d'invocazione, per esempio
  "Jarvis", "Alfredo", "mbare".

## Cosa serve

- Home Assistant 2026.9.0 o successivo.
- [HACS](https://hacs.xyz/) installato.
- Una API key di DeepSeek, da creare su
  <https://platform.deepseek.com/api_keys>.

## Installazione

1. In HACS apri il menu in alto a destra e scegli **Repository personalizzati**.
2. Incolla `https://github.com/iAlias/ha-jarvis`, scegli il tipo
   **Integrazione** e conferma.
3. Cerca **Jarvis** in HACS, installalo e riavvia Home Assistant.
4. Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione**,
   cerca **Jarvis** e incolla la API key di DeepSeek.

Jarvis controlla la chiave e si configura da solo. Se Home Assistant ha già un
motore di riconoscimento vocale e uno di sintesi vocale, crea anche l'assistente
vocale "Jarvis". Altrimenti ti mostra una notifica con i passaggi per aggiungerlo
a mano.

## Uso

Apri Assist dall'app o dal browser, scegli l'assistente **Jarvis** e scrivi,
oppure premi il microfono:

- "Accendi la luce del salotto"
- "Che temperatura c'è in camera?"
- "mbare, spegni tutto"
- "Spiegami cos'è un buco nero"

Jarvis vede e comanda solo i dispositivi che esponi tu in **Impostazioni →
Assistenti vocali → Esponi**.

## Il pulsante Jarvis

L'integrazione aggiunge alle dashboard la card **Jarvis**: un pulsante che apre
l'ascolto al tocco, senza dire la parola d'attivazione. Lo premi e parli:
"aggiornami sulla casa".

Per aggiungerla: modifica la dashboard → **Aggiungi scheda** → cerca **Jarvis**.
In YAML basta:

```yaml
type: custom:jarvis-card
```

Opzioni, tutte facoltative:

| Opzione | A cosa serve |
|---|---|
| `name` | Il nome mostrato sotto il pulsante. |
| `pipeline_id` | L'assistente da aprire. Se manca, la card usa quello collegato a Jarvis. |
| `color` | Il colore del pulsante, per esempio `#ff7043`. |

Nell'app di Home Assistant il pulsante apre l'ascolto dell'app. Nel browser il
microfono funziona solo se Home Assistant è raggiunto in HTTPS.

## Impostazioni

Apri **Impostazioni → Dispositivi e servizi → Jarvis → Configura**.

| Campo | A cosa serve |
|---|---|
| Parole d'invocazione | I nomi con cui lo chiami. Ne serve almeno uno. |
| Personalità | Il carattere e lo stile delle risposte. Accetta i template di Home Assistant. |
| Modello | `deepseek-flash` è veloce ed economico; `deepseek-v4-pro` è più capace ma più lento. |
| Strumenti | Lascia **Assist** per fargli leggere e comandare la casa. Se lo togli, conversa soltanto. |

Le modifiche valgono dalla richiesta successiva, senza riavviare.

## Costi

Paghi DeepSeek a consumo. Con `deepseek-flash` una richiesta tipica costa meno di
un centesimo di dollaro. I prezzi aggiornati sono su
<https://api-docs.deepseek.com/quick_start/pricing>.

## Riservatezza

DeepSeek riceve le tue frasi, le risposte, i nomi e gli stati dei dispositivi che
esponi ad Assist e gli esiti delle azioni. Non riceve audio, credenziali di Home
Assistant o dispositivi non esposti. La API key resta nell'archivio di Home
Assistant e non viene scritta nei log.

## Se qualcosa non va

| Cosa succede | Cosa fare |
|---|---|
| "La API key non è valida" | Controlla di averla copiata per intero, oppure creane una nuova. |
| Jarvis dice che il credito è esaurito | Ricarica il credito su DeepSeek. |
| Jarvis dice che non riesce a collegarsi | Controlla la connessione a internet di Home Assistant e riprova. |
| Home Assistant chiede di riconfigurare Jarvis | La chiave è stata revocata: inseriscine una nuova. |
| Jarvis non trova un dispositivo | Esponilo in Impostazioni → Assistenti vocali → Esponi. |
| Manca l'assistente "Jarvis" | Impostazioni → Assistenti vocali → Aggiungi assistente, e scegli Jarvis come agente di conversazione. |

Per i dettagli tecnici di un errore guarda **Impostazioni → Sistema → Registri**
e cerca `jarvis`.

## Cosa arriverà

1. **Nucleo** (questa versione): cervello, impostazioni, casa e conversazione.
2. **Orecchie PC:** programma per Windows con ascolto continuo, invocazione a
   voce con le tue parole e comandi per il PC.
3. **Orecchie HA:** invocazione a voce con le tue parole dai dispositivi vocali
   collegati a Home Assistant.
4. **Sicurezza:** avviso quando un nuovo dispositivo si collega a Jarvis o alla
   rete di casa.

In questa versione le parole d'invocazione sono già riconosciute nella frase, ma
il microfono si attiva ancora con il pulsante di Assist.

## Sviluppo

```
uv venv .venv --python 3.14
uv pip install --python .venv/Scripts/python.exe -r requirements_local.txt
.venv/Scripts/python -m pytest tests/unit
```

I test in `tests/unit` non dipendono da Home Assistant e girano ovunque. Quelli
in `tests/ha` richiedono Linux e girano su GitHub Actions a ogni modifica.

Design e piano sono in `docs/superpowers/`.

## Licenza

[MIT](LICENSE)
