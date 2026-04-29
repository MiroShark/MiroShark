"""
Run Summary Generator — produces an end-of-run cost/performance report.

Reads events.jsonl (global or per-simulation), aggregates LLM calls by
model and caller, computes estimated costs, and writes a human-readable
summary to the simulation directory.

Usage:
    from app.utils.run_summary import generate_run_summary
    summary = generate_run_summary(sim_dir, sim_id="sim_xxx", start_after="2026-04-15T22:30")
    # Returns dict + writes {sim_dir}/run_summary.md
"""

import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .logger import get_logger

logger = get_logger('miroshark.run_summary')

# ---------------------------------------------------------------------------
# OpenRouter pricing ($/1M tokens) — update as needed
# ---------------------------------------------------------------------------
MODEL_PRICING = {
    # Current Cloud preset (update as OpenRouter prices drift)
    "xiaomi/mimo-v2-flash":              {"input": 0.10, "output": 0.40},
    "x-ai/grok-4.1-fast":                {"input": 0.20, "output": 0.50},
    # Tracked for mixed / legacy setups
    "qwen/qwen3.5-flash-02-23":          {"input": 0.065, "output": 0.26},
    "deepseek/deepseek-v3.2":            {"input": 0.252, "output": 0.378},
    "google/gemini-2.0-flash-001":       {"input": 0.10, "output": 0.40},
    "google/gemini-2.0-flash-lite-001":  {"input": 0.075, "output": 0.30},
    "google/gemini-2.5-flash":           {"input": 0.15, "output": 0.60},
    "google/gemini-2.5-pro":             {"input": 1.25, "output": 10.00},
    # OpenAI
    "openai/gpt-5-nano":                 {"input": 0.05, "output": 0.20},
    "openai/gpt-4o-mini":                {"input": 0.15, "output": 0.60},
    # DeepSeek
    "deepseek/deepseek-chat-v3-0324":    {"input": 0.26, "output": 1.10},
    # Perplexity
    "perplexity/sonar":                  {"input": 1.00, "output": 1.00},
    "perplexity/sonar-pro":              {"input": 3.00, "output": 15.00},
    # Qwen
    "qwen/qwen3-235b-a22b-2507":        {"input": 0.50, "output": 2.00},
    # Embeddings
    "openai/text-embedding-3-small":     {"input": 0.02, "output": 0.00},
    "openai/text-embedding-3-large":     {"input": 0.13, "output": 0.00},
}

# :online suffix adds $0.02/search (approximated as fixed per-call cost)
ONLINE_SEARCH_COST = 0.02


def _get_model_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estimate cost for a single LLM call."""
    # Strip :online suffix for base pricing
    base_model = model.split(":")[0] if ":" in model else model
    pricing = MODEL_PRICING.get(base_model)
    if not pricing:
        # Try partial match
        for key, val in MODEL_PRICING.items():
            if key in model or model in key:
                pricing = val
                break
    if not pricing:
        return 0.0

    cost = (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000

    # Add search cost for :online models
    if ":online" in model:
        cost += ONLINE_SEARCH_COST

    return cost


def generate_run_summary(
    events_path: str,
    *,
    sim_id: Optional[str] = None,
    start_after: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a run summary from events.jsonl files.

    Reads both the global events.jsonl (LLMClient calls from Flask process)
    and the per-simulation events.jsonl (Wonderwall agent calls from subprocess),
    deduplicates by event_id, and merges into a single summary.

    Args:
        events_path: Path to global events.jsonl
        sim_id: Optional simulation ID filter
        start_after: Optional ISO timestamp — only include events after this
        output_dir: Directory to write run_summary.md (defaults to events_path parent)

    Returns:
        Summary dict with all aggregated data.
    """
    # Collect event files to read: global + per-sim
    event_files = []
    if os.path.exists(events_path):
        event_files.append(events_path)
    if output_dir:
        sim_events = os.path.join(output_dir, "events.jsonl")
        if os.path.exists(sim_events) and sim_events != events_path:
            event_files.append(sim_events)

    if not event_files:
        logger.warning(f"Events file not found: {events_path}")
        return {}

    # Load and filter events from all files, deduplicate by event_id
    events = []
    seen_ids = set()
    for fpath in event_files:
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("event_type") != "llm_call":
                    continue
                if start_after and e.get("timestamp", "") <= start_after:
                    continue
                if sim_id and e.get("simulation_id") and e.get("simulation_id") != sim_id:
                    continue
                eid = e.get("event_id")
                if eid and eid in seen_ids:
                    continue
                if eid:
                    seen_ids.add(eid)
                events.append(e)

    if not events:
        logger.info("No LLM call events found for summary")
        return {}

    # --- Aggregate ---
    summary = _aggregate(events)

    # --- Write markdown ---
    out_dir = output_dir or os.path.dirname(events_path)
    md = _render_markdown(summary)
    md_path = os.path.join(out_dir, "run_summary.md")
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)
        logger.info(f"Run summary written to {md_path}")
    except Exception as e:
        logger.warning(f"Failed to write run summary: {e}")

    # Also print to console
    print(md)

    return summary


