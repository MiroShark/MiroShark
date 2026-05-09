"""Simulation lineage navigator — fork / counterfactual graph traversal.

PR #75's reproducibility config export persisted ``parent_simulation_id``
+ ``lineage.kind`` (original / fork / counterfactual) + counterfactual
trigger metadata in every ``reproduce.json``. The data exists on disk —
but the lineage was *one-directional*: a child sim knows its parent,
the parent has no visibility into the children it spawned. A researcher
who ran a base scenario then triggered three counterfactual branches
had to remember each child sim id; the SPA could not walk from a parent
to "the three branches that diverged from this one at round 12".

``GET /api/simulation/<id>/lineage`` closes that gap. The endpoint
reads the requested simulation's ``state.json`` for its own parent
pointer + optional ``counterfactual_injection.json`` for its own kind,
then scans the public sim corpus for *children* — public sims whose
``parent_simulation_id`` matches the requested id. The result is a
compact graph slice the EmbedDialog renders as

    🌳 Lineage
    ↑ Parent — sim_abc12345 — "What if Aave's reserve factor doubled..."
    ↓ Children — 3 branches
       🪐 sim_def67890 — fork
       🔀 sim_ghi09876 — counterfactual at round 12 (ceo_resigns)
       🔀 sim_jkl54321 — counterfactual at round 18 (whale_withdraws)

so an operator (or a viewer who landed on a tweeted ``/share/<id>``
link) can navigate the fork/counterfactual network as a graph rather
than a flat list of sim ids.

Design notes
------------

* **Pure stdlib.** ``json`` + ``os``. No new dependencies; reuses
  ``repro_export``'s safe coercion helpers and the same on-disk
  artifacts (``state.json`` for the parent pointer,
  ``counterfactual_injection.json`` for kind + trigger metadata,
  ``simulation_config.json`` for the scenario preview).

* **Read-only.** The service never writes. A child whose
  ``state.json`` is mid-rewrite at scan time degrades to "skipped" —
  the lineage view never crashes a load.

* **Public-only children.** Only public children appear in the response.
  A private fork of a public sim is invisible from the parent's
  lineage view. Operators forking privately for in-progress work are
  not surprised to see those branches leak into a tweeted parent.

* **Bounded.** ``MAX_CHILDREN`` caps the response. The vast majority of
  sims have zero or a handful of children; ten branches across a single
  parent sim is already an extreme case. The cap is defense-in-depth
  against a (future) bulk-fork operator pattern.

* **Defense-in-depth.** Every disk read is wrapped — corrupt JSON,
  missing files, mid-write state never raise. The endpoint is part of
  the public discovery surface; a single bad artifact must not blank
  out the navigator.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Optional


# Cap the children list at 50 entries so the response never balloons
# even on a sim that someone pathologically forked dozens of times.
# 99% of sims have zero or one children; ten is already an outlier.
MAX_CHILDREN: int = 50

# Truncate the scenario preview that travels with parent + child entries
# so the EmbedDialog row stays one line on common viewports. 80 chars
# matches the YAML front-matter shape the transcript export uses.
SCENARIO_PREVIEW_CHARS: int = 80


def _safe_str(value: Any) -> str:
    """Coerce ``value`` to a stripped string; ``None`` ⇒ empty."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value).strip()
    except Exception:
        return ""


def _safe_int(value: Any, default: int = 0) -> int:
    """Coerce ``value`` to a non-negative int with a default fallback."""
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, ivalue)


