"""Shared infrastructure for the completion-notification channels.

Stdlib-only leaf module. Holds the per-channel dedup primitive and the plain
JSON POST helper reused by the Slack and Discord webhook dispatchers. Each
channel keeps its OWN :class:`Dedup` instance, so a send on one channel never
suppresses another channel's send for the same ``(sim_id, status)``.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple


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
