"""Unit tests for the peak-round belief analytics service + route wiring.

Pure offline — no Flask app, no network, no simulation runner. Covers the
contract the ``GET /api/simulation/<id>/peak-round`` endpoint depends on:

  1. ``load_trajectory_rounds`` projects ``trajectory.json`` into the
     per-round stance-split list, reusing the same ±0.2 threshold every
     other surface uses.
  2. ``compute_peak_rounds`` finds the earliest peak round per stance,
     the most-volatile round, and the max swing.
  3. Empty / missing trajectory data resolves to ``None`` (the route
     translates that to a 404).
  4. The route decorator, the publish gate, and the surface-stat
     increment exist in ``app/api/simulation.py``.
  5. ``peak_round`` is registered in the surface_stats schema.
  6. ``openapi.yaml`` documents ``/peak-round`` and the
     ``PeakRoundResponse`` schema so the drift test stays green.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services import peak_round  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────


def _write_trajectory(sim_dir: Path, snapshots: list[dict]) -> None:
    (sim_dir / "trajectory.json").write_text(
        json.dumps({"snapshots": snapshots}), encoding="utf-8"
    )


# ── load_trajectory_rounds ───────────────────────────────────────────────


def test_load_returns_empty_on_missing_file(tmp_path: Path):
    assert peak_round.load_trajectory_rounds(str(tmp_path)) == []


def test_load_returns_empty_on_corrupt_file(tmp_path: Path):
    (tmp_path / "trajectory.json").write_text("{not json", encoding="utf-8")
    assert peak_round.load_trajectory_rounds(str(tmp_path)) == []


def test_load_projects_stance_split_per_round(tmp_path: Path):
    """One bullish, one bearish, one neutral agent ⇒ 33.3% each — same
    ±0.2 threshold every other surface uses."""
    _write_trajectory(tmp_path, [
        {
            "round_num": 1,
            "belief_positions": {
                "1": {"t": 0.5},    # bullish
                "2": {"t": -0.5},   # bearish
                "3": {"t": 0.0},    # neutral
            },
        },
    ])
    rounds = peak_round.load_trajectory_rounds(str(tmp_path))
    assert len(rounds) == 1
    assert rounds[0]["round"] == 1
    assert rounds[0]["bullish_pct"] == pytest.approx(33.3, abs=0.1)
    assert rounds[0]["neutral_pct"] == pytest.approx(33.3, abs=0.1)
    assert rounds[0]["bearish_pct"] == pytest.approx(33.3, abs=0.1)


def test_load_sorts_rounds_ascending_and_skips_unnumbered(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 3, "belief_positions": {"1": {"t": 0.5}}},
        {"round_num": 1, "belief_positions": {"1": {"t": -0.5}}},
        {"belief_positions": {"1": {"t": 0.5}}},  # no round_num — skipped
        {"round_num": 2, "belief_positions": {"1": {"t": 0.0}}},
    ])
    rounds = peak_round.load_trajectory_rounds(str(tmp_path))
    assert [r["round"] for r in rounds] == [1, 2, 3]


# ── compute_peak_rounds ──────────────────────────────────────────────────


def test_compute_returns_none_on_empty():
    assert peak_round.compute_peak_rounds([]) is None


def test_single_round_puts_every_peak_at_that_round():
    rounds = [
        {"round": 1, "bullish_pct": 60.0, "neutral_pct": 30.0, "bearish_pct": 10.0},
    ]
    result = peak_round.compute_peak_rounds(rounds)
    assert result["bullish"] == {"round": 1, "pct": 60.0}
    assert result["neutral"] == {"round": 1, "pct": 30.0}
    assert result["bearish"] == {"round": 1, "pct": 10.0}
    assert result["most_volatile_round"] == 1
    assert result["max_swing_pct"] == 0.0
    assert result["total_rounds"] == 1


def test_multi_round_finds_correct_peak_round_per_stance():
    rounds = [
        {"round": 1, "bullish_pct": 20.0, "neutral_pct": 50.0, "bearish_pct": 30.0},
        {"round": 2, "bullish_pct": 70.0, "neutral_pct": 20.0, "bearish_pct": 10.0},
        {"round": 3, "bullish_pct": 40.0, "neutral_pct": 10.0, "bearish_pct": 50.0},
    ]
    result = peak_round.compute_peak_rounds(rounds)
    assert result["bullish"] == {"round": 2, "pct": 70.0}
    assert result["neutral"] == {"round": 1, "pct": 50.0}
    assert result["bearish"] == {"round": 3, "pct": 50.0}
    assert result["total_rounds"] == 3


def test_peak_tie_resolves_to_earliest_round():
    """Two rounds tie at the bullish max ⇒ the earlier round wins
    (answers 'when did bullish *first* peak')."""
    rounds = [
        {"round": 1, "bullish_pct": 50.0, "neutral_pct": 25.0, "bearish_pct": 25.0},
        {"round": 2, "bullish_pct": 50.0, "neutral_pct": 25.0, "bearish_pct": 25.0},
    ]
    result = peak_round.compute_peak_rounds(rounds)
    assert result["bullish"]["round"] == 1


def test_most_volatile_round_on_known_delta_sequence():
    """Round 2 swing = |40-20|+|40-60|+|20-20| = 40.
       Round 3 swing = |80-40|+|10-40|+|10-20| = 80 (the max)."""
    rounds = [
        {"round": 1, "bullish_pct": 20.0, "neutral_pct": 60.0, "bearish_pct": 20.0},
        {"round": 2, "bullish_pct": 40.0, "neutral_pct": 40.0, "bearish_pct": 20.0},
        {"round": 3, "bullish_pct": 80.0, "neutral_pct": 10.0, "bearish_pct": 10.0},
    ]
    result = peak_round.compute_peak_rounds(rounds)
    assert result["most_volatile_round"] == 3
    assert result["max_swing_pct"] == 80.0


def test_max_swing_rounds_to_two_dp():
    rounds = [
        {"round": 1, "bullish_pct": 0.0, "neutral_pct": 100.0, "bearish_pct": 0.0},
        {"round": 2, "bullish_pct": 33.33, "neutral_pct": 33.34, "bearish_pct": 33.33},
    ]
    result = peak_round.compute_peak_rounds(rounds)
    # |33.33-0| + |33.34-100| + |33.33-0| = 33.33 + 66.66 + 33.33 = 133.32
    assert result["max_swing_pct"] == 133.32


def test_total_rounds_matches_input_length():
    rounds = [
        {"round": r, "bullish_pct": 10.0 * r, "neutral_pct": 5.0, "bearish_pct": 0.0}
        for r in range(1, 6)
    ]
    result = peak_round.compute_peak_rounds(rounds)
    assert result["total_rounds"] == 5


def test_schema_version_is_one():
    rounds = [{"round": 1, "bullish_pct": 50.0, "neutral_pct": 25.0, "bearish_pct": 25.0}]
    assert peak_round.compute_peak_rounds(rounds)["schema_version"] == "1"


# ── End-to-end: load → compute ────────────────────────────────────────────


def test_load_then_compute_against_on_disk_trajectory(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"1": {"t": 0.5}, "2": {"t": -0.5}}},
        {"round_num": 2, "belief_positions": {"1": {"t": 0.5}, "2": {"t": 0.5}}},
    ])
    rounds = peak_round.load_trajectory_rounds(str(tmp_path))
    result = peak_round.compute_peak_rounds(rounds)
    # Round 2 is fully bullish ⇒ bullish peaks there at 100%.
    assert result["bullish"] == {"round": 2, "pct": 100.0}
    assert result["total_rounds"] == 2


# ── Static wiring guards ───────────────────────────────────────────────────


def _read_simulation_api() -> str:
    return (_BACKEND / "app" / "api" / "simulation.py").read_text(encoding="utf-8")


def test_route_decorator_registered():
    text = _read_simulation_api()
    assert (
        "@simulation_bp.route('/<simulation_id>/peak-round', methods=['GET'])" in text
    ), "GET /<id>/peak-round route decorator missing from simulation.py"
    assert "def get_peak_round" in text, (
        "get_peak_round handler function missing from simulation.py"
    )


def test_route_enforces_publish_gate():
    text = _read_simulation_api()
    # The handler reuses the embed-summary publish lookup.
    assert "_build_embed_summary_payload" in text
    assert "is_public" in text


def test_route_increments_peak_round_surface_stat():
    text = _read_simulation_api()
    assert '"peak_round"' in text, (
        "simulation.py must increment the peak_round counter via "
        "surface_stats.increment_surface_stat(..., \"peak_round\")"
    )
    assert "increment_surface_stat" in text


def test_surface_stats_registers_peak_round_key():
    from app.services import surface_stats

    assert "peak_round" in surface_stats.SURFACE_KEYS


def test_openapi_documents_peak_round_path_and_schema():
    spec_text = (_BACKEND / "openapi.yaml").read_text(encoding="utf-8")
    assert "/api/simulation/{simulation_id}/peak-round:" in spec_text, (
        "openapi.yaml is missing the /peak-round path entry"
    )
    assert "PeakRoundResponse:" in spec_text, (
        "openapi.yaml is missing the PeakRoundResponse schema"
    )