def _truncate_scenario(text: str, limit: int = SCENARIO_PREVIEW_CHARS) -> str:
    """Truncate ``text`` with a trailing ellipsis when it exceeds ``limit``."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def _load_state(sim_dir: str) -> Optional[Dict[str, Any]]:
    """Load ``<sim_dir>/state.json`` defensively. Missing/corrupt → ``None``."""
    if not sim_dir:
        return None
    state_path = os.path.join(sim_dir, "state.json")
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _load_config_scenario(sim_dir: str) -> str:
    """Read ``simulation_requirement`` from ``simulation_config.json``.

    The scenario lives in the LLM-generated config file. Falls back to
    the empty string when missing or corrupt; the caller is expected to
    fall back further to the state-level ``simulation_requirement``
    when older sims wrote the requirement onto state.
    """
    if not sim_dir:
        return ""
    cfg_path = os.path.join(sim_dir, "simulation_config.json")
    if not os.path.exists(cfg_path):
        return ""
    try:
        with open(cfg_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    return _safe_str(data.get("simulation_requirement"))


def _scenario_for(sim_dir: str, state: Optional[Dict[str, Any]]) -> str:
    """Compose the scenario preview from config + state fallbacks."""
    scenario = _load_config_scenario(sim_dir)
    if scenario:
        return _truncate_scenario(scenario)
    if isinstance(state, dict):
        legacy = _safe_str(state.get("simulation_requirement"))
        if legacy:
            return _truncate_scenario(legacy)
    return ""


def _load_counterfactual(sim_dir: str) -> Optional[Dict[str, Any]]:
    """Load ``<sim_dir>/counterfactual_injection.json`` if present.

    Returns the parsed dict on success, ``None`` when the file is absent
    or unparseable. Mirrors ``repro_export._build_lineage`` so the
    counterfactual marker is consistent across both surfaces.
    """
    if not sim_dir:
        return None
    cf_path = os.path.join(sim_dir, "counterfactual_injection.json")
    if not os.path.exists(cf_path):
        return None
    try:
        with open(cf_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _kind_for(state: Optional[Dict[str, Any]], cf: Optional[Dict[str, Any]]) -> str:
    """Discriminator: ``original`` / ``fork`` / ``counterfactual``."""
    parent = state.get("parent_simulation_id") if isinstance(state, dict) else None
    if not parent:
        return "original"
    return "counterfactual" if cf else "fork"


def _build_counterfactual_marker(
    cf: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Compact counterfactual sub-object travelling with a child entry.

    ``trigger_round`` + ``label`` are the headline values; the badge
    renders "🔀 Counterfactual at round 12 (ceo_resigns)" without a
    second fetch. ``None`` for forks + originals.
    """
    if not isinstance(cf, dict):
        return None
    return {
        "trigger_round": _safe_int(cf.get("trigger_round", 0)),
        "label": _safe_str(cf.get("label")),
    }


def _entry_for_sim(
    sim_id: str,
    sim_dir: str,
    state: Optional[Dict[str, Any]],
    *,
    include_kind: bool = False,
) -> Dict[str, Any]:
    """Compose a child / parent entry payload from on-disk state.

    Keys:

    * ``simulation_id`` — echoed.
    * ``scenario_preview`` — truncated to ``SCENARIO_PREVIEW_CHARS``.
    * ``created_at`` — best-effort UTC stamp from state.json.
    * ``is_public`` — visibility flag (children are always public; the
      parent may be private and renders without scenario text in that
      case).
    * ``kind`` — only on child entries (``include_kind=True``); the
      parent's own kind is on the top-level response.
    * ``counterfactual`` — present when ``kind == "counterfactual"``,
      carrying ``{trigger_round, label}``.
    """
    cf = _load_counterfactual(sim_dir)
    is_public = bool(state.get("is_public")) if isinstance(state, dict) else False
    payload: Dict[str, Any] = {
        "simulation_id": sim_id,
        "scenario_preview": _scenario_for(sim_dir, state) if is_public else "",
        "created_at": _safe_str(state.get("created_at")) if isinstance(state, dict) else "",
        "is_public": is_public,
    }
    if include_kind:
        kind = _kind_for(state, cf)
        payload["kind"] = kind
        marker = _build_counterfactual_marker(cf)
        if kind == "counterfactual" and marker is not None:
            payload["counterfactual"] = marker
        else:
            payload["counterfactual"] = None
    return payload


def _iter_candidate_sim_ids(data_dir: str) -> Iterable[str]:
    """Yield candidate simulation directory names from ``data_dir``.

    Skips dotfiles + non-directories. Never raises — a missing data dir
    yields nothing.
    """
    if not data_dir or not os.path.isdir(data_dir):
        return []
    try:
        names = os.listdir(data_dir)
    except OSError:
        return []
    out: List[str] = []
    for name in names:
        if not name or name.startswith("."):
            continue
        full = os.path.join(data_dir, name)
        if not os.path.isdir(full):
            continue
        out.append(name)
    return out


