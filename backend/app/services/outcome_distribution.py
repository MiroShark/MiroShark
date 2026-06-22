"""Platform-wide outcome distribution across every public, completed
simulation.

``platform_stats`` collapses the corpus into a single sim count, a
consensus distribution, and an average confidence. It answers *"how
big and how bullish-leaning is the platform?"*. It does not answer
*"what do MiroShark results **look like** in aggregate?"* — what
fraction of completed sims land in each confidence tier, how quality
distributes, how long a typical sim runs.

This module produces the missing shape envelope. ``GET
/api/stats/distribution.json`` reads from here; press write-ups
citing *"X% of public MiroShark sims clear a high-confidence
threshold,"* Aeon digests reporting month-over-month distribution
shifts, and integrators calibrating their own confidence thresholds
against the platform baseline all consume the same payload.

Design notes
------------

* **Same publish gate as every other platform-stats surface.** Only
  ``is_public == True`` AND ``status == "completed"`` sims count
  toward any bucket. Two surfaces, one source of truth — a sim that
  contributes to ``/api/stats.total_sims`` also contributes to
  ``/api/stats/distribution.json.total_analyzed`` and vice versa.

* **Same stance derivation as ``signal_service``.** Direction buckets
  follow the same plurality + tie-break rules
  (``bullish > bearish > neutral``) that produce the per-sim
  ``signal.json`` direction. A sim labelled Bullish on its signal.json
  lands in the ``bullish`` direction bucket here.

* **Confidence tier boundaries.** ``high`` is ``confidence_pct >= 70``,
  ``medium`` is ``40 <= confidence_pct < 70``, ``low`` is
  ``confidence_pct < 40``. Boundaries match the convention reported in
  the daily article series — the *"high-confidence"* threshold a
  reader sees in a write-up is the same threshold an integrator can
  filter against here.

* **Quality tier strings come from ``quality.json``.** ``excellent``
  / ``good`` / ``fair`` / ``poor`` — the same four-tier scale
  ``project_stats.quality_distribution`` reads. Case-insensitive;
  whitespace-stripped; unrecognised values are excluded from every
  bucket (so the bucket sum can be ``< total_analyzed``).

* **Round-count buckets.** ``short`` is ``total_rounds < 10``,
  ``medium`` is ``10 <= total_rounds <= 20``, ``long`` is
  ``total_rounds > 20``. ``total_rounds`` is the number of recorded
  snapshots in ``trajectory.json`` — same source ``peak_round`` uses
  for its ``total_rounds`` field, so the bucket a sim lands in here
  matches the count its per-sim peak-round surface reports.

* **One scan, 5-minute cache.** ``platform_stats`` runs a 60-second
  cache because the badge polling cadence drives that surface;
  ``outcome_distribution`` is consumed mostly by write-ups and
  dashboards refreshing on a slower beat. 300 s reduces disk churn on
  press-unfurl bursts; pass ``force_refresh=True`` to bypass.

* **ETag derives from the cheap inputs.** ``total_analyzed`` plus the
  most-recent ``completed_at[:7]`` (year-month prefix) is enough to
  detect material change without re-reading the corpus — a new sim
  completing in a fresh month bumps both. A polling consumer's
  ``If-None-Match`` GET short-circuits to ``304``.

* **Stdlib only.** ``os`` + ``json`` + ``time`` + ``threading`` +
  ``datetime``. No new dependencies — keeps the platform on its
  zero-new-deps streak.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Iterable, Optional, Tuple

from . import signal_service
from ..utils.json_io import safe_load_json as _safe_load_json
from ..utils.belief import bucket_snapshots
from ..utils.timeutils import utc_iso8601 as _iso_utc_now


# ── Configuration ─────────────────────────────────────────────────────────


CACHE_TTL_SECONDS = 300


# Tier thresholds — boundaries are inclusive on the lower edge.
_HIGH_CONFIDENCE_THRESHOLD = 70.0
_MEDIUM_CONFIDENCE_THRESHOLD = 40.0

_SHORT_ROUND_MAX_EXCLUSIVE = 10        # short: total_rounds < 10
_LONG_ROUND_MIN_EXCLUSIVE = 20         # long: total_rounds > 20
# medium: 10 <= total_rounds <= 20


_CONFIDENCE_BUCKETS: Tuple[str, ...] = ("high", "medium", "low")
_QUALITY_BUCKETS: Tuple[str, ...] = ("excellent", "good", "fair", "poor")
_ROUND_BUCKETS: Tuple[str, ...] = ("short", "medium", "long")


# ── Module-level cache ────────────────────────────────────────────────────


_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()


# ── Internal helpers ──────────────────────────────────────────────────────


def _iter_sim_dirs(sim_root: str) -> Iterable[Tuple[str, str]]:
    """Yield ``(simulation_id, sim_dir_path)`` for every directory under
    ``sim_root`` that looks like a simulation folder.

    Same posture as ``platform_stats._iter_sim_dirs`` — skips dotfiles
    and non-directories so a stray ``.DS_Store`` doesn't trip the scan.
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


