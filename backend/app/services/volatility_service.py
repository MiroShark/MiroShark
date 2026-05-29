"""Belief volatility analytics — quantifies how contested the path to
consensus was.

``signal.json`` answers *where the swarm landed* (direction + confidence).
``peak-round`` answers *when each stance peaked* and the single most
volatile round. Neither answers the question a quant operator asks third:
*"how turbulent was the path that got there?"* A high-volatility Bullish
result — where agents swung repeatedly before aligning — is a different
input than a low-volatility one where consensus formed in round three and
held. This module collapses the full trajectory into a single O(n)
turbulence summary:

  {
    "schema_version": "1",
    "simulation_id": "<id>",
    "mean_delta_pct": <float>,
    "std_dev_delta_pct": <float>,
    "max_delta_pct": <float>,
    "max_delta_round": <int>,
    "volatility_index": <float>,   # 0-100, normalized
    "trend": "converging" | "stable" | "contested",
    "total_rounds": <int>,
    "delta_count": <int>
  }

Design notes
------------

* **Pure derivation — same numbers as every other surface.** Reuses
  ``peak_round.load_trajectory_rounds`` so the per-round bullish /
  neutral / bearish percentages come from the exact same
  ``compute_stance_split`` (±0.2 threshold) that ``trajectory.csv``,
  ``chart.svg``, ``signal.json``, and ``peak-round`` use. A turbulence
  score derived from row 4 → row 5 matches a manual diff of those rows
  byte-for-byte; this surface adds *shape*, not new computation.
* **Delta definition matches peak-round's swing.** For each round after
  the first, the round-over-round delta is
  ``|Δbullish| + |Δneutral| + |Δbearish|`` — the same summed absolute
  belief movement ``peak-round`` already uses to pick its single
  ``most_volatile_round``. So ``max_delta_round`` here equals
  ``most_volatile_round`` from ``peak-round`` on the same trajectory by
  construction; the new value is the *distribution* of those deltas
  rather than just the maximum.
* **Volatility index normalization.** ``volatility_index =
  min(std_dev_delta_pct * 5, 100)`` — a std dev of 20 pp maps to 100.
  Chosen so a wholly flat trajectory lands at 0, a typical "mild
  oscillation" sim lands in the 20-40 band, and a single dramatic swing
  drives the index above 80. The 5× multiplier is a calibration knob;
  the formula is documented so external integrators can reproduce or
  rescale.
* **Trend classifier.** Three buckets:
    - ``"stable"`` when ``std_dev_delta_pct < 3.0`` (very tight cluster).
    - ``"converging"`` when the second half of the trajectory's deltas
      has strictly lower std dev than the first half (the swarm calmed
      down).
    - ``"contested"`` otherwise (high or rising volatility).
  A trajectory with fewer than 4 deltas cannot be split into halves, so
  it falls back to ``"stable"`` / ``"contested"`` based on the std dev
  threshold alone.
* **None for trajectories the metric can't describe.** Single-round and
  empty trajectories produce zero deltas, so ``compute_volatility``
  returns ``None`` (the route translates that to 404). A two-round
  trajectory has exactly one delta — ``std_dev_delta_pct`` is well
  defined (zero), and the metric ships.
* **Pure stdlib.** ``json`` + ``os`` + ``math`` for the std dev; no
  other imports. Same dependency posture as ``peak_round.py``.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from .peak_round import load_trajectory_rounds


# ``stable`` ↔ ``contested`` cutoff for the population std dev of
# round-over-round deltas. Below this, the trajectory is flat enough that
# the second-half-vs-first-half comparison wouldn't be meaningful.
_STABLE_STDDEV_THRESHOLD_PP = 3.0

# Multiplier turning the std dev (percentage points) into the 0-100
# volatility index. A std dev of 20 pp maps to 100; everything above is
# clamped.
_INDEX_MULTIPLIER = 5.0


def _round_delta(prev: dict[str, Any], curr: dict[str, Any]) -> float:
    """Summed absolute round-over-round belief swing.

    ``|Δbullish| + |Δneutral| + |Δbearish|`` — the exact swing
    ``peak_round.compute_peak_rounds`` already uses, so
    ``max_delta_round`` here matches ``most_volatile_round`` there on
    identical input.
    """
    return (
        abs(curr["bullish_pct"] - prev["bullish_pct"])
        + abs(curr["neutral_pct"] - prev["neutral_pct"])
        + abs(curr["bearish_pct"] - prev["bearish_pct"])
    )


def _population_stddev(values: list[float]) -> float:
    """Population std dev. ``0.0`` for an empty or singleton list.

    Population (not sample) so a single-delta trajectory reports
    ``0.0`` rather than raising on N-1=0. Matches NumPy's
    ``np.std(ddof=0)`` for the same input.
    """
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(variance)


def _classify_trend(deltas: list[float], std_dev: float) -> str:
    """Bucket the trajectory into ``stable`` / ``converging`` / ``contested``."""
    if std_dev < _STABLE_STDDEV_THRESHOLD_PP:
        return "stable"

    # ``converging`` requires at least 2 deltas per half so the std dev
    # comparison is well defined. With 2 or 3 total deltas there's no
    # honest half-vs-half claim — we report ``contested`` and let the
    # consumer interpret the index.
    if len(deltas) < 4:
        return "contested"

    midpoint = len(deltas) // 2
    first_half = deltas[:midpoint]
    second_half = deltas[midpoint:]

    first_half_std = _population_stddev(first_half)
    second_half_std = _population_stddev(second_half)

    if second_half_std < first_half_std:
        return "converging"
    return "contested"


def compute_volatility(rounds: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Collapse the per-round list into the volatility summary.

    ``rounds`` is the projection produced by
    ``peak_round.load_trajectory_rounds`` (one dict per round with
    ``round`` + the three ``*_pct`` fields). Returns ``None`` when no
    deltas can be computed (empty or single-round trajectory) so the
    route can emit 404.

    A two-round trajectory has exactly one delta — ``std_dev_delta_pct``
    is zero, the trend bucket is ``"stable"``, and the metric ships. The
    caller decides whether to surface that to end users; the metric
    itself stays well defined for any N ≥ 2.

    All percentage / index values are rounded to two decimal places — one
    more than the per-round CSV (which rounds to 1 dp) so a small swing
    between two 1-dp values doesn't disappear in ``max_delta_pct``.
    """
    if len(rounds) < 2:
        return None

    deltas: list[float] = []
    max_delta = 0.0
    max_delta_round = rounds[1]["round"]

    for prev, curr in zip(rounds, rounds[1:]):
        delta = _round_delta(prev, curr)
        deltas.append(delta)
        if delta > max_delta:
            max_delta = delta
            max_delta_round = curr["round"]

    delta_count = len(deltas)
    mean_delta = sum(deltas) / delta_count
    std_dev_delta = _population_stddev(deltas)

    # Normalized 0-100 turbulence index. A std dev of 20 pp maps to 100;
    # anything above clamps. The formula stays in the docstring so an
    # integrator can rescale to a different range without reverse-
    # engineering the multiplier.
    volatility_index = min(std_dev_delta * _INDEX_MULTIPLIER, 100.0)

    trend = _classify_trend(deltas, std_dev_delta)

    return {
        "schema_version": "1",
        "mean_delta_pct": round(mean_delta, 2),
        "std_dev_delta_pct": round(std_dev_delta, 2),
        "max_delta_pct": round(max_delta, 2),
        "max_delta_round": max_delta_round,
        "volatility_index": round(volatility_index, 2),
        "trend": trend,
        "total_rounds": len(rounds),
        "delta_count": delta_count,
    }


def compute_volatility_for_sim(sim_dir: str) -> Optional[dict[str, Any]]:
    """Load ``trajectory.json`` from ``sim_dir`` and compute the summary.

    Convenience wrapper for the route handler. Returns ``None`` when the
    trajectory file is missing, corrupt, or has fewer than two rounds.
    """
    rounds = load_trajectory_rounds(sim_dir)
    return compute_volatility(rounds)
