"""Shared best-effort JSON-artifact reader.

Every read-only surface that projects a simulation's on-disk artifacts
(``state.json``, ``trajectory.json``, ``signal.json``, ``quality.json``,
…) into an API response or export needs the same posture: trust nothing
on disk, never raise. A status / stats / feed endpoint that 500s on a
single stray corrupt file is worse than one that quietly excludes that
sim from the result — so the loader degrades a missing or malformed
artifact to ``None`` and lets the caller decide.

This was previously copy-pasted byte-for-byte as a private
``_safe_load_json`` in ~a dozen service modules; they now share this one
implementation so a future hardening of the read path (e.g. narrowing
the ``except`` or adding a size guard) happens in one place.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


def safe_load_json(path: str) -> Any:
    """Read a JSON file, returning ``None`` on missing / corrupt input.

    Never raises: an empty/falsy ``path`` or a file that is missing,
    unreadable, or not valid JSON all resolve to ``None`` so the caller
    can degrade gracefully instead of failing the request.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def load_state(sim_dir: str) -> Optional[Dict[str, Any]]:
    """Load ``<sim_dir>/state.json`` defensively. Missing/corrupt → ``None``.

    Narrower than :func:`safe_load_json`: a state file that parses to
    anything other than an object is treated as unusable, so callers can
    assume a mapping without re-checking.
    """
    if not sim_dir:
        return None
    state_path = os.path.join(sim_dir, "state.json")
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None
