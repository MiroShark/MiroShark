"""Platform health probe — *"is this MiroShark instance up and completing sims?"*

Every other platform-level surface in the codebase describes the corpus
shape: ``/api/stats`` aggregates analytics over every public completed
simulation, ``/api/surfaces.json`` enumerates the surface area an
integrator can call into, ``/api/ecosystem.json`` lists the integrators
already shipping on the platform. None of them answer the operational
question external status monitors care about: *"is the platform alive,
and is it making forward progress?"*

This module collapses that question into a single envelope — pending
sim count (in-flight work), completed-in-the-last-24h (forward
progress), last-completed timestamp (most recent heartbeat), total
sims (cumulative public throughput), surface count (capability surface
breadth), and a literal ``ok: true`` so a status-page check that just
matches on the body works on day one. The new ``GET /api/status.json``
endpoint reads from here; external monitors (Upptime, BetterUptime,
Statuspage.io), Aeon's heartbeat skill, and integrators pre-flighting a
batch run all consume the same payload.

Design notes
------------

* **No long-lived cache.** A 30-second HTTP ``Cache-Control`` is the
  only smoothing — this surface is meant to be live, so an in-process
  cache would make the freshness number a lie. The scan is the same
  shape as ``platform_stats._iter_sim_dirs``; on a corpus large enough
  for the per-scan cost to matter, the HTTP cache absorbs the polling
  load anyway.

* **Status semantics match the gallery + platform stats.** A sim
  contributes to ``queue_depth`` when its ``state.json.status`` is
  ``"running"`` (case-insensitive, matching the rest of the codebase).
  A sim contributes to ``completed_24h`` when ``status`` is
  ``"completed"`` AND ``state.json.updated_at`` falls within the last
  86400 seconds from the wall clock. Updated-at (not created-at)
  because a completed sim's updated_at is the completion timestamp —
  ``simulation_runner`` writes it on terminal-state transitions.

* **Total sims counts only public + completed sims** — the same
  ``is_public AND status == "completed"`` filter ``platform_stats``
  applies. This endpoint is unauthenticated (it serves external status
  monitors), so the cumulative count must not leak the volume of
  private or in-flight/failed sims to anonymous callers. ``queue_depth``
  and ``completed_24h`` stay whole-corpus liveness signals — they
  convey forward progress, not cumulative private-corpus size.

* **Surface count is injected.** The catalog is the source of truth
  for the surface count; rather than re-implementing the count here,
  the route handler reads ``surfaces_catalog.catalog_count()`` and
  passes it in. Keeps a single source of truth and lets the test suite
  drive the scan without standing up the catalog module.

* **``check_at`` always present.** The timestamp the response was
  generated, so a downstream cache (CDN, reverse-proxy) can compute
  freshness even after the body is cached.

* **Stdlib only.** ``os`` + ``json`` + ``time`` + ``datetime``. Zero
  new dependencies — same posture as ``platform_stats``,
  ``project_stats``, ``surfaces_catalog``, every other pure-data
  module in this tree.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from ..utils.json_io import safe_load_json as _safe_load_json


# ── Configuration ─────────────────────────────────────────────────────────


SCHEMA_VERSION = "1"

# The recency window that defines "completed in the last 24 hours".
# 86_400 seconds matches the natural cadence of a Status-page consumer
# (BetterUptime, Upptime) polling on a daily window. Exposed as a
# module constant so a test can patch it without monkey-patching
# the helper.
RECENT_WINDOW_SECONDS = 24 * 60 * 60


# ── Internal helpers ──────────────────────────────────────────────────────


def _iter_sim_dirs(sim_root: str) -> Iterable[Tuple[str, str]]:
    """Yield ``(simulation_id, sim_dir_path)`` for every simulation-shaped
    directory under ``sim_root``.

    Skips dotfiles + non-directories so a stray ``.DS_Store`` or
    leftover marker file doesn't trip the scan. Matches the posture of
    ``platform_stats._iter_sim_dirs`` byte-for-byte so a sim counted
    by one platform surface is counted by the other.
    """
    if not sim_root or not os.path.isdir(sim_root):
        return
    try:
        entries = sorted(os.listdir(sim_root))
    except OSError:
        return
    for sim_id in entries:
        if sim_id.startswith("."):
            continue
        sim_dir = os.path.join(sim_root, sim_id)
        if not os.path.isdir(sim_dir):
            continue
        yield sim_id, sim_dir


def _iso_to_epoch(iso_value: Any) -> Optional[float]:
    """Parse an ISO-8601 string to a UTC epoch float, or ``None``.

    ``state.json`` writes ``datetime.now().isoformat()`` — a naive
    local timestamp without a timezone suffix in the common case.
    ``fromisoformat`` handles both the naive and timezone-aware
    variants; for the naive case we treat the timestamp as UTC so the
    24-hour-window math is deterministic regardless of the deploy
    region. Trailing ``Z`` is normalised to ``+00:00`` so Python <3.11
    parses it cleanly.
    """
    if not isinstance(iso_value, str) or not iso_value:
        return None
    text = iso_value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _format_iso_utc(epoch_seconds: float) -> str:
    """Format an epoch second value as an ISO-8601 UTC string.

    Produces ``YYYY-MM-DDTHH:MM:SSZ`` (trailing ``Z``) — the shape a
    Statuspage-style consumer expects and the same shape every other
    ``check_at`` field in the API uses.
    """
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# ── Public API ────────────────────────────────────────────────────────────


def build_status(
    sim_root: str,
    *,
    surface_count: int = 0,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Return the platform-status envelope.

    Result shape::

        {
          "ok": true,
          "schema_version": "1",
          "queue_depth": <int>,
          "completed_24h": <int>,
          "last_completed_at": <ISO-8601 UTC str | None>,
          "total_sims": <int>,
          "surface_count": <int>,
          "check_at": <ISO-8601 UTC str>,
        }

    ``surface_count`` is injected by the caller (the route handler
    reads ``surfaces_catalog.catalog_count()`` and forwards it) so the
    service module never has to import the catalog and stays pure-data.

    ``now`` is an injection point for tests; production callers leave
    it ``None`` so the 24-hour window is computed against real
    wall-clock time. Pass a fixed epoch float to make
    ``completed_24h`` deterministic in unit tests.

    Empty / missing / unreadable ``sim_root`` returns a fully-zeroed
    envelope (still ``ok: true``, still well-formed) rather than
    raising — a fresh install probing its own status should see a
    valid envelope, not a 500.
    """
    current_time = time.time() if now is None else now
    window_cutoff = current_time - RECENT_WINDOW_SECONDS

    queue_depth = 0
    completed_24h = 0
    total_sims = 0
    last_completed_epoch: Optional[float] = None

    for _sim_id, sim_dir in _iter_sim_dirs(sim_root):
        state = _safe_load_json(os.path.join(sim_dir, "state.json"))
        if not isinstance(state, dict):
            continue

        status_value = str(state.get("status", "") or "").lower()

        # total_sims counts only public + completed sims — the same
        # ``is_public AND status == "completed"`` filter platform_stats
        # applies. /api/status.json is unauthenticated (it serves external
        # status monitors), so the cumulative count must not leak the volume
        # of private or in-flight/failed sims to anonymous callers.
        # queue_depth and completed_24h stay whole-corpus liveness signals.
        if bool(state.get("is_public", False)) and status_value == "completed":
            total_sims += 1

        if status_value == "running":
            queue_depth += 1

        if status_value == "completed":
            updated_at_epoch = _iso_to_epoch(state.get("updated_at"))
            if updated_at_epoch is None:
                # Fall back to ``created_at`` when ``updated_at`` is
                # missing — older sims written before completion
                # timestamps were instrumented still need to register
                # as "completed at some point" so the last-completed
                # value can be derived.
                updated_at_epoch = _iso_to_epoch(state.get("created_at"))

            if updated_at_epoch is not None:
                if updated_at_epoch >= window_cutoff:
                    completed_24h += 1
                if (
                    last_completed_epoch is None
                    or updated_at_epoch > last_completed_epoch
                ):
                    last_completed_epoch = updated_at_epoch

    last_completed_at = (
        _format_iso_utc(last_completed_epoch)
        if last_completed_epoch is not None
        else None
    )

    safe_surface_count = max(0, int(surface_count or 0))

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "queue_depth": queue_depth,
        "completed_24h": completed_24h,
        "last_completed_at": last_completed_at,
        "total_sims": total_sims,
        "surface_count": safe_surface_count,
        "check_at": _format_iso_utc(current_time),
    }
