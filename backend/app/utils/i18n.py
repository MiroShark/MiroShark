"""Lightweight locale helper for backend responses.

The frontend forwards the user's chosen locale on every request via the
``X-MiroShark-Locale`` header (preferred) and ``Accept-Language`` (fallback).
A ``?lang=`` query parameter wins over both for share-card / feed URLs that
need to be locale-pinned in their canonical form.

Adding a locale: append the BCP-47 code to :data:`SUPPORTED` and add a
matching prefix branch in :func:`normalize_locale`. Prompt translations
live under ``app/prompts/locales/<locale>/`` (see
``app.prompts`` docstring).
"""
from __future__ import annotations

import contextvars
from typing import Any, Mapping, Optional


SUPPORTED = ("en", "zh-CN")
DEFAULT = "en"

# Active locale for the current execution context. Set at the API entry
# point (or simulation runner entry point) and read by deep callers like
# prompt builders that don't have ``request`` in scope.
_active_locale: contextvars.ContextVar[str] = contextvars.ContextVar(
    "miroshark_active_locale", default=DEFAULT
)


def normalize_locale(raw: Optional[str]) -> str:
    """Normalise a free-form locale string to one of ``SUPPORTED``."""
    if not raw:
        return DEFAULT
    s = str(raw).strip()
    if not s:
        return DEFAULT
    # Accept-Language can be ``zh-CN,zh;q=0.9,en;q=0.8`` — only look at the
    # first tag.
    head = s.split(",", 1)[0].strip()
    head_lc = head.lower()
    if head_lc.startswith("zh"):
        return "zh-CN"
    if head_lc.startswith("en"):
        return "en"
    return DEFAULT


def get_locale(request) -> str:
    """Resolve the active locale from the Flask request object.

    Order of precedence: ``?lang=`` query param → ``X-MiroShark-Locale``
    header → ``Accept-Language`` → default.
    """
    if request is None:
        return DEFAULT
    try:
        q = request.args.get("lang")
        if q:
            return normalize_locale(q)
    except Exception:
        pass
    try:
        h = request.headers.get("X-MiroShark-Locale")
        if h:
            return normalize_locale(h)
    except Exception:
        pass
    try:
        h = request.headers.get("Accept-Language")
        if h:
            return normalize_locale(h)
    except Exception:
        pass
    return DEFAULT


def get_active_locale() -> str:
    """Return the locale set for the current execution context."""
    return _active_locale.get()


def set_active_locale(locale: Optional[str]) -> contextvars.Token:
    """Activate ``locale`` for the current context.

    Returns a token to pass to :func:`reset_active_locale`. Prefer
    :func:`use_locale` (a context manager) over manual token bookkeeping.
    """
    return _active_locale.set(normalize_locale(locale))


def reset_active_locale(token: contextvars.Token) -> None:
    """Reset the active locale to the value it had before ``set_active_locale``."""
    _active_locale.reset(token)


class use_locale:
    """Context manager that activates a locale for its body.

    Example::

        with use_locale("zh-CN"):
            run_simulation(...)
    """

    def __init__(self, locale: Optional[str]):
        self._locale = locale
        self._token: Optional[contextvars.Token] = None

    def __enter__(self) -> str:
        self._token = set_active_locale(self._locale)
        return get_active_locale()

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._token is not None:
            reset_active_locale(self._token)
            self._token = None


def t(en: str, zh: str, locale: str = DEFAULT) -> str:
    """Pick a translation given a locale.

    Falls back to the English source if no Chinese is provided.
    """
    if locale == "zh-CN" and zh:
        return zh
    return en


def apply_i18n(payload: Any, locale: str) -> Any:
    """Recursively merge embedded ``i18n[locale]`` blocks into a JSON payload.

    Looks for an ``i18n`` mapping on each dict node — when present and the
    requested locale is a key, the keys inside that block override the
    sibling keys at the same level.

    Example::

        {"name": "Crypto Token Launch",
         "i18n": {"zh-CN": {"name": "加密代币发布"}}}

    With ``locale='zh-CN'`` this becomes ``{"name": "加密代币发布"}``.

    The ``i18n`` block itself is dropped from the returned structure so
    clients never see the source overrides.
    """
    if locale == DEFAULT or not isinstance(payload, (dict, list)):
        # Still strip i18n blocks so the response shape is identical
        # regardless of locale.
        return _strip_i18n(payload)

    if isinstance(payload, list):
        return [apply_i18n(item, locale) for item in payload]

    if isinstance(payload, dict):
        out = dict(payload)
        overrides = out.pop("i18n", None)
        if isinstance(overrides, Mapping):
            block = overrides.get(locale)
            if isinstance(block, Mapping):
                for k, v in block.items():
                    out[k] = v
        # Recurse into nested values
        return {k: apply_i18n(v, locale) for k, v in out.items()}

    return payload


def _strip_i18n(payload: Any) -> Any:
    """Drop ``i18n`` keys recursively without applying overrides."""
    if isinstance(payload, list):
        return [_strip_i18n(item) for item in payload]
    if isinstance(payload, dict):
        return {k: _strip_i18n(v) for k, v in payload.items() if k != "i18n"}
    return payload
