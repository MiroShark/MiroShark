"""Shared infrastructure for the completion-notification channels.

Stdlib-only leaf module. Holds the per-channel dedup primitive, the plain
JSON POST helper reused by the Slack and Discord webhook dispatchers, and
the payload-formatting helpers every channel applies identically so a sim's
direction, status verb, and link read the same in Slack, Discord, Telegram,
and email. Each channel keeps its OWN :class:`Dedup` instance, so a send on
one channel never suppresses another channel's send for the same
``(sim_id, status)``.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


class Dedup:
    """Per-process, per-channel ``(sim_id, status)`` dedup set.

    The runner's two terminal code paths both notify, so each channel must
    fire at most once per terminal state. Channel-scoped: instantiate one per
    channel module.
    """

    def __init__(self, max_size: int = 4096) -> None:
        self._fired: set[Tuple[str, str]] = set()
        self._lock = threading.Lock()
        self._max = max_size

    def mark(self, sim_id: str, status: str) -> bool:
        """Record ``(sim_id, status)``; return ``True`` only on the first call."""
        key = (sim_id, status)
        with self._lock:
            if key in self._fired:
                return False
            if len(self._fired) >= self._max:
                self._fired.pop()
            self._fired.add(key)
            return True

    def reset(self) -> None:
        """Clear the set. Test-only convenience."""
        with self._lock:
            self._fired.clear()


def post_json(
    url: str,
    body: Dict[str, Any],
    timeout: float,
    *,
    user_agent: str,
    label: str,
) -> Tuple[bool, str]:
    """POST ``body`` as JSON. Returns ``(ok, message)`` — never raises.

    ``label`` names the channel in the serialize-error message (e.g. "Slack").
    """
    try:
        encoded = json.dumps(body).encode("utf-8")
    except Exception as exc:
        return False, f"Could not serialize {label} payload: {exc}"

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": user_agent,
    }
    req = urllib.request.Request(url, data=encoded, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            if 200 <= code < 300:
                return True, f"HTTP {code}"
            return False, f"HTTP {code}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"URL error: {reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def truncate(value: str, limit: int) -> str:
    """Clip ``value`` to ``limit`` chars with a trailing ellipsis."""
    if not isinstance(value, str):
        return ""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)].rstrip() + "…"


def status_verb(status: str) -> str:
    """Render a terminal status as the human phrase channels headline with."""
    if status == "completed":
        return "Completed"
    if status == "failed":
        return "Failed"
    if status == "test":
        return "Test event"
    return status.title() or "Unknown"


def resolve_share_url(payload: Dict[str, Any]) -> Optional[str]:
    """Return the payload's absolute ``share_url``, or ``None``.

    Chat clients render a link button only for an absolute
    ``http(s)://`` value, so a relative ``share_path`` is not a usable
    fallback here.
    """
    abs_url = payload.get("share_url")
    if isinstance(abs_url, str) and abs_url.strip():
        s = abs_url.strip()
        if s.startswith("http://") or s.startswith("https://"):
            return s
    return None


def consensus_direction(payload: Dict[str, Any]) -> str:
    """Return ``"Bullish"`` / ``"Neutral"`` / ``"Bearish"`` / ``"Failed"``.

    Drives the subject-line prefix and body header — same bucket logic
    as :func:`discord_notify._consensus_color` so every notification
    channel stays aligned on "what just happened."
    """
    if (payload.get("status") or "") == "failed":
        return "Failed"

    consensus = payload.get("final_consensus") or {}
    if not isinstance(consensus, dict):
        return "Neutral"

    try:
        b = float(consensus.get("bullish") or 0.0)
        n = float(consensus.get("neutral") or 0.0)
        r = float(consensus.get("bearish") or 0.0)
    except (TypeError, ValueError):
        return "Neutral"

    if b == 0.0 and n == 0.0 and r == 0.0:
        return "Neutral"

    if b >= r and b >= n:
        return "Bullish"
    if r >= b and r >= n:
        return "Bearish"
    return "Neutral"
