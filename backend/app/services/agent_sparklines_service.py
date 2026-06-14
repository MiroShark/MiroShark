"""Per-agent belief sparklines — the agent-level trajectory surface.

``chart.svg`` and the embed-summary draw the *aggregate* belief curve:
what the swarm concluded, round by round. ``peak-round`` collapses that
aggregate into inflection points. Neither exposes the layer underneath —
*each individual agent's* belief path. A researcher studying swarm
convergence ("did the financial-analyst agents align before the retail
ones? which agent anchored the consensus?") had no surface for it short
of parsing ``transcript.md`` by hand.

This module reads the same ``trajectory.json`` snapshots every other
surface shares and projects them the other way: instead of bucketing all
agents into one per-round percentage, it tracks **one scalar belief
position per agent per round**. The result is a list of per-agent
sparkline series the frontend renders as compact 40×15px SVG polylines,
each colored by the agent's final stance.

Design notes
------------

* **Same data, same threshold, transposed.** The per-agent scalar is the
  mean of that agent's per-topic ``belief_positions`` for the round —
  the exact ``_avg_position`` every other surface averages before
  bucketing. An agent whose final position is ``> +0.2`` is "bullish"
  here and "bullish" in the transcript; the ``±0.2`` threshold is shared
  so labels never drift across surfaces.
* **Names from the profile files.** ``belief_positions`` is keyed by
  integer ``user_id``; the human-readable name comes from
  ``reddit_profiles.json`` (then ``polymarket_profiles.json``), the same
  lookup the transcript renderer uses. An id with no profile row falls
  back to ``"Agent <id>"`` so a sparkline is never anonymous.
* **Deterministic order.** Agents are sorted most-bullish-first by final
  position, ties broken by ``agent_id`` ascending — so the rendered list
  reads top-to-bottom from the strongest bull to the strongest bear, and
  the same simulation always serializes in the same order.
* **``has_per_agent_data`` is a real signal.** It is ``true`` only when
  at least one agent has a 2-point trajectory — i.e. there are enough
  rounds to draw a line. A single-round simulation returns the agents
  (each a single dot) with the flag ``false`` so the frontend can show a
  "needs ≥2 rounds" note instead of a row of meaningless dots.
* **Pure stdlib.** ``json`` + ``os``. Same dependency posture as every
  other export module.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from ..utils.json_io import safe_load_json as _safe_load_json


TRAJECTORY_FILENAME = "trajectory.json"

# Same ±0.2 stance threshold the embed-summary, share card, transcript,
# trajectory.csv, chart.svg, and peak-round surfaces all use. A per-agent
# final position bucketed here MUST match how the same agent is labelled
# everywhere else, so the constant is pinned rather than configurable.
STANCE_THRESHOLD = 0.2

# Canonical stance colors — identical to chart_svg.py / badge_service.py
# so a "bullish" sparkline is the same green as a "bullish" chart line.
STANCE_COLORS: dict[str, str] = {
    "bullish": "#22c55e",
    "neutral": "#6b7280",
    "bearish": "#ef4444",
}


# ── On-disk readers ────────────────────────────────────────────────────────


def _load_profile_names(sim_dir: str) -> dict[int, str]:
    """``user_id → display name`` lookup for the simulation's agents.

    Reads ``reddit_profiles.json`` first (every run produces it), then
    ``polymarket_profiles.json`` as a secondary source. Mirrors the
    transcript renderer's lookup so an agent's name is identical across
    both surfaces. First write wins, so reddit_profiles takes precedence.
    """
    out: dict[int, str] = {}
    for filename in ("reddit_profiles.json", "polymarket_profiles.json"):
        data = _safe_load_json(os.path.join(sim_dir, filename))
        if not isinstance(data, list):
            continue
        for row in data:
            if not isinstance(row, dict):
                continue
            try:
                uid = int(row.get("user_id"))
            except (TypeError, ValueError):
                continue
            name = (row.get("name") or row.get("username") or "").strip()
            if not name:
                continue
            out.setdefault(uid, name)
    return out


# ── Stance helpers ─────────────────────────────────────────────────────────


def _avg_position(positions: Any) -> Optional[float]:
    """Mean of an agent's per-topic belief positions for one round.

    ``positions`` is the ``{topic: float}`` dict from one agent's entry in
    a snapshot's ``belief_positions``. Non-numeric / boolean values are
    filtered out; returns ``None`` when no usable value remains so the
    caller can skip the agent for that round.
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


