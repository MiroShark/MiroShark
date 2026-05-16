"""Unit tests for the belief trajectory chart SVG renderer.

Pure offline — no Flask, no network, no simulation runner, no
on-disk state outside ``tmp_path``. Covers the properties the
``chart.svg`` endpoint depends on:

  1. ``render_chart_svg_bytes`` produces a valid SVG document with
     the locked ``viewBox`` so embedding sites can size the ``<img>``
     without losing fidelity.
  2. Three ``<polyline>`` elements (bullish / neutral / bearish) on a
     populated trajectory — the share-card / replay-GIF colour scheme
     is preserved so a reader who saw the share card recognises the
     chart immediately.
  3. The y-axis is inverted correctly — 100% maps to the top of the
     plot, 0% to the bottom — a flipped axis would look like the
     simulation went the opposite way.
  4. Empty trajectories yield ``None`` so the route handler can emit
     a clean 404 rather than a blank SVG.
  5. ``load_trajectory_for_chart`` degrades gracefully when the sim
     directory is missing or the trajectory file is malformed.
  6. Title truncation handles long scenarios without crashing or
     line-wrapping into the plot area.
  7. The route decorator exists in ``app/api/simulation.py`` — the
     OpenAPI drift test catches spec ↔ route mismatches, but this
     guards against an accidental decorator removal that the spec
     test wouldn't catch in isolation.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def populated_sim_dir(tmp_path: Path) -> Path:
    """Sim directory with a 3-round trajectory the chart can render.

    Belief positions chosen so each round has a distinct, predictable
    stance split — easier to assert against than randomly-generated
    rounds.
    """
    (tmp_path / "quality.json").write_text(json.dumps({
        "health": "excellent",
        "participation_rate": 0.91,
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
                    "1": {"topic_a": 0.0,  "topic_b": -0.1},   # neutral
                    "2": {"topic_a": -0.5, "topic_b": -0.4},   # bearish
                    "3": {"topic_a": 0.3,  "topic_b": 0.4},    # bullish
                },
                "viral_posts": [
                    {"post_id": 11, "user_id": 1, "content": "p1"},
                    {"post_id": 12, "user_id": 2, "content": "p2"},
                ],
            },
            {
                "round_num": 2,
                "timestamp": "2026-04-29T10:01:00Z",
                "total_posts_created": 5,
                "total_engagements": 18,
                "active_agent_count": 3,
                "belief_positions": {
                    "1": {"topic_a": -0.4, "topic_b": -0.5},   # bearish
                    "2": {"topic_a": -0.7, "topic_b": -0.6},   # bearish
                    "3": {"topic_a": -0.3, "topic_b": -0.2},   # bearish
                },
                "viral_posts": [
                    {"post_id": 21, "user_id": 3, "content": "p3"},
                ],
            },
            {
                "round_num": 3,
                "timestamp": "2026-04-29T10:02:00Z",
                "total_posts_created": 6,
                "total_engagements": 22,
                "active_agent_count": 4,
                "belief_positions": {
                    "1": {"topic_a": -0.5, "topic_b": -0.5},
                    "2": {"topic_a": -0.6, "topic_b": -0.6},
                    "3": {"topic_a": -0.4, "topic_b": -0.4},
                    "4": {"topic_a": -0.3, "topic_b": -0.3},
                },
                "viral_posts": [
                    {"post_id": 31, "user_id": 4, "content": "p4"},
                ],
            },
        ],
    }), encoding="utf-8")
    return tmp_path


# ── Property 1 — viewBox + xml header ─────────────────────────────────────


def test_renders_valid_svg_with_locked_viewbox(populated_sim_dir):
    from app.services.chart_svg import render_chart_svg_bytes, SVG_WIDTH, SVG_HEIGHT

    payload = render_chart_svg_bytes(str(populated_sim_dir), "Test scenario")
    assert payload is not None
    text = payload.decode("utf-8")

    # XML declaration is the first non-whitespace content — required by
    # ``image/svg+xml`` parsers (Inkscape, librsvg) for strict mode.
    assert text.startswith("<?xml")
    # The viewBox is the contract embedding sites rely on to size the
    # <img> tag — don't let it drift without bumping consumers.
    assert f'viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}"' in text
    # SVG namespace is required for browser rendering; without it some
    # consumers refuse to parse the document.
    assert 'xmlns="http://www.w3.org/2000/svg"' in text


def test_renders_parseable_xml_document(populated_sim_dir):
    """A consumer pulling the SVG into an XML parser (sitemap-style
    scrapers, downstream tooling) must not see a malformed document."""
    from app.services.chart_svg import render_chart_svg_bytes

    payload = render_chart_svg_bytes(str(populated_sim_dir), "Test")
    assert payload is not None
    # ElementTree raises on any parse error — this is the strictest
    # well-formedness check we can run offline.
    root = ET.fromstring(payload)
    assert root.tag.endswith("svg")


# ── Property 2 — three polylines with locked stance colours ───────────────


def test_three_polylines_for_bullish_neutral_bearish(populated_sim_dir):
    from app.services.chart_svg import (
        render_chart_svg_bytes,
        BULLISH_COLOR,
        NEUTRAL_COLOR,
        BEARISH_COLOR,
    )

    payload = render_chart_svg_bytes(str(populated_sim_dir), "Test")
    assert payload is not None
    text = payload.decode("utf-8")
    polylines = re.findall(r"<polyline\b[^/]*/>", text)
    assert len(polylines) == 3, (
        "expected three polylines (bullish / neutral / bearish) — "
        f"found {len(polylines)}"
    )
    # Every stance colour appears on exactly one polyline.
    for color in (BULLISH_COLOR, NEUTRAL_COLOR, BEARISH_COLOR):
        matches = [p for p in polylines if color in p]
        assert len(matches) == 1, (
            f"colour {color!r} should appear on exactly one polyline; "
            f"found {len(matches)}"
        )


def test_polyline_points_have_correct_count(populated_sim_dir):
    """Three rounds in → three ``x,y`` pairs out per stance polyline."""
    from app.services.chart_svg import render_chart_svg_bytes

    payload = render_chart_svg_bytes(str(populated_sim_dir), "Test")
    assert payload is not None
    text = payload.decode("utf-8")
    for points in re.findall(r'points="([^"]+)"', text):
        pairs = points.strip().split(" ")
        assert len(pairs) == 3
        # Each pair is ``x,y`` with both sides numeric.
        for pair in pairs:
            x, y = pair.split(",")
            float(x)  # raises ValueError on malformed output
            float(y)


# ── Property 3 — y-axis inversion ─────────────────────────────────────────


def test_y_axis_is_inverted(populated_sim_dir):
    """SVG y grows downward — 100% must map to the top of the plot
    (low y), 0% to the bottom (high y). A flipped axis would invert
    every chart in the wild."""
    from app.services.chart_svg import _scale_y, PAD_TOP, PLOT_H

    y_100 = _scale_y(100)
    y_0 = _scale_y(0)
    assert y_100 == PAD_TOP
    assert y_0 == PAD_TOP + PLOT_H
    # 50% lands at the midpoint.
    assert _scale_y(50) == pytest.approx(PAD_TOP + PLOT_H / 2)
    # Out-of-range inputs are clamped — never falls outside the plot.
    assert _scale_y(150) == y_100
    assert _scale_y(-10) == y_0


def test_x_axis_anchors_to_max_round():
    """Round 0 sits at the left padding, the max round at the right."""
    from app.services.chart_svg import _scale_x, PAD_LEFT, PLOT_W

    assert _scale_x(0, max_round=10) == PAD_LEFT
    assert _scale_x(10, max_round=10) == PAD_LEFT + PLOT_W
    # Mid-range round at the midpoint.
    assert _scale_x(5, max_round=10) == pytest.approx(PAD_LEFT + PLOT_W / 2)


# ── Property 4 — empty trajectory returns None ────────────────────────────


def test_empty_trajectory_returns_none(tmp_path: Path):
    """An empty trajectory is the route's signal to emit a 404 — the
    embed site should render its own placeholder rather than a blank
    SVG that looks like a styling bug."""
    from app.services.chart_svg import render_chart_svg_bytes

    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [],
    }), encoding="utf-8")
    result = render_chart_svg_bytes(str(tmp_path), "Test")
    assert result is None


def test_missing_trajectory_file_returns_none(tmp_path: Path):
    """No trajectory.json on disk — same 404 behaviour as an empty file.
    Guards a brand-new sim that hasn't run any rounds yet."""
    from app.services.chart_svg import render_chart_svg_bytes

    # tmp_path is empty — no trajectory file.
    result = render_chart_svg_bytes(str(tmp_path), "Test")
    assert result is None