def _trajectory_snapshots(sim_dir: str) -> Optional[list]:
    """Return the list of trajectory snapshots, or ``None`` when the
    trajectory file is missing / unparsable / shaped wrong."""
    traj = _safe_load_json(os.path.join(sim_dir, "trajectory.json"))
    if not isinstance(traj, dict):
        return None
    snapshots = traj.get("snapshots")
    if not isinstance(snapshots, list):
        return None
    return snapshots


def _final_belief_from_snapshots(snapshots: list) -> Optional[Tuple[float, float, float]]:
    """Return ``(bullish_pct, neutral_pct, bearish_pct)`` for the final
    round in ``snapshots``, or ``None`` if the list is empty or carries
    no parseable belief positions.

    Mirrors ``platform_stats._final_belief_from_trajectory`` exactly —
    same ±0.2 stance threshold, same one-decimal rounding — so a sim's
    direction here matches its per-sim signal.json byte-for-byte.
    """
    final, _ = bucket_snapshots(snapshots)
    return final


def _signal_for_sim(sim_dir: str, snapshots: list) -> Optional[Dict[str, Any]]:
    """Derive the same signal payload ``signal_service.compute_signal``
    would emit for this sim, or ``None`` if the trajectory has no
    parseable belief positions.

    Reads ``quality.json`` for the health string — falls back to
    nothing when missing so ``risk_tier`` resolves to its high-risk
    default upstream.
    """
    final = _final_belief_from_snapshots(snapshots)
    if final is None:
        return None
    bullish, neutral, bearish = final

    quality_doc = _safe_load_json(os.path.join(sim_dir, "quality.json")) or {}
    health = quality_doc.get("health") if isinstance(quality_doc, dict) else None

    summary = {
        "belief": {
            "final": {"bullish": bullish, "neutral": neutral, "bearish": bearish},
        },
        "quality": {"health": health} if health else {},
    }
    return signal_service.compute_signal(summary)


def _quality_health_bucket(sim_dir: str) -> Optional[str]:
    """Return the normalised quality bucket for a sim, or ``None`` when
    the file is missing / unparsable / carries an unrecognised value.

    Case-insensitive match on the leading word so ``"Excellent "`` and
    ``"excellent"`` map to the same bucket — same posture as
    ``project_stats._quality_health_for_sim``.
    """
    quality_doc = _safe_load_json(os.path.join(sim_dir, "quality.json"))
    if not isinstance(quality_doc, dict):
        return None
    raw = quality_doc.get("health")
    if not isinstance(raw, str):
        return None
    normalised = raw.strip().lower()
    if not normalised:
        return None
    leading = normalised.split()[0]
    if leading in _QUALITY_BUCKETS:
        return leading
    return None


def _confidence_bucket(confidence_pct: float) -> str:
    """Map a confidence percentage to ``high`` / ``medium`` / ``low``.

    ``>= 70`` → ``high``; ``40 <= x < 70`` → ``medium``; ``< 40`` →
    ``low``. Boundaries are inclusive on the lower edge so a sim
    landing exactly at the threshold is classified upward.
    """
    if confidence_pct >= _HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if confidence_pct >= _MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def _round_count_bucket(total_rounds: int) -> str:
    """Map a round count to ``short`` / ``medium`` / ``long``.

    ``< 10`` → ``short``; ``10..20`` → ``medium``; ``> 20`` → ``long``.
    The medium band straddles the typical operator-template range; the
    short / long bands capture the early-stop and long-run tails.
    """
    if total_rounds < _SHORT_ROUND_MAX_EXCLUSIVE:
        return "short"
    if total_rounds > _LONG_ROUND_MIN_EXCLUSIVE:
        return "long"
    return "medium"


def _bucket_with_pcts(counts: Dict[str, int], total: int) -> Dict[str, Any]:
    """Convert a counts dict into a ``{key, key_pct}``-flavoured dict.

    Percentages are rounded to one decimal and ``0.0`` when ``total ==
    0``. Same convention as ``platform_stats._scan_platform_stats``.
    """
    out: Dict[str, Any] = {}
    for key, value in counts.items():
        out[key] = int(value)
        if total > 0:
            out[f"{key}_pct"] = round(value / total * 100, 1)
        else:
            out[f"{key}_pct"] = 0.0
    return out


