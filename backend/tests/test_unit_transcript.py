"""Unit tests for the simulation transcript export service.

Pure offline — no Flask, no network, no simulation runner. Cover the
five properties the transcript endpoints depend on:

  1. ``build_transcript_data`` produces a clean payload from the same
     on-disk artifacts the share card + replay GIF + gallery card
     consume, and degrades gracefully when files are missing or
     malformed (the route handlers must never 500 on the assembly step).
  2. The ±0.2 stance threshold matches what the embed summary, share
     card, replay GIF, gallery card, and webhook all use — a "bullish"
     agent in the transcript is the same agent's tag everywhere else.
  3. The Markdown renderer always returns a well-formed document with a
     YAML front-matter block (so Notion / Obsidian / Bear pick up
     metadata) and at least one ``## Round`` block per recorded round.
  4. The Markdown renderer truncates oversized trajectories (>80
     rounds) but always preserves the head + tail and emits a
     "skipped N rounds" annotation, so the resting consensus stays
     visible.
  5. The route decorators exist in ``app/api/simulation.py`` — the
     OpenAPI drift test will validate spec ↔ route equality, but this
     guards against an accidental decorator removal that the spec test
     wouldn't catch in isolation.
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


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def populated_sim_dir(tmp_path: Path) -> Path:
    """Simulation directory with the artifacts the transcript reads:
    profiles, trajectory (3 snapshots, viral_posts on each), quality,
    resolution, outcome."""
    (tmp_path / "reddit_profiles.json").write_text(json.dumps([
        {"user_id": 1, "username": "sarahc", "name": "Sarah Chen", "bio": "analyst"},
        {"user_id": 2, "username": "miker",  "name": "Mike Rodriguez", "bio": "trader"},
        {"user_id": 3, "username": "ja",     "name": "Jamal Adeyemi", "bio": "researcher"},
    ]), encoding="utf-8")
    (tmp_path / "polymarket_profiles.json").write_text(json.dumps([
        {"user_id": 4, "name": "Elena Park", "description": "trader"},
    ]), encoding="utf-8")
    (tmp_path / "quality.json").write_text(json.dumps({
        "health": "excellent",
        "participation_rate": 0.92,
    }), encoding="utf-8")
    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {
                "round_num": 1,
                "timestamp": "2026-04-29T10:00:00Z",
                "total_posts_created": 4,
                "total_engagements": 12,
                "active_agent_count": 3,
                "belief_positions": {
                    "1": {"topic_a": 0.0,  "topic_b": -0.1},
                    "2": {"topic_a": -0.5, "topic_b": -0.4},
                    "3": {"topic_a": 0.3,  "topic_b": 0.4},
                },
                "viral_posts": [
                    {"post_id": 11, "user_id": 1, "content": "Looking at the protocol's TVL curve over the last 6 hours, this could be the same MEV exploit pattern from Euler. Or just normal weekend rebalancing.", "num_likes": 4, "num_dislikes": 1},
                    {"post_id": 12, "user_id": 2, "content": "TVL drawdown matches the Euler exploit signature. Withdrawing.", "num_likes": 6, "num_dislikes": 0},
                ],
            },
            {
                "round_num": 2,
                "timestamp": "2026-04-29T10:01:00Z",
                "total_posts_created": 5,
                "total_engagements": 18,
                "active_agent_count": 3,
                "belief_positions": {
                    "1": {"topic_a": -0.4, "topic_b": -0.5},
                    "2": {"topic_a": -0.7, "topic_b": -0.6},
                    "3": {"topic_a": -0.3, "topic_b": -0.2},
                },
                "viral_posts": [
                    {"post_id": 21, "user_id": 3, "content": "Reversing my call — saw the multisig drain.", "num_likes": 9, "num_dislikes": 0},
                ],
            },
            {
                "round_num": 3,
                "timestamp": "2026-04-29T10:02:00Z",
                "total_posts_created": 3,
                "total_engagements": 22,
                "active_agent_count": 4,
                "belief_positions": {
                    "1": {"topic_a": -0.6},
                    "2": {"topic_a": -0.8},
                    "3": {"topic_a": -0.5},
                    "4": {"topic_a": -0.7},
                },
                "viral_posts": [
                    {"post_id": 31, "user_id": 4, "content": "Polymarket bid hit 88c on YES_HALT.", "num_likes": 11, "num_dislikes": 1},
                ],
            },
        ],
    }), encoding="utf-8")
    (tmp_path / "outcome.json").write_text(json.dumps({
        "label": "correct",
        "outcome_url": "https://example.com/aave-halted",
        "outcome_summary": "Aave halted withdrawals 2 hours after the simulation closed.",
        "submitted_at": "2026-04-29T12:00:00Z",
    }), encoding="utf-8")
    return tmp_path


@pytest.fixture
def populated_summary() -> dict:
    """The same dict ``_build_embed_summary_payload`` returns for the
    populated simulation."""
    return {
        "simulation_id": "sim_aave_001",
        "scenario": "A major lending protocol has paused withdrawals following anomalous outflows exceeding $200M in 4 hours.",
        "status": "completed",
        "runner_status": "finished",
        "current_round": 3,
        "total_rounds": 3,
        "profiles_count": 3,
        "created_date": "2026-04-29",
        "is_public": True,
        "belief": {
            "rounds": [1, 2, 3],
            "bullish": [33.3, 0.0, 0.0],
            "neutral": [33.3, 0.0, 0.0],
            "bearish": [33.3, 100.0, 100.0],
            "final": {"bullish": 0.0, "neutral": 0.0, "bearish": 100.0},
            "consensus_round": 2,
            "consensus_stance": "bearish",
        },
        "quality": {"health": "excellent", "participation_rate": 0.92},
        "resolution": None,
    }


# ── Stance bucketing ───────────────────────────────────────────────────────


def test_classify_stance_uses_same_threshold_as_other_surfaces():
    from app.services.transcript import _classify_stance, STANCE_THRESHOLD

    assert STANCE_THRESHOLD == 0.2
    assert _classify_stance(0.21) == "bullish"
    assert _classify_stance(-0.21) == "bearish"
    assert _classify_stance(0.2) == "neutral"
    assert _classify_stance(-0.2) == "neutral"
    assert _classify_stance(0.0) == "neutral"


def test_classify_stance_handles_garbage():
    from app.services.transcript import _classify_stance

    assert _classify_stance(None) == "neutral"
    assert _classify_stance("not-a-number") == "neutral"


# ── Profile name resolution ────────────────────────────────────────────────


def test_load_profile_names_merges_reddit_and_polymarket(populated_sim_dir):
    from app.services.transcript import _load_profile_names

    names = _load_profile_names(str(populated_sim_dir))
    assert names[1] == "Sarah Chen"
    assert names[2] == "Mike Rodriguez"
    assert names[3] == "Jamal Adeyemi"
    # Polymarket-only id should still resolve so its viral_posts get
    # a real name in the transcript.
    assert names[4] == "Elena Park"


def test_load_profile_names_missing_dir_is_empty(tmp_path):
    from app.services.transcript import _load_profile_names

    assert _load_profile_names(str(tmp_path)) == {}


def test_load_profile_names_skips_corrupt_rows(tmp_path):
    from app.services.transcript import _load_profile_names

    (tmp_path / "reddit_profiles.json").write_text(json.dumps([
        {"user_id": "not-an-int", "name": "Bad"},
        {"user_id": 7, "name": ""},          # empty name → skip
        {"user_id": 8, "name": "Good"},
    ]), encoding="utf-8")
    names = _load_profile_names(str(tmp_path))
    assert names == {8: "Good"}


# ── Transcript data assembly ───────────────────────────────────────────────


def test_build_transcript_data_full_pipeline(populated_sim_dir, populated_summary):
    from app.services.transcript import build_transcript_data

    data = build_transcript_data(populated_summary, str(populated_sim_dir))

    assert data["sim_id"] == "sim_aave_001"
    assert data["scenario"].startswith("A major lending protocol")
    assert data["agent_count"] == 3
    assert data["total_rounds"] == 3
    assert data["rounds_recorded"] == 3
    assert data["consensus"]["label"] == "bearish"
    assert data["consensus"]["round"] == 2
    assert data["quality"]["health"] == "excellent"
    assert data["outcome"]["label"] == "correct"
    assert data["outcome"]["outcome_url"] == "https://example.com/aave-halted"

    assert len(data["rounds"]) == 3
    r1 = data["rounds"][0]
    assert r1["round"] == 1
    assert r1["total_posts"] == 4
    assert len(r1["posts"]) == 2
    # Sarah's avg position is (-0.05) → neutral; Mike's avg is -0.45 → bearish
    sarah = next(p for p in r1["posts"] if p["agent_name"] == "Sarah Chen")
    mike = next(p for p in r1["posts"] if p["agent_name"] == "Mike Rodriguez")
    assert sarah["stance"] == "neutral"
    assert mike["stance"] == "bearish"
    # Stance split is computed from the same threshold — round 1 is
    # 1 bullish (Jamal) / 1 neutral (Sarah) / 1 bearish (Mike).
    assert r1["stance_split"]["bullish"] == pytest.approx(33.3, abs=0.5)
    assert r1["stance_split"]["bearish"] == pytest.approx(33.3, abs=0.5)


def test_build_transcript_data_resolves_polymarket_only_agent(populated_sim_dir, populated_summary):
    """A viral post by a polymarket-only agent (user_id 4 in the
    fixture) must come through with the real name, not ``Agent 4``."""
    from app.services.transcript import build_transcript_data

    data = build_transcript_data(populated_summary, str(populated_sim_dir))
    r3 = data["rounds"][2]
    elena = r3["posts"][0]
    assert elena["agent_name"] == "Elena Park"
    assert elena["agent_id"] == 4


def test_build_transcript_data_missing_trajectory(tmp_path, populated_summary):
    """A freshly published READY run hasn't snapshotted yet — the
    transcript must still assemble (with empty rounds) rather than
    raise. Mirrors the same posture the replay GIF takes."""
    from app.services.transcript import build_transcript_data

    data = build_transcript_data(populated_summary, str(tmp_path))
    assert data["rounds"] == []
    assert data["rounds_recorded"] == 0
    # Consensus still falls back to the embed summary's belief block.
    assert data["consensus"]["label"] == "bearish"


def test_build_transcript_data_corrupt_outcome_silently_ignored(populated_sim_dir, populated_summary):
    from app.services.transcript import build_transcript_data

    (populated_sim_dir / "outcome.json").write_text("{ this is not json", encoding="utf-8")
    data = build_transcript_data(populated_summary, str(populated_sim_dir))
    assert data["outcome"] is None


def test_build_transcript_data_strips_unsafe_outcome_url(populated_sim_dir, populated_summary):
    """Defense-in-depth: a corrupt outcome with a ``javascript:`` URL
    must come out empty rather than landing on the transcript. Mirrors
    the gallery card's defense."""
    from app.services.transcript import build_transcript_data

    (populated_sim_dir / "outcome.json").write_text(json.dumps({
        "label": "correct",
        "outcome_url": "javascript:alert(1)",
        "outcome_summary": "fine",
    }), encoding="utf-8")
    data = build_transcript_data(populated_summary, str(populated_sim_dir))
    assert data["outcome"] is not None
    assert data["outcome"]["outcome_url"] == ""


