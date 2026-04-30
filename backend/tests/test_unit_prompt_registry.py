"""Unit tests for the locale-aware prompt registry.

The registry serves prompt strings keyed by ``<module>.<name>`` for a
given locale, with English fallback when a key is missing.
"""
import pytest

from app.prompts import (
    available_locales,
    get_prompt,
    list_keys,
    missing_keys,
)
from app.prompts.registry import _reset_cache_for_tests
from app.utils import i18n


@pytest.fixture(autouse=True)
def _reset_registry():
    _reset_cache_for_tests()
    yield
    _reset_cache_for_tests()


def test_available_locales_includes_en_and_zh():
    locales = available_locales()
    assert "en" in locales
    assert "zh-CN" in locales


def test_zh_cn_has_no_missing_keys_relative_to_en():
    """Coverage gate: every English prompt must have a Chinese sibling.

    If this fails, a new EN prompt was added without translating it.
    Either translate it in ``locales/zh_CN/`` or accept the EN fallback
    by deleting this assertion (only do that if the prompt genuinely
    can't be translated).
    """
    missing = missing_keys("zh-CN")
    assert missing == [], (
        f"Chinese (zh-CN) is missing translations for: {missing}. "
        "Add them to backend/app/prompts/locales/zh_CN/ or document why "
        "they should fall back to English."
    )


def test_get_prompt_falls_back_to_english_for_unknown_locale():
    """Unknown locales should fall back to English silently."""
    out = get_prompt("social_simulations.twitter_system", "fr-FR",
                     description_block="...")
    assert "WHO YOU ARE" in out  # English content


def test_get_prompt_returns_chinese_for_zh_cn():
    out = get_prompt("social_simulations.twitter_system", "zh-CN",
                     description_block="你叫小明。")
    # At least one CJK character must be in the output to confirm we got
    # the Chinese variant rather than the English fallback.
    assert any("一" <= c <= "鿿" for c in out), out[:200]


def test_get_prompt_substitutes_placeholders():
    out = get_prompt(
        "social_simulations.description_name", "en", name="Alice",
    )
    assert out == "Your name is Alice."


def test_get_prompt_missing_key_raises():
    with pytest.raises(KeyError):
        get_prompt("nonexistent.key", "en")


def test_get_prompt_invalid_format_raises():
    with pytest.raises(ValueError):
        get_prompt("missing_dot_separator", "en")


def test_list_keys_en_is_non_empty():
    en_keys = list_keys("en")
    assert len(en_keys) > 0
    # All keys are namespaced
    assert all("." in k for k in en_keys)


def test_use_locale_context_manager_propagates_to_get_active_locale():
    assert i18n.get_active_locale() == "en"
    with i18n.use_locale("zh-CN"):
        assert i18n.get_active_locale() == "zh-CN"
    assert i18n.get_active_locale() == "en"