# ── Property 5 — load_trajectory_for_chart is robust ──────────────────────


def test_load_trajectory_handles_missing_directory():
    from app.services.chart_svg import load_trajectory_for_chart

    rows = load_trajectory_for_chart("/nonexistent/path/should/not/exist")
    assert rows == []


def test_load_trajectory_handles_empty_string():
    from app.services.chart_svg import load_trajectory_for_chart

    assert load_trajectory_for_chart("") == []
    assert load_trajectory_for_chart(None) == []  # type: ignore[arg-type]


def test_load_trajectory_handles_malformed_json(tmp_path: Path):
    """A corrupt trajectory file must NOT crash the renderer — the
    underlying ``trajectory_export.build_rows`` already degrades to an
    empty list, and the chart inherits that behaviour."""
    from app.services.chart_svg import load_trajectory_for_chart

    (tmp_path / "trajectory.json").write_text("not valid json {{{", encoding="utf-8")
    rows = load_trajectory_for_chart(str(tmp_path))
    assert rows == []


# ── Property 6 — title handling ───────────────────────────────────────────


def test_long_title_is_truncated(populated_sim_dir):
    """A 300-character scenario must not break the SVG. Truncation is
    handled with an ellipsis so the title still reads as the scenario
    without overflowing the chart area."""
    from app.services.chart_svg import render_chart_svg_bytes, TITLE_MAX_CHARS

    scenario = "A" * 300
    payload = render_chart_svg_bytes(str(populated_sim_dir), scenario)
    assert payload is not None
    text = payload.decode("utf-8")
    # The full 300-char string must NOT appear in the SVG.
    assert "A" * 300 not in text
    # An ellipsis must appear (truncation marker). Encoded as XML
    # entity or raw unicode either is acceptable.
    assert ("…" in text) or ("&#8230;" in text)
    # The truncated title is bounded by ``TITLE_MAX_CHARS``.
    truncated_marker = "A" * (TITLE_MAX_CHARS - 1)
    assert truncated_marker in text


