/* Card «Jarvis»: un pulsante che apre Assist già in ascolto, senza parola d'attivazione. */

const TEXTS = {
  it: {
    hint: "Tocca e parla",
    label: "Parla con Jarvis",
    name: "Nome mostrato",
    pipeline: "Assistente da usare",
    color: "Colore",
    description: "Un pulsante per parlare con Jarvis senza dire la parola d'attivazione.",
  },
  en: {
    hint: "Tap and speak",
    label: "Talk to Jarvis",
    name: "Displayed name",
    pipeline: "Assistant to use",
    color: "Colour",
    description: "A button to talk to Jarvis without saying the wake word.",
  },
};

const DEFAULT_COLOR = "#3ec6ff";

const STYLE = `
  :host {
    display: block;
    height: 100%;
  }
  ha-card {
    height: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 14px;
    padding: 24px 16px 20px;
    overflow: hidden;
  }
  .core {
    position: relative;
    width: 128px;
    height: 128px;
    flex: none;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    padding: 0;
    cursor: pointer;
    color: var(--accent);
    background: radial-gradient(
      circle at 50% 50%,
      color-mix(in srgb, var(--accent) 30%, transparent) 0%,
      color-mix(in srgb, var(--accent) 8%, transparent) 55%,
      transparent 72%
    );
    transition: transform 120ms ease-out;
    -webkit-tap-highlight-color: transparent;
  }
  .core:active {
    transform: scale(0.95);
  }
  .core:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 14px;
  }
  .ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 2px solid color-mix(in srgb, var(--accent) 75%, transparent);
    pointer-events: none;
  }
  .ring.dashed {
    inset: -10px;
    border: 1px dashed color-mix(in srgb, var(--accent) 55%, transparent);
    animation: jarvis-spin 28s linear infinite;
  }
  .ring.pulse {
    animation: jarvis-pulse 3s ease-out infinite;
  }
  ha-icon {
    --mdc-icon-size: 46px;
  }
  .name {
    font-size: 1.15rem;
    font-weight: 500;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--primary-text-color);
  }
  .hint {
    margin-top: -8px;
    font-size: 0.9rem;
    color: var(--secondary-text-color);
  }
  @keyframes jarvis-spin {
    to {
      transform: rotate(360deg);
    }
  }
  @keyframes jarvis-pulse {
    0% {
      transform: scale(1);
      opacity: 0.8;
    }
    70%,
    100% {
      transform: scale(1.28);
      opacity: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ring.dashed,
    .ring.pulse {
      animation: none;
    }
    .ring.pulse {
      display: none;
    }
  }
`;

const texts = (hass) => {
  const language = ((hass && hass.language) || "en").split("-")[0];
  return TEXTS[language] || TEXTS.en;
};

class JarvisCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._pipeline = undefined;
  }

  static getStubConfig() {
    return {};
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "name", selector: { text: {} } },
        { name: "pipeline_id", selector: { assist_pipeline: {} } },
        { name: "color", selector: { text: {} } },
      ],
      computeLabel: (schema, hass) => {
        const labels = texts(hass);
        return { name: labels.name, pipeline_id: labels.pipeline, color: labels.color }[
          schema.name
        ];
      },
    };
  }

  setConfig(config) {
    this._config = config || {};
    // Un assistente scelto a mano vince su quello trovato in automatico.
    this._pipeline = undefined;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._render();
      // Cerca subito l'assistente, così al tocco l'ascolto parte senza attese.
      this._resolvePipeline();
    }
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return { columns: 6, rows: 4, min_columns: 3, min_rows: 3 };
  }

  _render() {
    if (!this._hass) {
      return;
    }
    const labels = texts(this._hass);
    const root = this.shadowRoot;
    root.replaceChildren();

    const style = document.createElement("style");
    style.textContent = STYLE;

    const card = document.createElement("ha-card");
    card.style.setProperty("--accent", this._config.color || DEFAULT_COLOR);

    const button = document.createElement("button");
    button.className = "core";
    button.type = "button";
    button.setAttribute("aria-label", labels.label);
    button.addEventListener("click", () => this._listen());
    for (const kind of ["dashed", "pulse", ""]) {
      const ring = document.createElement("span");
      ring.className = `ring ${kind}`.trim();
      button.append(ring);
    }
    const icon = document.createElement("ha-icon");
    icon.setAttribute("icon", "mdi:microphone");
    button.append(icon);

    const name = document.createElement("div");
    name.className = "name";
    name.textContent = this._config.name || "Jarvis";

    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = labels.hint;

    card.append(button, name, hint);
    root.append(style, card);
  }

  /* L'assistente da aprire: quello indicato nella card, altrimenti quello che
     usa l'agente di Jarvis, altrimenti il preferito di Home Assistant. */
  _resolvePipeline() {
    if (this._config.pipeline_id) {
      return Promise.resolve(this._config.pipeline_id);
    }
    if (!this._pipeline) {
      this._pipeline = this._findJarvisPipeline().catch(() => "preferred");
    }
    return this._pipeline;
  }

  async _findJarvisPipeline() {
    const agent = Object.values(this._hass.entities || {}).find(
      (entity) =>
        entity.platform === "jarvis" && entity.entity_id.startsWith("conversation.")
    );
    if (!agent) {
      return "preferred";
    }
    const result = await this._hass.callWS({ type: "assist_pipeline/pipeline/list" });
    const pipeline = result.pipelines.find(
      (item) => item.conversation_engine === agent.entity_id
    );
    return pipeline ? pipeline.id : "preferred";
  }

  async _listen() {
    const pipelineId = await this._resolvePipeline();
    // Azione ufficiale del frontend: nell'app apre l'ascolto nativo, nel
    // browser la finestra di Assist con il microfono già attivo.
    const event = new Event("hass-action", { bubbles: true, composed: true });
    event.detail = {
      config: {
        tap_action: { action: "assist", pipeline_id: pipelineId, start_listening: true },
      },
      action: "tap",
    };
    this.dispatchEvent(event);
  }
}

if (!customElements.get("jarvis-card")) {
  customElements.define("jarvis-card", JarvisCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "jarvis-card")) {
  window.customCards.push({
    type: "jarvis-card",
    name: "Jarvis",
    description: TEXTS.it.description,
    preview: true,
  });
}
