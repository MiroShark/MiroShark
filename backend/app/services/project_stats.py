"""Per-project aggregate statistics across one operator's simulations.

The per-project sibling of ``platform_stats``. Where ``platform_stats``
collapses every public, completed simulation on disk into a single
deployment-wide envelope (press kits, the Shields.io platform badge,
LLM-agent health checks), this module produces the same shape of
aggregate scoped to a single ``project_id``.

The motivating use case is the operator hat: an organisation that has
published twenty sims across three named projects has no API call
today to ask *"how is project X performing specifically — consensus
distribution, average confidence, total surface views across just
that project?"*. ``/api/stats`` collapses every project into one
number; the per-sim surfaces describe one run. Per-project stats is
the missing middle.

The ``project_id`` field is already tracked per sim in
``platform_stats._scan_platform_stats`` (line ~396). This module
reuses that same field as the filter key — a sim contributes to the
project aggregate iff its ``state.project_id`` matches the requested
id exactly.

Design notes
------------

* **Same gate as platform stats.** Only ``is_public == True`` AND
  ``status == "completed"`` simulations count toward any aggregate.
  An incomplete sim's mid-run beliefs could flip before the run ends,
  so an operator-facing number that included them would fluctuate.
  Two surfaces, one source of truth — a sim that contributes to
  ``/api/stats`` also contributes to its project's stats, and vice
  versa.

* **Same stance derivation as ``signal_service``.** The same
  plurality + tie-break rules (``bullish > bearish > neutral``) that
  produce the per-sim ``signal.json`` direction land on the
  per-project distribution here. A sim labelled Bullish on its
  signal.json is counted in the project's ``bullish`` bucket.

* **Quality distribution is the new field.** The platform aggregate
  doesn't bucket quality — the corpus is too heterogeneous for the
  distribution to be useful. Inside one project the distribution *is*
  useful: an operator wants to see *"6 excellent, 2 good, 0 fair, 0
  poor"* to know their workflow is producing high-quality sims.
  Reuses the ``quality.health`` field every other surface already
  reads.

* **Unknown project_id → all-zero envelope, not 404.** Absence of a
  project is not an error — it's a valid state (the project hasn't
  shipped its first public sim yet, or every sim is still running).
  A consumer rendering *"N sims published for project X"* doesn't
  need to special-case the fresh-project case.

* **One scan, 60-second cache.** Per-project cache keyed on the
  ``(sim_root, project_id)`` pair so two different projects on the
  same deployment don't share an entry. Same TTL as the platform
  scan so a polling consumer sees consistent freshness across the
  two surfaces. Pass ``force_refresh=True`` to bypass the cache.

* **ETag derives from the cheap inputs.** ``total_sims`` +
  ``newest_sim_id`` is enough to detect material change without
  re-reading the corpus — a new sim in the project bumps both. The
  route handler builds the ETag from those two values so a polling
  consumer's ``If-None-Match`` GET short-circuits to ``304``.

* **Stdlib only.** ``os`` + ``json`` + ``re`` + ``time`` +
  ``threading``. No new dependencies — keeps the platform on its
  zero-new-deps streak.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any, Dict, Iterable, Optional, Tuple

from . import signal_service
from .surface_stats import SURFACE_STATS_FILENAME, SURFACE_KEYS


# ── Configuration ─────────────────────────────────────────────────────────


CACHE_TTL_SECONDS = 60


# Sanity bound on the ``project_id`` URL parameter. Matches the shape
# Wonderwall already generates (``proj_<hex>`` and human-typed slugs
# from the operator workflow) and rejects anything else cheaply at
# the API boundary so a malformed input never reaches the scan loop.
PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,120}$")


_QUALITY_BUCKETS: Tuple[str, ...] = ("excellent", "good", "fair", "poor")


# ── Module-level cache ────────────────────────────────────────────────────


_cache: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()


# ── Internal helpers ──────────────────────────────────────────────────────


def _safe_load_json(path: str) -> Optional[Any]:
    """Best-effort JSON load — never raises.

    Returns ``None`` on missing file, unreadable bytes, or invalid JSON.
    The per-project scan must survive a single corrupt sim folder
    rather than tanking the whole aggregate, same posture as
    ``platform_stats._safe_load_json``.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _iter_sim_dirs(sim_root: str) -> Iterable[Tuple[str, str]]:
    """Yield ``(simulation_id, sim_dir_path)`` for every directory under
    ``sim_root`` that looks like a simulation folder.

    Skips dotfiles and non-directories — same posture as
    ``platform_stats._iter_sim_dirs``.
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

    Mirrors ``platform_stats._final_belief_from_trajectory`` exactly —
    same ±0.2 stance threshold, same one-decimal rounding — so a sim's
    contribution to its project aggregate matches its contribution to
    the platform aggregate byte-for-byte.
    """
    traj = _safe_load_json(os.path.join(sim_dir, "trajectory.json"))
    if not isinstance(traj, dict):
        return None
    snapshots = traj.get("snapshots")
    if not isinstance(snapshots, list):
        return None

    final: Optional[Tuple[float, float, float]] = None
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        positions = snap.get("belief_positions") or {}
        if not isinstance(positions, dict) or not positions:
            continue
        stances = []
        for p in positions.values():
            if isinstance(p, dict) and p:
                try:
                    stances.append(sum(p.values()) / len(p))
                except (TypeError, ZeroDivisionError):
                    continue
        if not stances:
            continue
        total = len(stances)
        nb = sum(1 for s in stances if s > 0.2)
        nbe = sum(1 for s in stances if s < -0.2)
        nn = total - nb - nbe
        final = (
            round(nb / total * 100, 1),
            round(nn / total * 100, 1),
            round(nbe / total * 100, 1),
        )
    return final


