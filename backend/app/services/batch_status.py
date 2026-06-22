"""Multi-sim status lookup — *"give me the current state of these N sims in one call"*.

The publish-gated per-sim surfaces in this codebase answer the question
*"what is sim X doing right now?"* one sim at a time. An integrator
running parallel batches — AntFleet's benchmark pipeline, Capacitr's
polling loop, anyone shipping the ecosystem-table pattern — has to fire
N HTTP requests to poll N sims, which scales poorly the moment the
batch grows past a handful.

``build_batch_status`` collapses that to a single call: it accepts a
list of sim ids (capped at :data:`MAX_BATCH_SIZE`) and returns one
entry per id with the minimum useful state envelope — status, current
round, and (for completed public sims) the same direction +
confidence + quality fields the per-sim ``signal.json`` would emit.
The route handler at ``POST /api/simulation/batch-status`` reads from
here.

Design notes
------------

* **One round-trip per N sims, not N.** The whole reason this surface
  exists is to reduce the request count an integrator needs to poll a
  batch run. The 20-id cap (also documented in
  :data:`MAX_BATCH_SIZE`) is set by the route handler so a runaway
  client can't ask the backend to do 1000 sim reads in one call; the
  service itself accepts any list length the caller passes.

* **Publish gate applied per id, not per batch.** A private sim in
  the batch returns ``found: false`` rather than leaking its fields.
  An unknown sim id (typo, never-existed) returns the same
  ``found: false`` envelope — the integrator cannot distinguish
  "private" from "doesn't exist" from "deleted" by reading the
  response. This is deliberate: the surface is unauthenticated, and
  the existence-of-a-private-sim signal is itself a leak.

* **Status semantics match the rest of the platform.** A sim is
  ``"running"`` when ``state.json.status`` is the string ``"running"``
  (case-insensitive, matching ``platform_status`` and
  ``platform_stats``). ``"completed"`` is the only terminal value
  that earns analytics fields — ``"failed"`` / ``"cancelled"`` /
  any other terminal label returns the bare ``status`` + ``null``
  analytics. A consumer can render the failed badge without the
  signal pretending the sim has a direction.

* **Signal fields are derived, not stored.** ``direction``,
  ``confidence_pct``, ``quality_health`` come from
  :mod:`signal_service.compute_signal` over the same final-round
  belief split the per-sim ``signal.json`` surface uses. Helpers
  duplicate the trajectory-walk pattern from ``platform_stats`` /
  ``project_stats`` byte-for-byte so a sim's batch entry matches its
  per-sim signal entry for the same simulation.

* **``total_rounds`` is the trajectory length.** A completed sim's
  ``total_rounds`` is ``len(trajectory.snapshots)`` — the same value
  ``peak_round.compute_peak_round`` reports. For a running sim
  ``total_rounds`` is ``null`` (the final length is unknown until
  the sim terminates); ``current_round`` is what the state.json
  carries during the run.

* **No cache.** Each request reads the relevant sim folders
  directly. Per-id reads are cheap (a state.json + at most a
  trajectory.json + quality.json), and the route handler caps the
  call at 20 ids, so the worst case is 60 small JSON loads — well
  inside a single tick. An in-process cache would also make the
  result stale, which defeats the polling use case the surface is
  built for. ``Cache-Control: no-store`` is set at the route layer
  for the same reason.

* **Order preserved.** ``results`` is returned in the order the
  caller supplied ``sim_ids``. A duplicate id in the request emits a
  duplicate entry in the response — the service treats the input as
  a list, not a set, so a caller polling the same id twice in the
  same batch gets the same answer twice and can correlate by index.

* **Stdlib only.** ``os`` + ``json`` + ``re``. No new dependencies —
  keeps the platform on its 40-PR zero-new-deps streak. Reuses
  :mod:`signal_service` (already a dep of platform_stats /
  project_stats / per-sim signal.json) so the math is one place.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from . import signal_service
from ..utils.json_io import safe_load_json as _safe_load_json
from ..utils.belief import bucket_snapshots


# ── Configuration ────────────────────────────────────────────────────────


SCHEMA_VERSION = "1"


# Hard cap on the number of sim ids the route handler accepts in one
# call. 20 is loose enough that a researcher polling a benchmark batch
# never hits it in practice, tight enough that a runaway client cannot
# trigger a 1 000-sim scan in one round-trip. Exposed as a module
# constant so the route handler and the unit tests reference one number.
MAX_BATCH_SIZE = 20


# Matches the shape ``backend/app/utils/validation.validate_simulation_id``
# enforces — alphanumeric + hyphen + underscore + dot, no slashes, no
# parent-dir refs. Re-implemented here (rather than imported) so the
# service module stays a pure-data dep and can be unit-tested without
# importing the Flask app tree.
_SAFE_SIM_ID = re.compile(r"^[A-Za-z0-9_\-\.]{1,128}$")


# ── Internal helpers ──────────────────────────────────────────────────────


def _final_belief_from_trajectory(
    sim_dir: str,
) -> Optional[Tuple[float, float, float, int]]:
    """Return ``(bullish_pct, neutral_pct, bearish_pct, total_rounds)``
    for the final round of ``trajectory.json``, or ``None`` if the
    trajectory is missing / empty / unparsable.

    Mirrors ``platform_stats._final_belief_from_trajectory`` /
    ``project_stats._final_belief_from_trajectory`` exactly — same
    ±0.2 stance threshold, same one-decimal rounding — so a sim's
    batch-status entry matches its platform / project / per-sim
    contribution byte-for-byte. ``total_rounds`` is appended so the
    caller doesn't have to walk the snapshots a second time.
    """
    traj = _safe_load_json(os.path.join(sim_dir, "trajectory.json"))
    if not isinstance(traj, dict):
        return None
    snapshots = traj.get("snapshots")
    if not isinstance(snapshots, list):
        return None

    final, counted_rounds = bucket_snapshots(snapshots)
    if final is None:
        return None
    return (final[0], final[1], final[2], counted_rounds)


def _signal_for_sim(
    sim_dir: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    """Return ``(signal_payload, total_rounds)`` for one sim.

    The signal payload is the same dict :mod:`signal_service.compute_signal`
    emits for the per-sim ``/signal.json`` surface — ``direction``,
    ``confidence_pct``, ``risk_tier``, the three component percentages,
    ``quality_health``, ``signal_generated_at`` — or ``None`` when the
    sim has no recorded rounds yet. ``total_rounds`` is the trajectory
    snapshot count, or ``None`` when the trajectory is missing.
    """
    belief = _final_belief_from_trajectory(sim_dir)
    if belief is None:
        return None, None
    bullish, neutral, bearish, total_rounds = belief

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


def _empty_entry(sim_id: str) -> Dict[str, Any]:
    """Return the ``found: false`` envelope.

    The same shape is emitted for an unknown id and for a private id —
    a caller cannot distinguish the two by reading the response.
    """
    return {
        "sim_id": sim_id,
        "found": False,
        "status": None,
        "current_round": None,
        "total_rounds": None,
        "direction": None,
        "confidence_pct": None,
        "quality_health": None,
        "completed_at": None,
    }


def _normalise_completed_at(state: Dict[str, Any]) -> Optional[str]:
    """Pick the completion timestamp for a completed sim.

    ``state.json.updated_at`` is what ``simulation_runner`` writes on
    the terminal-state transition. Falls back to ``created_at`` when
    ``updated_at`` is missing (older sims written before completion
    timestamps were instrumented) so a completed-but-undated sim still
    registers a heartbeat.
    """
    for key in ("updated_at", "created_at"):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _coerce_int_or_none(value: Any) -> Optional[int]:
    """Coerce ``value`` to ``int``, or ``None`` on failure.

    Used for ``current_round`` reads — a malformed value in state.json
    should not tank the whole batch entry. ``bool`` is rejected
    explicitly so a stray ``True`` doesn't masquerade as ``1``.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ── Public API ────────────────────────────────────────────────────────────


