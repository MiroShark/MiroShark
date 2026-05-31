"""Simulation clone payload — exposes the *inputs* a sim was built with.

Every share surface this platform exposes returns *outputs*:
``signal.json`` (direction + confidence), ``chart.svg`` (the visual),
``peak-round`` (inflection points), ``volatility`` (turbulence),
``polymarket.json`` (binary-market shape), the badge, the share card.
None of them return the *inputs* — the exact configuration that produced
those outputs. So an AntFleet benchmark workflow that wants to run the
same scenario with 40 agents instead of 20, or a researcher who wants to
re-run a published sim in their own deployment, has no machine-readable
way to ask "what was this sim configured with?"

This module fills that gap with one stdlib derivation:

  {
    "schema_version": "1",
    "simulation_id":  "<echoed>",
    "project_id":     "<the project this sim was created under>",
    "graph_id":       "<the knowledge graph used>",
    "simulation_requirement": "<the scenario text — what the agents debate>",
    "scenario_preview":       "<truncated to 200 chars for log lines>",
    "clone_payload": {            # ← exact POST /api/simulation/create body
      "project_id":             "proj_xyz",
      "graph_id":               "miroshark_def",
      "enable_twitter":         true,
      "enable_reddit":          true,
      "enable_polymarket":      false,
      "polymarket_market_count": 1,
      "country":                null,
      "demographic_filters":    null
    },
    "example_curl": "curl -fsSL -X POST 'https://your-host/api/simulation/create' -H 'Content-Type: application/json' -d '{…}'"
  }

Design notes
------------

* **Inputs, not outputs.** Every other surface re-derives from
  ``trajectory.json`` or ``simulation_config.json`` to summarize what
  happened. This surface reads ``state.json`` + ``simulation_config.json``
  to summarize what was *configured*. The two are complementary: clone
  the inputs, run the sim, then compare against the original's outputs
  with ``/api/simulation/compare``.

* **Wire-compatible with /api/simulation/create.** ``clone_payload`` is
  the literal request body that endpoint accepts. A caller with the
  same ``project_id`` re-runs the sim with one ``curl -X POST``; a
  caller forking into a different project swaps the id and keeps the
  rest. No re-shaping required.

* **simulation_requirement is informational, not on the create body.**
  The scenario text lives at the project level (a project may host
  multiple simulations across the same graph + scenario). ``create``
  doesn't accept ``simulation_requirement`` — the project's existing
  value is reused. We echo the requirement separately so a fork can
  optionally update the project's ``simulation_requirement`` before
  hitting ``create``.

* **Publish-gated.** Same gate as every other share surface
  (``is_public=true``). A private sim's configuration is its operator's
  business; the gate is enforced by the route handler (not this module)
  before ``build_clone_payload`` is called.

* **Stable JSON.** ``sort_keys=True`` + ``indent=2`` so
  ``curl > clone.json`` produces a diff-friendly file. Same posture as
  ``signal.json`` and ``peak-round`` — bytewise stability is the route
  handler's responsibility (``Content-Disposition`` filename, ETag),
  not this module's.

* **Pure stdlib.** ``json`` + ``os``. No new dependencies; same module
  shape as ``signal_service``, ``peak_round``, ``volatility_service``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


SCHEMA_VERSION = "1"

# The scenario preview travels in the response so a log line or status
# dashboard can render a one-line summary of what the cloned sim is
# about. 200 chars matches the cap the embed-summary uses for
# ``scenario_truncated`` so the two views stay consistent.
SCENARIO_PREVIEW_CHARS = 200


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


def _safe_bool(value: Any, default: bool) -> bool:
    """Coerce ``value`` to a bool with an explicit default."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "on"):
            return True
        if lowered in ("0", "false", "no", "off", ""):
            return False
    return default


