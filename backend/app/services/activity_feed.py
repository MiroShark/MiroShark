"""Lightweight *"what just completed in the last hour?"* activity feed.

Every prior discovery surface in this codebase answers a different
shape of that question. ``GET /api/simulation/public`` is the full
filterable gallery (pagination, search, sort, the kitchen sink).
``GET /api/feed.rss`` + ``GET /api/feed.atom`` are subscription-style
syndication feeds for RSS / Atom readers. ``GET /api/status.json`` is
a liveness probe (queue depth, completed_24h, last_completed_at) but
not a per-sim stream.

None of them answer the polling-loop question integrators actually
ask: *"give me the N most recent completions in a single small JSON
payload, no auth, no gallery framing, fast cache."* That's the surface
this module builds.

The route handler at ``GET /api/activity.json`` reads from here.
Consumers — Aeon's push-recap skill checking what completed since the
last run, Capacitr / AntFleet polling their batch outcomes, status
dashboards rendering a *"recent runs"* strip, social bots that
auto-post when a sim finishes — all consume the same envelope.

Design notes
------------

* **Same publish gate as every other platform-stats surface.** Only
  ``is_public == True`` AND ``status == "completed"`` sims appear. The
  feed is unauthenticated (built for keyless polling), so the
  publish gate keeps the surface from leaking private corpus volume
  to anonymous callers — every sim a consumer reads is one the
  operator already toggled public on the gallery.

* **Sorted by ``completed_at`` descending.** ``completed_at`` is taken
  from ``state.json.updated_at`` — the timestamp ``simulation_runner``
  writes on the terminal-state transition — falling back to
  ``created_at`` for older sims whose updated_at predates the
  completion-timestamp instrumentation. Lexicographic ISO-8601
  compare; sims without any usable timestamp are skipped from the
  ordering (they'd otherwise float arbitrarily on a stable sort).

* **Signal fields derived, not stored.** ``direction``,
  ``confidence_pct``, ``quality_health`` come from
  :mod:`signal_service.compute_signal` over the same final-round
  belief split the per-sim ``signal.json`` surface uses. A sim's
  ``direction`` here matches its per-sim signal byte-for-byte. The
  trajectory walk mirrors ``platform_stats`` / ``project_stats`` /
  ``batch_status`` so all four surfaces report the same answer for
  the same sim.

* **``total_rounds`` is the trajectory length** — the same value
  ``peak_round.total_rounds`` and ``batch_status.total_rounds`` use.
  Walked once alongside the belief positions so the scan stays a
  single pass per sim.

* **``scenario_title`` is truncated.** The scenario text lives in
  ``simulation_config.json`` as ``simulation_requirement`` (often a
  full paragraph) — same source ``GET /api/simulation/<id>/clone.json``
  reads. Truncated to ``SCENARIO_TITLE_MAX_CHARS`` characters with a
  trailing ellipsis on overflow so the activity payload stays tight
  for status-dashboard layouts; full scenario text remains available
  on the per-sim surfaces.

* **``limit`` is clamped, not rejected.** The query param accepts any
  positive integer; values below ``MIN_LIMIT`` clamp up, values above
  ``MAX_LIMIT`` clamp down. Non-numeric or absent → ``DEFAULT_LIMIT``.
  This matches the gallery API posture (loose clamps over hard
  errors) and prevents a polling loop with a typo'd param from 400-ing.

* **One scan, no in-process cache.** The route handler sets a 30-second
  HTTP ``Cache-Control``, which is the only smoothing. An in-process
  cache would either make the *"recent completions"* number stale
  (defeating the polling use case) or require invalidation hooks in
  every code path that finishes a sim. The HTTP cache absorbs the
  polling load on its own.

* **Stdlib only.** ``os`` + ``json``. Zero new dependencies — keeps
  the platform on its zero-new-deps streak alongside every other
  pure-data module in this tree.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import signal_service
from ..utils.json_io import safe_load_json as _safe_load_json
from ..utils.belief import bucket_snapshots


# ── Configuration ────────────────────────────────────────────────────────


SCHEMA_VERSION = "1"


# Per-request ``?limit=`` clamp. Default 20 matches the article spec
# and the feed surfaces' default page size. Min 1 / Max 50 reflects
# the same posture every other paginated surface in the codebase uses
# (gallery API + RSS / Atom feed).
DEFAULT_LIMIT = 20
MIN_LIMIT = 1
MAX_LIMIT = 50


# Scenario titles are full paragraphs in ``simulation_config.json``.
# 100 chars is long enough that a status-dashboard row reads cleanly,
# short enough that the activity payload stays compact for a polling
# loop pulling every 30 seconds. Matches the title cap the Atom / RSS
# feed renderer uses for the same payload.
SCENARIO_TITLE_MAX_CHARS = 100


# ── Internal helpers ──────────────────────────────────────────────────────


def _iter_sim_dirs(sim_root: str) -> Iterable[Tuple[str, str]]:
    """Yield ``(simulation_id, sim_dir_path)`` for every simulation-shaped
    directory under ``sim_root``.

    Skips dotfiles + non-directories — same posture as
    ``platform_stats._iter_sim_dirs`` and ``platform_status._iter_sim_dirs``
    so a sim counted by one platform surface is counted by the others.
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


