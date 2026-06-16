"""Per-simulation cost surface — the "$1 to simulate anything" claim,
served as structured JSON.

MiroShark's headline pitch is "simulate anything for ~$1". The number
behind that claim is already computed at run completion by
``app.utils.run_summary`` (token counts × an OpenRouter price table) and
written to ``run_summary.md`` on disk — human-readable, but not
queryable. ``/api/observability/stats`` exposes per-sim *token* counts
but no dollar figure. So the one number that proves the pitch — what
*this* run actually cost — has no machine-readable surface.

This service closes that gap. It reuses ``run_summary``'s event
collection + aggregation (single source of truth for the pricing table,
so the JSON and the markdown can never disagree) and reshapes the result
into a stable public envelope: a headline ``estimated_cost_usd`` plus
token / latency totals and per-model / per-phase breakdowns.

Honesty posture (STRATEGY hard constraint — never present a simulation
as ground truth): the payload is explicitly flagged ``is_estimate`` and
carries a ``pricing_basis`` note. Calls on models absent from the price
table contribute ``$0`` to the total, so the figure is a *lower bound* —
the note says so rather than overclaiming precision.

Pure read: no network, no mutation, no engine state touched. Returns
``None`` when the sim has logged no LLM calls yet, so the route can 404 a
"not ready" sim apart from a "private" one (403, handled upstream).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from ..utils import run_summary

logger = get_logger("miroshark.cost_service")


# Schema version literal — bump on breaking changes to the envelope field
# set. v1 is the only published version.
SCHEMA_VERSION = "1"


_PRICING_BASIS = (
    "Estimated from token counts x OpenRouter list prices ($/1M tokens) "
    "snapshotted in run_summary.MODEL_PRICING. Calls on models absent from "
    "that table count as $0.00, so the true spend is at or above this "
    "figure. Excludes infrastructure, embeddings priced at $0, and any "
    "non-LLM cost."
)


def _round_usd(value: Any) -> float:
    return round(float(value or 0.0), 4)


def _breakdown_rows(grouped: Dict[str, Dict[str, Any]], label_key: str) -> List[Dict[str, Any]]:
    """Reshape a ``run_summary`` group dict (by_model / by_phase) into a
    list of stable, JSON-friendly rows, dropping the internal latency_ms
    accumulator the public surface doesn't expose. ``run_summary`` already
    yields the groups in descending-cost / descending-latency order, so the
    list preserves that ordering."""
    rows: List[Dict[str, Any]] = []
    for name, g in (grouped or {}).items():
        rows.append({
            label_key: name,
            "calls": int(g.get("calls", 0)),
            "tokens_input": int(g.get("tokens_in", 0)),
            "tokens_output": int(g.get("tokens_out", 0)),
            "errors": int(g.get("errors", 0)),
            "estimated_cost_usd": _round_usd(g.get("cost", 0.0)),
        })
    return rows


def build_cost_payload(sim_dir: str, simulation_id: str) -> Optional[Dict[str, Any]]:
    """Build the ``cost.json`` payload for a simulation, or ``None`` when no
    LLM-call events have been logged yet.

    ``sim_dir`` is the absolute per-simulation directory
    (``WONDERWALL_SIMULATION_DATA_DIR / simulation_id``); it holds the
    per-sim ``events.jsonl``. The global ``logs/events.jsonl`` is read too
    (and deduped) so calls made from the Flask process are included.
    """
    from ..utils.event_logger import LOG_DIR

    global_events = os.path.join(LOG_DIR, "events.jsonl")
    try:
        summary = run_summary.collect_cost_summary(
            global_events, sim_id=simulation_id, output_dir=sim_dir,
        )
    except Exception as exc:  # noqa: BLE001 — cost accounting must never 500 a sim
        logger.warning(f"cost_service: aggregation failed for {simulation_id}: {exc}")
        return None

    if not summary:
        return None

    return {
        "schema_version": SCHEMA_VERSION,
        "simulation_id": simulation_id,
        "currency": "USD",
        "is_estimate": True,
        "pricing_basis": _PRICING_BASIS,
        "estimated_cost_usd": _round_usd(summary.get("total_cost", 0.0)),
        "totals": {
            "llm_calls": int(summary.get("total_calls", 0)),
            "errors": int(summary.get("total_errors", 0)),
            "tokens_input": int(summary.get("total_tokens_in", 0)),
            "tokens_output": int(summary.get("total_tokens_out", 0)),
            "tokens_total": int(summary.get("total_tokens", 0)),
            "llm_seconds": round(float(summary.get("total_latency_s", 0.0)), 1),
        },
        "latency_ms": {
            "p50": int(summary.get("latency_p50_ms", 0)),
            "p90": int(summary.get("latency_p90_ms", 0)),
            "max": int(summary.get("latency_max_ms", 0)),
        },
        "wall_clock": {
            "start": summary.get("wall_clock_start") or None,
            "end": summary.get("wall_clock_end") or None,
        },
        "by_model": _breakdown_rows(summary.get("by_model", {}), "model"),
        "by_phase": _breakdown_rows(summary.get("by_phase", {}), "phase"),
    }
