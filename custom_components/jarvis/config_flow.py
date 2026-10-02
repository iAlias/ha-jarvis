"""Configurazione di Jarvis dall'interfaccia di Home Assistant."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LLM_HASS_API,
    CONF_MODEL,
    CONF_PROMPT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_INVOCATION_WORDS,
    DEFAULT_INVOCATION_WORDS,
    DEFAULT_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    FALLBACK_MODELS,
)
from .deepseek import (
    DeepSeekAuthError,
    DeepSeekBalanceError,
    DeepSeekClient,
    DeepSeekError,
)
from .texts import clean_invocation_words, default_prompt

API_KEYS_URL = "https://platform.deepseek.com/api_keys"

API_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    }
)


async def _async_validate_key(hass: HomeAssistant, api_key: str) -> str | None:
    """Verifica la API key; restituisce il codice d'errore per il modulo, se c'è."""
    client = DeepSeekClient(async_get_clientsession(hass), api_key)
    try:
        await client.list_models()
    except DeepSeekAuthError:
        return "invalid_auth"
    except DeepSeekBalanceError:
        # Credito esaurito: la chiave è comunque valida.
        return None
    except DeepSeekError:
        return "cannot_connect"
    return None


class JarvisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Prima configurazione e riautenticazione."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Chiede la API key e crea la voce con le impostazioni consigliate."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error = await _async_validate_key(self.hass, api_key)
            if error is None:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_API_KEY: api_key},
                    options={
                        CONF_INVOCATION_WORDS: list(DEFAULT_INVOCATION_WORDS),
                        CONF_PROMPT: default_prompt(self.hass.config.language),
                        CONF_MODEL: DEFAULT_MODEL,
                        CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=API_KEY_SCHEMA,
            errors=errors,
            description_placeholders={"api_keys_url": API_KEYS_URL},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Avvia la riautenticazione quando la chiave non è più valida."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Chiede la nuova API key e ricarica Jarvis."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            error = await _async_validate_key(self.hass, api_key)
            if error is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: api_key}
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=API_KEY_SCHEMA,
            errors=errors,
            description_placeholders={"api_keys_url": API_KEYS_URL},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> JarvisOptionsFlow:
        """Restituisce il modulo delle impostazioni."""
        return JarvisOptionsFlow()


class JarvisOptionsFlow(OptionsFlowWithReload):
    """Impostazioni: parole d'invocazione, personalità, modello, strumenti."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Mostra e salva le impostazioni."""
        errors: dict[str, str] = {}
        options: dict[str, Any] = dict(self.config_entry.options)

        if user_input is not None:
            words = clean_invocation_words(user_input.get(CONF_INVOCATION_WORDS, []))
            if words:
                return self.async_create_entry(
                    data={
                        CONF_INVOCATION_WORDS: words,
                        CONF_PROMPT: user_input.get(CONF_PROMPT)
                        or default_prompt(self.hass.config.language),
                        CONF_MODEL: user_input[CONF_MODEL],
                        CONF_LLM_HASS_API: user_input.get(CONF_LLM_HASS_API, []),
                    }
                )
            errors[CONF_INVOCATION_WORDS] = "no_invocation_words"
            # Il modulo si ripresenta con ciò che l'utente aveva scritto.
            options = {**options, **user_input}

        return self.async_show_form(
            step_id="init",
            data_schema=await self._async_schema(options),
            errors=errors,
        )

    async def _async_schema(self, options: Mapping[str, Any]) -> vol.Schema:
        """Costruisce il modulo con i valori attuali come proposta."""
        apis = [
            SelectOptionDict(label=api.name, value=api.id)
            for api in llm.async_get_apis(self.hass)
        ]
        valid_api_ids = {api["value"] for api in apis}
        selected_apis = [
            api_id
            for api_id in options.get(CONF_LLM_HASS_API, [])
            if api_id in valid_api_ids
        ]
        current_model = options.get(CONF_MODEL, DEFAULT_MODEL)

        return vol.Schema(
            {
                vol.Required(
                    CONF_INVOCATION_WORDS,
                    description={
                        "suggested_value": options.get(
                            CONF_INVOCATION_WORDS, DEFAULT_INVOCATION_WORDS
                        )
                    },
                ): TextSelector(TextSelectorConfig(multiple=True)),
                vol.Optional(
                    CONF_PROMPT,
                    description={"suggested_value": options.get(CONF_PROMPT)},
                ): TemplateSelector(),
                vol.Required(CONF_MODEL, default=current_model): SelectSelector(
                    SelectSelectorConfig(
                        options=await self._async_model_options(current_model),
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                vol.Optional(
                    CONF_LLM_HASS_API,
                    description={"suggested_value": selected_apis},
                ): SelectSelector(SelectSelectorConfig(options=apis, multiple=True)),
            }
        )

    async def _async_model_options(self, current_model: str) -> list[SelectOptionDict]:
        """Elenco dei modelli da DeepSeek, con un ripiego se non è raggiungibile."""
        client = DeepSeekClient(
            async_get_clientsession(self.hass), self.config_entry.data[CONF_API_KEY]
        )
        try:
            models = {model.id: model.name for model in await client.list_models()}
        except DeepSeekError:
            models = {model_id: model_id for model_id in FALLBACK_MODELS}
        # Il modello salvato resta selezionabile anche se non è più in elenco.
        models.setdefault(current_model, current_model)
        return [
            SelectOptionDict(value=model_id, label=name)
            for model_id, name in models.items()
        ]