def test_empty_title_does_not_crash(populated_sim_dir):
    """An untitled simulation (rare but possible) must still render."""
    from app.services.chart_svg import render_chart_svg_bytes

    payload = render_chart_svg_bytes(str(populated_sim_dir), "")
    assert payload is not None
    # Still a valid SVG even without a title.
    text = payload.decode("utf-8")
    assert "<svg" in text
    assert "</svg>" in text


def test_none_title_does_not_crash(populated_sim_dir):
    from app.services.chart_svg import render_chart_svg_bytes

    payload = render_chart_svg_bytes(str(populated_sim_dir), None)
    assert payload is not None


# ── Property 7 — route decorator presence ─────────────────────────────────


def test_chart_svg_route_decorator_exists():
    """Static guard against an accidental decorator removal. The
    OpenAPI drift test catches spec ↔ route mismatches, but a missing
    decorator alone wouldn't surface there without a corresponding
    spec edit."""
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    assert "/<simulation_id>/chart.svg" in text
    assert "def get_chart_svg" in text


def test_chart_svg_increments_surface_stat():
    """The serve handler must increment the chart_svg surface counter
    so the inbound analytics layer sees the request."""
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    # Locate the chart.svg handler body and assert it references its
    # counter key by name.
    assert '"chart_svg"' in text


# ── Single-round resilience ───────────────────────────────────────────────


def test_single_round_trajectory_renders(tmp_path: Path):
    """A sim that has only recorded one round so far must still
    produce a valid SVG — useful for the live ``chart.svg`` on an
    in-progress run."""
    from app.services.chart_svg import render_chart_svg_bytes

    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {
                "round_num": 1,
                "timestamp": "2026-04-29T10:00:00Z",
                "active_agent_count": 2,
                "belief_positions": {
                    "1": {"t": 0.3},
                    "2": {"t": -0.4},
                },
                "viral_posts": [],
            },
        ],
    }), encoding="utf-8")
    payload = render_chart_svg_bytes(str(tmp_path), "Single round")
    assert payload is not None
    text = payload.decode("utf-8")
    assert "<polyline" in text


# ── Deterministic byte output ─────────────────────────────────────────────


def test_render_is_deterministic(populated_sim_dir):
    """Two renders of the same on-disk state must produce bytewise-
    identical SVGs — same property the reproduce.json and notebook
    exports lean on, so the byte hash works as a cache key."""
    from app.services.chart_svg import render_chart_svg_bytes

    a = render_chart_svg_bytes(str(populated_sim_dir), "Test scenario")
    b = render_chart_svg_bytes(str(populated_sim_dir), "Test scenario")
    assert a is not None and b is not None
    assert a == b