def test_build_transcript_data_excerpts_long_posts(tmp_path):
    """Posts longer than the per-post char cap get the ellipsis."""
    from app.services.transcript import (
        POST_EXCERPT_CHARS,
        build_transcript_data,
    )

    long_text = "word " * 200  # well over 400 chars
    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {
                "round_num": 1,
                "belief_positions": {"1": {"t": 0.0}},
                "viral_posts": [
                    {"post_id": 1, "user_id": 1, "content": long_text, "num_likes": 0, "num_dislikes": 0},
                ],
            }
        ],
    }), encoding="utf-8")
    summary = {
        "simulation_id": "sim_long",
        "scenario": "x",
        "is_public": True,
        "profiles_count": 1,
        "total_rounds": 1,
        "belief": {"final": {"bullish": 0.0, "neutral": 100.0, "bearish": 0.0}},
    }
    data = build_transcript_data(summary, str(tmp_path))
    body = data["rounds"][0]["posts"][0]["content"]
    assert body.endswith("…")
    # Ellipsis adds 1 char beyond the cap; word-boundary trim is at
    # most 30 chars before the cap, so the body is bounded.
    assert len(body) <= POST_EXCERPT_CHARS + 1


# ── Markdown renderer ─────────────────────────────────────────────────────


def test_render_markdown_has_yaml_front_matter(populated_sim_dir, populated_summary):
    from app.services.transcript import build_transcript_data, render_markdown

    md = render_markdown(build_transcript_data(populated_summary, str(populated_sim_dir)))

    # Front matter delimiters at start of doc.
    assert md.startswith("---\n")
    end_idx = md.index("\n---\n", 4)
    front = md[4:end_idx]
    # Notion / Obsidian look for these specific keys; pin them.
    for key in (
        "sim_id:",
        "scenario:",
        "agent_count:",
        "total_rounds:",
        "rounds_recorded:",
        "consensus_label:",
        "source: MiroShark",
    ):
        assert key in front, f"front matter missing `{key}` line"


