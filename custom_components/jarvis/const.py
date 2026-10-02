"""Costanti dell'integrazione Jarvis."""

import logging

DOMAIN = "jarvis"
LOGGER = logging.getLogger(__package__)

DEFAULT_NAME = "Jarvis"

CONF_INVOCATION_WORDS = "invocation_words"
CONF_ASSISTANT_CREATED = "assistant_created"

DEFAULT_MODEL = "deepseek-flash"
# Modelli proposti quando l'elenco di DeepSeek non è raggiungibile.
FALLBACK_MODELS = ["deepseek-flash", "deepseek-v4-pro"]
DEFAULT_INVOCATION_WORDS = ["Jarvis"]

# Tetto di sicurezza su costo e durata: le risposte vocali sono brevi.
MAX_TOKENS = 1024
MAX_TOOL_ITERATIONS = 10
