"""Platform-level aggregate statistics across all published simulations.

Every other share surface in the codebase describes one simulation in
some level of detail — share card, replay GIF, transcript, trajectory
CSV / JSONL, watch page, reproduce.json, notebook.ipynb, chart.svg,
signal.json, archive.zip, badge.svg, cite.bib, polymarket.json. None
of them describe the platform itself.

This module collapses every public, completed simulation on disk into
a single envelope: a sim count, a consensus distribution, an average
confidence percentage, a sum of all share-surface counter increments,
a unique-projects count, and the newest-sim metadata. Two consumers
need it: the new ``GET /api/stats`` endpoint (press kits, external
dashboards, LLM-agent health checks) and the platform badge
(``GET /api/stats/badge.svg``) that renders the same sim count as a
flat 20-pixel Shields.io-compatible pill for any community README.

Design notes
------------

* **One scan, 60-second cache.** The scan is O(n) where n is the
  number of simulations on disk; with a few thousand sims each
  ``state.json`` is a small JSON file and the read amortises. A
  module-level cache keyed on ``WONDERWALL_SIMULATION_DATA_DIR``
  expires after ``CACHE_TTL_SECONDS`` seconds so a bursty press
  unfurl doesn't re-scan on every request. Pass ``force_refresh=True``
  to skip the cache (used by tests and the badge route in CI).

* **Filters mirror the public gallery.** Only ``is_public == True``
  AND ``status == "completed"`` simulations count toward any
  aggregate. An incomplete sim's mid-run beliefs could flip before
  the run ends, so a press-kit number that included them would
  fluctuate. The gallery already uses ``is_public`` as the
  publish-gate; we add the completion gate on top so platform
  numbers are stable.

* **Stance derivation reuses ``signal_service``.** The same plurality
  + tie-break rules that produce ``Bullish`` / ``Neutral`` /
  ``Bearish`` on the per-sim signal.json land on the platform
  distribution here. Two surfaces, one source of truth.

* **Unique projects, not operators.** ``SimulationState`` has no
  operator / created_by field — the closest stable identifier is
  ``project_id`` (each project is a single research / operator
  workspace). The aggregate is exposed as
  ``unique_projects`` rather than ``unique_operators`` so the field
  name doesn't promise data the model can't back. Add an explicit
  ``operator`` field to the model later if a stronger guarantee is
  needed.

* **ETag derives from the cheap inputs.** ``total_sims`` +
  ``newest_sim_id`` is enough to detect material change without
  re-reading the corpus — a new sim bumps both. The route handler
  builds the ETag from those two values so a ``If-None-Match``
  conditional GET short-circuits to 304 before the JSON body is
  built.

* **Stdlib only.** ``os`` + ``json`` + ``time`` + ``threading``. No
  new dependencies — keeps the platform on its 31-PR zero-new-deps
  streak.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Iterable, Optional, Tuple

from . import signal_service
from .surface_stats import SURFACE_STATS_FILENAME, SURFACE_KEYS
from ..utils.json_io import safe_load_json as _safe_load_json
from ..utils.belief import bucket_snapshots


# ── Configuration ─────────────────────────────────────────────────────────


CACHE_TTL_SECONDS = 60


# ── Module-level cache ────────────────────────────────────────────────────
#
# Keyed on the absolute sim_root path so two configured roots in the same
# process (unlikely in practice, but tests sometimes spin up several) get
# independent caches. Guarded by a lock so two concurrent requests don't
# re-scan in parallel after the TTL expires.


_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()


# ── Internal helpers ──────────────────────────────────────────────────────


def _iter_sim_dirs(sim_root: str) -> Iterable[Tuple[str, str]]:
    """Yield ``(simulation_id, sim_dir_path)`` for every directory under
    ``sim_root`` that looks like a simulation folder.

    Skips dotfiles and non-directories so a stray ``.DS_Store`` or
    leftover marker file doesn't trip the scan. Same posture as
    ``SimulationManager.list_simulations``.
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


def _final_belief_from_trajectory(sim_dir: str) -> Optional[Tuple[float, float, float]]:
    """Return ``(bullish_pct, neutral_pct, bearish_pct)`` for the final
    round in ``trajectory.json``, or ``None`` if the trajectory is
    missing / empty / unparsable.

    Computation mirrors ``_build_embed_summary_payload`` in
    ``app/api/simulation.py`` so a stance reported here matches what the
    per-sim signal.json and badge.svg surfaces report for the same
    simulation.
    """
    traj = _safe_load_json(os.path.join(sim_dir, "trajectory.json"))
    if not isinstance(traj, dict):
        return None
    snapshots = traj.get("snapshots")
    if not isinstance(snapshots, list):
        return None

    final, _ = bucket_snapshots(snapshots)
    return final