def _empty_direction_counts() -> Dict[str, int]:
    return {"bullish": 0, "neutral": 0, "bearish": 0}


def _empty_confidence_counts() -> Dict[str, int]:
    return {bucket: 0 for bucket in _CONFIDENCE_BUCKETS}


def _empty_quality_counts() -> Dict[str, int]:
    return {bucket: 0 for bucket in _QUALITY_BUCKETS}


def _empty_round_counts() -> Dict[str, int]:
    return {bucket: 0 for bucket in _ROUND_BUCKETS}


def _empty_envelope() -> Dict[str, Any]:
    return {
        "schema_version": "1",
        "generated_at": _iso_utc_now(),
        "total_analyzed": 0,
        "by_direction": _bucket_with_pcts(_empty_direction_counts(), 0),
        "by_confidence": _bucket_with_pcts(_empty_confidence_counts(), 0),
        "by_quality": _bucket_with_pcts(_empty_quality_counts(), 0),
        "by_round_count": _bucket_with_pcts(_empty_round_counts(), 0),
        "avg_confidence_pct": 0.0,
        "avg_total_rounds": 0.0,
        "newest_completed_at": None,
    }


# ── Public API ────────────────────────────────────────────────────────────


def build_distribution(
    sim_root: str,
    *,
    force_refresh: bool = False,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Return the platform-wide outcome distribution for every public,
    completed simulation under ``sim_root``.

    Result shape::

        {
          "schema_version": "1",
          "generated_at": <ISO-8601 UTC str>,
          "total_analyzed": <int>,
          "by_direction": {
            "bullish": <int>, "bullish_pct": <float>,
            "neutral": <int>, "neutral_pct": <float>,
            "bearish": <int>, "bearish_pct": <float>,
          },
          "by_confidence": {
            "high": <int>, "high_pct": <float>,
            "medium": <int>, "medium_pct": <float>,
            "low": <int>, "low_pct": <float>,
          },
          "by_quality": {
            "excellent": <int>, "excellent_pct": <float>,
            "good": <int>, "good_pct": <float>,
            "fair": <int>, "fair_pct": <float>,
            "poor": <int>, "poor_pct": <float>,
          },
          "by_round_count": {
            "short": <int>, "short_pct": <float>,
            "medium": <int>, "medium_pct": <float>,
            "long": <int>, "long_pct": <float>,
          },
          "avg_confidence_pct": <float>,
          "avg_total_rounds": <float>,
          "newest_completed_at": <ISO-8601 str | None>,
        }

    Cached for ``CACHE_TTL_SECONDS`` (300 s) per ``sim_root`` to absorb
    bursty unfurls. Pass ``force_refresh=True`` to bypass the cache.
    ``now`` is an injection point for tests; production callers leave
    it ``None`` so the cache check uses real wall-clock time.

    Empty / missing ``sim_root`` returns a fully-zeroed envelope rather
    than raising — a fresh install renders *"0 simulations analysed"*
    the same way a 1000-sim deployment renders its real numbers.
    """
    sim_root_abs = os.path.abspath(sim_root) if sim_root else ""
    current_time = time.time() if now is None else now

    if not force_refresh:
        with _cache_lock:
            entry = _cache.get(sim_root_abs)
            if entry is not None:
                cached_at, payload = entry
                if current_time - cached_at < CACHE_TTL_SECONDS:
                    return _deep_copy_envelope(payload)

    payload = _scan_distribution(sim_root_abs)

    with _cache_lock:
        _cache[sim_root_abs] = (current_time, _deep_copy_envelope(payload))

    return payload


def invalidate_cache(sim_root: Optional[str] = None) -> None:
    """Drop the cached distribution for ``sim_root`` (or every root when
    ``None``). Useful in tests so a freshly-written sim is reflected on
    the next ``build_distribution`` call without waiting out the TTL.
    """
    with _cache_lock:
        if sim_root is None:
            _cache.clear()
            return
        _cache.pop(os.path.abspath(sim_root), None)


def distribution_etag(payload: Dict[str, Any]) -> str:
    """Build a short ETag from the cheap inputs.

    ``total_analyzed`` + the year-month prefix of ``newest_completed_at``
    detects material change without re-reading the corpus — a new sim
    completing in a fresh month bumps both, a new sim completing in the
    current month bumps ``total_analyzed``, and a same-corpus reload
    keeps both identical. The returned value is a quoted ASCII string
    suitable for direct use as an ``ETag`` header.
    """
    total = int(payload.get("total_analyzed", 0) or 0)
    newest = payload.get("newest_completed_at") or ""
    # First 7 chars cover "YYYY-MM" — short enough to keep the ETag
    # compact, long enough that two distinct months don't collide.
    return f'"distribution-{total}-{str(newest)[:7]}"'


# ── Implementation details ────────────────────────────────────────────────


def _deep_copy_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the envelope — mutation-safe.

    The payload is a small fixed-shape dict; manual copying is cheaper
    than ``copy.deepcopy`` and keeps the cache hot path
    allocation-light.
    """
    return {
        "schema_version": payload.get("schema_version", "1"),
        "generated_at": payload.get("generated_at"),
        "total_analyzed": payload.get("total_analyzed", 0),
        "by_direction": dict(payload.get("by_direction") or {}),
        "by_confidence": dict(payload.get("by_confidence") or {}),
        "by_quality": dict(payload.get("by_quality") or {}),
        "by_round_count": dict(payload.get("by_round_count") or {}),
        "avg_confidence_pct": payload.get("avg_confidence_pct", 0.0),
        "avg_total_rounds": payload.get("avg_total_rounds", 0.0),
        "newest_completed_at": payload.get("newest_completed_at"),
    }


def _scan_distribution(sim_root: str) -> Dict[str, Any]:
    """One-shot scan of ``sim_root`` — no cache, no locking."""
    payload = _empty_envelope()
    if not sim_root or not os.path.isdir(sim_root):
        return payload

    direction_counts = _empty_direction_counts()
    confidence_counts = _empty_confidence_counts()
    quality_counts = _empty_quality_counts()
    round_counts = _empty_round_counts()

    total_analyzed = 0
    confidence_total = 0.0
    confidence_n = 0
    round_total = 0
    round_n = 0
    newest_completed_at: Optional[str] = None

    for _sim_id, sim_dir in _iter_sim_dirs(sim_root):
        state = _safe_load_json(os.path.join(sim_dir, "state.json"))
        if not isinstance(state, dict):
            continue
        if not bool(state.get("is_public", False)):
            continue
        if str(state.get("status", "")).lower() != "completed":
            continue

        total_analyzed += 1

        snapshots = _trajectory_snapshots(sim_dir)
        if snapshots is None:
            snapshots = []

        signal = _signal_for_sim(sim_dir, snapshots)
        if signal is not None:
            direction = (signal.get("direction") or "").lower()
            if direction in direction_counts:
                direction_counts[direction] += 1
            try:
                confidence_pct = float(signal.get("confidence_pct", 0.0))
            except (TypeError, ValueError):
                confidence_pct = 0.0
            confidence_counts[_confidence_bucket(confidence_pct)] += 1
            confidence_total += confidence_pct
            confidence_n += 1

        quality = _quality_health_bucket(sim_dir)
        if quality is not None:
            quality_counts[quality] += 1

        # ``total_rounds`` derives from the number of recorded
        # snapshots — same source ``peak_round.total_rounds`` uses, so
        # a sim's bucket here matches its per-sim peak-round count.
        total_rounds = sum(1 for snap in snapshots if isinstance(snap, dict))
        if total_rounds > 0:
            round_counts[_round_count_bucket(total_rounds)] += 1
            round_total += total_rounds
            round_n += 1

        # Newest completed sim — falls back to ``updated_at`` when
        # ``completed_at`` is absent (older sims written before the
        # field was added). Lexicographic compare on ISO-8601.
        completed_at = state.get("completed_at") or state.get("updated_at")
        if isinstance(completed_at, str) and completed_at:
            if newest_completed_at is None or completed_at > newest_completed_at:
                newest_completed_at = completed_at

    avg_confidence = round(confidence_total / confidence_n, 1) if confidence_n > 0 else 0.0
    avg_rounds = round(round_total / round_n, 1) if round_n > 0 else 0.0

    payload["total_analyzed"] = total_analyzed
    payload["by_direction"] = _bucket_with_pcts(direction_counts, total_analyzed)
    payload["by_confidence"] = _bucket_with_pcts(confidence_counts, total_analyzed)
    payload["by_quality"] = _bucket_with_pcts(quality_counts, total_analyzed)
    payload["by_round_count"] = _bucket_with_pcts(round_counts, total_analyzed)
    payload["avg_confidence_pct"] = avg_confidence
    payload["avg_total_rounds"] = avg_rounds
    payload["newest_completed_at"] = newest_completed_at

    return payload
