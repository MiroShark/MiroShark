"""Unit tests for the agents.json roster export service + wiring.

Pure offline — no Flask app, no network, no simulation runner. Covers
the contract the ``GET /api/simulation/<id>/agents.json`` endpoint
depends on:

  1. ``build_agent_export`` returns ``None`` when no profile file
     exists (route translates to 404).
  2. Happy-path envelope shape — schema_version, simulation_id,
     scenario_preview, agent_count, has_trajectory_data, agents[].
  3. Roster fields populated from ``reddit_profiles.json``; missing
     optional fields fall back to typed defaults.
  4. ``polymarket_profiles.json`` is a secondary source — reddit wins
     on duplicate ``user_id`` (matches the transcript renderer).
  5. ``final_stance`` and ``final_position`` derive from
     ``trajectory.json`` via ``agent_sparklines_service``; the same
     ±0.2 threshold every other surface uses.
  6. Profile-only agents (no trajectory entry) appear in the roster
     with neutral / null / zero defaults.
  7. ``persona_preview`` is truncated to 280 chars with a trailing
     ellipsis; ``bio`` is truncated to 280; ``scenario_preview`` is
     truncated to 200.
  8. ``interested_topics`` de-duplicates while preserving order and
     drops empties; non-list inputs degrade to an empty list.
  9. Roster sort order is most-bullish-first by final_position; ties
     broken by agent_id; profile-only agents land at the bottom.
 10. Payload is JSON-serialisable with ``sort_keys=True`` (the route
     handler serialisation will not raise).
 11. ``agents_json`` is registered in ``surface_stats.SURFACE_KEYS``
     and the surfaces catalog tracked-keys set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services import agent_export  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────


def _write_reddit_profiles(sim_dir: Path, profiles: list[dict]) -> None:
    (sim_dir / "reddit_profiles.json").write_text(
        json.dumps(profiles), encoding="utf-8"
    )


def _write_polymarket_profiles(sim_dir: Path, profiles: list[dict]) -> None:
    (sim_dir / "polymarket_profiles.json").write_text(
        json.dumps(profiles), encoding="utf-8"
    )


def _write_trajectory(sim_dir: Path, snapshots: list[dict]) -> None:
    (sim_dir / "trajectory.json").write_text(
        json.dumps({"snapshots": snapshots}), encoding="utf-8"
    )


def _write_config(sim_dir: Path, scenario: str) -> None:
    (sim_dir / "simulation_config.json").write_text(
        json.dumps({"simulation_requirement": scenario}), encoding="utf-8"
    )


def _make_profile(uid: int, **overrides) -> dict:
    """Wonderwall reddit-shape profile with the manager-default fields."""
    profile = {
        "user_id": uid,
        "username": f"reddit_user_{uid}",
        "name": f"Agent {uid} Name",
        "bio": f"Bio for agent {uid}.",
        "persona": f"Persona for agent {uid}. Cares about markets.",
        "karma": 1000 + uid,
        "age": 30 + uid,
        "gender": "non-binary",
        "mbti": "INTJ",
        "country": "United States",
        "profession": "Software Engineer",
        "interested_topics": ["finance", "ai"],
        "created_at": "2026-06-01",
    }
    profile.update(overrides)
    return profile


def _make_snapshot(round_num: int, positions_by_uid: dict[int, dict[str, float]]) -> dict:
    """Single trajectory snapshot in the shape agent_sparklines_service reads."""
    return {
        "round_num": round_num,
        "belief_positions": {
            str(uid): pos for uid, pos in positions_by_uid.items()
        },
    }


# ── Missing / empty data ─────────────────────────────────────────────────


def test_returns_none_when_no_profiles_exist(tmp_path: Path):
    sim_dir = tmp_path / "sim_missing"
    sim_dir.mkdir()
    assert agent_export.build_agent_export("sim_missing", str(sim_dir)) is None


def test_returns_none_when_profile_file_is_empty_list(tmp_path: Path):
    sim_dir = tmp_path / "sim_empty"
    sim_dir.mkdir()
    _write_reddit_profiles(sim_dir, [])
    assert agent_export.build_agent_export("sim_empty", str(sim_dir)) is None


def test_returns_none_when_profile_file_is_corrupt(tmp_path: Path):
    sim_dir = tmp_path / "sim_corrupt"
    sim_dir.mkdir()
    (sim_dir / "reddit_profiles.json").write_text("{not json", encoding="utf-8")
    assert agent_export.build_agent_export("sim_corrupt", str(sim_dir)) is None


def test_returns_none_when_all_profile_rows_lack_user_id(tmp_path: Path):
    sim_dir = tmp_path / "sim_bad"
    sim_dir.mkdir()
    _write_reddit_profiles(
        sim_dir, [{"username": "anon", "bio": "no id"}, {"name": "still no id"}]
    )
    assert agent_export.build_agent_export("sim_bad", str(sim_dir)) is None


# ── Happy-path envelope ─────────────────────────────────────────────────


def test_happy_path_envelope_shape(tmp_path: Path):
    sim_dir = tmp_path / "sim_happy"
    sim_dir.mkdir()
    _write_reddit_profiles(
        sim_dir,
        [_make_profile(1), _make_profile(2), _make_profile(3)],
    )
    _write_trajectory(
        sim_dir,
        [
            _make_snapshot(1, {1: {"crypto": 0.5}, 2: {"crypto": -0.5}, 3: {"crypto": 0.0}}),
            _make_snapshot(2, {1: {"crypto": 0.7}, 2: {"crypto": -0.7}, 3: {"crypto": 0.1}}),
        ],
    )
    _write_config(sim_dir, "Will Aave's reserve factor doubling reduce TVL?")

    payload = agent_export.build_agent_export("sim_happy", str(sim_dir))

    assert payload is not None
    assert payload["schema_version"] == "1"
    assert payload["simulation_id"] == "sim_happy"
    assert payload["scenario_preview"] == "Will Aave's reserve factor doubling reduce TVL?"
    assert payload["agent_count"] == 3
    assert payload["has_trajectory_data"] is True
    assert isinstance(payload["agents"], list)
    assert len(payload["agents"]) == 3

    first = payload["agents"][0]
    required_keys = {
        "agent_id", "username", "name", "bio", "persona_preview",
        "age", "gender", "mbti", "country", "profession",
        "interested_topics", "karma", "created_at",
        "final_stance", "final_position", "rounds_participated",
    }
    assert required_keys <= set(first.keys())


def test_payload_is_json_serialisable_with_sort_keys(tmp_path: Path):
    """The route handler dumps with sort_keys=True — a non-serialisable
    value would crash the response build."""
    sim_dir = tmp_path / "sim_ser"
    sim_dir.mkdir()
    _write_reddit_profiles(sim_dir, [_make_profile(7)])
    _write_trajectory(
        sim_dir,
        [_make_snapshot(1, {7: {"topic": 0.3}})],
    )

    payload = agent_export.build_agent_export("sim_ser", str(sim_dir))
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    assert "schema_version" in body
    assert "agents" in body


# ── Field population + defaults ─────────────────────────────────────────


def test_profile_fields_propagate_to_roster(tmp_path: Path):
    sim_dir = tmp_path / "sim_fields"
    sim_dir.mkdir()
    _write_reddit_profiles(
        sim_dir,
        [_make_profile(
            42,
            username="alice_42",
            name="Alice Forty-Two",
            bio="DeFi researcher.",
            age=29,
            gender="female",
            mbti="ENTJ",
            country="Singapore",
            profession="Quant",
            interested_topics=["defi", "policy"],
            karma=5000,
        )],
    )
    payload = agent_export.build_agent_export("sim_fields", str(sim_dir))
    agent = payload["agents"][0]

    assert agent["agent_id"] == 42
    assert agent["username"] == "alice_42"
    assert agent["name"] == "Alice Forty-Two"
    assert agent["bio"] == "DeFi researcher."
    assert agent["age"] == 29
    assert agent["gender"] == "female"
    assert agent["mbti"] == "ENTJ"
    assert agent["country"] == "Singapore"
    assert agent["profession"] == "Quant"
    assert agent["interested_topics"] == ["defi", "policy"]
    assert agent["karma"] == 5000


def test_missing_optional_fields_fall_back_to_typed_defaults(tmp_path: Path):
    """A bare profile with only user_id must still produce a fixed key
    set so the JSON consumer doesn't have to special-case missing keys."""
    sim_dir = tmp_path / "sim_min"
    sim_dir.mkdir()
    _write_reddit_profiles(sim_dir, [{"user_id": 1}])
    payload = agent_export.build_agent_export("sim_min", str(sim_dir))
    agent = payload["agents"][0]

    assert agent["agent_id"] == 1
    assert agent["username"] == ""
    assert agent["name"] == "Agent 1"
    assert agent["bio"] == ""
    assert agent["persona_preview"] == ""
    assert agent["age"] is None
    assert agent["gender"] is None
    assert agent["mbti"] is None
    assert agent["country"] is None
    assert agent["profession"] is None
    assert agent["interested_topics"] == []
    assert agent["karma"] == 0
    assert agent["created_at"] == ""
    assert agent["final_stance"] == "neutral"
    assert agent["final_position"] is None
    assert agent["rounds_participated"] == 0