def test_render_markdown_escapes_quotes_and_newlines_in_scenario(tmp_path):
    """A scenario containing a double quote or an embedded newline
    must produce parseable YAML — otherwise tools that read the front
    matter (Obsidian, Bear, Substack) error on import."""
    from app.services.transcript import build_transcript_data, render_markdown

    summary = {
        "simulation_id": "sim_q",
        "scenario": 'A "quoted" headline\nwith a newline',
        "is_public": True,
        "profiles_count": 0,
        "total_rounds": 0,
        "belief": {"final": {"bullish": 0.0, "neutral": 100.0, "bearish": 0.0}},
    }
    md = render_markdown(build_transcript_data(summary, str(tmp_path)))
    front = md.split("\n---\n", 1)[0]
    scenario_line = next(line for line in front.splitlines() if line.startswith("scenario:"))
    # Embedded `"` must be escaped, embedded newline must be flattened.
    assert '\\"quoted\\"' in scenario_line
    assert "\n" not in scenario_line


def test_render_markdown_emits_one_section_per_recorded_round(populated_sim_dir, populated_summary):
    from app.services.transcript import build_transcript_data, render_markdown

    md = render_markdown(build_transcript_data(populated_summary, str(populated_sim_dir)))
    headings = re.findall(r"^## Round \d+", md, flags=re.MULTILINE)
    assert headings == ["## Round 1", "## Round 2", "## Round 3"]
    # Posts render as block quotes with a `### Agent — *stance*` header.
    assert "### Sarah Chen — *neutral*" in md
    assert "### Mike Rodriguez — *bearish*" in md
    assert "### Elena Park — *bearish*" in md
    # Engagement footer line.
    assert "❤" in md