def is_valid_sim_id(sim_id: Any) -> bool:
    """Return ``True`` iff ``sim_id`` is a non-empty string matching
    :data:`_SAFE_SIM_ID` and free of path-traversal sequences.

    Used at the API boundary so a malformed input never reaches the
    scan loop. Matches ``backend/app/utils/validation.validate_simulation_id``
    semantics: alphanumeric + hyphen + underscore + dot, no slashes,
    no ``..``.
    """
    if not isinstance(sim_id, str):
        return False
    if not sim_id:
        return False
    if ".." in sim_id:
        return False
    if "/" in sim_id or "\\" in sim_id:
        return False
    return bool(_SAFE_SIM_ID.match(sim_id))


def build_batch_status(
    sim_root: str,
    sim_ids: List[str],
) -> Dict[str, Any]:
    """Return the batch-status envelope for ``sim_ids``.

    Result shape::

        {
          "schema_version": "1",
          "count": <int>,
          "results": [
            {
              "sim_id": <str>,
              "found": <bool>,
              "status": <str | null>,
              "current_round": <int | null>,
              "total_rounds": <int | null>,
              "direction": <"Bullish" | "Neutral" | "Bearish" | null>,
              "confidence_pct": <float | null>,
              "quality_health": <str | null>,
              "completed_at": <ISO-8601 str | null>
            },
            ...
          ]
        }

    ``results`` preserves the input order; a duplicate id in
    ``sim_ids`` produces a duplicate entry. ``count`` equals
    ``len(sim_ids)`` — the caller can assert the loop ran to
    completion without scanning the array.

    The function trusts that the caller has already validated each id
    against :func:`is_valid_sim_id`. The route handler returns 400
    before reaching this point if any id is malformed, so the service
    never needs to defend against path-traversal at the disk read.
    """
    results: List[Dict[str, Any]] = []
    sim_root_abs = sim_root or ""

    for sim_id in sim_ids:
        if not sim_root_abs or not os.path.isdir(sim_root_abs):
            # No sim root configured / mounted — every id degrades to
            # found: false. Same shape as an unknown id; a fresh deploy
            # probing itself with batch-status still returns a
            # well-formed envelope rather than 500-ing.
            results.append(_empty_entry(sim_id))
            continue

        sim_dir = os.path.join(sim_root_abs, sim_id)
        if not os.path.isdir(sim_dir):
            results.append(_empty_entry(sim_id))
            continue

        state = _safe_load_json(os.path.join(sim_dir, "state.json"))
        if not isinstance(state, dict):
            results.append(_empty_entry(sim_id))
            continue

        # Private sims fall through to the same shape as an unknown id —
        # a caller cannot distinguish "private" from "doesn't exist".
        if not bool(state.get("is_public", False)):
            results.append(_empty_entry(sim_id))
            continue

        status_value = str(state.get("status", "") or "").lower() or None
        current_round = _coerce_int_or_none(state.get("current_round"))

        entry: Dict[str, Any] = {
            "sim_id": sim_id,
            "found": True,
            "status": status_value,
            "current_round": current_round,
            "total_rounds": None,
            "direction": None,
            "confidence_pct": None,
            "quality_health": None,
            "completed_at": None,
        }

        # Only completed sims earn the analytics fields. A failed or
        # cancelled sim returns the bare status + null analytics so the
        # consumer can render the right badge without the response
        # pretending the run produced a signal.
        if status_value == "completed":
            entry["completed_at"] = _normalise_completed_at(state)
            signal, total_rounds = _signal_for_sim(sim_dir)
            if signal is not None:
                entry["direction"] = signal.get("direction")
                entry["confidence_pct"] = signal.get("confidence_pct")
                entry["quality_health"] = signal.get("quality_health")
                entry["total_rounds"] = total_rounds
            else:
                # Completed without a usable trajectory — still report
                # the completed_at heartbeat, but leave the analytics
                # null so a consumer doesn't act on absent data.
                entry["total_rounds"] = total_rounds

        results.append(entry)

    return {
        "schema_version": SCHEMA_VERSION,
        "count": len(sim_ids),
        "results": results,
    }