# ── Profile sourcing ─────────────────────────────────────────────────────


def test_reddit_profiles_take_precedence_over_polymarket_on_duplicate_id(tmp_path: Path):
    sim_dir = tmp_path / "sim_dupe"
    sim_dir.mkdir()
    _write_reddit_profiles(
        sim_dir,
        [_make_profile(5, name="From Reddit")],
    )
    _write_polymarket_profiles(
        sim_dir,
        [_make_profile(5, name="From Polymarket"), _make_profile(6, name="Only Polymarket")],
    )
    payload = agent_export.build_agent_export("sim_dupe", str(sim_dir))
    by_id = {a["agent_id"]: a for a in payload["agents"]}

    assert by_id[5]["name"] == "From Reddit"
    assert by_id[6]["name"] == "Only Polymarket"
    assert payload["agent_count"] == 2


# ── Belief layer ─────────────────────────────────────────────────────────


def test_final_stance_uses_plus_minus_0_2_threshold(tmp_path: Path):
    sim_dir = tmp_path / "sim_stance"
    sim_dir.mkdir()
    _write_reddit_profiles(
        sim_dir,
        [_make_profile(1), _make_profile(2), _make_profile(3)],
    )
    _write_trajectory(
        sim_dir,
        [
            _make_snapshot(1, {
                1: {"topic": 0.5},   # bullish
                2: {"topic": -0.5},  # bearish
                3: {"topic": 0.1},   # neutral (between ±0.2)
            }),
        ],
    )
    payload = agent_export.build_agent_export("sim_stance", str(sim_dir))
    by_id = {a["agent_id"]: a for a in payload["agents"]}

    assert by_id[1]["final_stance"] == "bullish"
    assert by_id[2]["final_stance"] == "bearish"
    assert by_id[3]["final_stance"] == "neutral"


