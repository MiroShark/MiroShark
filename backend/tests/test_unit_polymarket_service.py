"""Unit tests for the Polymarket prediction-JSON adapter.

Pure offline — no Flask, no network, no simulation runner, no on-disk
state. Covers the properties the ``polymarket.json`` endpoint depends
on:

  1. ``compute_polymarket`` returns the documented payload shape from
     a well-formed embed-summary dict with ``status="completed"``.
  2. ``yes_probability`` is direction-aware: ``>0.5`` for Bullish,
     ``<0.5`` for Bearish, exactly ``0.5`` for Neutral.
  3. ``yes_probability + no_probability == 1.0`` (within float
     tolerance) for every direction.
  4. ``confidence_tier`` maps the four-bucket scale correctly with
     exclusive upper bounds.
  5. The suggested market title starts with ``"Will "`` and ends with
     ``"?"`` (single character) for every reasonable scenario string.
  6. Sims with status != ``"completed"`` return ``None``.
  7. Sims missing belief / final blocks return ``None``.
  8. ``polymarket_generated_at`` is ISO-8601 UTC with trailing ``Z``.
  9. The route decorator + service hookup exist in
     ``app/api/simulation.py``.
 10. ``polymarket_json`` is registered in the surface_stats schema.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Fixtures ──────────────────────────────────────────────────────────────


def _summary(
    *,
    bullish: float = 62.0,
    neutral: float = 18.0,
    bearish: float = 20.0,
    health: str = "excellent",
    status: str = "completed",
    is_public: bool = True,
    scenario: str = "Aave passes the safety-module change before end of Q3",
) -> dict:
    """Minimal embed-summary-shaped dict for the polymarket derivation."""
    return {
        "simulation_id": "sim-test-0001",
        "scenario": scenario,
        "status": status,
        "is_public": is_public,
        "belief": {
            "rounds": [1, 2, 3],
            "bullish": [55.0, 60.0, bullish],
            "neutral": [20.0, 19.0, neutral],
            "bearish": [25.0, 21.0, bearish],
            "final": {
                "bullish": bullish,
                "neutral": neutral,
                "bearish": bearish,
            },
        },
        "quality": {"health": health, "participation_rate": 0.91},
    }


# ── Property 1 — documented payload shape ─────────────────────────────────


def test_payload_has_documented_keys():
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(_summary(), "sim-test-0001")
    assert payload is not None
    assert set(payload.keys()) == {
        "schema_version",
        "simulation_id",
        "direction",
        "yes_probability",
        "no_probability",
        "confidence_pct",
        "confidence_tier",
        "risk_tier",
        "bullish_pct",
        "neutral_pct",
        "bearish_pct",
        "quality_health",
        "suggested_market_title",
        "source_sim_id",
        "polymarket_generated_at",
    }
    assert payload["schema_version"] == "1"


def test_payload_is_json_serializable():
    """The route handler ``json.dumps()``-es the result; a non-serializable
    field would crash the response build."""
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(_summary(), "sim-test-0001")
    assert payload is not None
    blob = json.dumps(payload, sort_keys=True)
    parsed = json.loads(blob)
    assert parsed["yes_probability"] == payload["yes_probability"]
    assert parsed["direction"] == payload["direction"]


def test_simulation_id_is_echoed_in_both_fields():
    """``simulation_id`` mirrors every other share surface;
    ``source_sim_id`` matches the field name a Polymarket bot expects
    when writing back to its audit log. Both should hold the same id."""
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(_summary(), "sim-special-abc")
    assert payload is not None
    assert payload["simulation_id"] == "sim-special-abc"
    assert payload["source_sim_id"] == "sim-special-abc"


# ── Property 2 — direction-aware yes_probability ──────────────────────────


def test_bullish_sim_yes_probability_above_half():
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(
        _summary(bullish=62.0, neutral=18.0, bearish=20.0), "sim-bullish"
    )
    assert payload is not None
    assert payload["direction"] == "Bullish"
    assert payload["yes_probability"] > 0.5
    assert payload["yes_probability"] == pytest.approx(0.62, abs=1e-4)


def test_bearish_sim_yes_probability_below_half():
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(
        _summary(bullish=12.0, neutral=18.0, bearish=70.0), "sim-bearish"
    )
    assert payload is not None
    assert payload["direction"] == "Bearish"
    assert payload["yes_probability"] < 0.5
    # YES residual = 1 - 0.70 = 0.30
    assert payload["yes_probability"] == pytest.approx(0.30, abs=1e-4)


def test_neutral_sim_yes_probability_is_exactly_half():
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(
        _summary(bullish=10.0, neutral=80.0, bearish=10.0), "sim-neutral"
    )
    assert payload is not None
    assert payload["direction"] == "Neutral"
    assert payload["yes_probability"] == 0.5
    assert payload["no_probability"] == 0.5


# ── Property 3 — yes + no sums to 1.0 ─────────────────────────────────────


@pytest.mark.parametrize(
    "bullish, neutral, bearish",
    [
        (62.0, 18.0, 20.0),  # Bullish
        (10.0, 80.0, 10.0),  # Neutral
        (12.0, 18.0, 70.0),  # Bearish
        (45.1, 9.8, 45.1),   # near-tie bullish wins
        (100.0, 0.0, 0.0),   # unanimous bullish
        (0.0, 0.0, 100.0),   # unanimous bearish
    ],
)
def test_yes_and_no_sum_to_one(bullish, neutral, bearish):
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(
        _summary(bullish=bullish, neutral=neutral, bearish=bearish),
        "sim-roundtrip",
    )
    assert payload is not None
    total = payload["yes_probability"] + payload["no_probability"]
    assert total == pytest.approx(1.0, abs=1e-6)


# ── Property 4 — confidence_tier mapping ──────────────────────────────────


@pytest.mark.parametrize(
    "confidence_input, expected_tier",
    [
        (0.0, "speculative"),
        (12.0, "speculative"),
        (24.9, "speculative"),
        (25.0, "moderate"),         # exclusive lower bound flips here
        (40.0, "moderate"),
        (49.9, "moderate"),
        (50.0, "confident"),        # exclusive bound flips
        (70.0, "confident"),
        (74.9, "confident"),
        (75.0, "high-conviction"),  # exclusive bound flips
        (95.0, "high-conviction"),
        (100.0, "high-conviction"),
    ],
)
def test_confidence_tier_buckets(confidence_input, expected_tier):
    from app.services.polymarket_service import _confidence_tier

    assert _confidence_tier(confidence_input) == expected_tier


def test_confidence_tier_is_present_on_payload():
    """Smoke-check the field is actually emitted (not just the helper)."""
    from app.services.polymarket_service import compute_polymarket

    # bullish=100, neutral=0, bearish=0 → confidence_pct=100 → high-conviction
    payload = compute_polymarket(
        _summary(bullish=100.0, neutral=0.0, bearish=0.0), "sim-max"
    )
    assert payload is not None
    assert payload["confidence_tier"] == "high-conviction"


# ── Property 5 — suggested_market_title shape ─────────────────────────────


@pytest.mark.parametrize(
    "scenario",
    [
        "Aave passes the safety-module change",
        "Aave passes the safety-module change.",
        "Will Aave pass the safety-module change?",
        "WILL Aave pass the safety-module change",
        "ETH closes above $5K by year-end!",
        "    ETH crosses $5K    ",
    ],
)
def test_market_title_starts_with_will_and_ends_with_question_mark(scenario):
    from app.services.polymarket_service import _suggested_market_title

    title = _suggested_market_title(scenario)
    assert title.startswith("Will ")
    assert title.endswith("?")
    # Only one trailing "?" — Polymarket display rail otherwise renders
    # "??" verbatim.
    assert not title.endswith("??")


def test_market_title_truncates_very_long_scenarios():
    from app.services.polymarket_service import _suggested_market_title

    body = "X" * 500
    title = _suggested_market_title(body)
    assert title.startswith("Will ")
    assert title.endswith("…?")
    # "Will " (5) + 120 body chars + "…?" (2) = 127. Anything longer
    # means truncation regressed.
    assert len(title) <= 127


def test_market_title_falls_back_for_empty_scenario():
    from app.services.polymarket_service import _suggested_market_title

    assert _suggested_market_title("") == "Will resolve YES?"
    assert _suggested_market_title("   ") == "Will resolve YES?"
    assert _suggested_market_title(None) == "Will resolve YES?"
    assert _suggested_market_title(42) == "Will resolve YES?"  # type: ignore[arg-type]


def test_market_title_strips_redundant_will_prefix():
    """A scenario that already starts with "Will " should not become
    ``"Will Will the…"``."""
    from app.services.polymarket_service import _suggested_market_title

    title = _suggested_market_title("Will Aave pass the safety-module change?")
    assert title == "Will Aave pass the safety-module change?"
    # Exactly one "Will ", at the start.
    assert title.count("Will ") == 1


# ── Property 6 — non-completed sims return None ───────────────────────────


@pytest.mark.parametrize(
    "status",
    [
        "running",
        "pending",
        "paused",
        "failed",
        "cancelled",
        "",
        "RUNNING",
    ],
)
def test_returns_none_for_non_completed_status(status):
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(_summary(status=status), "sim-incomplete")
    assert payload is None, (
        f"polymarket payload must be None for status={status!r}"
    )


def test_completed_is_case_insensitive():
    """``Completed`` (capital C) is accepted as completed — defensive
    against a future state-machine that emits a title-cased value."""
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(_summary(status="Completed"), "sim-cap")
    assert payload is not None


# ── Property 7 — missing belief / final returns None ──────────────────────


def test_returns_none_when_summary_is_not_dict():
    from app.services.polymarket_service import compute_polymarket

    assert compute_polymarket(None, "sim-x") is None
    assert compute_polymarket("not a dict", "sim-x") is None  # type: ignore[arg-type]
    assert compute_polymarket([1, 2, 3], "sim-x") is None  # type: ignore[arg-type]


def test_returns_none_when_belief_final_missing():
    from app.services.polymarket_service import compute_polymarket

    summary = _summary()
    summary["belief"] = {"rounds": [], "bullish": [], "neutral": [], "bearish": []}
    assert compute_polymarket(summary, "sim-x") is None


def test_returns_none_when_belief_block_missing():
    from app.services.polymarket_service import compute_polymarket

    summary = _summary()
    summary["belief"] = None
    assert compute_polymarket(summary, "sim-x") is None


# ── Property 8 — polymarket_generated_at is ISO-8601 UTC ──────────────────


def test_polymarket_generated_at_is_iso_utc_z():
    from app.services.polymarket_service import compute_polymarket

    payload = compute_polymarket(_summary(), "sim-test-0001")
    assert payload is not None
    ts = payload["polymarket_generated_at"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts), (
        f"polymarket_generated_at must be ISO-8601 UTC with trailing Z; got {ts!r}"
    )


# ── Property 9 — route decorator presence ─────────────────────────────────


def test_polymarket_json_route_decorator_exists():
    """Static guard against an accidental decorator removal."""
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    assert "/<simulation_id>/polymarket.json" in text
    assert "def get_polymarket_json" in text


def test_polymarket_json_handler_increments_surface_stat():
    """The serve handler must increment the polymarket_json counter so
    the inbound analytics layer sees the request."""
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    assert '"polymarket_json"' in text


# ── Property 10 — surface_stats registers the polymarket_json key ─────────


def test_polymarket_json_is_registered_in_surface_stats():
    from app.services.surface_stats import SURFACE_KEYS, read_surface_stats

    assert "polymarket_json" in SURFACE_KEYS
    stats = read_surface_stats(None)
    assert stats["polymarket_json"] == 0
    assert "total" in stats


# ── Component fields preserve signal_service-derived values ───────────────


def test_component_pcts_match_signal_payload():
    """The Polymarket payload should echo the same per-stance percentages
    that signal.json publishes — they're the same numbers, just reshaped."""
    from app.services.polymarket_service import compute_polymarket
    from app.services.signal_service import compute_signal

    summary = _summary(bullish=62.3, neutral=17.7, bearish=20.0)
    poly = compute_polymarket(summary, "sim-pct-echo")
    signal = compute_signal(summary)
    assert poly is not None
    assert signal is not None
    assert poly["bullish_pct"] == signal["bullish_pct"]
    assert poly["neutral_pct"] == signal["neutral_pct"]
    assert poly["bearish_pct"] == signal["bearish_pct"]
    assert poly["confidence_pct"] == signal["confidence_pct"]
    assert poly["risk_tier"] == signal["risk_tier"]
    assert poly["direction"] == signal["direction"]


def test_risk_tier_propagates_from_quality_health():
    """Quality health → risk_tier mapping is owned by signal_service;
    the polymarket payload should mirror it verbatim."""
    from app.services.polymarket_service import compute_polymarket

    for health, expected in [
        ("excellent", "low-risk"),
        ("good", "medium-risk"),
        ("fair", "high-risk"),
        ("poor", "high-risk"),
        ("N/A", "high-risk"),
    ]:
        payload = compute_polymarket(_summary(health=health), "sim-quality")
        assert payload is not None
        assert payload["risk_tier"] == expected, (
            f"risk_tier for health={health!r} should be {expected!r}, "
            f"got {payload['risk_tier']!r}"
        )