def _signal_for_sim(sim_dir: str) -> Optional[Dict[str, Any]]:
    """Derive the same signal payload ``signal_service.compute_signal``
    would emit for this sim, or ``None`` if the trajectory is empty.
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

    Ignores unknown keys — same posture as ``platform_stats``. Returns
    ``0`` when the counter file is missing.
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


def _quality_health_for_sim(sim_dir: str) -> Optional[str]:
    """Return the normalised ``quality.health`` value for a sim, or
    ``None`` if the quality file is missing / unparsable / carries an
    unrecognised value.

    Recognised values are ``"excellent" / "good" / "fair" / "poor"`` —
    the same set ``signal_service`` reads. Case-insensitive match;
    surrounding whitespace stripped.
    """
    quality_doc = _safe_load_json(os.path.join(sim_dir, "quality.json"))
    if not isinstance(quality_doc, dict):
        return None
    raw = quality_doc.get("health")
    if not isinstance(raw, str):
        return None
    normalised = raw.strip().lower()
    if normalised in _QUALITY_BUCKETS:
        return normalised
    return None


def _empty_distribution() -> Dict[str, Any]:
    return {
        "bullish": 0,
        "neutral": 0,
        "bearish": 0,
        "bullish_pct": 0.0,
        "neutral_pct": 0.0,
        "bearish_pct": 0.0,
    }


def _empty_quality_distribution() -> Dict[str, int]:
    return {bucket: 0 for bucket in _QUALITY_BUCKETS}


def _empty_stats(project_id: str) -> Dict[str, Any]:
    return {
        "schema_version": "1",
        "project_id": project_id,
        "total_sims": 0,
        "published_sims": 0,
        "consensus_distribution": _empty_distribution(),
        "avg_confidence_pct": 0.0,
        "quality_distribution": _empty_quality_distribution(),
        "total_surface_views": 0,
        "newest_sim_id": None,
        "newest_sim_created_at": None,
    }


# ── Public API ────────────────────────────────────────────────────────────


def is_valid_project_id(project_id: Any) -> bool:
    """Return ``True`` iff ``project_id`` is a non-empty string matching
    :data:`PROJECT_ID_PATTERN`.

    Used at the API boundary to reject obviously malformed inputs before
    they reach the scan loop — saves a full sim-directory walk on a
    bogus request.
    """
    if not isinstance(project_id, str) or not project_id:
        return False
    return bool(PROJECT_ID_PATTERN.match(project_id))


def compute_project_stats(
    sim_root: str,
    project_id: str,
    *,
    force_refresh: bool = False,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Return per-project aggregate statistics for ``project_id`` under
    ``sim_root``.

    Result shape::

        {
          "schema_version": "1",
          "project_id": <str>,
          "total_sims": <int>,           # public + completed for this project
          "published_sims": <int>,       # alias of total_sims (publish-gated)
          "consensus_distribution": {
            "bullish": <int>, "neutral": <int>, "bearish": <int>,
            "bullish_pct": <float>, "neutral_pct": <float>,
            "bearish_pct": <float>,
          },
          "avg_confidence_pct": <float>,
          "quality_distribution": {
            "excellent": <int>, "good": <int>, "fair": <int>, "poor": <int>,
          },
          "total_surface_views": <int>,
          "newest_sim_id": <str | None>,
          "newest_sim_created_at": <ISO-8601 str | None>,
        }

    An unknown project_id (no matching sims) returns a fully-zeroed
    envelope rather than raising — absence is a valid state, not an
    error. Cached for ``CACHE_TTL_SECONDS`` (60s) per
    ``(sim_root, project_id)`` pair so two different projects don't
    share a cache entry. Pass ``force_refresh=True`` to bypass the
    cache (used by tests and by the route in CI). ``now`` is an
    injection point for tests; production callers leave it ``None``.

    Empty ``project_id`` is normalised to a literal empty string and
    returns the all-zero envelope — the route validates and short-
    circuits before this function is reached, but the defensive
    default keeps the service safe to call from anywhere.
    """
    sim_root_abs = os.path.abspath(sim_root) if sim_root else ""
    project_key = project_id if isinstance(project_id, str) else ""
    cache_key = (sim_root_abs, project_key)
    current_time = time.time() if now is None else now

    if not force_refresh:
        with _cache_lock:
            entry = _cache.get(cache_key)
            if entry is not None:
                cached_at, payload = entry
                if current_time - cached_at < CACHE_TTL_SECONDS:
                    return _deep_copy_stats(payload)

    payload = _scan_project_stats(sim_root_abs, project_key)

    with _cache_lock:
        _cache[cache_key] = (current_time, _deep_copy_stats(payload))

    return payload


