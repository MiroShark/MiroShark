"""Shared belief-position helpers."""

from typing import Any, Optional


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