def _final_belief_and_rounds(
    sim_dir: str,
) -> Tuple[Optional[Tuple[float, float, float]], int]:
    """Return ``((bullish_pct, neutral_pct, bearish_pct), total_rounds)``.

    The first element is ``None`` when the trajectory is missing /
    empty / has no parseable belief positions; ``total_rounds`` is
    still meaningful (count of well-formed snapshots) in that case.

    Mirrors ``batch_status._final_belief_from_trajectory`` exactly —
    same ±0.2 stance threshold, same one-decimal rounding — so a sim's
    direction here matches its per-sim signal.json / batch-status
    entry byte-for-byte.
    """
    traj = _safe_load_json(os.path.join(sim_dir, "trajectory.json"))
    if not isinstance(traj, dict):
        return None, 0
    snapshots = traj.get("snapshots")
    if not isinstance(snapshots, list):
        return None, 0

    # counted_rounds = snapshots with a parseable stance; matches
    # batch_status so activity_feed.total_rounds equals BatchStatusEntry
    # .total_rounds byte-for-byte for the same sim.
    final, counted_rounds = bucket_snapshots(snapshots)
    return final, counted_rounds


def _signal_for_sim(
    sim_dir: str,
) -> Tuple[Optional[Dict[str, Any]], int]:
    """Return ``(signal_payload, total_rounds)`` for one completed sim.

    Signal payload is the same dict :mod:`signal_service.compute_signal`
    emits for the per-sim ``/signal.json`` surface; ``None`` when the
    trajectory has no parseable belief positions. ``total_rounds`` is
    the snapshot count from the trajectory (always returned, even when
    the signal is ``None``).
    """
    belief, total_rounds = _final_belief_and_rounds(sim_dir)
    if belief is None:
        return None, total_rounds
    bullish, neutral, bearish = belief

    quality_doc = _safe_load_json(os.path.join(sim_dir, "quality.json")) or {}
    health = quality_doc.get("health") if isinstance(quality_doc, dict) else None

    summary = {
        "belief": {
            "final": {"bullish": bullish, "neutral": neutral, "bearish": bearish},
        },
        "quality": {"health": health} if health else {},
    }
    signal = signal_service.compute_signal(summary)
    return signal, total_rounds


def _scenario_title(sim_dir: str) -> str:
    """Pull the scenario text from ``simulation_config.json`` and
    truncate it for the activity feed.

    Returns the empty string when the config is missing or carries no
    ``simulation_requirement`` field — the route emits the raw value
    rather than a stand-in like ``"(untitled)"`` so a status-dashboard
    consumer can render its own placeholder.
    """
    config = _safe_load_json(os.path.join(sim_dir, "simulation_config.json"))
    if not isinstance(config, dict):
        return ""
    raw = config.get("simulation_requirement")
    if not isinstance(raw, str):
        return ""
    cleaned = raw.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= SCENARIO_TITLE_MAX_CHARS:
        return cleaned
    return cleaned[: SCENARIO_TITLE_MAX_CHARS - 1].rstrip() + "…"


def _normalise_completed_at(state: Dict[str, Any]) -> Optional[str]:
    """Pick the completion timestamp for a completed sim.

    ``state.json.updated_at`` is what ``simulation_runner`` writes on
    the terminal-state transition. Falls back to ``created_at`` for
    older sims written before the completion-timestamp field was
    instrumented so a completed-but-undated sim still appears in the
    feed.
    """
    for key in ("updated_at", "created_at"):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


# ── Public API ────────────────────────────────────────────────────────────


def clamp_limit(value: Any) -> int:
    """Clamp ``value`` into ``[MIN_LIMIT, MAX_LIMIT]``.

    Non-numeric, missing, ``None``, or ``bool`` inputs fall back to
    ``DEFAULT_LIMIT``. Numeric inputs below ``MIN_LIMIT`` clamp up,
    above ``MAX_LIMIT`` clamp down. ``True`` / ``False`` are rejected
    explicitly (a stray boolean from a misparse should not masquerade
    as ``1`` / ``0``).
    """
    if value is None or isinstance(value, bool):
        return DEFAULT_LIMIT
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    if coerced < MIN_LIMIT:
        return MIN_LIMIT
    if coerced > MAX_LIMIT:
        return MAX_LIMIT
    return coerced


