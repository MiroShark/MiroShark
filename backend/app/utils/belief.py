"""Shared belief-position helpers."""

from typing import Any, List, Optional, Tuple

# Per-agent mean stance above +0.2 reads as bullish, below -0.2 as bearish,
# in between as neutral. Every belief surface uses this same cutoff.
STANCE_THRESHOLD = 0.2


def bucket_snapshots(
    snapshots: Any,
) -> Tuple[Optional[Tuple[float, float, float]], int]:
    """Reduce trajectory snapshots to a final bullish/neutral/bearish split.

    For each snapshot, average every agent's per-topic belief positions, then
    bucket those means at ±:data:`STANCE_THRESHOLD`. Returns the distribution of
    the LAST snapshot with any parseable stance (percentages rounded to one
    decimal) plus ``counted_rounds`` (how many snapshots contributed); returns
    ``(None, 0)`` when none do. Non-dict snapshots, empty/non-dict belief maps,
    and per-agent maps that aren't summable are skipped (mid-write tolerance).
    """
    final: Optional[Tuple[float, float, float]] = None
    counted_rounds = 0
    if not isinstance(snapshots, list):
        return final, counted_rounds
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        positions = snap.get("belief_positions") or {}
        if not isinstance(positions, dict) or not positions:
            continue
        stances: List[float] = []
        for p in positions.values():
            if isinstance(p, dict) and p:
                try:
                    stances.append(sum(p.values()) / len(p))
                except (TypeError, ZeroDivisionError):
                    continue
        if not stances:
            continue
        total = len(stances)
        nb = sum(1 for s in stances if s > STANCE_THRESHOLD)
        nbe = sum(1 for s in stances if s < -STANCE_THRESHOLD)
        nn = total - nb - nbe
        final = (
            round(nb / total * 100, 1),
            round(nn / total * 100, 1),
            round(nbe / total * 100, 1),
        )
        counted_rounds += 1
    return final, counted_rounds


def avg_position(positions: Any) -> Optional[float]:
    """Mean of an agent's per-topic belief positions for one round.

    ``positions`` is the ``{topic: float}`` dict from one agent's entry in a
    snapshot's ``belief_positions``. Non-numeric and boolean values are
    filtered out (a snapshot can be mid-write, and ``bool`` is a numeric
    subtype we never want averaged in); returns ``None`` when no usable value
    remains so the caller can skip that agent for the round.
    """
    if not isinstance(positions, dict) or not positions:
        return None
    values = [
        float(v)
        for v in positions.values()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    if not values:
        return None
    return sum(values) / len(values)
