"""Shared readers over the on-disk simulation corpus.

Every platform-wide aggregate — activity feed, batch status, platform /
project stats, outcome distribution, platform status — walks the same
``WONDERWALL_SIMULATION_DATA_DIR`` tree and projects the same artifacts
(``trajectory.json``, ``quality.json``, ``surface-stats.json``,
``state.json``) into its own shape. The walk and those projections must
agree across surfaces: a sim counted by one aggregate has to be counted
by the others, and a direction reported by one has to match the
direction reported by the rest.

These helpers were previously copy-pasted byte-for-byte into each of
those modules. They now live here so the corpus scan and its derived
values have one definition.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional, Tuple

from ..services import signal_service
from ..services.surface_stats import SURFACE_STATS_FILENAME, SURFACE_KEYS
from .belief import bucket_snapshots
from .json_io import safe_load_json


def iter_sim_dirs(sim_root: str) -> Iterable[Tuple[str, str]]:
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


def final_belief_from_trajectory(sim_dir: str) -> Optional[Tuple[float, float, float]]:
    """Return ``(bullish_pct, neutral_pct, bearish_pct)`` for the final
    round in ``trajectory.json``, or ``None`` if the trajectory is
    missing / empty / unparsable.

    Same ±0.2 stance threshold and one-decimal rounding the per-sim
    signal.json and badge.svg surfaces use, so an aggregate never
    disagrees with the individual sims it summarises.
    """
    traj = safe_load_json(os.path.join(sim_dir, "trajectory.json"))
    if not isinstance(traj, dict):
        return None
    snapshots = traj.get("snapshots")
    if not isinstance(snapshots, list):
        return None

    final, _ = bucket_snapshots(snapshots)
    return final


def signal_for_sim(sim_dir: str) -> Optional[Dict[str, Any]]:
    """Derive the same signal payload ``signal_service.compute_signal``
    would emit for this sim, or ``None`` if the trajectory is empty.

    Reads ``quality.json`` for the health field — falls back to
    ``"N/A"`` when missing so ``risk_tier`` still resolves.
    """
    final = final_belief_from_trajectory(sim_dir)
    if final is None:
        return None
    bullish, neutral, bearish = final

    quality_path = os.path.join(sim_dir, "quality.json")
    quality_doc = safe_load_json(quality_path) or {}
    health = quality_doc.get("health") if isinstance(quality_doc, dict) else None

    summary = {
        "belief": {
            "final": {"bullish": bullish, "neutral": neutral, "bearish": bearish},
        },
        "quality": {"health": health} if health else {},
    }
    return signal_service.compute_signal(summary)


def surface_views_for_sim(sim_dir: str) -> int:
    """Sum every recognised key in this sim's ``surface-stats.json``.

    Ignores ``total`` (it's a synthetic field added by
    ``surface_stats.read_surface_stats``, not persisted to disk) and any
    unknown key — same posture as ``surface_stats._load_raw``.
    """
    payload = safe_load_json(os.path.join(sim_dir, SURFACE_STATS_FILENAME))
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


def empty_distribution() -> Dict[str, Any]:
    return {
        "bullish": 0,
        "neutral": 0,
        "bearish": 0,
        "bullish_pct": 0.0,
        "neutral_pct": 0.0,
        "bearish_pct": 0.0,
    }


def normalise_completed_at(state: Dict[str, Any]) -> Optional[str]:
    """Pick the completion timestamp for a completed sim.

    ``state.json.updated_at`` is what ``simulation_runner`` writes on
    the terminal-state transition. Falls back to ``created_at`` for
    older sims written before the completion-timestamp field was
    instrumented so a completed-but-undated sim still appears.
    """
    for key in ("updated_at", "created_at"):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None
