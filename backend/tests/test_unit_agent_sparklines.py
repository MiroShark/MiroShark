"""Unit tests for the per-agent belief sparklines service + route wiring.

Pure offline — no Flask app, no network, no simulation runner. Covers the
contract the ``GET /api/simulation/<id>/agents/sparklines`` endpoint
depends on:

  1. ``load_agent_trajectories`` groups ``trajectory.json`` per-agent
     belief positions into per-agent point series, reusing the same
     ``_avg_position`` mean every other surface uses.
  2. ``build_agent_sparklines`` assembles the payload — final-stance
     classification (±0.2 threshold), stance colors, most-bullish-first
     ordering, ``has_per_agent_data`` flag, ``round_count``, and
     profile-name resolution.
  3. Empty / missing trajectory data resolves to ``None`` (the route
     translates that to a 404).
  4. The route decorator, the publish gate, and the surface-stat
     increment exist in ``app/api/simulation.py``.
  5. ``agent_sparklines`` is registered in the surface_stats schema.
  6. ``openapi.yaml`` documents ``/agents/sparklines`` and the
     ``AgentSparklinesResponse`` schema so the drift test stays green.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services import agent_sparklines_service as svc  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────


def _write_trajectory(sim_dir: Path, snapshots: list[dict]) -> None:
    (sim_dir / "trajectory.json").write_text(
        json.dumps({"snapshots": snapshots}), encoding="utf-8"
    )


def _write_profiles(sim_dir: Path, profiles: list[dict]) -> None:
    (sim_dir / "reddit_profiles.json").write_text(
        json.dumps(profiles), encoding="utf-8"
    )


# ── load_agent_trajectories ──────────────────────────────────────────────


def test_load_returns_empty_on_missing_file(tmp_path: Path):
    assert svc.load_agent_trajectories(str(tmp_path)) == []


def test_load_returns_empty_on_corrupt_file(tmp_path: Path):
    (tmp_path / "trajectory.json").write_text("{not json", encoding="utf-8")
    assert svc.load_agent_trajectories(str(tmp_path)) == []


def test_load_groups_points_per_agent_sorted_by_round(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 2, "belief_positions": {"1": {"t": 0.4}, "2": {"t": -0.3}}},
        {"round_num": 1, "belief_positions": {"1": {"t": 0.1}, "2": {"t": -0.5}}},
    ])
    trajs = svc.load_agent_trajectories(str(tmp_path))
    by_id = {t["agent_id"]: t for t in trajs}
    assert set(by_id) == {1, 2}
    # Points are sorted ascending by round even though snapshots were not.
    assert [p["round"] for p in by_id[1]["trajectory"]] == [1, 2]
    assert by_id[1]["trajectory"][0]["position"] == 0.1
    assert by_id[1]["trajectory"][1]["position"] == 0.4


def test_load_skips_rounds_without_belief_for_an_agent(tmp_path: Path):
    """An agent absent from one round's belief_positions just has fewer
    points — the sparkline connects the rounds it does have."""
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"1": {"t": 0.5}, "2": {"t": -0.5}}},
        {"round_num": 2, "belief_positions": {"1": {"t": 0.6}}},  # agent 2 absent
    ])
    by_id = {t["agent_id"]: t for t in svc.load_agent_trajectories(str(tmp_path))}
    assert [p["round"] for p in by_id[1]["trajectory"]] == [1, 2]
    assert [p["round"] for p in by_id[2]["trajectory"]] == [1]


def test_load_averages_multi_topic_positions(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"1": {"a": 0.2, "b": 0.6}}},
    ])
    by_id = {t["agent_id"]: t for t in svc.load_agent_trajectories(str(tmp_path))}
    # (0.2 + 0.6) / 2 = 0.4
    assert by_id[1]["trajectory"][0]["position"] == 0.4


# ── build_agent_sparklines ────────────────────────────────────────────────


def test_build_returns_none_on_empty(tmp_path: Path):
    assert svc.build_agent_sparklines(str(tmp_path)) is None


def test_build_returns_none_when_no_numeric_positions(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"1": {"t": "nope"}}},
    ])
    assert svc.build_agent_sparklines(str(tmp_path)) is None


def test_build_classifies_final_stance_and_color(tmp_path: Path):
    """Final stance comes from the LAST round's position, using ±0.2."""
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"1": {"t": -0.1}, "2": {"t": 0.1}, "3": {"t": 0.0}}},
        {"round_num": 2, "belief_positions": {"1": {"t": 0.5}, "2": {"t": -0.5}, "3": {"t": 0.0}}},
    ])
    payload = svc.build_agent_sparklines(str(tmp_path))
    by_id = {a["agent_id"]: a for a in payload["agents"]}
    assert by_id[1]["final_stance"] == "bullish"
    assert by_id[1]["color"] == "#22c55e"
    assert by_id[2]["final_stance"] == "bearish"
    assert by_id[2]["color"] == "#ef4444"
    assert by_id[3]["final_stance"] == "neutral"
    assert by_id[3]["color"] == "#6b7280"