def _safe_int(value: Any, default: int) -> int:
    """Coerce ``value`` to an int with a fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _load_config(sim_dir: str) -> Dict[str, Any]:
    """Load ``<sim_dir>/simulation_config.json`` defensively. Missing/corrupt → ``{}``."""
    if not sim_dir:
        return {}
    cfg_path = os.path.join(sim_dir, "simulation_config.json")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_demographic_filters(value: Any) -> Optional[Dict[str, Any]]:
    """Pass-through dict; drop non-dict (matches /create's coercion)."""
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    if not value:
        return None
    return value


def _normalize_country(value: Any) -> Optional[str]:
    """Lowercase + strip; empty → ``None``. Matches manager.create_simulation."""
    raw = _safe_str(value).lower()
    return raw or None


def build_clone_payload(
    simulation_id: str,
    sim_dir: str,
) -> Optional[Dict[str, Any]]:
    """Compose the clone-payload response for a published sim.

    Reads ``state.json`` (the structural fields ``/create`` accepts) and
    ``simulation_config.json`` (the scenario text). Returns ``None``
    when the sim has no ``state.json`` on disk — the route handler
    translates that to a 404 ("not ready / not found") rather than a
    half-baked envelope.

    The returned dict is JSON-serialisable and safe to dump directly
    with ``json.dumps(..., sort_keys=True)`` — every value is either a
    string, int, bool, ``None``, or a plain nested dict. No datetime
    objects, no custom classes.

    Args:
        simulation_id: Echoed in the response. Validated by the route
            handler's URL-decoder before reaching here.
        sim_dir: Absolute path to the sim's data directory
            (``Config.WONDERWALL_SIMULATION_DATA_DIR / simulation_id``).

    Returns:
        The full envelope dict, or ``None`` when the sim has no
        ``state.json`` on disk.
    """
    state = _load_state(sim_dir)
    if not state:
        return None

    config = _load_config(sim_dir)

    project_id = _safe_str(state.get("project_id"))
    graph_id = _safe_str(state.get("graph_id"))

    enable_twitter = _safe_bool(state.get("enable_twitter"), default=True)
    enable_reddit = _safe_bool(state.get("enable_reddit"), default=True)
    enable_polymarket = _safe_bool(state.get("enable_polymarket"), default=False)
    polymarket_market_count = max(
        1, min(5, _safe_int(state.get("polymarket_market_count", 1), 1))
    )

    country = _normalize_country(state.get("country"))
    demographic_filters = _normalize_demographic_filters(
        state.get("demographic_filters")
    )

    # Scenario text — the config file is authoritative (the LLM-driven
    # config copies the project's ``simulation_requirement`` into it at
    # prepare time). If the config is missing (mid-prepare), the field
    # is empty rather than absent so consumers can read it without a
    # KeyError.
    simulation_requirement = _safe_str(config.get("simulation_requirement"))
    scenario_preview = _truncate_scenario(simulation_requirement)

    clone_payload: Dict[str, Any] = {
        "project_id": project_id,
        "graph_id": graph_id,
        "enable_twitter": enable_twitter,
        "enable_reddit": enable_reddit,
        "enable_polymarket": enable_polymarket,
        "polymarket_market_count": polymarket_market_count,
        "country": country,
        "demographic_filters": demographic_filters,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "simulation_id": simulation_id,
        "project_id": project_id,
        "graph_id": graph_id,
        "simulation_requirement": simulation_requirement,
        "scenario_preview": scenario_preview,
        "clone_payload": clone_payload,
        "example_curl": build_example_curl(clone_payload),
    }


def build_example_curl(clone_payload: Dict[str, Any]) -> str:
    """Build a one-line ``curl`` invocation re-creating this sim.

    Uses the literal placeholder ``https://your-host`` so a copy-paste
    of the example never accidentally hits an internal URL — the same
    posture the surfaces-catalog example_curl fields take. The body is
    the exact ``clone_payload`` dict, serialised without whitespace so
    the printed command stays on one line in narrow terminals.
    """
    body = json.dumps(clone_payload, sort_keys=True, separators=(",", ":"))
    # Single quotes around the body so a shell paste survives unescaped
    # JSON double-quotes. The ``clone_payload`` itself contains no
    # single quotes (every value is either a stringified key the API
    # accepts or a JSON primitive) so single-quoting is safe here.
    return (
        "curl -fsSL -X POST 'https://your-host/api/simulation/create' "
        "-H 'Content-Type: application/json' "
        f"-d '{body}'"
    )
