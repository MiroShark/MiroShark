"""Simple local accounting for paid image renders."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

DEFAULT_OPENAI_DAILY_LIMIT = 20


class RenderLimitError(RuntimeError):
    """Raised when a paid render would exceed a configured local budget cap."""


def current_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def get_render_accounting(session: dict[str, Any]) -> dict[str, Any]:
    accounting = session.setdefault("render_accounting", {})
    accounting.setdefault("total", {})
    accounting.setdefault("daily", {})
    accounting.setdefault("events", [])
    return accounting


def get_openai_daily_limit() -> int:
    raw = os.environ.get("OPENAI_IMAGE_DAILY_LIMIT", str(DEFAULT_OPENAI_DAILY_LIMIT))
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_OPENAI_DAILY_LIMIT


def provider_count_today(session: dict[str, Any], provider: str, day: str | None = None) -> int:
    accounting = get_render_accounting(session)
    day_key = day or current_day()
    daily = accounting.get("daily", {}).get(day_key, {})
    if provider == "openai":
        return sum(int(count) for name, count in daily.items() if str(name).startswith("openai"))
    return int(daily.get(provider, 0))


def assert_render_allowed(session: dict[str, Any], provider: str, requested: int = 1) -> None:
    if not str(provider).startswith("openai"):
        return
    limit = get_openai_daily_limit()
    used = provider_count_today(session, provider)
    if used + requested > limit:
        raise RenderLimitError(f"OpenAI image daily limit exceeded: used {used}, requested {requested}, limit {limit}")


def record_render_event(session: dict[str, Any], *, provider: str, model: str, slide_index: int, bytes: int, quality: str | None = None, size: str | None = None) -> dict[str, Any]:
    accounting = get_render_accounting(session)
    day_key = current_day()
    accounting["total"][provider] = int(accounting["total"].get(provider, 0)) + 1
    accounting["daily"].setdefault(day_key, {})
    accounting["daily"][day_key][provider] = int(accounting["daily"][day_key].get(provider, 0)) + 1
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "slide_index": slide_index,
        "bytes": bytes,
        "quality": quality,
        "size": size,
    }
    accounting["events"].append(event)
    # Keep the session JSON bounded.
    accounting["events"] = accounting["events"][-200:]
    return accounting


def accounting_summary(session: dict[str, Any]) -> dict[str, Any]:
    accounting = get_render_accounting(session)
    day_key = current_day()
    openai_used_today = provider_count_today(session, "openai", day_key)
    return {
        "day": day_key,
        "openai_daily_limit": get_openai_daily_limit(),
        "openai_used_today": openai_used_today,
        "openai_remaining_today": max(0, get_openai_daily_limit() - openai_used_today),
        "total": accounting.get("total", {}),
        "daily": accounting.get("daily", {}),
    }
