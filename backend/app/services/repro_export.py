"""Reproducibility config export — citation primitive for share surfaces.

Closes the **reproducibility gap** in the surface-multiplication arc.
Six of the ten share surfaces (transcript, trajectory, thread, watch,
GIF, share card) make a finished simulation *citable* — but until now
nothing made it *reproducible*. PR #71's ``?scenario=...`` URL carries
the scenario text and template slug; it does not carry the agent count,
total rounds, or research depth that determine the simulation's
behavior. A researcher quoting Aaron's Aave risk sim has to guess or
manually inspect to reproduce it.

``GET /api/simulation/<id>/reproduce.json`` exports a complete
machine-readable reproducibility blob for a published simulation:
scenario, agent count, total rounds, platform toggles, model preset
hint, time-config knobs, director events (if any), and lineage
(``parent_simulation_id`` + counterfactual marker if branched). Anyone
with the blob has every parameter the simulation depends on, suitable
for a paper citation, a thread reproduction, or a downstream eval
pipeline. The blob is the citation primitive that the academic and
quant audiences need before they can cite MiroShark seriously.

Design notes
------------

* **Pure stdlib.** ``json`` + ``os``. No new dependencies.
* **Read-only.** This module never writes — it composes a blob from
  on-disk artifacts (``state.json``, ``simulation_config.json``,
  ``counterfactual_injection.json``, optional director events).
* **Schema-locked.** ``SCHEMA_VERSION`` constant + every required field
  is in ``REQUIRED_KEYS`` so a downstream consumer can validate cheaply.
  Extra keys past v1 land under ``meta.extensions`` to keep the v1
  schema stable for parsers built against it.
* **Defense-in-depth.** Corrupt artifacts degrade to ``null`` rather
  than 500ing the export — the citation surface must be available even
  when ancillary files are missing.

Schema (v1)::

    {
      "schema_version": "1",
      "exported_at": "2026-05-08T12:34:56Z",
      "simulation_id": "sim_abcdef123456",
      "scenario": "What if Aave's reserve factor doubled overnight?",
      "agent_count": 36,
      "total_rounds": 24,
      "platforms": {
        "twitter": true,
        "reddit": true,
        "polymarket": false,
        "polymarket_market_count": 1
      },
      "time_config": {
        "minutes_per_round": 60,
        "total_simulation_hours": 24,
        "peak_hours": [...],
        "off_peak_hours": [...]
      },
      "lineage": {
        "parent_simulation_id": null | "sim_xxx",
        "kind": "original" | "fork" | "counterfactual",
        "counterfactual": null | { "trigger_round": 12, "label": "...",
                                   "preview": "..." }
      },
      "director_events": null | [ { "round": int, "label": str,
                                    "description": str|null } ],
      "config_reasoning": "LLM rationale for the generated knobs..."
    }

The frontend renders the blob as a download button + curl snippet;
``lineage`` powers the badge on the share / watch pages.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1"


# Every key that v1 consumers should be able to expect on every
# successful export. Tests pin this set so a future refactor can't
# silently drop a field a downstream parser depends on.
REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "exported_at",
        "simulation_id",
        "scenario",
        "agent_count",
        "total_rounds",
        "platforms",
        "time_config",
        "lineage",
        "director_events",
        "config_reasoning",
    }
)


def _utc_iso8601() -> str:
    """Return the current UTC time as an ISO-8601 ``Z``-suffixed string.

    Matches the timestamp shape used by the webhook delivery log + the
    transcript front matter so downstream parsers see one timestamp
    grammar across every export.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_int(value: Any, default: int = 0) -> int:
    """Coerce ``value`` to a non-negative int with a default fallback.

    Belief: every numeric field in the export is non-negative — agent
    count, round count, market count, everything. A hand-edited config
    file producing ``"agent_count": "lots"`` should land as ``0`` in the
    export rather than crashing the read.
    """
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, ivalue)


