"""Test dei testi: lingua, parole d'invocazione, prompt, messaggi d'errore."""

import jinja2
import pytest

ERROR_KINDS = [
    "auth",
    "balance",
    "rate_limit",
    "server",
    "connection",
    "too_many_steps",
]


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("it", "it"),
        ("it-IT", "it"),
        ("IT", "it"),
        ("it_CH", "it"),
        ("en", "en"),
        ("de", "en"),
        ("", "en"),
        (None, "en"),
        ("*", "en"),
    ],
)
def test_language_key(texts, language, expected) -> None:
    assert texts.language_key(language) == expected


def test_clean_invocation_words(texts) -> None:
    words = [" Jarvis ", "jarvis", "", "   ", "Alfredo", "mbare", "ALFREDO", "il  capo"]

    assert texts.clean_invocation_words(words) == [
        "Jarvis",
        "Alfredo",
        "mbare",
        "il capo",
    ]


def test_clean_invocation_words_empty(texts) -> None:
    assert texts.clean_invocation_words([]) == []
    assert texts.clean_invocation_words(["", "  "]) == []


def test_default_prompt_follows_language(texts) -> None:
    assert "maggiordomo" in texts.default_prompt("it")
    assert "butler" in texts.default_prompt("en")
    assert texts.default_prompt("fr") == texts.default_prompt("en")


def test_build_prompt_appends_names(texts) -> None:
    prompt = texts.build_prompt("Sei un assistente.\n", ["Jarvis", "mbare"], "it")
    rendered = jinja2.Template(prompt).render()

    assert rendered.startswith("Sei un assistente.\n")
    assert "Rispondi a questi nomi: Jarvis, mbare." in rendered


def test_build_prompt_names_line_follows_language(texts) -> None:
    rendered = jinja2.Template(texts.build_prompt("Hi.", ["Jarvis"], "en")).render()

    assert "You answer to these names: Jarvis." in rendered


def test_build_prompt_without_words_is_unchanged(texts) -> None:
    assert texts.build_prompt("Sei un assistente.", [], "it") == "Sei un assistente."


def test_build_prompt_keeps_personality_template(texts) -> None:
    """La personalità resta un template di HA; i nomi no."""
    prompt = texts.build_prompt("Casa «{{ ha_name }}».", ["Jarvis"], "it")

    assert jinja2.Template(prompt).render(ha_name="Mia").startswith("Casa «Mia».")


@pytest.mark.parametrize(
    "word",
    [
        "{{ 1/0 }}",
        "{% for x in y %}",
        "a {% endraw %} {{ 1/0 }}",
        "{%- endraw -%}{{ 1/0 }}",
    ],
)
def test_build_prompt_names_are_never_templates(texts, word) -> None:
    """Una parola d'invocazione non deve poter rompere il prompt."""
    prompt = texts.build_prompt("Ciao.", [word, "Jarvis"], "it")

    rendered = jinja2.Template(prompt).render()

    assert "Jarvis" in rendered
    assert "1/0" in rendered or "for x in y" in rendered


@pytest.mark.parametrize("kind", ERROR_KINDS)
def test_error_messages_exist_in_both_languages(texts, kind) -> None:
    italian = texts.error_message(kind, "it")
    english = texts.error_message(kind, "en")

    assert italian and english
    assert italian != english


def test_error_messages_are_distinct(texts) -> None:
    assert len({texts.error_message(kind, "it") for kind in ERROR_KINDS}) == len(
        ERROR_KINDS
    )


def test_unknown_error_kind_falls_back_to_service_error(texts) -> None:
    assert texts.error_message("mai visto", "it") == texts.error_message("server", "it")


def test_assistant_help_explains_the_manual_steps(texts) -> None:
    italian_title, italian_message = texts.assistant_help("it")
    english_title, english_message = texts.assistant_help("en")

    assert "Jarvis" in italian_title and "Jarvis" in english_title
    assert "Assistenti vocali" in italian_message
    assert "Voice assistants" in english_message
    assert texts.assistant_help("de") == texts.assistant_help("en")
