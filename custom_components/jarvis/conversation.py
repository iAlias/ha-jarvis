"""L'agente conversazionale di Jarvis."""

from typing import Any, Literal

from homeassistant.components import conversation
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL, CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import JarvisConfigEntry
from .chat import async_transform_stream, build_messages, format_tool
from .const import (
    CONF_INVOCATION_WORDS,
    DEFAULT_MODEL,
    DOMAIN,
    LOGGER,
    MAX_TOKENS,
    MAX_TOOL_ITERATIONS,
)
from .deepseek import DeepSeekAuthError, DeepSeekError, DeepSeekServerError
from .texts import build_prompt, default_prompt, error_message


class TooManyStepsError(DeepSeekError):
    """Il modello continua a chiedere strumenti oltre il limite dei giri."""

    kind = "too_many_steps"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JarvisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crea l'agente conversazionale."""
    async_add_entities([JarvisConversationEntity(config_entry)])


class JarvisConversationEntity(conversation.ConversationEntity):
    """Agente conversazionale che usa DeepSeek come cervello."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supports_streaming = True

    def __init__(self, entry: JarvisConfigEntry) -> None:
        """Prepara l'agente a partire dalla voce di configurazione."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="DeepSeek",
            model=entry.options.get(CONF_MODEL, DEFAULT_MODEL),
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        if entry.options.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Il modello capisce qualunque lingua."""
        return MATCH_ALL

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Risponde a una frase dell'utente."""
        options = self.entry.options
        prompt = build_prompt(
            options.get(CONF_PROMPT) or default_prompt(user_input.language),
            options.get(CONF_INVOCATION_WORDS, []),
            user_input.language,
        )

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                prompt,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        try:
            await self._async_run_tool_loop(chat_log)
        except DeepSeekError as err:
            return self._error_result(user_input, chat_log, err)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_run_tool_loop(self, chat_log: conversation.ChatLog) -> None:
        """Chiama DeepSeek finché non arriva una risposta senza strumenti."""
        client = self.entry.runtime_data
        payload: dict[str, Any] = {
            "model": self.entry.options.get(CONF_MODEL, DEFAULT_MODEL),
            "stream": True,
            # DeepSeek ragiona di default: per la voce conta la rapidità.
            "thinking": {"type": "disabled"},
            "max_tokens": MAX_TOKENS,
        }
        if chat_log.llm_api and chat_log.llm_api.tools:
            payload["tools"] = [
                format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        for _iteration in range(MAX_TOOL_ITERATIONS):
            payload["messages"] = build_messages(chat_log.content)

            received = False
            async for _content in chat_log.async_add_delta_content_stream(
                self.entity_id,
                async_transform_stream(client.stream_chat(payload)),
            ):
                received = True
            if not received:
                raise DeepSeekServerError("Risposta vuota da DeepSeek")

            if not chat_log.unresponded_tool_results:
                return

        raise TooManyStepsError("Limite dei giri di strumenti raggiunto")

    def _error_result(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
        err: DeepSeekError,
    ) -> conversation.ConversationResult:
        """Trasforma un errore in un messaggio che Assist pronuncia."""
        LOGGER.warning("Richiesta a DeepSeek non riuscita: %s", err)
        if isinstance(err, DeepSeekAuthError):
            self.entry.async_start_reauth(self.hass)

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_error(
            intent.IntentResponseErrorCode.UNKNOWN,
            error_message(err.kind, user_input.language),
        )
        return conversation.ConversationResult(
            response=response, conversation_id=chat_log.conversation_id
        )