def find_children(
    parent_id: str,
    data_dir: str,
    *,
    max_children: int = MAX_CHILDREN,
) -> List[Dict[str, Any]]:
    """Return the public children whose ``parent_simulation_id`` matches.

    Walks ``data_dir`` once, loading each sim's state.json. A sim is a
    child when its ``parent_simulation_id`` equals ``parent_id`` *and*
    its ``is_public`` flag is true. Private children are silently
    skipped — operators forking privately for in-progress work do not
    leak those branches into a tweeted parent's lineage view.

    Returns up to ``max_children`` entries sorted by ``created_at``
    ascending (oldest fork first — the natural narrative order). Each
    entry carries ``simulation_id``, ``scenario_preview``,
    ``created_at``, ``is_public=True``, ``kind`` (``fork`` /
    ``counterfactual``), and an optional ``counterfactual`` marker.
    """
    if not parent_id:
        return []

    matches: List[Dict[str, Any]] = []
    for sim_id in _iter_candidate_sim_ids(data_dir):
        if sim_id == parent_id:
            continue
        sim_dir = os.path.join(data_dir, sim_id)
        state = _load_state(sim_dir)
        if not isinstance(state, dict):
            continue
        if _safe_str(state.get("parent_simulation_id")) != parent_id:
            continue
        if not bool(state.get("is_public")):
            continue
        matches.append(_entry_for_sim(sim_id, sim_dir, state, include_kind=True))

    # Oldest-first reads as the lineage's narrative order: the parent
    # was forked into branch A first, then branch B, etc. created_at
    # may be missing on hand-edited fixtures — those sort to the front
    # via the empty string, which is fine.
    matches.sort(key=lambda e: (e.get("created_at") or "", e.get("simulation_id") or ""))
    return matches[: max(0, int(max_children))]


def build_lineage_payload(
    simulation_id: str,
    data_dir: str,
    *,
    max_children: int = MAX_CHILDREN,
) -> Dict[str, Any]:
    """Compose the full lineage response payload for ``simulation_id``.

    Args:
        simulation_id: The sim whose lineage view we're building.
        data_dir: Absolute path to the simulations storage directory
            (the manager's ``SIMULATION_DATA_DIR``). Used to locate the
            requested sim + scan candidate children.
        max_children: Per-call override of the ``MAX_CHILDREN`` cap;
            primarily used by tests.

    Returns:
        A dict with keys

            ``simulation_id`` — echoed.
            ``lineage_kind`` — ``"original"`` / ``"fork"`` /
                ``"counterfactual"``.
            ``parent`` — ``None`` for originals, otherwise the parent
                entry shape (``simulation_id`` / ``scenario_preview`` /
                ``created_at`` / ``is_public``). The scenario preview
                is empty when the parent has been unpublished.
            ``children`` — list of public-child entries (each with
                ``kind`` + optional ``counterfactual`` marker).
            ``total_children`` — count of *public* children present on
                disk; matches ``len(children)`` unless capped.
            ``counterfactual`` — when the requested sim itself is a
                counterfactual branch, the trigger_round + label travel
                along so the badge can render the headline without
                fetching the full ``reproduce.json``.

        Empty-state callers (sims with no parent + no children) get
        a fully-populated payload with ``parent=None`` and
        ``children=[]``; the SPA hides the lineage section in that case.
    """
    if not simulation_id:
        raise ValueError("simulation_id is required")

    sim_dir = os.path.join(data_dir or "", simulation_id)
    state = _load_state(sim_dir)
    if not isinstance(state, dict):
        # The route handler normally guards this with a 404 before we
        # get here, but defensive: still produce a coherent shape.
        state = {}

    cf = _load_counterfactual(sim_dir)
    kind = _kind_for(state, cf)

    parent_id = _safe_str(state.get("parent_simulation_id"))
    parent_entry: Optional[Dict[str, Any]] = None
    if parent_id:
        parent_dir = os.path.join(data_dir or "", parent_id)
        parent_state = _load_state(parent_dir)
        # Even when the parent has been deleted we still echo the id
        # so the badge can show "Forked from sim_abc..." — but with no
        # scenario and is_public=False so the SPA renders the bare
        # placeholder rather than a click-through link.
        parent_entry = _entry_for_sim(
            parent_id, parent_dir, parent_state, include_kind=False
        )

    # Find public children. The total_children counter reflects what
    # actually traveled in the response — capped by ``max_children``,
    # public-only. A future paginated form can lift the cap.
    all_children = find_children(simulation_id, data_dir, max_children=MAX_CHILDREN)
    total_children = len(all_children)
    children = all_children[: max(0, int(max_children))]

    payload: Dict[str, Any] = {
        "simulation_id": simulation_id,
        "lineage_kind": kind,
        "parent": parent_entry,
        "children": children,
        "total_children": total_children,
        "counterfactual": _build_counterfactual_marker(cf) if kind == "counterfactual" else None,
    }
    return payload
