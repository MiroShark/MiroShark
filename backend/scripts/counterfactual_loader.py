"""Load counterfactual-injection specs for the simulation runner.

The Flask API writes ``counterfactual_injection.json`` when a user branches a
simulation via ``POST /api/simulation/branch-counterfactual``. The runner
loads it at the start of each round and, when ``round_num >= trigger_round``,
prepends ``injection_text`` to every agent's observation prompt — turning a
static fork into a MiroJiang-style counterfactual scenario.

Missing / malformed files return None so the runner behaves identically to
un-branched simulations. Never raises.
"""

from __future__ import annotations

import json
import os
from typing import Optional, TypedDict


class CounterfactualSpec(TypedDict, total=False):
    trigger_round: int
    injection_text: str
    label: str
    parent_simulation_id: str
    branch_id: Optional[str]
    created_at: str


def load_counterfactual(sim_dir: str) -> Optional[CounterfactualSpec]:
    """Read ``<sim_dir>/counterfactual_injection.json`` or return None."""
    if not sim_dir or not os.path.isdir(sim_dir):
        return None
    path = os.path.join(sim_dir, "counterfactual_injection.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    # Minimal validation — runner should tolerate extra fields.
    if not isinstance(raw.get("trigger_round"), int):
        return None
    if not isinstance(raw.get("injection_text"), str) or not raw["injection_text"].strip():
        return None
    return raw  # type: ignore[return-value]


def injection_prefix_for_round(
    spec: Optional[CounterfactualSpec],
    round_num: int,
) -> str:
    """Return a prompt-ready prefix for agents this round, or "".

    The prefix is an ALL-CAPS banner plus the injection text, so LLM agents
    reliably treat it as breaking news rather than simulation background.
    """
    if not spec:
        return ""
    trigger = int(spec.get("trigger_round", 0))
    if round_num < trigger:
        return ""
    label = spec.get("label") or "counterfactual event"
    text = spec["injection_text"].strip()
    return (
        "\n[BREAKING COUNTERFACTUAL EVENT — this supersedes prior context]\n"
        f"[{label}]\n"
        f"{text}\n"
        "[END BREAKING]\n"
    )
