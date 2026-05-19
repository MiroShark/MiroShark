"""Unit tests for the trading-signal derivation service.

Pure offline — no Flask, no network, no simulation runner, no on-disk
state. Covers the properties the ``signal.json`` endpoint depends on:

  1. ``compute_signal`` produces the documented payload shape from a
     well-formed embed-summary dict.
  2. The plurality stance becomes ``direction`` (with the locked
     tie-break order ``bullish`` > ``bearish`` > ``neutral``).
  3. ``confidence_pct`` anchors to the three-way-split baseline —
     33.333% leading is 0% confident, 100% leading is 100% confident.
  4. ``risk_tier`` maps quality health correctly: ``excellent`` →
     ``low-risk``, ``good`` → ``medium-risk``, everything else →
     ``high-risk`` (including missing / ``"N/A"``).
  5. Missing belief / final / numeric fields return ``None`` so the
     route handler can emit a clean 404.
  6. ``signal_generated_at`` is ISO-8601 UTC with trailing ``Z``.
  7. The route decorator + service hookup exist in
     ``app/api/simulation.py``.
  8. ``signal_json`` is registered in the surface_stats schema.
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
    is_public: bool = True,
) -> dict:
    """Minimal embed-summary-shaped dict for the signal derivation."""
    return {
        "simulation_id": "sim-test-0001",
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


def test_signal_payload_has_documented_keys():
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary())
    assert signal is not None
    # Keys locked by the OpenAPI schema — adding / renaming must bump
    # ``schema_version``.
    assert set(signal.keys()) == {
        "schema_version",
        "direction",
        "confidence_pct",
        "risk_tier",
        "bullish_pct",
        "neutral_pct",
        "bearish_pct",
        "quality_health",
        "signal_generated_at",
    }
    assert signal["schema_version"] == "1"


def test_payload_is_json_serializable():
    """Route handler will json.dumps() the result; a non-serializable
    value would crash the response build."""
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary())
    assert signal is not None
    blob = json.dumps(signal, sort_keys=True)
    # Round-trip parse to confirm.
    parsed = json.loads(blob)
    assert parsed["direction"] == signal["direction"]


# ── Property 2 — plurality + tie-break ────────────────────────────────────


@pytest.mark.parametrize(
    "bullish, neutral, bearish, expected",
    [
        (62.0, 18.0, 20.0, "Bullish"),
        (12.0, 73.0, 15.0, "Neutral"),
        (10.0, 25.0, 65.0, "Bearish"),
        # Edge: 50/50 split between bullish and bearish — documented
        # tie-break order is ``bullish > bearish > neutral``.
        (45.0, 10.0, 45.0, "Bullish"),
        # Edge: ``bearish == neutral``, both lead. Bearish wins per
        # tie-break order.
        (10.0, 45.0, 45.0, "Bearish"),
        # Edge: all three equal — bullish wins per tie-break order.
        (33.3, 33.4, 33.3, "Neutral"),  # neutral genuinely leads
    ],
)
def test_direction_follows_plurality(bullish, neutral, bearish, expected):
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary(bullish=bullish, neutral=neutral, bearish=bearish))
    assert signal is not None
    assert signal["direction"] == expected


def test_three_way_tie_breaks_to_bullish():
    """Pure even split — bullish wins the tie."""
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary(bullish=33.3, neutral=33.3, bearish=33.3))
    assert signal is not None
    assert signal["direction"] == "Bullish"


# ── Property 3 — confidence anchors to the three-way baseline ─────────────


def test_confidence_pct_is_zero_for_three_way_split():
    """A 33.3% leading stance is the noise floor — 0% confident."""
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary(bullish=33.3, neutral=33.3, bearish=33.4))
    assert signal is not None
    # Leading is 33.4; (33.4 - 33.333) / 66.667 * 100 ≈ 0.1%.
    assert signal["confidence_pct"] == pytest.approx(0.1, abs=0.05)


def test_confidence_pct_is_one_hundred_for_unanimous():
    """Unanimous leading stance = max confidence."""
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary(bullish=100.0, neutral=0.0, bearish=0.0))
    assert signal is not None
    assert signal["confidence_pct"] == 100.0


def test_confidence_pct_is_fifty_at_midpoint():
    """Leading stance at the midpoint between baseline and unanimous
    (~66.7%) should produce ~50% confidence.

    Tolerance is ``abs=0.2`` rather than ``0.1``: the implementation
    rounds the raw computation to one decimal, so a leading stance of
    ``66.7`` lands at ``50.1`` (raw ``50.05005…`` rounds up), and
    ``abs(50.1 - 50.0)`` is ``0.10000000000000142`` in IEEE 754 —
    a hair above ``0.1``, which would false-fail. ``0.2`` covers the
    one-decimal-place quantum on either side of the midpoint without
    changing what the test actually asserts (\"about 50%\")."""
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary(bullish=66.7, neutral=16.6, bearish=16.7))
    assert signal is not None
    assert signal["confidence_pct"] == pytest.approx(50.0, abs=0.2)


def test_confidence_pct_is_rounded_to_one_decimal():
    """API contract: ``confidence_pct`` is rounded to 1 dp."""
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary(bullish=62.0, neutral=18.0, bearish=20.0))
    assert signal is not None
    # Smoke check: the value is representable in one decimal place.
    text = f"{signal['confidence_pct']:.1f}"
    assert float(text) == signal["confidence_pct"]


def test_confidence_pct_is_bounded():
    """A pathological renderer that emitted 105% bullish must not
    produce a >100 confidence — the contract is ``[0, 100]``."""
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary(bullish=105.0, neutral=0.0, bearish=0.0))
    assert signal is not None
    assert 0.0 <= signal["confidence_pct"] <= 100.0