def build_activity_feed(
    sim_root: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Return the activity-feed envelope.

    Result shape::

        {
          "schema_version": "1",
          "count": <int>,
          "results": [
            {
              "sim_id": <str>,
              "scenario_title": <str>,         # truncated to 100 chars
              "direction": <"Bullish" | "Neutral" | "Bearish" | None>,
              "confidence_pct": <float | None>,
              "quality_health": <str | None>,
              "total_rounds": <int>,
              "completed_at": <ISO-8601 str | None>,
              "project_id": <str | None>,
            },
            ...
          ]
        }

    ``results`` is ordered by ``completed_at`` descending. ``count``
    equals ``len(results)`` (always ``<= limit``) so a caller can
    assert the response is well-formed without scanning the array.

    Only ``is_public == True`` AND ``status == "completed"`` sims
    contribute — the same publish gate ``/api/feed.rss`` and
    ``/api/stats`` apply. Sims missing both ``updated_at`` and
    ``created_at`` are excluded (they'd otherwise float arbitrarily
    on the sort).

    Empty / missing ``sim_root`` returns ``{"schema_version": "1",
    "count": 0, "results": []}`` rather than raising — a fresh install
    polling itself sees a well-formed empty envelope, not a 500.

    The caller is expected to pre-clamp ``limit`` via :func:`clamp_limit`;
    callers passing a raw ``limit`` outside the allowed range still
    get a sane response (the function applies the clamp defensively).
    """
    effective_limit = clamp_limit(limit)

    if not sim_root or not os.path.isdir(sim_root):
        return {
            "schema_version": SCHEMA_VERSION,
            "count": 0,
            "results": [],
        }

    # Collect (sort_key, entry) tuples; sort once at the end. Reading
    # the whole corpus is bounded by disk I/O — the sort itself is
    # cheap relative to the per-sim JSON loads.
    candidates: List[Tuple[str, Dict[str, Any]]] = []

    for sim_id, sim_dir in _iter_sim_dirs(sim_root):
        state = _safe_load_json(os.path.join(sim_dir, "state.json"))
        if not isinstance(state, dict):
            continue
        if not bool(state.get("is_public", False)):
            continue
        if str(state.get("status", "") or "").lower() != "completed":
            continue

        completed_at = _normalise_completed_at(state)
        if not completed_at:
            # Without a usable timestamp we can't place the sim in the
            # ordering. Skip rather than emit an unsortable entry that
            # would float to an arbitrary slot.
            continue

        signal, total_rounds = _signal_for_sim(sim_dir)

        direction: Optional[str] = None
        confidence_pct: Optional[float] = None
        quality_health: Optional[str] = None
        if signal is not None:
            direction = signal.get("direction")
            confidence_pct = signal.get("confidence_pct")
            quality_health = signal.get("quality_health")

        project_id = state.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            project_id_out: Optional[str] = None
        else:
            project_id_out = project_id.strip()

        entry: Dict[str, Any] = {
            "sim_id": sim_id,
            "scenario_title": _scenario_title(sim_dir),
            "direction": direction,
            "confidence_pct": confidence_pct,
            "quality_health": quality_health,
            "total_rounds": int(total_rounds),
            "completed_at": completed_at,
            "project_id": project_id_out,
        }
        candidates.append((completed_at, entry))

    # Sort by completed_at descending (lexicographic ISO-8601 compare).
    # Ties (same timestamp) break on sim_id descending so the order is
    # deterministic across calls — useful for the ETag and for tests.
    candidates.sort(key=lambda pair: (pair[0], pair[1]["sim_id"]), reverse=True)

    results = [entry for _ts, entry in candidates[:effective_limit]]

    return {
        "schema_version": SCHEMA_VERSION,
        "count": len(results),
        "results": results,
    }


def feed_etag(payload: Dict[str, Any]) -> str:
    """Build a short ``ETag`` from the cheap inputs.

    ``count`` + the newest entry's ``completed_at`` is enough to detect
    material change without re-reading the corpus — a new completion
    bumps the timestamp, a request with a different ``?limit=`` bumps
    the count. The returned value is a quoted ASCII string suitable
    for direct use as an ``ETag`` header.
    """
    count = int(payload.get("count", 0) or 0)
    results = payload.get("results") or []
    newest = ""
    if results and isinstance(results[0], dict):
        candidate = results[0].get("completed_at")
        if isinstance(candidate, str):
            newest = candidate
    # Trim the timestamp prefix to keep the ETag compact; full second
    # precision is plenty for invalidation.
    return f'"activity-{count}-{newest[:19]}"'
