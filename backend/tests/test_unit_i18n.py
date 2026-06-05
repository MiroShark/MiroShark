"""Unit tests for the locale helper at ``app.utils.i18n``.

This module is the single source of truth for how a request's active
locale gets resolved (``?lang=`` > ``X-MiroShark-Locale`` >
``Accept-Language`` > default), how localized strings are picked
(``t``), and how embedded ``i18n`` override blocks merge into JSON
payloads (``apply_i18n``). Every API surface that returns translated
copy — ``/api/templates``, the share card, the RSS / Atom feeds, the
report agent narration — depends on this contract.

The contracts covered:

  1. ``normalize_locale`` accepts free-form input — ``None``, empty
     string, raw BCP-47 tags, full ``Accept-Language`` lists — and
     always returns a value in ``SUPPORTED``. Anything unrecognised
     falls back to ``DEFAULT`` (``"en"``).
  2. ``get_locale`` honours the precedence chain: ``?lang=`` wins over
     headers, ``X-MiroShark-Locale`` wins over ``Accept-Language``, a
     missing request returns ``DEFAULT``. Per-source exceptions don't
     abort resolution — they fall through to the next source.
  3. ``t`` picks the Chinese variant only when the active locale is
     ``zh-CN`` *and* a non-empty Chinese string was supplied; empty
     ``zh`` falls back to English even under ``zh-CN``. Unknown locales
     fall back to English without raising.
  4. ``apply_i18n`` merges sibling overrides from an ``i18n`` block at
     each dict node, drops the ``i18n`` key from the response, and
     recurses into nested dicts and lists. The English default path
     still strips ``i18n`` blocks so the response shape is
     locale-independent.
  5. ``_strip_i18n`` walks the structure recursively without applying
     any overrides — used by ``apply_i18n`` for the default-locale
     path.
  6. The ``use_locale`` context manager activates a locale for its
     body, restores the prior value on exit (including from nested
     blocks), and tolerates exceptions raised inside the block.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.utils.i18n import (  # noqa: E402
    DEFAULT,
    SUPPORTED,
    _strip_i18n,
    apply_i18n,
    get_active_locale,
    get_locale,
    normalize_locale,
    reset_active_locale,
    set_active_locale,
    t,
    use_locale,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


class _FakeRequest:
    """Minimal Flask-shaped request stub: ``.args`` + ``.headers``.

    Both are plain ``dict``-like with a ``.get(key, default=None)`` API,
    which matches what ``get_locale`` actually reaches for.
    """

    def __init__(self, args=None, headers=None, raise_on=None):
        self.args = _RaisingDict(args or {}, raise_on)
        self.headers = _RaisingDict(headers or {}, raise_on)


class _RaisingDict(dict):
    """A dict whose ``.get`` raises for a configured key (precedence test)."""

    def __init__(self, mapping, raise_on):
        super().__init__(mapping)
        self._raise_on = raise_on or ()

    def get(self, key, default=None):
        if key in self._raise_on:
            raise RuntimeError(f"forced failure on {key!r}")
        return super().get(key, default)


@pytest.fixture(autouse=True)
def _reset_active_locale_between_tests():
    """Restore the default active locale between tests.

    ``ContextVar`` state would otherwise leak across tests sharing the
    same execution context and surface as cross-test order dependence.
    """
    token = set_active_locale(DEFAULT)
    yield
    reset_active_locale(token)


# ── normalize_locale ────────────────────────────────────────────────────────


def test_normalize_locale_returns_default_for_none_and_empty():
    assert normalize_locale(None) == DEFAULT
    assert normalize_locale("") == DEFAULT
    assert normalize_locale("   ") == DEFAULT


def test_normalize_locale_maps_zh_prefixes_to_zh_cn():
    assert normalize_locale("zh") == "zh-CN"
    assert normalize_locale("zh-CN") == "zh-CN"
    assert normalize_locale("zh-TW") == "zh-CN"
    assert normalize_locale("ZH-cn") == "zh-CN"


def test_normalize_locale_maps_en_prefixes_to_en():
    assert normalize_locale("en") == "en"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("EN-gb") == "en"


def test_normalize_locale_picks_first_tag_from_accept_language_list():
    """An ``Accept-Language`` list is parsed left-to-right."""
    assert normalize_locale("zh-CN,zh;q=0.9,en;q=0.8") == "zh-CN"
    assert normalize_locale("en-US,en;q=0.9,zh;q=0.8") == "en"


def test_normalize_locale_unknown_tag_falls_back_to_default():
    assert normalize_locale("fr-FR") == DEFAULT
    assert normalize_locale("klingon") == DEFAULT
    assert normalize_locale("xx-YY,zz;q=0.9") == DEFAULT


def test_normalize_locale_always_returns_a_supported_value():
    """Any input ends up in ``SUPPORTED`` so downstream code can index safely."""
    for raw in (None, "", "  ", "en", "en-GB", "zh", "zh-TW",
                "fr", "klingon", "zh-CN,en;q=0.8"):
        assert normalize_locale(raw) in SUPPORTED


# ── get_locale ──────────────────────────────────────────────────────────────


def test_get_locale_returns_default_for_none_request():
    assert get_locale(None) == DEFAULT


def test_get_locale_query_param_wins_over_headers():
    req = _FakeRequest(
        args={"lang": "zh"},
        headers={"X-MiroShark-Locale": "en", "Accept-Language": "en-US"},
    )
    assert get_locale(req) == "zh-CN"


def test_get_locale_header_wins_over_accept_language():
    req = _FakeRequest(
        args={},
        headers={"X-MiroShark-Locale": "zh-CN", "Accept-Language": "en-US"},
    )
    assert get_locale(req) == "zh-CN"


def test_get_locale_falls_back_to_accept_language():
    req = _FakeRequest(
        args={},
        headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
    )
    assert get_locale(req) == "zh-CN"


def test_get_locale_empty_request_yields_default():
    assert get_locale(_FakeRequest()) == DEFAULT


def test_get_locale_query_exception_falls_through_to_headers():
    """A broken ``.args`` doesn't abort resolution — headers still run."""
    req = _FakeRequest(
        args={},
        headers={"X-MiroShark-Locale": "zh-CN"},
        raise_on=("lang",),
    )
    assert get_locale(req) == "zh-CN"