# ── Property 4 — risk_tier mapping ────────────────────────────────────────


@pytest.mark.parametrize(
    "health, expected",
    [
        ("excellent", "low-risk"),
        ("Excellent", "low-risk"),
        ("good", "medium-risk"),
        ("Good", "medium-risk"),
        ("fair", "high-risk"),
        ("poor", "high-risk"),
        ("Poor — disagreement collapsed", "high-risk"),
        ("N/A", "high-risk"),
        ("", "high-risk"),
    ],
)
def test_risk_tier_maps_quality_health(health, expected):
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary(health=health))
    assert signal is not None
    assert signal["risk_tier"] == expected


def test_missing_quality_block_defaults_to_high_risk():
    """A simulation with no quality.json on disk — embed summary may
    omit the ``quality`` field entirely. Risk tier must still resolve."""
    from app.services.signal_service import compute_signal

    summary = _summary()
    summary["quality"] = None
    signal = compute_signal(summary)
    assert signal is not None
    assert signal["risk_tier"] == "high-risk"
    assert signal["quality_health"] == "N/A"


def test_missing_health_field_defaults_to_high_risk():
    """``quality`` block present but ``health`` is missing — same
    fall-through behaviour as a missing quality block."""
    from app.services.signal_service import compute_signal

    summary = _summary()
    summary["quality"] = {"participation_rate": 0.5}
    signal = compute_signal(summary)
    assert signal is not None
    assert signal["risk_tier"] == "high-risk"
    assert signal["quality_health"] == "N/A"


# ── Property 5 — None returned when inputs are incomplete ─────────────────


def test_returns_none_when_summary_is_none():
    from app.services.signal_service import compute_signal

    assert compute_signal(None) is None


def test_returns_none_when_summary_is_not_dict():
    from app.services.signal_service import compute_signal

    assert compute_signal("not a dict") is None  # type: ignore[arg-type]
    assert compute_signal([1, 2, 3]) is None  # type: ignore[arg-type]


def test_returns_none_when_belief_block_missing():
    from app.services.signal_service import compute_signal

    summary = _summary()
    summary["belief"] = None
    assert compute_signal(summary) is None


def test_returns_none_when_final_block_missing():
    """Simulation that recorded rounds but didn't yet have a final
    snapshot — the embed-summary omits ``belief.final``."""
    from app.services.signal_service import compute_signal

    summary = _summary()
    summary["belief"] = {"rounds": [], "bullish": [], "neutral": [], "bearish": []}
    assert compute_signal(summary) is None


def test_returns_none_when_any_pct_is_missing():
    from app.services.signal_service import compute_signal

    for missing_key in ("bullish", "neutral", "bearish"):
        summary = _summary()
        summary["belief"]["final"].pop(missing_key)
        assert compute_signal(summary) is None, (
            f"signal must be None when {missing_key!r} is missing"
        )


def test_returns_none_when_pct_is_non_numeric():
    from app.services.signal_service import compute_signal

    summary = _summary()
    summary["belief"]["final"]["bullish"] = "sixty-two"
    assert compute_signal(summary) is None


def test_handles_negative_percentages_defensively():
    """A negative percentage is non-physical but defensively clamped to
    0 — better than crashing the route handler."""
    from app.services.signal_service import compute_signal

    summary = _summary(bullish=-5.0, neutral=50.0, bearish=55.0)
    signal = compute_signal(summary)
    assert signal is not None
    assert signal["bullish_pct"] == 0.0


# ── Property 6 — signal_generated_at is ISO-8601 UTC with trailing Z ──────


def test_signal_generated_at_is_iso_utc_z():
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary())
    assert signal is not None
    ts = signal["signal_generated_at"]
    # Strict regex against ``YYYY-MM-DDTHH:MM:SSZ`` — matches the webhook
    # log + reproduce.json formats.
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts), (
        f"signal_generated_at must be ISO-8601 UTC with trailing Z; got {ts!r}"
    )


# ── Property 7 — route decorator presence ─────────────────────────────────


def test_signal_json_route_decorator_exists():
    """Static guard against an accidental decorator removal. The
    OpenAPI drift test catches spec ↔ route mismatches, but a missing
    decorator alone wouldn't surface there without a corresponding
    spec edit."""
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    assert "/<simulation_id>/signal.json" in text
    assert "def get_signal_json" in text


def test_signal_json_handler_increments_surface_stat():
    """The serve handler must increment the signal_json surface counter
    so the inbound analytics layer sees the request."""
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    assert '"signal_json"' in text


# ── Property 8 — surface_stats registers the signal_json key ──────────────


def test_signal_json_is_registered_in_surface_stats():
    from app.services.surface_stats import SURFACE_KEYS, read_surface_stats

    assert "signal_json" in SURFACE_KEYS
    stats = read_surface_stats(None)
    assert stats["signal_json"] == 0
    assert "total" in stats


# ── Component percentages are preserved on the response payload ───────────


def test_component_pcts_are_echoed_unchanged():
    """The signal payload mirrors the input percentages with one-decimal
    rounding — a quant tool consuming the signal should be able to read
    the underlying breakdown without a second request."""
    from app.services.signal_service import compute_signal

    signal = compute_signal(_summary(bullish=62.3, neutral=17.7, bearish=20.0))
    assert signal is not None
    assert signal["bullish_pct"] == 62.3
    assert signal["neutral_pct"] == 17.7
    assert signal["bearish_pct"] == 20.0