def _classify_stance(value: float) -> str:
    """Bucket a continuous belief position into bullish/neutral/bearish.

    Mirrors the ±0.2 threshold every other surface uses so the per-agent
    label here matches the agent's label in the transcript and gallery.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "neutral"
    if v > STANCE_THRESHOLD:
        return "bullish"
    if v < -STANCE_THRESHOLD:
        return "bearish"
    return "neutral"


# ── Trajectory assembly ────────────────────────────────────────────────────


def load_agent_trajectories(sim_dir: str) -> list[dict[str, Any]]:
    """Project ``trajectory.json`` into a per-agent belief-position series.

    Walks every snapshot, computes each agent's scalar position
    (``_avg_position``) for the rounds in which it holds a belief, and
    groups those points by ``agent_id``. Each returned dict is::

        {"agent_id": <int>, "trajectory": [{"round": <int>,
                                            "position": <float>}, ...]}

    Points are sorted ascending by round so the sparkline draws
    left-to-right in time even if a runner ever writes snapshots out of
    order. Agents with no usable position in any round are omitted.
    Returns ``[]`` on missing / corrupt trajectory data so the route can
    emit a 404.
    """
    trajectory = _safe_load_json(os.path.join(sim_dir, TRAJECTORY_FILENAME))
    snapshots = trajectory.get("snapshots") if isinstance(trajectory, dict) else None
    if not isinstance(snapshots, list):
        return []

    # agent_id → list of (round, position) points.
    series: dict[int, list[dict[str, Any]]] = {}
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        try:
            round_num = int(snap.get("round_num"))
        except (TypeError, ValueError):
            continue
        positions = snap.get("belief_positions")
        if not isinstance(positions, dict):
            continue
        for agent_id_raw, agent_positions in positions.items():
            try:
                agent_id = int(agent_id_raw)
            except (TypeError, ValueError):
                continue
            avg = _avg_position(agent_positions)
            if avg is None:
                continue
            series.setdefault(agent_id, []).append(
                {"round": round_num, "position": round(avg, 3)}
            )

    out: list[dict[str, Any]] = []
    for agent_id, points in series.items():
        points.sort(key=lambda p: p["round"])
        out.append({"agent_id": agent_id, "trajectory": points})
    return out


def build_agent_sparklines(sim_dir: str) -> Optional[dict[str, Any]]:
    """Assemble the full sparklines payload for a simulation directory.

    Returns ``None`` when no agent holds a usable belief position in any
    round (the route translates that to a 404 — "no per-agent trajectory
    data yet"), distinguishing a not-ready sim from a private one (403).

    On success returns::

        {
          "schema_version": "1",
          "agent_count": <int>,
          "round_count": <int>,
          "has_per_agent_data": <bool>,
          "agents": [
            {"agent_id": <int>, "name": <str>, "final_stance": <str>,
             "final_position": <float>, "color": <hex>,
             "trajectory": [{"round": <int>, "position": <float>}, ...]},
            ...
          ]
        }

    Agents are ordered most-bullish-first by final position (ties broken
    by ``agent_id``). ``round_count`` is the number of distinct rounds
    that carry per-agent data; ``has_per_agent_data`` is ``true`` only
    when at least one agent has a 2-point trajectory (enough to draw a
    line).
    """
    trajectories = load_agent_trajectories(sim_dir)
    if not trajectories:
        return None

    names = _load_profile_names(sim_dir)

    agents: list[dict[str, Any]] = []
    all_rounds: set[int] = set()
    max_points = 0
    for entry in trajectories:
        agent_id = entry["agent_id"]
        points = entry["trajectory"]
        if not points:
            continue
        max_points = max(max_points, len(points))
        for p in points:
            all_rounds.add(p["round"])
        final_position = points[-1]["position"]
        stance = _classify_stance(final_position)
        agents.append(
            {
                "agent_id": agent_id,
                "name": names.get(agent_id, f"Agent {agent_id}"),
                "final_stance": stance,
                "final_position": final_position,
                "color": STANCE_COLORS[stance],
                "trajectory": points,
            }
        )

    if not agents:
        return None

    # Most-bullish-first; ties broken by agent_id so the order is stable.
    agents.sort(key=lambda a: (-a["final_position"], a["agent_id"]))

    return {
        "schema_version": "1",
        "agent_count": len(agents),
        "round_count": len(all_rounds),
        "has_per_agent_data": max_points >= 2,
        "agents": agents,
    }
