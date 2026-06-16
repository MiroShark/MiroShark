"""Unit tests for the per-simulation cost surface.

Pure offline — no Flask app context, no network. Exercises the two
layers behind ``GET /api/simulation/<id>/cost.json``:

  * ``app.utils.run_summary._collect_llm_events`` /
    ``collect_cost_summary`` — the shared event reader + pure aggregator
    extracted so the JSON surface and the on-disk ``run_summary.md``
    price calls off the same table.
  * ``app.services.cost_service.build_cost_payload`` — the public
    envelope shaping, including the honesty flags the STRATEGY hard
    constraint requires (``is_estimate`` + ``pricing_basis``) and the
    lower-bound behaviour for models absent from the price table.

Plus a drift guard tying the new ``cost`` surface key into the catalog
and the surface-stats registry.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import cost_service  # noqa: E402
from app.services import surface_stats  # noqa: E402
from app.services import surfaces_catalog  # noqa: E402
from app.utils import run_summary  # noqa: E402


def _llm_event(event_id, model, caller, tok_in, tok_out, latency_ms, ts, error=False):
    """Build one ``llm_call`` event line matching the on-disk schema."""
    return {
        "event_id": event_id,
        "event_type": "llm_call",
        "timestamp": ts,
        "data": {
            "model": model,
            "caller": caller,
            "tokens_input": tok_in,
            "tokens_output": tok_out,
            "latency_ms": latency_ms,
            "error": error,
        },
    }


# Two calls on a priced model + one call on an untracked model.
# gemini-2.5-flash is $0.15/1M in, $0.60/1M out in run_summary.MODEL_PRICING.
#   A: 1,000,000 in  + 0 out          -> $0.15
#   B: 0 in          + 1,000,000 out  -> $0.60
#   C: untracked model                -> $0.00 (lower-bound behaviour)
_EVENTS = [
    _llm_event("e1", "google/gemini-2.5-flash", "wonderwall_profile_generator.run",
               1_000_000, 0, 200, "2026-06-16T00:00:01Z"),
    _llm_event("e2", "google/gemini-2.5-flash", "SocialAgent.act",
               0, 1_000_000, 400, "2026-06-16T00:00:05Z"),
    _llm_event("e3", "vendor/untracked-model", "report_agent.write",
               100_000, 100_000, 100, "2026-06-16T00:00:09Z", error=True),
]


def _write_events(path: Path, events):
    path.write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )


# ── collect_cost_summary (pure aggregation) ────────────────────────────


def test_collect_cost_summary_prices_and_aggregates(tmp_path):
    sim_dir = tmp_path / "sim_cost"
    sim_dir.mkdir()
    _write_events(sim_dir / "events.jsonl", _EVENTS)
    # Global events path intentionally absent — only the per-sim file feeds in.
    summary = run_summary.collect_cost_summary(
        str(tmp_path / "nonexistent-global.jsonl"),
        sim_id="sim_cost",
        output_dir=str(sim_dir),
    )

    assert summary["total_calls"] == 3
    assert summary["total_errors"] == 1
    # 0.15 + 0.60 + 0.00 — the untracked model contributes nothing.
    assert round(summary["total_cost"], 4) == 0.75
    assert summary["total_tokens_in"] == 1_100_000
    assert summary["total_tokens_out"] == 1_100_000
    assert summary["total_tokens"] == 2_200_000
    # latencies [100, 200, 400] -> p50 = 200, max = 400
    assert summary["latency_p50_ms"] == 200
    assert summary["latency_max_ms"] == 400


def test_collect_cost_summary_empty_when_no_events(tmp_path):
    assert run_summary.collect_cost_summary(
        str(tmp_path / "nope.jsonl"), sim_id="sim_x", output_dir=str(tmp_path)
    ) == {}


def test_collect_llm_events_dedups_by_event_id(tmp_path):
    sim_dir = tmp_path / "sim_dedup"
    sim_dir.mkdir()
    dupes = _EVENTS + [_EVENTS[0]]  # repeat e1
    _write_events(sim_dir / "events.jsonl", dupes)
    events = run_summary._collect_llm_events(
        str(tmp_path / "nonexistent.jsonl"), sim_id="sim_dedup", output_dir=str(sim_dir)
    )
    assert len(events) == 3  # the repeated e1 is dropped


# ── build_cost_payload (public envelope) ───────────────────────────────


def test_build_cost_payload_shape_and_honesty_flags(tmp_path, monkeypatch):
    # Isolate the global event log to an empty dir so only the sim's
    # per-sim events.jsonl contributes — keeps the test hermetic.
    from app.utils import event_logger
    empty_global = tmp_path / "global_logs"
    empty_global.mkdir()
    monkeypatch.setattr(event_logger, "LOG_DIR", str(empty_global))

    sim_dir = tmp_path / "sim_payload"
    sim_dir.mkdir()
    _write_events(sim_dir / "events.jsonl", _EVENTS)

    payload = cost_service.build_cost_payload(str(sim_dir), "sim_payload")
    assert payload is not None

    # Envelope + honesty posture (STRATEGY hard constraint).
    assert payload["schema_version"] == "1"
    assert payload["simulation_id"] == "sim_payload"
    assert payload["currency"] == "USD"
    assert payload["is_estimate"] is True
    assert isinstance(payload["pricing_basis"], str) and payload["pricing_basis"]
    assert payload["estimated_cost_usd"] == 0.75

    totals = payload["totals"]
    assert totals["llm_calls"] == 3
    assert totals["errors"] == 1
    assert totals["tokens_total"] == 2_200_000

    assert payload["latency_ms"]["p50"] == 200
    assert payload["latency_ms"]["max"] == 400
    assert payload["wall_clock"]["start"] == "2026-06-16T00:00:01Z"
    assert payload["wall_clock"]["end"] == "2026-06-16T00:00:09Z"

    # by_model: priced model carries the whole cost; untracked model is $0.
    model_costs = {row["model"]: row["estimated_cost_usd"] for row in payload["by_model"]}
    assert model_costs["google/gemini-2.5-flash"] == 0.75
    assert model_costs["vendor/untracked-model"] == 0.0

    # by_phase: callers bucket into the friendly phase names.
    phases = {row["phase"] for row in payload["by_phase"]}
    assert {"Profile Generation", "Wonderwall Simulation", "Report Generation"} <= phases

    # Whole payload must survive json.dumps (it's what the route serialises).
    assert json.dumps(payload, sort_keys=True)


def test_build_cost_payload_none_when_no_events(tmp_path, monkeypatch):
    from app.utils import event_logger
    empty_global = tmp_path / "global_logs"
    empty_global.mkdir()
    monkeypatch.setattr(event_logger, "LOG_DIR", str(empty_global))

    sim_dir = tmp_path / "sim_empty"
    sim_dir.mkdir()  # no events.jsonl written
    assert cost_service.build_cost_payload(str(sim_dir), "sim_empty") is None


# ── Drift guards ───────────────────────────────────────────────────────


def test_cost_surface_registered_in_surface_keys():
    assert "cost" in surface_stats.SURFACE_KEYS


def test_cost_surface_catalogued_with_expected_endpoint():
    entries = {e["key"]: e for e in surfaces_catalog.get_surfaces_catalog()}
    assert "cost" in entries
    cost = entries["cost"]
    assert cost["endpoint"] == "/api/simulation/<simulation_id>/cost.json"
    assert cost["method"] == "GET"
    assert cost["type"] in surfaces_catalog.SURFACE_TYPES