def test_rounds_participated_counts_usable_positions(tmp_path: Path):
    sim_dir = tmp_path / "sim_rounds"
    sim_dir.mkdir()
    _write_reddit_profiles(sim_dir, [_make_profile(1), _make_profile(2)])
    _write_trajectory(
        sim_dir,
        [
            _make_snapshot(1, {1: {"topic": 0.4}}),
            _make_snapshot(2, {1: {"topic": 0.5}, 2: {"topic": 0.3}}),
            _make_snapshot(3, {1: {"topic": 0.6}, 2: {"topic": 0.2}}),
        ],
    )
    payload = agent_export.build_agent_export("sim_rounds", str(sim_dir))
    by_id = {a["agent_id"]: a for a in payload["agents"]}

    assert by_id[1]["rounds_participated"] == 3
    assert by_id[2]["rounds_participated"] == 2


def test_profile_only_agent_gets_neutral_null_zero_defaults(tmp_path: Path):
    """An agent listed in reddit_profiles but with no entry in any
    trajectory snapshot still appears in the roster — the surface
    answers *who was here*, not *did they say anything*."""
    sim_dir = tmp_path / "sim_silent"
    sim_dir.mkdir()
    _write_reddit_profiles(
        sim_dir,
        [_make_profile(1), _make_profile(99, name="Silent agent")],
    )
    _write_trajectory(
        sim_dir,
        [_make_snapshot(1, {1: {"topic": 0.3}})],
    )
    payload = agent_export.build_agent_export("sim_silent", str(sim_dir))
    by_id = {a["agent_id"]: a for a in payload["agents"]}

    assert 99 in by_id
    assert by_id[99]["final_stance"] == "neutral"
    assert by_id[99]["final_position"] is None
    assert by_id[99]["rounds_participated"] == 0


# ── Truncation ───────────────────────────────────────────────────────────


def test_persona_truncated_to_280_chars_with_ellipsis(tmp_path: Path):
    sim_dir = tmp_path / "sim_persona"
    sim_dir.mkdir()
    long_persona = "x" * 400
    _write_reddit_profiles(sim_dir, [_make_profile(1, persona=long_persona)])
    payload = agent_export.build_agent_export("sim_persona", str(sim_dir))
    persona = payload["agents"][0]["persona_preview"]

    assert len(persona) == 280
    assert persona.endswith("…")


def test_bio_truncated_to_280_chars_with_ellipsis(tmp_path: Path):
    sim_dir = tmp_path / "sim_bio"
    sim_dir.mkdir()
    long_bio = "b" * 400
    _write_reddit_profiles(sim_dir, [_make_profile(1, bio=long_bio)])
    payload = agent_export.build_agent_export("sim_bio", str(sim_dir))
    bio = payload["agents"][0]["bio"]

    assert len(bio) == 280
    assert bio.endswith("…")


def test_scenario_preview_truncated_to_200_chars_with_ellipsis(tmp_path: Path):
    sim_dir = tmp_path / "sim_scenario"
    sim_dir.mkdir()
    long_scenario = "s" * 300
    _write_reddit_profiles(sim_dir, [_make_profile(1)])
    _write_config(sim_dir, long_scenario)
    payload = agent_export.build_agent_export("sim_scenario", str(sim_dir))

    assert len(payload["scenario_preview"]) == 200
    assert payload["scenario_preview"].endswith("…")


