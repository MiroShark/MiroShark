"""Unit tests for the Twitter / X tweet thread formatter service.

Pure offline — no Flask, no network, no simulation runner, no on-disk
state outside ``tmp_path``. Cover the properties the
``thread.txt`` + ``thread.json`` endpoints depend on:

  1. ``STANCE_THRESHOLD`` matches the ±0.2 every other surface uses
     (gallery, share card, replay GIF, transcript, trajectory CSV,
     webhook, feed) — so a "bullish" inflection in the thread points
     at the same round a "bullish" pct on the share card does.
  2. ``find_inflection_points`` only emits flips of the dominant
     stance, with a small hysteresis on near-ties so a balanced
     simulation doesn't generate noise tweets.
  3. ``build_thread`` produces an intro + body + close with each
     tweet ≤280 characters, even on edge cases (long scenarios,
     no inflections, no agents, missing belief data).
  4. ``MAX_THREAD_TWEETS`` truncation kicks in for many-flip runs and
     emits a single bridge tweet between head + tail inflections.
  5. ``thread.txt`` and ``thread.json`` round-trip through the
     renderers without losing tweets or reordering them.
  6. The route decorators exist in ``app/api/simulation.py`` — the
     OpenAPI drift test will validate spec ↔ route equality, but this
     guards against an accidental decorator removal that the spec
     test wouldn't catch in isolation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def populated_sim_dir(tmp_path: Path) -> Path:
    """Sim directory with a 5-snapshot trajectory that has two clear
    dominant-stance flips:

      - round 1: 1 bullish, 1 neutral, 1 bearish ⇒ flat (no dominant)
      - round 2: 3 bullish, 0 neutral, 0 bearish ⇒ bullish dominant
      - round 3: 3 bullish, 0 neutral, 0 bearish ⇒ bullish (no flip)
      - round 4: 0 bullish, 0 neutral, 3 bearish ⇒ bearish (flip)
      - round 5: 0 bullish, 1 neutral, 2 bearish ⇒ bearish (no flip)

    Two inflections expected: round 2 (intro) + round 4 (flip).
    """
    (tmp_path / "trajectory.json").write_text(
        json.dumps(
            {
                "snapshots": [
                    {
                        "round_num": 1,
                        "belief_positions": {
                            "1": {"t": 0.5},
                            "2": {"t": 0.0},
                            "3": {"t": -0.5},
                        },
                    },
                    {
                        "round_num": 2,
                        "belief_positions": {
                            "1": {"t": 0.6},
                            "2": {"t": 0.5},
                            "3": {"t": 0.4},
                        },
                    },
                    {
                        "round_num": 3,
                        "belief_positions": {
                            "1": {"t": 0.6},
                            "2": {"t": 0.5},
                            "3": {"t": 0.4},
                        },
                    },
                    {
                        "round_num": 4,
                        "belief_positions": {
                            "1": {"t": -0.6},
                            "2": {"t": -0.5},
                            "3": {"t": -0.4},
                        },
                    },
                    {
                        "round_num": 5,
                        "belief_positions": {
                            "1": {"t": 0.0},
                            "2": {"t": -0.5},
                            "3": {"t": -0.4},
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def summary_for_populated() -> dict:
    """The same shape ``_build_embed_summary_payload`` returns for the
    populated simulation. Final stance lines up with round 5 (bearish
    dominant in our fixture)."""
    return {
        "simulation_id": "sim_t1",
        "scenario": "Will the SEC approve a spot Solana ETF before Q4 2026?",
        "is_public": True,
        "status": "completed",
        "runner_status": "completed",
        "current_round": 5,
        "total_rounds": 5,
        "profiles_count": 3,
        "belief": {
            "rounds": [1, 2, 3, 4, 5],
            "bullish": [33.3, 100.0, 100.0, 0.0, 0.0],
            "neutral": [33.3, 0.0, 0.0, 0.0, 33.3],
            "bearish": [33.3, 0.0, 0.0, 100.0, 66.7],
            "final": {"bullish": 0.0, "neutral": 33.3, "bearish": 66.7},
            "consensus_round": 4,
            "consensus_stance": "bearish",
        },
        "quality": {"health": "Good", "participation_rate": 0.78},
    }


@pytest.fixture
def summary_no_belief() -> dict:
    """A published sim with no recorded trajectory yet. The thread should
    still produce intro + close (with "split" consensus) without crashing."""
    return {
        "simulation_id": "sim_t2",
        "scenario": "Will the Fed cut by 25bps in June 2026?",
        "is_public": True,
        "status": "running",
        "runner_status": "running",
        "current_round": 0,
        "total_rounds": 30,
        "profiles_count": 24,
        "belief": None,
        "quality": None,
    }


# ── STANCE_THRESHOLD parity ────────────────────────────────────────────────


def test_stance_threshold_matches_other_surfaces():
    """The thread's inflection detection must read the same ±0.2
    threshold every other surface uses; otherwise a 'shifted to
    bullish' tweet would point at a round the gallery card disagrees
    on."""
    from app.services.thread_formatter import STANCE_THRESHOLD

    assert STANCE_THRESHOLD == 0.2


# ── Dominant-stance helper ────────────────────────────────────────────────


def test_dominant_stance_picks_clear_leader():
    from app.services.thread_formatter import dominant_stance

    assert dominant_stance({"bullish": 70, "neutral": 20, "bearish": 10}) == "bullish"
    assert dominant_stance({"bullish": 10, "neutral": 30, "bearish": 60}) == "bearish"


def test_dominant_stance_returns_none_on_near_tie():
    """Hysteresis: a runner-up within 0.2pp returns None — keeps the
    thread from emitting noise inflections on a balanced sim."""
    from app.services.thread_formatter import dominant_stance

    # 49.9 vs 50.0 — under the 0.2pp guard.
    assert dominant_stance({"bullish": 50.0, "neutral": 49.9, "bearish": 0.1}) is None


def test_dominant_stance_returns_none_on_zeros():
    """A flat all-zero split (e.g. round with no agents) returns None
    rather than picking 'bullish' by lexical tiebreak."""
    from app.services.thread_formatter import dominant_stance

    assert dominant_stance({"bullish": 0.0, "neutral": 0.0, "bearish": 0.0}) is None


# ── Inflection detection ───────────────────────────────────────────────────


def test_find_inflection_points_emits_first_dominant_round(populated_sim_dir: Path):
    from app.services.thread_formatter import _build_round_series, find_inflection_points

    rows = _build_round_series(str(populated_sim_dir))
    inflections = find_inflection_points(rows)
    # Round 1 is flat ⇒ skipped; round 2 introduces bullish; round 4
    # flips to bearish; round 3 / 5 are continuation, not inflections.
    assert [(i["round"], i["dominant"]) for i in inflections] == [
        (2, "bullish"),
        (4, "bearish"),
    ]


def test_find_inflection_points_skips_no_dominant_rounds():
    """A trajectory that's flat the whole way through produces zero
    inflections — the thread will be intro + close only."""
    from app.services.thread_formatter import find_inflection_points

    rows = [
        {"round": 1, "split": {"bullish": 33.3, "neutral": 33.3, "bearish": 33.3}, "dominant": None},
        {"round": 2, "split": {"bullish": 33.3, "neutral": 33.3, "bearish": 33.3}, "dominant": None},
    ]
    assert find_inflection_points(rows) == []


# ── build_thread → tweet structure ────────────────────────────────────────


def test_build_thread_produces_intro_inflections_close(
    populated_sim_dir: Path, summary_for_populated: dict
):
    from app.services.thread_formatter import build_thread

    thread = build_thread(
        sim_dir=str(populated_sim_dir),
        summary=summary_for_populated,
        watch_url="https://example.com/watch/sim_t1",
        share_url="https://example.com/share/sim_t1",
    )
    # 2 inflections + intro + close = 4 tweets.
    assert thread["total"] == 4
    assert thread["truncated"] is False
    assert thread["inflections_recorded"] == 2
    # Intro carries the scenario.
    assert "Solana ETF" in thread["tweets"][0]
    # Body tweets reference the inflection rounds.
    assert "Round 2" in thread["tweets"][1] or "Round 2" in thread["tweets"][2]
    assert "Round 4" in thread["tweets"][1] or "Round 4" in thread["tweets"][2]
    # Close carries both URLs.
    assert "https://example.com/watch/sim_t1" in thread["tweets"][-1]
    assert "https://example.com/share/sim_t1" in thread["tweets"][-1]


def test_every_tweet_under_280_chars(
    populated_sim_dir: Path, summary_for_populated: dict
):
    from app.services.thread_formatter import build_thread, MAX_TWEET_CHARS

    thread = build_thread(
        sim_dir=str(populated_sim_dir),
        summary=summary_for_populated,
        watch_url="https://example.com/watch/sim_t1",
        share_url="https://example.com/share/sim_t1",
    )
    for i, tw in enumerate(thread["tweets"]):
        assert len(tw) <= MAX_TWEET_CHARS, f"tweet {i} exceeds {MAX_TWEET_CHARS}: len={len(tw)}\n{tw}"


def test_long_scenario_truncated_into_intro(populated_sim_dir: Path):
    """A 1000-character scenario must still produce an intro tweet that
    fits under 280 chars and ends with an ellipsis."""
    from app.services.thread_formatter import build_thread, MAX_TWEET_CHARS

    long_scenario = (
        "Will any of the following events happen before Q4 2026: "
        "(a) the SEC approves a spot Solana ETF, (b) the EU finalises "
        "MiCA-2 with a clarified treatment of restaking yields, (c) "
        "Tether publishes a fully audited reserve attestation under "
        "PCAOB standards, (d) a major prime broker offers DeFi-native "
        "cash management to U.S. registered investment advisors at "
        "scale, (e) a hardware-attested private key custody scheme is "
        "endorsed by FATF, (f) at least one G7 central bank publishes "
        "a public roadmap for native CBDC issuance with retail wallets?"
    )
    summary = {
        "simulation_id": "sim_long",
        "scenario": long_scenario,
        "is_public": True,
        "runner_status": "completed",
        "status": "completed",
        "current_round": 5,
        "total_rounds": 5,
        "profiles_count": 3,
        "belief": {"final": {"bullish": 50, "neutral": 30, "bearish": 20}},
        "quality": None,
    }
    thread = build_thread(
        sim_dir=str(populated_sim_dir),
        summary=summary,
        watch_url="https://example.com/watch/sim_long",
        share_url="https://example.com/share/sim_long",
    )
    intro = thread["tweets"][0]
    assert len(intro) <= MAX_TWEET_CHARS
    assert "…" in intro


def test_no_belief_falls_back_to_split_close(summary_no_belief: dict, tmp_path: Path):
    """A pre-run sim has no trajectory.json — the thread must still
    produce intro + close without raising."""
    from app.services.thread_formatter import build_thread

    thread = build_thread(
        sim_dir=str(tmp_path),  # empty dir — no trajectory.json
        summary=summary_no_belief,
        watch_url="https://example.com/watch/sim_t2",
        share_url="https://example.com/share/sim_t2",
    )
    assert thread["total"] == 2  # intro + close, zero inflections
    assert thread["inflections_recorded"] == 0
    # "split" consensus when no belief data is present yet.
    assert "Final: Split" in thread["tweets"][-1] or "split" in thread["tweets"][-1].lower()


def test_corrupt_trajectory_does_not_raise(tmp_path: Path, summary_for_populated: dict):
    """A malformed trajectory.json must degrade to intro + close
    rather than 500-ing the route."""
    from app.services.thread_formatter import build_thread

    (tmp_path / "trajectory.json").write_text("not json", encoding="utf-8")
    thread = build_thread(
        sim_dir=str(tmp_path),
        summary=summary_for_populated,
        watch_url="https://example.com/watch/sim_t3",
        share_url="https://example.com/share/sim_t3",
    )
    assert thread["total"] >= 2
    assert thread["inflections_recorded"] == 0


# ── Truncation ────────────────────────────────────────────────────────────


def test_thread_truncates_to_head_tail_with_bridge(tmp_path: Path):
    """A trajectory with many flips must produce a thread under
    ``MAX_THREAD_TWEETS`` with a single bridge line between the head
    and tail inflections."""
    from app.services.thread_formatter import build_thread, MAX_THREAD_TWEETS

    # Alternate stance every round across 20 rounds — round 1 introduces
    # bullish (first inflection), rounds 2..20 each flip the dominant
    # stance, for 20 inflections total.
    snapshots = []
    for r in range(1, 21):
        sign = 1 if r % 2 == 1 else -1
        val = 0.6 * sign
        snapshots.append(
            {
                "round_num": r,
                "belief_positions": {
                    "1": {"t": val},
                    "2": {"t": val},
                    "3": {"t": val},
                },
            }
        )
    (tmp_path / "trajectory.json").write_text(
        json.dumps({"snapshots": snapshots}), encoding="utf-8"
    )

    summary = {
        "simulation_id": "sim_busy",
        "scenario": "Busy scenario",
        "is_public": True,
        "runner_status": "completed",
        "status": "completed",
        "current_round": 20,
        "total_rounds": 20,
        "profiles_count": 3,
        "belief": {"final": {"bullish": 0, "neutral": 0, "bearish": 100}},
        "quality": None,
    }
    thread = build_thread(
        sim_dir=str(tmp_path),
        summary=summary,
        watch_url="https://example.com/watch/sim_busy",
        share_url="https://example.com/share/sim_busy",
    )
    assert thread["truncated"] is True
    assert thread["total"] <= MAX_THREAD_TWEETS
    # 20 inflections (round 1 introduces bullish; rounds 2..20 each flip).
    assert thread["inflections_recorded"] == 20
    # Bridge line carries the skipped count: 20 - 3 (head) - 3 (tail) = 14.
    bridge = next((t for t in thread["tweets"] if "more flips" in t), None)
    assert bridge is not None
    assert "14 more flips" in bridge


# ── Renderers ─────────────────────────────────────────────────────────────


def test_render_thread_txt_separator_and_terminator(populated_sim_dir: Path, summary_for_populated: dict):
    from app.services.thread_formatter import build_thread, render_thread_txt

    thread = build_thread(
        sim_dir=str(populated_sim_dir),
        summary=summary_for_populated,
        watch_url="https://example.com/watch/sim_t1",
        share_url="https://example.com/share/sim_t1",
    )
    body = render_thread_txt(thread).decode("utf-8")
    # Trailing newline so the bytes write cleanly to a POSIX file.
    assert body.endswith("\n")
    # Tweets separated by ``---`` on its own line.
    assert "\n---\n" in body
    # Tweets count via separator: N-1 separators ⇒ N tweets.
    assert body.count("\n---\n") == thread["total"] - 1


def test_render_thread_json_round_trip(populated_sim_dir: Path, summary_for_populated: dict):
    from app.services.thread_formatter import build_thread, render_thread_json

    thread = build_thread(
        sim_dir=str(populated_sim_dir),
        summary=summary_for_populated,
        watch_url="https://example.com/watch/sim_t1",
        share_url="https://example.com/share/sim_t1",
    )
    parsed = json.loads(render_thread_json(thread).decode("utf-8"))
    assert parsed["total"] == thread["total"]
    assert parsed["inflections_recorded"] == thread["inflections_recorded"]
    assert parsed["truncated"] == thread["truncated"]
    assert parsed["tweets"] == thread["tweets"]


# ── Module-presence guards ────────────────────────────────────────────────


def test_thread_routes_registered_on_simulation_blueprint():
    """Sanity guard alongside the OpenAPI drift test — the
    ``thread.txt`` and ``thread.json`` decorators must exist in
    ``app/api/simulation.py``. The drift test in
    ``test_unit_openapi.py`` validates the spec matches; this one
    confirms the source side hasn't been accidentally renamed."""
    from app.api import simulation as sim_module
    import inspect

    src = inspect.getsource(sim_module)
    assert "@simulation_bp.route('/<simulation_id>/thread.txt'" in src
    assert "@simulation_bp.route('/<simulation_id>/thread.json'" in src