def _signal_for_sim(sim_dir: str) -> Optional[Dict[str, Any]]:
    """Derive the same signal payload ``signal_service.compute_signal``
    would emit for this sim, or ``None`` if the trajectory is empty.

    Reads ``quality.json`` for the health field — falls back to
    ``"N/A"`` when missing so ``risk_tier`` still resolves.
    """
    final = _final_belief_from_trajectory(sim_dir)
    if final is None:
        return None
    bullish, neutral, bearish = final

    quality_path = os.path.join(sim_dir, "quality.json")
    quality_doc = _safe_load_json(quality_path) or {}
    health = quality_doc.get("health") if isinstance(quality_doc, dict) else None

    summary = {
        "belief": {
            "final": {"bullish": bullish, "neutral": neutral, "bearish": bearish},
        },
        "quality": {"health": health} if health else {},
    }
    return signal_service.compute_signal(summary)


def _surface_views_for_sim(sim_dir: str) -> int:
    """Sum every recognised key in this sim's ``surface-stats.json``.

    Ignores ``total`` (it's a synthetic field added by
    ``surface_stats.read_surface_stats``, not persisted to disk) and any
    unknown key — same posture as ``surface_stats._load_raw``.
    """
    payload = _safe_load_json(os.path.join(sim_dir, SURFACE_STATS_FILENAME))
    if not isinstance(payload, dict):
        return 0
    total = 0
    for key in SURFACE_KEYS:
        value = payload.get(key, 0)
        try:
            ivalue = int(value)
        except (TypeError, ValueError):
            ivalue = 0
        total += max(0, ivalue)
    return total


def _empty_distribution() -> Dict[str, Any]:
    return {
        "bullish": 0,
        "neutral": 0,
        "bearish": 0,
        "bullish_pct": 0.0,
        "neutral_pct": 0.0,
        "bearish_pct": 0.0,
    }


def _empty_stats() -> Dict[str, Any]:
    return {
        "schema_version": "1",
        "total_sims": 0,
        "consensus_distribution": _empty_distribution(),
        "avg_confidence_pct": 0.0,
        "total_surface_views": 0,
        "unique_projects": 0,
        "newest_sim_id": None,
        "newest_sim_created_at": None,
    }


# ── Public API ────────────────────────────────────────────────────────────


