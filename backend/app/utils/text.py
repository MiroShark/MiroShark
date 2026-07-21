"""Shared string-coercion helpers for read-only projection surfaces.

Anything that renders on-disk artifacts (state.json, config files) into
an API response, sitemap, or export needs the same posture: trust
nothing on disk, never raise. These coercions degrade unusable input to
a benign empty value so a single stray field can't blank out a whole
response.
"""

from __future__ import annotations

from typing import Any


def safe_str(value: Any) -> str:
    """Coerce ``value`` to a stripped string; ``None`` ⇒ empty."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value).strip()
    except Exception:
        return ""