def test_scenario_preview_empty_when_config_missing(tmp_path: Path):
    sim_dir = tmp_path / "sim_no_config"
    sim_dir.mkdir()
    _write_reddit_profiles(sim_dir, [_make_profile(1)])
    payload = agent_export.build_agent_export("sim_no_config", str(sim_dir))

    assert payload["scenario_preview"] == ""


# ── Topic normalisation ─────────────────────────────────────────────────


def test_interested_topics_dedup_preserves_order_and_drops_empties(tmp_path: Path):
    sim_dir = tmp_path / "sim_topics"
    sim_dir.mkdir()
    _write_reddit_profiles(
        sim_dir,
        [_make_profile(
            1, interested_topics=["ai", "", "defi", "ai", "  ", "policy"]
        )],
    )
    payload = agent_export.build_agent_export("sim_topics", str(sim_dir))
    assert payload["agents"][0]["interested_topics"] == ["ai", "defi", "policy"]


def test_interested_topics_non_list_coerces_to_empty(tmp_path: Path):
    sim_dir = tmp_path / "sim_topics_bad"
    sim_dir.mkdir()
    _write_reddit_profiles(sim_dir, [_make_profile(1, interested_topics="ai,defi")])
    payload = agent_export.build_agent_export("sim_topics_bad", str(sim_dir))
    assert payload["agents"][0]["interested_topics"] == []


# ── Sort order ───────────────────────────────────────────────────────────


def test_roster_sorted_most_bullish_first_ties_on_agent_id(tmp_path: Path):
    sim_dir = tmp_path / "sim_sort"
    sim_dir.mkdir()
    _write_reddit_profiles(
        sim_dir,
        [_make_profile(1), _make_profile(2), _make_profile(3), _make_profile(4)],
    )
    _write_trajectory(
        sim_dir,
        [
            _make_snapshot(1, {
                1: {"topic": 0.5},   # bullish, mid
                2: {"topic": 0.5},   # bullish, mid — tie with 1
                3: {"topic": 0.8},   # bullish, top
                4: {"topic": -0.3},  # bearish
            }),
        ],
    )
    payload = agent_export.build_agent_export("sim_sort", str(sim_dir))
    ordered_ids = [a["agent_id"] for a in payload["agents"]]
    assert ordered_ids == [3, 1, 2, 4]


def test_profile_only_agents_sort_to_bottom(tmp_path: Path):
    sim_dir = tmp_path / "sim_silent_bottom"
    sim_dir.mkdir()
    _write_reddit_profiles(
        sim_dir,
        [_make_profile(1), _make_profile(2), _make_profile(99)],
    )
    _write_trajectory(
        sim_dir,
        [_make_snapshot(1, {1: {"topic": 0.3}, 2: {"topic": -0.4}})],
    )
    payload = agent_export.build_agent_export("sim_silent_bottom", str(sim_dir))
    ordered_ids = [a["agent_id"] for a in payload["agents"]]
    # 1 is bullish (first), 2 is bearish (second), 99 has no belief (last).
    assert ordered_ids == [1, 2, 99]


def test_has_trajectory_data_flag(tmp_path: Path):
    """``has_trajectory_data`` is True when any agent has a final
    position; False when every agent is profile-only."""
    sim_dir_with = tmp_path / "sim_with"
    sim_dir_with.mkdir()
    _write_reddit_profiles(sim_dir_with, [_make_profile(1)])
    _write_trajectory(sim_dir_with, [_make_snapshot(1, {1: {"topic": 0.4}})])
    payload_with = agent_export.build_agent_export("sim_with", str(sim_dir_with))
    assert payload_with["has_trajectory_data"] is True

    sim_dir_without = tmp_path / "sim_without"
    sim_dir_without.mkdir()
    _write_reddit_profiles(sim_dir_without, [_make_profile(1)])
    payload_without = agent_export.build_agent_export("sim_without", str(sim_dir_without))
    assert payload_without["has_trajectory_data"] is False


# ── Surface-key registration ─────────────────────────────────────────────


def test_agents_json_registered_in_surface_stats_keys():
    from app.services import surface_stats
    assert "agents_json" in surface_stats.SURFACE_KEYS


def test_agents_json_registered_in_surfaces_catalog_tracked_keys():
    from app.services import surfaces_catalog
    assert "agents_json" in surfaces_catalog._PER_SIM_TRACKED_KEYS
    # And appears in the catalog list.
    keys = {entry["key"] for entry in surfaces_catalog.get_surfaces_catalog()}
    assert "agents_json" in keys
