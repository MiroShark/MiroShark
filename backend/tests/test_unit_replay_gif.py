"""Unit tests for the animated belief-replay GIF renderer.

Pure offline — no Flask, no network, no simulation runner. Verifies:

  - the renderer returns valid GIF bytes for trajectory-bearing summaries,
  - empty / missing trajectories produce a single-frame poster GIF
    (so the endpoint never 500s on a freshly published READY run),
  - per-round percentages drive the rendered frame count,
  - oversized trajectories subsample to the MAX_FRAMES cap with the
    final round always preserved,
  - the cache key is deterministic and changes only when render-affecting
    fields change,
  - the cache key tolerates float jitter in the percentage series.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── GIF header helpers ─────────────────────────────────────────────────────


def _is_gif(data: bytes) -> bool:
    """GIF signature is GIF87a or GIF89a in the first 6 bytes."""
    return len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a")


def _gif_size(data: bytes) -> tuple[int, int]:
    """Logical screen width/height from bytes 6-10 (little-endian)."""
    assert _is_gif(data)
    width, height = struct.unpack("<HH", data[6:10])
    return width, height


def _gif_frame_count(data: bytes) -> int:
    """Count frames by reading the GIF with Pillow.

    Avoids hand-parsing the GCT / image descriptor blocks — Pillow's
    iterator already knows how to walk the chunks and the test has
    Pillow available anyway."""
    import io
    from PIL import Image, ImageSequence

    img = Image.open(io.BytesIO(data))
    return sum(1 for _ in ImageSequence.Iterator(img))


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def full_summary() -> dict:
    """20-round simulation summary — same shape as the embed-summary
    endpoint produces for a completed run."""
    rounds = list(range(1, 21))
    # Synthetic trajectory: bullish climbs 10→62, bearish drops 80→25
    bullish = [10.0 + i * 2.6 for i in range(20)]
    bearish = [80.0 - i * 2.7 for i in range(20)]
    neutral = [max(0.0, 100.0 - bullish[i] - bearish[i]) for i in range(20)]

    return {
        "simulation_id": "sim_abc123def456",
        "scenario": "Will the SEC approve a spot Solana ETF before the end of Q3 2026?",
        "total_rounds": 20,
        "current_round": 20,
        "is_public": True,
        "belief": {
            "rounds": rounds,
            "bullish": bullish,
            "neutral": neutral,
            "bearish": bearish,
            "final": {"bullish": bullish[-1], "neutral": neutral[-1], "bearish": bearish[-1]},
            "consensus_round": 14,
            "consensus_stance": "bullish",
        },
    }


# ── Renderer tests ─────────────────────────────────────────────────────────


def test_renders_animated_gif_for_full_trajectory(full_summary):
    from app.services.replay_gif import render_replay_gif

    gif = render_replay_gif(full_summary)
    assert _is_gif(gif)
    w, h = _gif_size(gif)
    assert (w, h) == (1200, 630)
    # 20 rounds → 20 frames (under MAX_FRAMES, no subsampling)
    assert _gif_frame_count(gif) == 20
    # A 20-frame 1200×630 GIF should land in the tens of KB at minimum;
    # blank-rendered GIFs would be ~1KB.
    assert len(gif) > 5000


def test_renders_poster_gif_when_trajectory_missing():
    """Freshly published READY runs may have no trajectory yet —
    the renderer must still produce a valid GIF (single-frame poster)
    rather than 500-ing the unfurler."""
    from app.services.replay_gif import render_replay_gif

    gif = render_replay_gif(
        {"simulation_id": "sim_x", "scenario": "Pending run", "is_public": True}
    )
    assert _is_gif(gif)
    assert _gif_size(gif) == (1200, 630)
    assert _gif_frame_count(gif) == 1


def test_renders_poster_gif_when_belief_arrays_empty():
    """Empty belief arrays — same as missing belief — should fall back
    to the poster, not crash on division-by-zero."""
    from app.services.replay_gif import render_replay_gif

    gif = render_replay_gif(
        {
            "simulation_id": "sim_y",
            "scenario": "Empty",
            "belief": {"rounds": [], "bullish": [], "neutral": [], "bearish": []},
        }
    )
    assert _is_gif(gif)
    assert _gif_frame_count(gif) == 1


def test_renders_with_long_scenario_wraps_without_crashing():
    from app.services.replay_gif import render_replay_gif

    summary = {
        "simulation_id": "sim_long",
        # Force the 2-line cap into ellipsis territory.
        "scenario": "Q1 2026 macro outlook — " + "very long word stream " * 30,
        "total_rounds": 3,
        "belief": {
            "rounds": [1, 2, 3],
            "bullish": [33.0, 50.0, 70.0],
            "neutral": [34.0, 30.0, 20.0],
            "bearish": [33.0, 20.0, 10.0],
        },
    }
    gif = render_replay_gif(summary)
    assert _is_gif(gif)
    assert _gif_frame_count(gif) == 3


def test_renders_with_single_round():
    """One-round simulation — must still produce a valid (single-frame)
    animated GIF, with the final-hold duration applied."""
    from app.services.replay_gif import render_replay_gif

    summary = {
        "simulation_id": "sim_one",
        "scenario": "Quick run",
        "total_rounds": 1,
        "belief": {
            "rounds": [1],
            "bullish": [40.0],
            "neutral": [30.0],
            "bearish": [30.0],
        },
    }
    gif = render_replay_gif(summary)
    assert _is_gif(gif)
    assert _gif_frame_count(gif) == 1


# ── Subsampling for oversized trajectories ────────────────────────────────


def test_subsamples_oversized_trajectory_to_cap():
    """A 200-round simulation must compress to the MAX_FRAMES cap so
    the GIF stays under ~1 minute of playback. Final round must always
    be preserved so the resting consensus stays visible."""
    from app.services.replay_gif import (
        MAX_FRAMES,
        extract_frames_from_summary,
        render_replay_gif,
    )

    rounds = list(range(1, 201))
    summary = {
        "simulation_id": "sim_huge",
        "scenario": "Long run",
        "total_rounds": 200,
        "belief": {
            "rounds": rounds,
            "bullish": [33.0] * 200,
            "neutral": [33.0] * 200,
            "bearish": [34.0] * 200,
        },
    }

    frames = extract_frames_from_summary(summary)
    assert len(frames) <= MAX_FRAMES
    # Final round always preserved.
    assert frames[-1]["round"] == 200
    # First round is always at index 0 (step 0 → round 1).
    assert frames[0]["round"] == 1

    gif = render_replay_gif(summary)
    assert _is_gif(gif)
    assert _gif_frame_count(gif) <= MAX_FRAMES


def test_extract_frames_passes_through_when_under_cap():
    from app.services.replay_gif import extract_frames_from_summary

    summary = {
        "belief": {
            "rounds": [1, 2, 3],
            "bullish": [10.0, 20.0, 30.0],
            "neutral": [50.0, 40.0, 30.0],
            "bearish": [40.0, 40.0, 40.0],
        }
    }
    frames = extract_frames_from_summary(summary)
    assert [f["round"] for f in frames] == [1, 2, 3]
    assert frames[-1]["bullish"] == 30.0
    assert frames[-1]["bearish"] == 40.0


def test_extract_frames_returns_empty_when_arrays_misaligned():
    """``rounds`` shorter than ``bullish`` should not produce phantom
    frames — extract takes the min length across all four series."""
    from app.services.replay_gif import extract_frames_from_summary

    summary = {
        "belief": {
            "rounds": [1, 2],
            "bullish": [10.0, 20.0, 30.0],
            "neutral": [10.0, 20.0, 30.0],
            "bearish": [10.0, 20.0, 30.0],
        }
    }
    frames = extract_frames_from_summary(summary)
    assert len(frames) == 2


def test_extract_frames_returns_empty_when_belief_missing():
    from app.services.replay_gif import extract_frames_from_summary

    assert extract_frames_from_summary({}) == []
    assert extract_frames_from_summary({"belief": None}) == []
    assert extract_frames_from_summary({"belief": {}}) == []


# ── Cache-key tests ────────────────────────────────────────────────────────


def test_cache_key_stable_across_calls(full_summary):
    from app.services.replay_gif import summary_cache_key

    a = summary_cache_key(full_summary)
    b = summary_cache_key(dict(full_summary))
    assert a == b
    assert len(a) == 16


def test_cache_key_changes_when_belief_changes(full_summary):
    from app.services.replay_gif import summary_cache_key

    base = summary_cache_key(full_summary)

    # Swap the final round's bullish — must bust the cache.
    new_belief = dict(full_summary["belief"])
    new_belief["bullish"] = list(full_summary["belief"]["bullish"])
    new_belief["bullish"][-1] = 90.0
    s2 = {**full_summary, "belief": new_belief}
    assert summary_cache_key(s2) != base


def test_cache_key_changes_when_scenario_changes(full_summary):
    from app.services.replay_gif import summary_cache_key

    base = summary_cache_key(full_summary)
    s2 = {**full_summary, "scenario": full_summary["scenario"] + "?"}
    assert summary_cache_key(s2) != base


def test_cache_key_tolerates_float_jitter(full_summary):
    """Floating-point noise below the 0.1 rounding threshold must not
    bust the cache — otherwise every read of trajectory.json that goes
    through ``json.load`` (different float repr depending on platform)
    could produce a fresh hash and re-render the GIF."""
    from app.services.replay_gif import summary_cache_key

    base = summary_cache_key(full_summary)

    new_belief = dict(full_summary["belief"])
    new_belief["bullish"] = [v + 0.0001 for v in full_summary["belief"]["bullish"]]
    s2 = {**full_summary, "belief": new_belief}
    assert summary_cache_key(s2) == base


def test_cache_key_ignores_non_render_fields(full_summary):
    from app.services.replay_gif import summary_cache_key

    base = summary_cache_key(full_summary)

    extra = {**full_summary, "parent_simulation_id": "sim_zzz", "extra_unused": [1, 2, 3]}
    assert summary_cache_key(extra) == base


# ── Endpoint shape ─────────────────────────────────────────────────────────


def test_route_decorator_registered():
    """Static check that the GIF endpoint exists in the Flask blueprint
    file — the OpenAPI drift test will still validate it end-to-end,
    but this guards against a code-review accidentally removing the
    handler without the spec test catching it."""
    sim_api = (
        _BACKEND / "app" / "api" / "simulation.py"
    ).read_text(encoding="utf-8")
    assert "@simulation_bp.route('/<simulation_id>/replay.gif'" in sim_api
    assert "render_replay_gif" in sim_api