def _safe_str(value: Any, default: str = "") -> str:
    """Coerce ``value`` to a stripped string."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value).strip()
    except Exception:
        return default


def _build_platforms(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the platform-toggle subset out of a state dict."""
    return {
        "twitter": bool(state_dict.get("enable_twitter", True)),
        "reddit": bool(state_dict.get("enable_reddit", True)),
        "polymarket": bool(state_dict.get("enable_polymarket", False)),
        "polymarket_market_count": _safe_int(
            state_dict.get("polymarket_market_count", 1) or 1, default=1
        ),
    }


def _build_time_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the time-config knobs that actually drive runtime cadence.

    The full LLM-generated config includes per-agent posting frequency
    + event schedules + platform-specific tuning, but those are derived
    from the entity graph — not parameters a researcher reproduces by
    hand. The reproducibility-relevant subset is the four cadence
    knobs: minutes per round, total hours, peak windows, off-peak
    windows. Anyone with those four can reproduce the temporal envelope.
    """
    if not isinstance(config_data, dict):
        return {}
    time_cfg = config_data.get("time_config") or {}
    if not isinstance(time_cfg, dict):
        return {}

    out: Dict[str, Any] = {}
    if "minutes_per_round" in time_cfg:
        out["minutes_per_round"] = _safe_int(
            time_cfg.get("minutes_per_round", 60) or 60, default=60
        )
    if "total_simulation_hours" in time_cfg:
        out["total_simulation_hours"] = _safe_int(
            time_cfg.get("total_simulation_hours", 0) or 0, default=0
        )

    # Peak / off-peak hour lists — preserve as-is when present, otherwise
    # leave the key off so v1 consumers don't have to special-case empty
    # arrays vs missing keys.
    for key in ("peak_hours", "off_peak_hours"):
        value = time_cfg.get(key)
        if isinstance(value, list):
            # Coerce each item to int — defense-in-depth against a
            # corrupt config that has stringified hours.
            cleaned: List[int] = []
            for item in value:
                try:
                    cleaned.append(int(item))
                except (TypeError, ValueError):
                    continue
            out[key] = cleaned

    return out


def _build_lineage(state_dict: Dict[str, Any], sim_dir: str) -> Dict[str, Any]:
    """Compose the ``lineage`` subobject describing the sim's parentage.

    Three cases:

    * ``parent_simulation_id`` unset → ``kind = "original"``,
      ``counterfactual = None``. The sim was created from a fresh project
      via the standard prepare/start flow.
    * ``parent_simulation_id`` set + ``counterfactual_injection.json``
      present → ``kind = "counterfactual"``. The injection file's
      ``trigger_round`` / ``label`` / preview travel along so the badge
      can show "🔀 Counterfactual branch of X at round Y" without a
      second fetch.
    * ``parent_simulation_id`` set + no counterfactual file → ``kind =
      "fork"``. Plain fork via ``/api/simulation/fork``.
    """
    parent = state_dict.get("parent_simulation_id")
    if not parent:
        return {
            "parent_simulation_id": None,
            "kind": "original",
            "counterfactual": None,
        }

    cf_path = os.path.join(sim_dir or "", "counterfactual_injection.json")
    cf_block: Optional[Dict[str, Any]] = None

    if sim_dir and os.path.exists(cf_path):
        try:
            with open(cf_path, "r", encoding="utf-8") as fh:
                cf_raw = json.load(fh)
            if isinstance(cf_raw, dict):
                # Preview at 140 chars matches the parent-side
                # ``config_diff.counterfactual.preview`` cap so the two
                # surfaces always show the same headline.
                injection_text = _safe_str(cf_raw.get("injection_text"))
                preview = injection_text[:140] if injection_text else None
                cf_block = {
                    "trigger_round": _safe_int(cf_raw.get("trigger_round", 0)),
                    "label": _safe_str(cf_raw.get("label")),
                    "preview": preview,
                }
        except Exception:
            cf_block = None

    return {
        "parent_simulation_id": _safe_str(parent),
        "kind": "counterfactual" if cf_block else "fork",
        "counterfactual": cf_block,
    }


def _read_director_events(sim_dir: str) -> Optional[List[Dict[str, Any]]]:
    """Return the director events for the sim, or ``None`` if absent.

    Director events are stored in a JSONL file the runner writes; we
    surface them in the reproduction blob so a researcher knows which
    operator-injected events shaped the belief curve. Missing-or-corrupt
    file degrades to ``None`` so the most common case (a sim with no
    director mode usage) leaves the field as ``None``, not ``[]``.
    """
    if not sim_dir:
        return None

    # Two storage shapes have appeared historically — a list-style
    # ``director-events.json`` and a JSON-Lines ``director-events.jsonl``.
    # Try both, JSONL first since that is the current shape.
    jsonl_path = os.path.join(sim_dir, "director-events.jsonl")
    json_path = os.path.join(sim_dir, "director-events.json")

    raw_events: List[Dict[str, Any]] = []

    if os.path.exists(jsonl_path):
        try:
            with open(jsonl_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except Exception:
                        # Skip a single corrupt line; other lines may
                        # still be valid and worth preserving.
                        continue
                    if isinstance(item, dict):
                        raw_events.append(item)
        except Exception:
            return None
    elif os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, list):
                raw_events = [item for item in payload if isinstance(item, dict)]
            elif isinstance(payload, dict) and isinstance(
                payload.get("events"), list
            ):
                raw_events = [
                    item
                    for item in payload["events"]
                    if isinstance(item, dict)
                ]
        except Exception:
            return None
    else:
        return None

    if not raw_events:
        return None

    cleaned: List[Dict[str, Any]] = []
    for event in raw_events:
        round_value = event.get("round")
        if round_value is None:
            round_value = event.get("trigger_round")
        round_int = _safe_int(round_value, default=0)

        label = _safe_str(event.get("label") or event.get("name"))
        if not label:
            # An event with no label is meaningless to a downstream
            # consumer; drop it rather than emit ``"label": ""``.
            continue

        description = event.get("description")
        if description is not None:
            description = _safe_str(description) or None

        cleaned.append(
            {
                "round": round_int,
                "label": label,
                "description": description,
            }
        )

    cleaned.sort(key=lambda e: e["round"])
    return cleaned or None


def _derive_total_rounds(
    state_dict: Dict[str, Any], config_data: Dict[str, Any]
) -> int:
    """Mirror ``_build_embed_summary_payload``'s total-rounds derivation.

    Prefer the runner's own ``total_rounds`` if it landed on the state
    dict; otherwise reconstruct from time-config knobs the same way the
    embed summary does (``total_simulation_hours * 60 / minutes_per_round``).
    Falls back to ``0`` if neither path yields a positive value — the
    citation blob must be returnable even on a sim that hasn't started
    running yet.
    """
    state_total = _safe_int(state_dict.get("total_rounds", 0))
    if state_total:
        return state_total

    if not isinstance(config_data, dict):
        return 0

    time_cfg = config_data.get("time_config") or {}
    if not isinstance(time_cfg, dict):
        return 0
    minutes = _safe_int(time_cfg.get("minutes_per_round", 60) or 60, default=60)
    if minutes <= 0:
        minutes = 60
    hours = _safe_int(time_cfg.get("total_simulation_hours", 0) or 0)
    if hours <= 0:
        return 0
    return int(hours * 60 / minutes)


def build_repro_config(
    state_dict: Dict[str, Any],
    config_data: Optional[Dict[str, Any]],
    sim_dir: Optional[str],
) -> Dict[str, Any]:
    """Compose a reproducibility blob from on-disk simulation artifacts.

    Args:
        state_dict: The serialized ``SimulationState`` dict (typically
            ``state.to_dict()``). Provides scenario, agent_count, platform
            toggles, lineage parent.
        config_data: Optional ``simulation_config.json`` dict. Provides
            ``time_config`` + ``simulation_requirement`` + LLM rationale.
            ``None`` when the sim hasn't reached the prepared state.
        sim_dir: Absolute path to the sim's on-disk directory. Used for
            counterfactual + director event lookups. ``None`` for tests
            that only exercise the in-memory composition.

    Returns:
        A dict matching the v1 schema in the module docstring. Every
        ``REQUIRED_KEYS`` entry is present (some may be ``None`` or
        empty when the underlying data is unavailable).
    """
    if not isinstance(state_dict, dict):
        state_dict = {}
    cfg: Dict[str, Any] = config_data if isinstance(config_data, dict) else {}

    # Scenario lives in the LLM-generated config but falls back to the
    # state dict in older sims that wrote the requirement onto state.
    scenario = _safe_str(cfg.get("simulation_requirement"))
    if not scenario:
        scenario = _safe_str(state_dict.get("simulation_requirement"))

    sim_id = _safe_str(state_dict.get("simulation_id"))

    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": _utc_iso8601(),
        "simulation_id": sim_id,
        "scenario": scenario,
        "agent_count": _safe_int(state_dict.get("profiles_count", 0)),
        "total_rounds": _derive_total_rounds(state_dict, cfg),
        "platforms": _build_platforms(state_dict),
        "time_config": _build_time_config(cfg),
        "lineage": _build_lineage(state_dict, sim_dir or ""),
        "director_events": _read_director_events(sim_dir or ""),
        "config_reasoning": _safe_str(state_dict.get("config_reasoning")),
    }


def render_json_bytes(payload: Dict[str, Any]) -> bytes:
    """Pretty-print the blob as UTF-8 bytes for the route handler.

    Pretty-print (indent=2) so a ``curl > config.json`` is immediately
    readable in a paper appendix or a thread screenshot. Stable key
    ordering via ``sort_keys=True`` so two exports of the same sim are
    bytewise identical — important for citation hashes.
    """
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def validate_blob(blob: Any) -> List[str]:
    """Return a list of human-readable validation errors against v1.

    Empty list = blob is structurally valid for the v1 schema. The
    helper exists for downstream consumers (Python SDK, doc tooling)
    that want a cheap shape check without writing their own; the route
    handler does not call it on the read path because it composes the
    blob in-process.
    """
    errors: List[str] = []
    if not isinstance(blob, dict):
        errors.append("blob must be a JSON object")
        return errors

    for key in REQUIRED_KEYS:
        if key not in blob:
            errors.append(f"missing required key: {key}")

    if blob.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version mismatch: expected {SCHEMA_VERSION!r}, "
            f"got {blob.get('schema_version')!r}"
        )

    if "agent_count" in blob and not isinstance(blob.get("agent_count"), int):
        errors.append("agent_count must be an integer")
    if "total_rounds" in blob and not isinstance(blob.get("total_rounds"), int):
        errors.append("total_rounds must be an integer")

    platforms = blob.get("platforms")
    if not isinstance(platforms, dict):
        errors.append("platforms must be an object")
    else:
        for plat_key in ("twitter", "reddit", "polymarket"):
            if plat_key in platforms and not isinstance(
                platforms[plat_key], bool
            ):
                errors.append(f"platforms.{plat_key} must be a boolean")

    lineage = blob.get("lineage")
    if not isinstance(lineage, dict):
        errors.append("lineage must be an object")
    else:
        kind = lineage.get("kind")
        if kind not in {"original", "fork", "counterfactual"}:
            errors.append(
                f"lineage.kind must be one of original/fork/counterfactual "
                f"(got {kind!r})"
            )

    director_events = blob.get("director_events")
    if director_events is not None and not isinstance(director_events, list):
        errors.append("director_events must be null or a list")

    return errors