def _aggregate(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate LLM call events into summary stats."""
    total_calls = len(events)
    total_errors = 0
    total_cost = 0.0
    total_tokens_in = 0
    total_tokens_out = 0
    total_latency_ms = 0.0

    # By model
    by_model: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "calls": 0, "tokens_in": 0, "tokens_out": 0,
        "cost": 0.0, "latency_ms": 0.0, "errors": 0,
    })

    # By caller
    by_caller: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "calls": 0, "tokens_in": 0, "tokens_out": 0,
        "cost": 0.0, "latency_ms": 0.0, "errors": 0, "models": set(),
    })

    # By phase (group callers into logical phases)
    phase_map = {
        "ner_extractor": "NER Extraction",
        "ontology_generator": "Ontology Generation",
        "wonderwall_profile_generator": "Profile Generation",
        "web_enrichment": "Web Enrichment",
        "simulation_config_generator": "Simulation Config",
        "belief_state": "Belief Tracking",
        "round_memory": "Memory Compaction",
        "report_agent": "Report Generation",
        "graph_tools": "Graph Tools / Interviews",
        "simulation": "Simulation Misc",
        "SocialAgent": "Wonderwall Simulation",
    }

    by_phase: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "calls": 0, "tokens_in": 0, "tokens_out": 0,
        "cost": 0.0, "latency_ms": 0.0, "errors": 0,
    })

    # Latency percentiles
    latencies = []

    timestamps = []

    for e in events:
        d = e.get("data", {})
        model = d.get("model", "unknown")
        caller = d.get("caller", "unknown")
        tok_in = d.get("tokens_input", 0) or 0
        tok_out = d.get("tokens_output", 0) or 0
        lat = d.get("latency_ms", 0) or 0
        has_error = bool(d.get("error"))

        cost = _get_model_cost(model, tok_in, tok_out)

        total_tokens_in += tok_in
        total_tokens_out += tok_out
        total_latency_ms += lat
        total_cost += cost
        if has_error:
            total_errors += 1
        latencies.append(lat)
        timestamps.append(e.get("timestamp", ""))

        # By model
        m = by_model[model]
        m["calls"] += 1
        m["tokens_in"] += tok_in
        m["tokens_out"] += tok_out
        m["cost"] += cost
        m["latency_ms"] += lat
        if has_error:
            m["errors"] += 1

        # By caller
        c = by_caller[caller]
        c["calls"] += 1
        c["tokens_in"] += tok_in
        c["tokens_out"] += tok_out
        c["cost"] += cost
        c["latency_ms"] += lat
        c["models"].add(model)
        if has_error:
            c["errors"] += 1

        # By phase
        phase_key = "Other"
        for prefix, phase_name in phase_map.items():
            if caller.startswith(prefix):
                phase_key = phase_name
                break
        p = by_phase[phase_key]
        p["calls"] += 1
        p["tokens_in"] += tok_in
        p["tokens_out"] += tok_out
        p["cost"] += cost
        p["latency_ms"] += lat
        if has_error:
            p["errors"] += 1

    # Compute percentiles
    latencies.sort()
    n = len(latencies)

    ts_sorted = sorted(t for t in timestamps if t)
    wall_clock_start = ts_sorted[0] if ts_sorted else ""
    wall_clock_end = ts_sorted[-1] if ts_sorted else ""

    return {
        "total_calls": total_calls,
        "total_errors": total_errors,
        "total_cost": total_cost,
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
        "total_tokens": total_tokens_in + total_tokens_out,
        "total_latency_s": total_latency_ms / 1000,
        "latency_p50_ms": latencies[n // 2] if n else 0,
        "latency_p90_ms": latencies[int(n * 0.9)] if n else 0,
        "latency_max_ms": latencies[-1] if n else 0,
        "wall_clock_start": wall_clock_start,
        "wall_clock_end": wall_clock_end,
        "by_model": {k: dict(v) for k, v in sorted(by_model.items(), key=lambda x: -x[1]["cost"])},
        "by_caller": {k: {**v, "models": list(v["models"])} for k, v in sorted(by_caller.items(), key=lambda x: -x[1]["latency_ms"])},
        "by_phase": {k: dict(v) for k, v in sorted(by_phase.items(), key=lambda x: -x[1]["latency_ms"])},
    }


def _render_markdown(s: Dict[str, Any]) -> str:
    """Render summary dict as a readable markdown report."""
    lines = []
    lines.append("# MiroShark Run Summary")
    lines.append("")
    lines.append(f"**Period:** {s['wall_clock_start'][:19]} → {s['wall_clock_end'][:19]}")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total LLM calls | {s['total_calls']} |")
    lines.append(f"| Errors | {s['total_errors']} |")
    lines.append(f"| Estimated cost | **${s['total_cost']:.4f}** |")
    lines.append(f"| Total tokens | {s['total_tokens']:,} ({s['total_tokens_in']:,} in + {s['total_tokens_out']:,} out) |")
    lines.append(f"| Total LLM time | {s['total_latency_s']:.1f}s |")
    lines.append(f"| Latency p50 | {s['latency_p50_ms']/1000:.1f}s |")
    lines.append(f"| Latency p90 | {s['latency_p90_ms']/1000:.1f}s |")
    lines.append(f"| Latency max | {s['latency_max_ms']/1000:.1f}s |")
    lines.append("")

    # By model
    lines.append("## Cost by Model")
    lines.append("")
    lines.append("| Model | Calls | Tokens In | Tokens Out | Cost | Avg Latency | Errors |")
    lines.append("|-------|-------|-----------|------------|------|-------------|--------|")
    for model, m in s["by_model"].items():
        avg_lat = m["latency_ms"] / m["calls"] / 1000 if m["calls"] else 0
        err_str = str(m["errors"]) if m["errors"] else "-"
        lines.append(
            f"| `{model}` | {m['calls']} | {m['tokens_in']:,} | {m['tokens_out']:,} "
            f"| ${m['cost']:.4f} | {avg_lat:.1f}s | {err_str} |"
        )
    lines.append("")

    # By phase
    lines.append("## Time by Pipeline Phase")
    lines.append("")
    lines.append("| Phase | Calls | Wall Time | Cost | Errors |")
    lines.append("|-------|-------|-----------|------|--------|")
    for phase, p in s["by_phase"].items():
        err_str = str(p["errors"]) if p["errors"] else "-"
        lines.append(
            f"| {phase} | {p['calls']} | {p['latency_ms']/1000:.1f}s "
            f"| ${p['cost']:.4f} | {err_str} |"
        )
    lines.append("")

    # By caller (top 15)
    lines.append("## Top Callers (by wall time)")
    lines.append("")
    lines.append("| Caller | Calls | Wall Time | Avg | Tokens | Cost | Model(s) |")
    lines.append("|--------|-------|-----------|-----|--------|------|----------|")
    for caller, c in list(s["by_caller"].items())[:15]:
        avg_lat = c["latency_ms"] / c["calls"] / 1000 if c["calls"] else 0
        tok = f"{c['tokens_in']:,}+{c['tokens_out']:,}"
        models = ", ".join(f"`{m}`" for m in c["models"])
        lines.append(
            f"| {caller} | {c['calls']} | {c['latency_ms']/1000:.1f}s "
            f"| {avg_lat:.1f}s | {tok} | ${c['cost']:.4f} | {models} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("*Generated by MiroShark run_summary*")

    return "\n".join(lines)