def test_render_markdown_includes_outcome_and_quality(populated_sim_dir, populated_summary):
    from app.services.transcript import build_transcript_data, render_markdown

    md = render_markdown(build_transcript_data(populated_summary, str(populated_sim_dir)))
    assert "Verified outcome" in md
    assert "Aave halted withdrawals" in md
    assert "https://example.com/aave-halted" in md
    assert "**Quality.**" in md
    assert "92% participation" in md


def test_render_markdown_handles_no_rounds(tmp_path):
    """READY simulation with no snapshots — the document must still be
    coherent (header + consensus block) rather than an empty file."""
    from app.services.transcript import build_transcript_data, render_markdown

    summary = {
        "simulation_id": "sim_pending",
        "scenario": "Pending",
        "is_public": True,
        "profiles_count": 5,
        "total_rounds": 10,
        "belief": {"final": {"bullish": 50.0, "neutral": 25.0, "bearish": 25.0}},
    }
    md = render_markdown(build_transcript_data(summary, str(tmp_path)))
    assert "MiroShark Simulation Transcript" in md
    assert "## Consensus" in md
    assert "No round snapshots recorded yet" in md


def test_render_markdown_truncates_oversized_runs(tmp_path):
    """200-round runs must elide the middle but keep the first 20 +
    last 20 + a "skipped N rounds" annotation. Final round must
    always be visible so the resting consensus reads."""
    from app.services.transcript import (
        MAX_MD_ROUNDS,
        build_transcript_data,
        render_markdown,
    )

    snaps = [
        {
            "round_num": i,
            "belief_positions": {"1": {"t": 0.0}},
            "viral_posts": [
                {"post_id": i, "user_id": 1, "content": f"round {i} note", "num_likes": 0, "num_dislikes": 0},
            ],
        }
        for i in range(1, 201)
    ]
    (tmp_path / "trajectory.json").write_text(json.dumps({"snapshots": snaps}), encoding="utf-8")
    (tmp_path / "reddit_profiles.json").write_text(json.dumps([
        {"user_id": 1, "name": "Solo"},
    ]), encoding="utf-8")

    summary = {
        "simulation_id": "sim_huge",
        "scenario": "Long run",
        "is_public": True,
        "profiles_count": 1,
        "total_rounds": 200,
        "belief": {"final": {"bullish": 0.0, "neutral": 100.0, "bearish": 0.0}},
    }
    data = build_transcript_data(summary, str(tmp_path))
    # JSON form keeps every round.
    assert data["rounds_recorded"] == 200
    assert len(data["rounds"]) == 200

    md = render_markdown(data)
    headings = re.findall(r"^## Round (\d+)", md, flags=re.MULTILINE)
    nums = [int(h) for h in headings]
    # Markdown must keep first + last and clip the middle.
    assert 1 in nums
    assert 200 in nums
    assert len(nums) <= MAX_MD_ROUNDS
    assert "middle rounds omitted" in md


