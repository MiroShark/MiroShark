"""Locale-aware prompt loader with English fallback.

Templates are stored as plain strings with ``{placeholder}`` substitution
(``str.format`` syntax) so they can be authored without code execution
and shipped as-is. Each locale lives under ``locales/<dir>/`` where
``<dir>`` is the locale code with ``-`` replaced by ``_`` (so ``zh-CN``
becomes ``zh_CN``).
"""
from __future__ import annotations

import importlib
import os
import pkgutil
from threading import Lock
from typing import Any

DEFAULT_LOCALE = "en"

_cache: dict[str, dict[str, str]] = {}
_locales_cache: list[str] | None = None
_lock = Lock()


def _locale_to_dirname(locale: str) -> str:
    """Map a BCP-47 locale code to a Python package directory name."""
    return locale.replace("-", "_")


def _load_module(locale: str, module: str) -> dict[str, str]:
    """Return the ``PROMPTS`` dict from ``locales.<locale>.<module>``.

    Returns an empty dict if either the module or the dict is missing.
    Cached after first load.
    """
    cache_key = f"{locale}::{module}"
    if cache_key in _cache:
        return _cache[cache_key]

    with _lock:
        # Re-check inside the lock to avoid duplicate imports.
        if cache_key in _cache:
            return _cache[cache_key]
        dirname = _locale_to_dirname(locale)
        try:
            mod = importlib.import_module(
                f"app.prompts.locales.{dirname}.{module}"
            )
            prompts = getattr(mod, "PROMPTS", {}) or {}
            if not isinstance(prompts, dict):
                prompts = {}
        except ModuleNotFoundError:
            prompts = {}
        _cache[cache_key] = prompts
        return prompts


def available_locales() -> list[str]:
    """Discover locale subdirectories under ``locales/``.

    Returns directory names converted back to locale codes (``zh_CN`` →
    ``zh-CN``). Cached on first call.
    """
    global _locales_cache
    if _locales_cache is not None:
        return list(_locales_cache)
    locales_pkg = importlib.import_module("app.prompts.locales")
    dirnames = [
        info.name for info in pkgutil.iter_modules(locales_pkg.__path__)
        if info.ispkg
    ]
    # Convert snake_case folder names back to BCP-47 (zh_CN -> zh-CN).
    # Heuristic: split on first underscore; uppercase the suffix.
    out = []
    for d in dirnames:
        if "_" in d:
            head, _, tail = d.partition("_")
            out.append(f"{head}-{tail.upper()}")
        else:
            out.append(d)
    _locales_cache = sorted(out)
    return list(_locales_cache)


def get_prompt(key: str, locale: str = DEFAULT_LOCALE, **kwargs: Any) -> str:
    """Look up a prompt template and substitute placeholders.

    ``key`` is ``<module>.<name>``. The lookup tries the requested
    locale first, then English. Raises ``KeyError`` if neither has the
    key.

    Placeholders in the template use ``str.format`` syntax. Pass values
    via ``**kwargs``. Missing placeholders raise ``KeyError`` with the
    prompt key in the message.
    """
    if "." not in key:
        raise ValueError(f"Prompt key must be 'module.name', got {key!r}")
    module, name = key.split(".", 1)

    template: str | None = None
    locale_norm = locale or DEFAULT_LOCALE

    if locale_norm != DEFAULT_LOCALE:
        template = _load_module(locale_norm, module).get(name)
    if template is None:
        template = _load_module(DEFAULT_LOCALE, module).get(name)
    if template is None:
        raise KeyError(
            f"Prompt {key!r} not found in locale {locale_norm!r} or default"
        )

    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except KeyError as exc:
        raise KeyError(
            f"Missing placeholder {exc} for prompt {key!r}"
        ) from exc


def list_keys(locale: str = DEFAULT_LOCALE) -> list[str]:
    """Return all ``module.name`` keys available in the given locale.

    Used by coverage tests. Iterates every module file under the locale
    folder (no auto-discovery of new modules in production code paths).
    """
    dirname = _locale_to_dirname(locale)
    pkg_name = f"app.prompts.locales.{dirname}"
    try:
        pkg = importlib.import_module(pkg_name)
    except ModuleNotFoundError:
        return []
    keys: list[str] = []
    for info in pkgutil.iter_modules(pkg.__path__):
        prompts = _load_module(locale, info.name)
        for name in prompts.keys():
            keys.append(f"{info.name}.{name}")
    return sorted(keys)


def missing_keys(locale: str) -> list[str]:
    """Return keys present in English but missing in ``locale``.

    Used by tests to flag untranslated prompts. Returns an empty list
    when ``locale`` is the default.
    """
    if locale == DEFAULT_LOCALE:
        return []
    en_keys = set(list_keys(DEFAULT_LOCALE))
    other_keys = set(list_keys(locale))
    return sorted(en_keys - other_keys)


def _reset_cache_for_tests() -> None:
    """Clear the module cache (only for tests that mutate locale files)."""
    global _locales_cache
    with _lock:
        _cache.clear()
        _locales_cache = None