def test_get_locale_header_exception_falls_through_to_accept_language():
    req = _FakeRequest(
        args={},
        headers={"Accept-Language": "zh-CN"},
        raise_on=("X-MiroShark-Locale",),
    )
    assert get_locale(req) == "zh-CN"


# ── t ───────────────────────────────────────────────────────────────────────


def test_t_returns_english_by_default():
    assert t("hello", "你好") == "hello"


def test_t_returns_chinese_under_zh_cn():
    assert t("hello", "你好", "zh-CN") == "你好"


def test_t_falls_back_to_english_when_zh_is_empty_under_zh_cn():
    """An empty Chinese string is treated as a missing translation."""
    assert t("hello", "", "zh-CN") == "hello"


def test_t_unknown_locale_falls_back_to_english():
    """Adding a 3rd locale must not break callers that haven't migrated yet."""
    assert t("hello", "你好", "fr") == "hello"
    assert t("hello", "你好", "klingon") == "hello"


# ── apply_i18n ──────────────────────────────────────────────────────────────


def test_apply_i18n_overrides_sibling_keys_under_zh_cn():
    payload = {
        "name": "Crypto Token Launch",
        "i18n": {"zh-CN": {"name": "加密代币发布"}},
    }
    assert apply_i18n(payload, "zh-CN") == {"name": "加密代币发布"}