def test_build_orders_most_bullish_first(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"1": {"t": -0.4}, "2": {"t": 0.8}, "3": {"t": 0.1}}},
    ])
    payload = svc.build_agent_sparklines(str(tmp_path))
    assert [a["agent_id"] for a in payload["agents"]] == [2, 3, 1]
    # Final positions descend.
    finals = [a["final_position"] for a in payload["agents"]]
    assert finals == sorted(finals, reverse=True)


def test_build_order_ties_break_by_agent_id(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"3": {"t": 0.5}, "1": {"t": 0.5}, "2": {"t": 0.5}}},
    ])
    payload = svc.build_agent_sparklines(str(tmp_path))
    assert [a["agent_id"] for a in payload["agents"]] == [1, 2, 3]


def test_build_resolves_profile_names(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"7": {"t": 0.5}, "9": {"t": -0.5}}},
    ])
    _write_profiles(tmp_path, [
        {"user_id": 7, "name": "Skeptical Trader"},
    ])
    payload = svc.build_agent_sparklines(str(tmp_path))
    by_id = {a["agent_id"]: a for a in payload["agents"]}
    assert by_id[7]["name"] == "Skeptical Trader"
    # No profile row ⇒ deterministic fallback, never anonymous.
    assert by_id[9]["name"] == "Agent 9"


def test_build_has_per_agent_data_false_for_single_round(tmp_path: Path):
    """One round ⇒ each agent is a single dot; the flag is false so the
    frontend can show a 'needs ≥2 rounds' note instead of dots."""
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"1": {"t": 0.5}}},
    ])
    payload = svc.build_agent_sparklines(str(tmp_path))
    assert payload["has_per_agent_data"] is False
    assert payload["round_count"] == 1
    assert payload["agent_count"] == 1


def test_build_has_per_agent_data_true_for_multi_round(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"1": {"t": 0.2}}},
        {"round_num": 2, "belief_positions": {"1": {"t": 0.5}}},
        {"round_num": 3, "belief_positions": {"1": {"t": 0.6}}},
    ])
    payload = svc.build_agent_sparklines(str(tmp_path))
    assert payload["has_per_agent_data"] is True
    assert payload["round_count"] == 3
    assert payload["agent_count"] == 1
    assert len(payload["agents"][0]["trajectory"]) == 3


def test_build_schema_version_is_one(tmp_path: Path):
    _write_trajectory(tmp_path, [
        {"round_num": 1, "belief_positions": {"1": {"t": 0.5}}},
    ])
    assert svc.build_agent_sparklines(str(tmp_path))["schema_version"] == "1"


# ── Static wiring guards ───────────────────────────────────────────────────


def _read_simulation_api() -> str:
    return (_BACKEND / "app" / "api" / "simulation.py").read_text(encoding="utf-8")


def test_route_decorator_registered():
    text = _read_simulation_api()
    assert (
        "@simulation_bp.route('/<simulation_id>/agents/sparklines', methods=['GET'])" in text
    ), "GET /<id>/agents/sparklines route decorator missing from simulation.py"
    assert "def get_agent_sparklines" in text, (
        "get_agent_sparklines handler function missing from simulation.py"
    )


def test_route_enforces_publish_gate():
    text = _read_simulation_api()
    assert "_build_embed_summary_payload" in text
    assert "is_public" in text


def test_route_increments_agent_sparklines_surface_stat():
    text = _read_simulation_api()
    assert '"agent_sparklines"' in text, (
        "simulation.py must increment the agent_sparklines counter via "
        "surface_stats.increment_surface_stat(..., \"agent_sparklines\")"
    )
    assert "increment_surface_stat" in text


def test_surface_stats_registers_agent_sparklines_key():
    from app.services import surface_stats

    assert "agent_sparklines" in surface_stats.SURFACE_KEYS


def test_openapi_documents_agent_sparklines_path_and_schema():
    spec_text = (_BACKEND / "openapi.yaml").read_text(encoding="utf-8")
    assert "/api/simulation/{simulation_id}/agents/sparklines:" in spec_text, (
        "openapi.yaml is missing the /agents/sparklines path entry"
    )
    assert "AgentSparklinesResponse:" in spec_text, (
        "openapi.yaml is missing the AgentSparklinesResponse schema"
    )