def invalidate_cache(
    sim_root: Optional[str] = None,
    project_id: Optional[str] = None,
) -> None:
    """Drop the cached stats for ``(sim_root, project_id)``.

    With both arguments ``None`` the entire cache is cleared. With only
    ``sim_root`` set, every project under that root is dropped. Useful
    in tests so a freshly-written sim is reflected on the next
    ``compute_project_stats`` call without waiting out the TTL.
    """
    with _cache_lock:
        if sim_root is None and project_id is None:
            _cache.clear()
            return
        if sim_root is None:
            return
        target_root = os.path.abspath(sim_root)
        if project_id is None:
            for key in list(_cache.keys()):
                if key[0] == target_root:
                    _cache.pop(key, None)
            return
        _cache.pop((target_root, project_id), None)


def stats_etag(payload: Dict[str, Any]) -> str:
    """Build a short ETag from the cheap inputs.

    ``total_sims`` + ``newest_sim_id`` is enough to detect material
    change without re-reading the corpus — a new sim in the project
    bumps both. The returned value is a quoted ASCII string suitable
    for direct use as an ``ETag`` header.
    """
    total = int(payload.get("total_sims", 0) or 0)
    newest = payload.get("newest_sim_id") or ""
    return f'"project-{total}-{str(newest)[:24]}"'


# ── Implementation details ────────────────────────────────────────────────


def _deep_copy_stats(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the stats payload — mutation-safe."""
    distribution = payload.get("consensus_distribution") or {}
    quality = payload.get("quality_distribution") or {}
    return {
        "schema_version": payload.get("schema_version", "1"),
        "project_id": payload.get("project_id", ""),
        "total_sims": payload.get("total_sims", 0),
        "published_sims": payload.get("published_sims", 0),
        "consensus_distribution": {
            "bullish": distribution.get("bullish", 0),
            "neutral": distribution.get("neutral", 0),
            "bearish": distribution.get("bearish", 0),
            "bullish_pct": distribution.get("bullish_pct", 0.0),
            "neutral_pct": distribution.get("neutral_pct", 0.0),
            "bearish_pct": distribution.get("bearish_pct", 0.0),
        },
        "avg_confidence_pct": payload.get("avg_confidence_pct", 0.0),
        "quality_distribution": {
            bucket: int(quality.get(bucket, 0) or 0) for bucket in _QUALITY_BUCKETS
        },
        "total_surface_views": payload.get("total_surface_views", 0),
        "newest_sim_id": payload.get("newest_sim_id"),
        "newest_sim_created_at": payload.get("newest_sim_created_at"),
    }


def _scan_project_stats(sim_root: str, project_id: str) -> Dict[str, Any]:
    """One-shot scan of ``sim_root`` filtered to ``project_id`` — no
    cache, no locking.

    An empty ``project_id`` short-circuits to the all-zero envelope so
    a caller can't accidentally aggregate every project under the same
    bucket via a blank filter.
    """
    payload = _empty_stats(project_id)
    if not project_id or not sim_root or not os.path.isdir(sim_root):
        return payload

    bullish_count = 0
    neutral_count = 0
    bearish_count = 0
    confidence_total = 0.0
    confidence_n = 0
    surface_views = 0
    quality_counts = _empty_quality_distribution()
    newest_sim_id: Optional[str] = None
    newest_created_at: Optional[str] = None
    total_sims = 0

    for sim_id, sim_dir in _iter_sim_dirs(sim_root):
        state = _safe_load_json(os.path.join(sim_dir, "state.json"))
        if not isinstance(state, dict):
            continue
        sim_project = state.get("project_id")
        if not isinstance(sim_project, str) or sim_project != project_id:
            continue
        if not bool(state.get("is_public", False)):
            continue
        if str(state.get("status", "")).lower() != "completed":
            continue

        total_sims += 1

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

        health = _quality_health_for_sim(sim_dir)
        if health is not None:
            quality_counts[health] += 1

        surface_views += _surface_views_for_sim(sim_dir)

        created_at = state.get("created_at")
        if isinstance(created_at, str) and created_at:
            # Lexicographic compare works on ISO-8601 timestamps.
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
    payload["published_sims"] = total_sims
    payload["consensus_distribution"] = distribution
    payload["avg_confidence_pct"] = avg_confidence
    payload["quality_distribution"] = quality_counts
    payload["total_surface_views"] = surface_views
    payload["newest_sim_id"] = newest_sim_id
    payload["newest_sim_created_at"] = newest_created_at

    return payload