def test_apply_i18n_strips_i18n_block_under_default_locale():
    """The English path strips i18n so response shape is locale-independent."""
    payload = {
        "name": "Crypto Token Launch",
        "i18n": {"zh-CN": {"name": "加密代币发布"}},
    }
    assert apply_i18n(payload, DEFAULT) == {"name": "Crypto Token Launch"}


def test_apply_i18n_with_no_override_for_active_locale_keeps_defaults():
    """A payload with overrides for ``zh-CN`` but a request for ``fr`` keeps EN."""
    payload = {
        "name": "Crypto Token Launch",
        "i18n": {"zh-CN": {"name": "加密代币发布"}},
    }
    assert apply_i18n(payload, "fr") == {"name": "Crypto Token Launch"}


def test_apply_i18n_recurses_into_nested_dicts():
    payload = {
        "outer": {
            "label": "Outer",
            "i18n": {"zh-CN": {"label": "外部"}},
            "inner": {
                "label": "Inner",
                "i18n": {"zh-CN": {"label": "内部"}},
            },
        }
    }
    assert apply_i18n(payload, "zh-CN") == {
        "outer": {"label": "外部", "inner": {"label": "内部"}}
    }


def test_apply_i18n_recurses_into_lists():
    payload = {
        "items": [
            {"name": "Alpha", "i18n": {"zh-CN": {"name": "甲"}}},
            {"name": "Beta",  "i18n": {"zh-CN": {"name": "乙"}}},
        ]
    }
    assert apply_i18n(payload, "zh-CN") == {
        "items": [{"name": "甲"}, {"name": "乙"}]
    }


def test_apply_i18n_passes_through_scalars():
    """Non-collection payloads round-trip unchanged."""
    assert apply_i18n("hello", "zh-CN") == "hello"
    assert apply_i18n(42, "zh-CN") == 42
    assert apply_i18n(None, "zh-CN") is None


def test_apply_i18n_tolerates_non_mapping_overrides():
    """A malformed ``i18n`` value is silently ignored, not crashed."""
    payload = {"name": "Crypto", "i18n": "not-a-mapping"}
    assert apply_i18n(payload, "zh-CN") == {"name": "Crypto"}


# ── _strip_i18n ─────────────────────────────────────────────────────────────


def test_strip_i18n_removes_top_level_block():
    payload = {"name": "Crypto", "i18n": {"zh-CN": {"name": "加密"}}}
    assert _strip_i18n(payload) == {"name": "Crypto"}


def test_strip_i18n_recurses_into_nested_structures():
    payload = {
        "items": [
            {"name": "Alpha", "i18n": {"zh-CN": {"name": "甲"}}},
            {"nested": {"name": "Beta", "i18n": {"zh-CN": {"name": "乙"}}}},
        ]
    }
    assert _strip_i18n(payload) == {
        "items": [{"name": "Alpha"}, {"nested": {"name": "Beta"}}]
    }


# ── use_locale + active-locale propagation ──────────────────────────────────


def test_use_locale_activates_inside_block_and_restores_on_exit():
    assert get_active_locale() == DEFAULT
    with use_locale("zh-CN"):
        assert get_active_locale() == "zh-CN"
    assert get_active_locale() == DEFAULT


def test_use_locale_normalises_input():
    """The context manager runs raw input through ``normalize_locale``."""
    with use_locale("zh-TW"):
        assert get_active_locale() == "zh-CN"
    with use_locale("klingon"):
        assert get_active_locale() == DEFAULT


def test_use_locale_restores_prior_value_when_nested():
    with use_locale("zh-CN"):
        assert get_active_locale() == "zh-CN"
        with use_locale("en"):
            assert get_active_locale() == "en"
        assert get_active_locale() == "zh-CN"
    assert get_active_locale() == DEFAULT


def test_use_locale_restores_on_exception():
    with pytest.raises(RuntimeError):
        with use_locale("zh-CN"):
            assert get_active_locale() == "zh-CN"
            raise RuntimeError("boom")
    assert get_active_locale() == DEFAULT