def compute_platform_stats(
    sim_root: str,
    *,
    force_refresh: bool = False,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Return platform-level aggregate statistics for every public,
    completed simulation under ``sim_root``.

    Result shape::

        {
          "schema_version": "1",
          "total_sims": <int>,
          "consensus_distribution": {
            "bullish": <int>, "neutral": <int>, "bearish": <int>,
            "bullish_pct": <float>, "neutral_pct": <float>,
            "bearish_pct": <float>,
          },
          "avg_confidence_pct": <float>,
          "total_surface_views": <int>,
          "unique_projects": <int>,
          "newest_sim_id": <str | None>,
          "newest_sim_created_at": <ISO-8601 str | None>,
        }

    Cached for ``CACHE_TTL_SECONDS`` (60s) per ``sim_root`` to absorb
    repeat hits. Pass ``force_refresh=True`` to bypass the cache.
    ``now`` is an injection point for tests; production callers leave
    it ``None`` so the cache check uses real wall-clock time.

    Empty / missing ``sim_root`` returns a fully-zeroed envelope
    rather than raising — the caller can render "0 simulations" the
    same way a 1000-sim deployment renders its real number.
    """
    sim_root_abs = os.path.abspath(sim_root) if sim_root else ""
    current_time = time.time() if now is None else now

    if not force_refresh:
        with _cache_lock:
            entry = _cache.get(sim_root_abs)
            if entry is not None:
                cached_at, payload = entry
                if current_time - cached_at < CACHE_TTL_SECONDS:
                    # Return a shallow-cloned copy so a caller mutating
                    # the dict (e.g. injecting a frontend-only field)
                    # doesn't pollute the cache.
                    return _deep_copy_stats(payload)

    payload = _scan_platform_stats(sim_root_abs)

    with _cache_lock:
        _cache[sim_root_abs] = (current_time, _deep_copy_stats(payload))

    return payload


def invalidate_cache(sim_root: Optional[str] = None) -> None:
    """Drop the cached stats for ``sim_root`` (or every root when ``None``).

    Useful in tests so a freshly-written sim is reflected on the next
    ``compute_platform_stats`` call without waiting out the TTL.
    """
    with _cache_lock:
        if sim_root is None:
            _cache.clear()
            return
        _cache.pop(os.path.abspath(sim_root), None)


def stats_etag(payload: Dict[str, Any]) -> str:
    """Build a short ETag from the cheap inputs.

    ``total_sims`` + ``newest_sim_id`` is enough to detect material
    change without re-reading the corpus — a new sim bumps both. The
    returned value is a quoted ASCII string suitable for direct use as
    an ``ETag`` header.
    """
    total = int(payload.get("total_sims", 0) or 0)
    newest = payload.get("newest_sim_id") or ""
    # Trim the sim_id to keep the ETag short — the prefix is unique
    # enough across realistic corpora and we already mix in
    # ``total_sims`` for collision avoidance.
    return f'"{total}-{str(newest)[:24]}"'


# ── Implementation details ────────────────────────────────────────────────


def _deep_copy_stats(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the stats payload — mutation-safe.

    The payload is a small fixed-shape dict; manual copying is cheaper
    than ``copy.deepcopy`` and keeps the cache hot path allocation-light.
    """
    distribution = payload.get("consensus_distribution") or {}
    return {
        "schema_version": payload.get("schema_version", "1"),
        "total_sims": payload.get("total_sims", 0),
        "consensus_distribution": {
            "bullish": distribution.get("bullish", 0),
            "neutral": distribution.get("neutral", 0),
            "bearish": distribution.get("bearish", 0),
            "bullish_pct": distribution.get("bullish_pct", 0.0),
            "neutral_pct": distribution.get("neutral_pct", 0.0),
            "bearish_pct": distribution.get("bearish_pct", 0.0),
        },
        "avg_confidence_pct": payload.get("avg_confidence_pct", 0.0),
        "total_surface_views": payload.get("total_surface_views", 0),
        "unique_projects": payload.get("unique_projects", 0),
        "newest_sim_id": payload.get("newest_sim_id"),
        "newest_sim_created_at": payload.get("newest_sim_created_at"),
    }


def _scan_platform_stats(sim_root: str) -> Dict[str, Any]:
    """One-shot scan of ``sim_root`` — no cache, no locking."""
    payload = _empty_stats()
    if not sim_root or not os.path.isdir(sim_root):
        return payload

    bullish_count = 0
    neutral_count = 0
    bearish_count = 0
    confidence_total = 0.0
    confidence_n = 0
    surface_views = 0
    project_ids: set[str] = set()
    newest_sim_id: Optional[str] = None
    newest_created_at: Optional[str] = None
    total_sims = 0

    for sim_id, sim_dir in _iter_sim_dirs(sim_root):
        state = _safe_load_json(os.path.join(sim_dir, "state.json"))
        if not isinstance(state, dict):
            continue
        if not bool(state.get("is_public", False)):
            continue
        if str(state.get("status", "")).lower() != "completed":
            continue

        total_sims += 1

        project_id = state.get("project_id")
        if isinstance(project_id, str) and project_id.strip():
            project_ids.add(project_id.strip())

        signal = _signal_for_sim(sim_dir)
        if signal is not None:
            direction = (signal.get("direction") or "").lower()
            if direction == "bullish":
                bullish_count += 1
            elif direction == "bearish":
                bearish_count += 1
            elif direction == "neutral":
                neutral_count += 1
            try:
                confidence_total += float(signal.get("confidence_pct", 0.0))
                confidence_n += 1
            except (TypeError, ValueError):
                pass

        surface_views += _surface_views_for_sim(sim_dir)

        created_at = state.get("created_at")
        if isinstance(created_at, str) and created_at:
            # Lexicographic compare works on ISO-8601 timestamps — every
            # state.json writes ``datetime.now().isoformat()``.
            if newest_created_at is None or created_at > newest_created_at:
                newest_created_at = created_at
                newest_sim_id = sim_id

    distribution = _empty_distribution()
    if total_sims > 0:
        distribution["bullish"] = bullish_count
        distribution["neutral"] = neutral_count
        distribution["bearish"] = bearish_count
        distribution["bullish_pct"] = round(bullish_count / total_sims * 100, 1)
        distribution["neutral_pct"] = round(neutral_count / total_sims * 100, 1)
        distribution["bearish_pct"] = round(bearish_count / total_sims * 100, 1)

    avg_confidence = round(confidence_total / confidence_n, 1) if confidence_n > 0 else 0.0

    payload["total_sims"] = total_sims
    payload["consensus_distribution"] = distribution
    payload["avg_confidence_pct"] = avg_confidence
    payload["total_surface_views"] = surface_views
    payload["unique_projects"] = len(project_ids)
    payload["newest_sim_id"] = newest_sim_id
    payload["newest_sim_created_at"] = newest_created_at

    return payload