# ── JSON renderer ──────────────────────────────────────────────────────────


def test_render_json_bytes_is_pretty_utf8(populated_sim_dir, populated_summary):
    from app.services.transcript import build_transcript_data, render_json_bytes

    data = build_transcript_data(populated_summary, str(populated_sim_dir))
    raw = render_json_bytes(data)
    assert isinstance(raw, bytes)
    text = raw.decode("utf-8")
    parsed = json.loads(text)
    # Round trip preserves the structured payload.
    assert parsed["sim_id"] == data["sim_id"]
    assert parsed["rounds"][0]["posts"][0]["agent_name"] == "Sarah Chen"
    # Pretty-printed (indent=2) — first-level keys land on their own line.
    assert "\n  " in text


# ── Endpoint shape (decorator presence guard) ─────────────────────────────


def test_route_decorators_registered():
    """Static check that both transcript endpoints exist in the Flask
    blueprint file. The OpenAPI drift test will validate the spec ↔
    route equality, but this guards against an accidental decorator
    removal that the spec test wouldn't catch in isolation (e.g. the
    decorator is removed AND the spec is updated to drop the path)."""
    sim_api = (
        _BACKEND / "app" / "api" / "simulation.py"
    ).read_text(encoding="utf-8")
    assert "@simulation_bp.route('/<simulation_id>/transcript.md'" in sim_api
    assert "@simulation_bp.route('/<simulation_id>/transcript.json'" in sim_api
    assert "transcript.build_transcript_data" in sim_api or "build_transcript_data" in sim_api
