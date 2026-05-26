"""Peak-round belief analytics — machine-readable inflection points.

``trajectory.csv`` (PR-era fifth surface) hands an analyst the raw
per-round belief split; ``chart.svg`` draws the same numbers as a vector
line. Neither answers the two questions a quant operator actually asks
first — *"which round did bullish peak?"* and *"which round had the
biggest swing?"* — without parsing every row. This module collapses the
whole trajectory into a single O(n) summary:

  {
    "schema_version": "1",
    "simulation_id": "<id>",
    "bullish":  {"round": <int>, "pct": <float>},
    "neutral":  {"round": <int>, "pct": <float>},
    "bearish":  {"round": <int>, "pct": <float>},
    "most_volatile_round": <int>,
    "max_swing_pct": <float>,
    "total_rounds": <int>
  }

Design notes
------------

* **Pure derivation — same numbers as every other surface.** The
  per-round bullish/neutral/bearish percentages come from
  ``trajectory_export.compute_stance_split`` — the exact function
  ``trajectory.csv`` uses, with the same ±0.2 stance threshold. A
  "bullish peaked at 71% on round 4" here matches row 4 of the CSV
  byte-for-byte; this surface adds *shape*, not new computation.
* **First-occurrence peaks.** When two rounds tie for a stance's
  maximum, the *earliest* round wins (strict ``>`` comparison). This
  answers "when did bullish *first* reach its high" deterministically,
  so a consumer can predict the output on a flat-topped trajectory.
* **Volatility = summed absolute round-over-round delta.** For each
  round after the first, ``|Δbullish| + |Δneutral| + |Δbearish|``
  measures how much the whole distribution moved. The first round has
  no predecessor, so its delta is zero. ``most_volatile_round`` is the
  earliest round carrying the maximum swing; a fully flat (or
  single-round) trajectory reports the first round with a ``0.0`` swing.
* **Pure stdlib.** ``json`` + ``os`` for the on-disk read; no other
  imports. Same dependency posture as every other export module.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from .trajectory_export import compute_stance_split


TRAJECTORY_FILENAME = "trajectory.json"

# The three stance keys, in the canonical order used across every
# surface. Iterating this rather than hard-coding three blocks keeps the
# peak scan and the response shape in lock-step.
_STANCES = ("bullish", "neutral", "bearish")


def _safe_load_trajectory(sim_dir: str) -> Optional[dict]:
    """Read ``trajectory.json`` from ``sim_dir``; ``None`` on any failure.

    Never raises — a missing or corrupt trajectory file must resolve to
    "no data yet" (the route translates that to a 404), not a 500.
    """
    if not sim_dir:
        return None
    path = os.path.join(sim_dir, TRAJECTORY_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_trajectory_rounds(sim_dir: str) -> list[dict[str, Any]]:
    """Project ``trajectory.json`` into the per-round stance-split list.

    Returns one dict per usable snapshot::

        {"round": <int>, "bullish_pct": <float>,
         "neutral_pct": <float>, "bearish_pct": <float>}

    Snapshots without an integer ``round_num`` are skipped (mid-write
    or malformed rows). The list is sorted ascending by round so the
    volatility scan compares true neighbours even if a runner ever
    writes snapshots out of order. Returns ``[]`` on missing / corrupt
    trajectory data.
    """
    trajectory = _safe_load_trajectory(sim_dir)
    if not trajectory:
        return []

    snapshots = trajectory.get("snapshots")
    if not isinstance(snapshots, list):
        return []

    rounds: list[dict[str, Any]] = []
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        try:
            round_num = int(snap.get("round_num"))
        except (TypeError, ValueError):
            continue
        split = compute_stance_split(snap.get("belief_positions"))
        rounds.append(
            {
                "round": round_num,
                "bullish_pct": split["bullish"],
                "neutral_pct": split["neutral"],
                "bearish_pct": split["bearish"],
            }
        )

    rounds.sort(key=lambda r: r["round"])
    return rounds


def compute_peak_rounds(rounds: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Collapse the per-round list into the peak-round summary.

    Returns ``None`` for empty input so the route handler can emit a
    404 ("no trajectory data yet") rather than a misleading all-zero
    payload. One O(n) pass tracks, per stance, the earliest round at
    which it reached its maximum, and the round carrying the largest
    summed absolute round-over-round delta.

    All percentage values are rounded to two decimal places — one more
    than the per-round CSV (which rounds to 1 dp) so a small swing
    between two 1-dp values isn't lost to rounding in ``max_swing_pct``.
    """
    if not rounds:
        return None

    first = rounds[0]
    # Seed each stance's peak with the first round so a single-round
    # trajectory reports every peak at that round.
    peaks: dict[str, dict[str, Any]] = {
        stance: {"round": first["round"], "pct": first[f"{stance}_pct"]}
        for stance in _STANCES
    }

    most_volatile_round = first["round"]
    max_swing = 0.0
    prev: Optional[dict[str, Any]] = None

    for current in rounds:
        for stance in _STANCES:
            pct = current[f"{stance}_pct"]
            if pct > peaks[stance]["pct"]:
                peaks[stance] = {"round": current["round"], "pct": pct}

        if prev is not None:
            swing = (
                abs(current["bullish_pct"] - prev["bullish_pct"])
                + abs(current["neutral_pct"] - prev["neutral_pct"])
                + abs(current["bearish_pct"] - prev["bearish_pct"])
            )
            if swing > max_swing:
                max_swing = swing
                most_volatile_round = current["round"]

        prev = current

    return {
        "schema_version": "1",
        "bullish": {
            "round": peaks["bullish"]["round"],
            "pct": round(peaks["bullish"]["pct"], 2),
        },
        "neutral": {
            "round": peaks["neutral"]["round"],
            "pct": round(peaks["neutral"]["pct"], 2),
        },
        "bearish": {
            "round": peaks["bearish"]["round"],
            "pct": round(peaks["bearish"]["pct"], 2),
        },
        "most_volatile_round": most_volatile_round,
        "max_swing_pct": round(max_swing, 2),
        "total_rounds": len(rounds),
    }
