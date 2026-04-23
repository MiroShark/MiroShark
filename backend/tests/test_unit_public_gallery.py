"""Unit tests for the public gallery helper.

The ``_build_gallery_card_payload`` helper assembles the card payload
returned by ``GET /api/simulation/public``. These tests verify its
offline behavior — no Flask, no database, just tmp-path artifacts. We
cover three paths that matter for gallery rendering:

  1. A minimal state with no on-disk artifacts still produces a valid
     card (graceful degradation — the gallery shouldn't blow up on
     in-progress sims that haven't written trajectory yet).
  2. A fully-populated simulation dir yields every optional field —
     quality, final consensus, resolution — so the card has enough
     signal to render nicely.
  3. Scenario headlines longer than 180 chars are truncated with a
     unicode ellipsis so the grid stays visually even.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


class _FakeStatus:
    value = "completed"


def _make_state(
    simulation_id: str = "sim_abc123def456",
    *,
    is_public: bool = True,
    profiles_count: int = 248,
    created_at: str = "2026-04-22T10:12:34",
    parent_simulation_id=None,
):
    """Lightweight stand-in for SimulationState — only the attributes the
    gallery helper reads."""
    class _State:
        pass
    s = _State()
    s.simulation_id = simulation_id
    s.is_public = is_public
    s.profiles_count = profiles_count
    s.created_at = created_at
    s.parent_simulation_id = parent_simulation_id
    s.status = _FakeStatus()
    return s


@pytest.fixture(autouse=True)
def _no_runner_state():
    """Bypass SimulationRunner.get_run_state — it touches disk + process
    state we don't care about here. A ``None`` run_state makes the helper
    fall back to the values it derives from simulation_config.json alone.
    """
    from app.api import simulation as sim_mod
    with patch.object(sim_mod.SimulationRunner, "get_run_state", return_value=None):
        yield


def test_minimal_card_for_missing_artifacts(tmp_path: Path):
    """When the sim dir is empty (e.g. a freshly published but not-yet-run
    simulation), the card still renders without raising."""
    from app.api.simulation import _build_gallery_card_payload

    state = _make_state()
    card = _build_gallery_card_payload(state, str(tmp_path))

    assert card["simulation_id"] == state.simulation_id
    assert card["agent_count"] == 248
    assert card["scenario"] == ""
    assert card["status"] == "completed"
    assert card["quality_health"] is None
    assert card["final_consensus"] is None
    assert card["resolution_outcome"] is None
    assert card["share_card_url"].endswith("/share-card.png")
    assert card["share_landing_url"].startswith("/share/")


def test_full_card_from_complete_simulation_dir(tmp_path: Path):
    """All optional fields populated when each artifact file exists."""
    from app.api.simulation import _build_gallery_card_payload

    (tmp_path / "simulation_config.json").write_text(json.dumps({
        "simulation_requirement": "Will the SEC approve a spot Solana ETF?",
        "time_config": {
            "minutes_per_round": 60,
            "total_simulation_hours": 20,
        },
    }))
    (tmp_path / "quality.json").write_text(json.dumps({
        "health": "Excellent",
        "participation_rate": 0.92,
    }))
    # A minimal two-snapshot trajectory where round 1 has clear bullish
    # dominance.
    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {
                "round_num": 0,
                "belief_positions": {
                    "a": {"topic": 0.0},
                    "b": {"topic": 0.0},
                    "c": {"topic": 0.0},
                },
            },
            {
                "round_num": 1,
                "belief_positions": {
                    "a": {"topic": 0.6},
                    "b": {"topic": 0.4},
                    "c": {"topic": -0.5},
                    "d": {"topic": 0.0},
                },
            },
        ],
    }))
    (tmp_path / "resolution.json").write_text(json.dumps({
        "actual_outcome": "YES",
        "predicted_consensus": "YES",
        "accuracy_score": 1.0,
    }))

    state = _make_state()
    card = _build_gallery_card_payload(state, str(tmp_path))

    assert card["scenario"] == "Will the SEC approve a spot Solana ETF?"
    assert card["total_rounds"] == 20  # 20h * 60m / 60m per round
    assert card["quality_health"] == "Excellent"
    assert card["resolution_outcome"] == "YES"

    consensus = card["final_consensus"]
    assert consensus is not None
    # 2/4 stances > 0.2 = bullish; 1/4 < -0.2 = bearish; 1/4 neutral.
    assert consensus["bullish"] == 50.0
    assert consensus["bearish"] == 25.0
    assert consensus["neutral"] == 25.0


def test_scenario_gets_truncated_when_too_long(tmp_path: Path):
    """Scenarios over 180 chars get an ellipsis so card layout stays
    uniform."""
    from app.api.simulation import _build_gallery_card_payload

    long_scenario = "A " * 200  # 400 chars
    (tmp_path / "simulation_config.json").write_text(json.dumps({
        "simulation_requirement": long_scenario,
        "time_config": {"minutes_per_round": 60, "total_simulation_hours": 10},
    }))

    state = _make_state()
    card = _build_gallery_card_payload(state, str(tmp_path))

    assert len(card["scenario"]) <= 180
    assert card["scenario"].endswith("…")


def test_empty_trajectory_yields_no_consensus(tmp_path: Path):
    """An empty or malformed trajectory shouldn't raise — it just means
    no consensus pill is rendered."""
    from app.api.simulation import _build_gallery_card_payload

    (tmp_path / "trajectory.json").write_text(json.dumps({"snapshots": []}))

    state = _make_state()
    card = _build_gallery_card_payload(state, str(tmp_path))
    assert card["final_consensus"] is None


def test_malformed_artifact_json_is_swallowed(tmp_path: Path):
    """Corrupt JSON on any optional artifact shouldn't take down the card.
    The gallery helper must keep returning a card so one bad sim doesn't
    blank out the whole /explore page."""
    from app.api.simulation import _build_gallery_card_payload

    (tmp_path / "simulation_config.json").write_text("{this is not json")
    (tmp_path / "quality.json").write_text("also not json")
    (tmp_path / "trajectory.json").write_text("definitely not json")
    (tmp_path / "resolution.json").write_text("{")

    state = _make_state()
    card = _build_gallery_card_payload(state, str(tmp_path))

    assert card["simulation_id"] == state.simulation_id
    assert card["scenario"] == ""
    assert card["quality_health"] is None
    assert card["final_consensus"] is None
    assert card["resolution_outcome"] is None
