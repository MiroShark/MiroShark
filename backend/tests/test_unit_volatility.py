"""Unit tests for the belief-volatility analytics service + route wiring.

Pure offline — no Flask app, no network, no simulation runner. Covers
the contract the ``GET /api/simulation/<id>/volatility`` endpoint
depends on:

  1. ``compute_volatility`` returns ``None`` for empty / single-round
     input (the route translates that to 404).
  2. Population std dev + max delta are computed against the same
     ``|Δbullish| + |Δneutral| + |Δbearish|`` swing peak-round uses, so
     ``max_delta_round`` here equals ``most_volatile_round`` there on
     identical input.
  3. ``volatility_index = min(std_dev * 5, 100)`` — flat trajectory ⇒ 0,
     very swingy trajectory ⇒ capped at 100.
  4. Trend classifier picks ``stable`` / ``converging`` / ``contested``
     under the documented rules.
  5. Single-delta (two-round) trajectory is well defined — std dev is
     0.0, trend is ``stable``, the metric ships rather than raising.
  6. The route decorator, the publish gate, and the surface-stat
     increment exist in ``app/api/simulation.py``.
  7. ``volatility`` is registered in the surface_stats schema.
  8. ``openapi.yaml`` documents ``/volatility`` and the
     ``VolatilityResponse`` schema so the drift test stays green.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services import peak_round, volatility_service  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────


def _make_round(round_num: int, b: float, n: float, x: float) -> dict:
    """Shorthand for a stance-split row matching the peak-round projection."""
    return {
        "round": round_num,
        "bullish_pct": b,
        "neutral_pct": n,
        "bearish_pct": x,
    }


# ── compute_volatility — boundary cases ───────────────────────────────────


def test_compute_returns_none_on_empty():
    assert volatility_service.compute_volatility([]) is None


def test_compute_returns_none_on_single_round():
    """One round ⇒ no deltas ⇒ no volatility statistic to ship."""
    rounds = [_make_round(1, 50.0, 25.0, 25.0)]
    assert volatility_service.compute_volatility(rounds) is None


def test_compute_two_rounds_yields_single_delta_with_zero_stddev():
    """Two rounds ⇒ one delta. Std dev of a singleton is 0; trend is
    ``stable`` because std dev < 3."""
    rounds = [
        _make_round(1, 60.0, 30.0, 10.0),
        _make_round(2, 50.0, 40.0, 10.0),
    ]
    result = volatility_service.compute_volatility(rounds)
    assert result is not None
    # |50-60| + |40-30| + |10-10| = 20
    assert result["mean_delta_pct"] == 20.0
    assert result["std_dev_delta_pct"] == 0.0
    assert result["max_delta_pct"] == 20.0
    assert result["max_delta_round"] == 2
    assert result["volatility_index"] == 0.0
    assert result["trend"] == "stable"
    assert result["total_rounds"] == 2
    assert result["delta_count"] == 1


# ── compute_volatility — delta arithmetic ─────────────────────────────────


def test_max_delta_round_matches_peak_round_most_volatile():
    """The volatility surface's ``max_delta_round`` MUST equal
    peak-round's ``most_volatile_round`` on identical input, because
    both derive from the same summed-absolute-swing definition."""
    rounds = [
        _make_round(1, 20.0, 60.0, 20.0),
        _make_round(2, 40.0, 40.0, 20.0),  # swing = 40
        _make_round(3, 80.0, 10.0, 10.0),  # swing = 80 — the max
    ]
    vol = volatility_service.compute_volatility(rounds)
    pr = peak_round.compute_peak_rounds(rounds)
    assert vol["max_delta_round"] == pr["most_volatile_round"] == 3
    assert vol["max_delta_pct"] == pr["max_swing_pct"] == 80.0


def test_mean_delta_arithmetic_average():
    """Three deltas of 10, 20, 30 ⇒ mean = 20.0."""
    rounds = [
        _make_round(1, 0.0, 100.0, 0.0),
        _make_round(2, 5.0, 95.0, 0.0),   # delta = 10
        _make_round(3, 15.0, 85.0, 0.0),  # delta = 20
        _make_round(4, 30.0, 70.0, 0.0),  # delta = 30
    ]
    result = volatility_service.compute_volatility(rounds)
    assert result["mean_delta_pct"] == 20.0
    assert result["delta_count"] == 3


def test_population_stddev_of_known_deltas():
    """Deltas 10, 20, 30 — population std dev = sqrt(((10-20)^2 +
    (20-20)^2 + (30-20)^2) / 3) = sqrt(200/3) ≈ 8.165."""
    rounds = [
        _make_round(1, 0.0, 100.0, 0.0),
        _make_round(2, 5.0, 95.0, 0.0),
        _make_round(3, 15.0, 85.0, 0.0),
        _make_round(4, 30.0, 70.0, 0.0),
    ]
    result = volatility_service.compute_volatility(rounds)
    assert result["std_dev_delta_pct"] == pytest.approx(8.16, abs=0.01)


# ── volatility_index normalization ────────────────────────────────────────


def test_volatility_index_zero_on_constant_trajectory():
    """Identical rounds ⇒ every delta is 0 ⇒ std dev 0 ⇒ index 0."""
    rounds = [_make_round(r, 60.0, 30.0, 10.0) for r in range(1, 6)]
    result = volatility_service.compute_volatility(rounds)
    assert result["std_dev_delta_pct"] == 0.0
    assert result["volatility_index"] == 0.0


def test_volatility_index_capped_at_100():
    """Std dev × 5 above 100 must clamp to 100."""
    # Alternating 0/100 stance gives huge deltas. With three rounds we
    # have two deltas of 200, std dev is 0 (constant) — so build an
    # extremely uneven trajectory by mixing tiny and giant swings.
    rounds = [
        _make_round(1, 0.0, 100.0, 0.0),
        _make_round(2, 0.0, 100.0, 0.0),     # delta 0
        _make_round(3, 100.0, 0.0, 0.0),     # delta 200 — std dev between 0 and 200 is 100
    ]
    result = volatility_service.compute_volatility(rounds)
    # std dev of [0, 200] = 100 ⇒ index = 500, clamped to 100.
    assert result["volatility_index"] == 100.0


# ── trend classifier ──────────────────────────────────────────────────────


def test_trend_stable_when_stddev_under_threshold():
    """Constant trajectory ⇒ std dev 0 ⇒ trend "stable"."""
    rounds = [_make_round(r, 50.0, 25.0, 25.0) for r in range(1, 6)]
    result = volatility_service.compute_volatility(rounds)
    assert result["trend"] == "stable"


def test_trend_converging_when_second_half_calmer():
    """First half has bigger swings than the second half ⇒ ``converging``."""
    rounds = [
        _make_round(1, 0.0, 100.0, 0.0),
        _make_round(2, 30.0, 70.0, 0.0),   # delta 60
        _make_round(3, 10.0, 90.0, 0.0),   # delta 40
        _make_round(4, 11.0, 89.0, 0.0),   # delta 2
        _make_round(5, 12.0, 88.0, 0.0),   # delta 2
    ]
    result = volatility_service.compute_volatility(rounds)
    assert result["trend"] == "converging"


def test_trend_contested_when_second_half_louder():
    """Second half swings harder than first ⇒ ``contested``."""
    rounds = [
        _make_round(1, 50.0, 25.0, 25.0),
        _make_round(2, 52.0, 24.0, 24.0),   # delta 4
        _make_round(3, 50.0, 25.0, 25.0),   # delta 4
        _make_round(4, 90.0, 5.0, 5.0),     # delta 80
        _make_round(5, 10.0, 45.0, 45.0),   # delta 160
    ]
    result = volatility_service.compute_volatility(rounds)
    assert result["trend"] == "contested"


# ── End-to-end: load → compute via the convenience wrapper ────────────────


def test_compute_volatility_for_sim_reads_trajectory_on_disk(tmp_path: Path):
    (tmp_path / "trajectory.json").write_text(
        json.dumps({
            "snapshots": [
                {"round_num": 1, "belief_positions": {"1": {"t": 0.5}, "2": {"t": -0.5}}},
                {"round_num": 2, "belief_positions": {"1": {"t": 0.5}, "2": {"t": 0.5}}},
            ]
        }),
        encoding="utf-8",
    )
    result = volatility_service.compute_volatility_for_sim(str(tmp_path))
    assert result is not None
    assert result["total_rounds"] == 2
    assert result["delta_count"] == 1
    assert result["schema_version"] == "1"


def test_compute_volatility_for_sim_returns_none_on_missing_trajectory(tmp_path: Path):
    """No trajectory.json ⇒ no rounds ⇒ ``None``."""
    assert volatility_service.compute_volatility_for_sim(str(tmp_path)) is None


# ── Schema guards ─────────────────────────────────────────────────────────


def test_schema_version_is_one():
    rounds = [
        _make_round(1, 60.0, 30.0, 10.0),
        _make_round(2, 50.0, 40.0, 10.0),
    ]
    result = volatility_service.compute_volatility(rounds)
    assert result["schema_version"] == "1"


def test_total_rounds_matches_input_length():
    rounds = [_make_round(r, 10.0 * r, 5.0, 0.0) for r in range(1, 6)]
    result = volatility_service.compute_volatility(rounds)
    assert result["total_rounds"] == 5
    assert result["delta_count"] == 4


# ── Static wiring guards ──────────────────────────────────────────────────


def _read_simulation_api() -> str:
    return (_BACKEND / "app" / "api" / "simulation.py").read_text(encoding="utf-8")


def test_route_decorator_registered():
    text = _read_simulation_api()
    assert (
        "@simulation_bp.route('/<simulation_id>/volatility', methods=['GET'])" in text
    ), "GET /<id>/volatility route decorator missing from simulation.py"
    assert "def get_volatility" in text, (
        "get_volatility handler function missing from simulation.py"
    )


def test_route_enforces_publish_gate():
    text = _read_simulation_api()
    # The handler reuses the embed-summary publish lookup (same pattern
    # as peak-round / signal.json / agent-sparklines).
    assert "_build_embed_summary_payload" in text
    assert "is_public" in text


def test_route_increments_volatility_surface_stat():
    text = _read_simulation_api()
    assert '"volatility"' in text, (
        "simulation.py must increment the volatility counter via "
        "surface_stats.increment_surface_stat(..., \"volatility\")"
    )
    assert "increment_surface_stat" in text


def test_surface_stats_registers_volatility_key():
    from app.services import surface_stats

    assert "volatility" in surface_stats.SURFACE_KEYS


def test_openapi_documents_volatility_path_and_schema():
    spec_text = (_BACKEND / "openapi.yaml").read_text(encoding="utf-8")
    assert "/api/simulation/{simulation_id}/volatility:" in spec_text, (
        "openapi.yaml is missing the /volatility path entry"
    )
    assert "VolatilityResponse:" in spec_text, (
        "openapi.yaml is missing the VolatilityResponse schema"
    )
