"""Locale-aware prompt registry.

The registry serves prompt strings keyed by ``<module>.<name>`` for a given
locale, with automatic English fallback when a locale is missing a key.

Adding a new language
---------------------
1. Pick a locale code (BCP-47 style, e.g. ``ja-JP`` or ``fr-FR``).
2. Create ``backend/app/prompts/locales/<locale>/`` (replace ``-`` with
   ``_`` in the directory name so it's a valid Python package).
3. Mirror any English module file you want translated. Each module
   exports a ``PROMPTS`` dict; missing keys silently fall back to
   English so partial translations are fine.
4. Add the locale code to :data:`app.utils.i18n.SUPPORTED` and to
   ``frontend/src/i18n.js`` if you want it user-selectable.

Adding a new prompt
-------------------
1. Add the key to ``backend/app/prompts/locales/en/<module>.py``'s
   ``PROMPTS`` dict.
2. Use ``{placeholders}`` for runtime substitution (``str.format``
   syntax — single braces). Escape literal braces as ``{{`` / ``}}``.
3. Look it up at the call site with
   ``get_prompt("<module>.<name>", locale, key=value, ...)``.
4. Translate by mirroring the entry in other locale folders. Coverage
   tests warn when a non-English locale is missing a key (see
   ``backend/tests/test_unit_prompt_registry.py``).
"""
from .registry import get_prompt, list_keys, missing_keys, available_locales

__all__ = ["get_prompt", "list_keys", "missing_keys", "available_locales"]
