"""Unit tests for the spectator-watch renderer + route module.

Pure offline tests — no live Flask app, no Neo4j, no simulation data
on disk. Verifies that the renderer produces well-formed HTML with
the expected Open Graph + Twitter card meta tags, a bootstrap blob a
client-side parser can recover, percentage values that match the
visible legend numbers, and a graceful private-sim fallback that
never leaks scenario detail.

Mirrors the structure of ``test_unit_share_card.py``'s landing-page
tests so a reader can compare the two surfaces (``/share/<id>`` and
``/watch/<id>``) at a glance.
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


@pytest.fixture
def running_summary() -> dict:
    """An in-flight, public simulation mid-run."""
    return {
        "simulation_id": "sim_running123",
        "scenario": "Will the Fed cut rates by 25bps at the June 2026 FOMC?",
        "is_public": True,
        "status": "running",
        "runner_status": "running",
        "current_round": 12,
        "total_rounds": 30,
        "profiles_count": 48,
        "belief": {
            "rounds": list(range(1, 13)),
            "bullish": [10, 12, 18, 22, 28, 34, 40, 44, 48, 52, 56, 60.0],
            "neutral": [60, 58, 54, 50, 46, 42, 38, 34, 30, 26, 22, 18.0],
            "bearish": [30, 30, 28, 28, 26, 24, 22, 22, 22, 22, 22, 22.0],
            "final": {"bullish": 60.0, "neutral": 18.0, "bearish": 22.0},
            "consensus_round": 10,
            "consensus_stance": "bullish",
        },
        "quality": {"health": "Excellent", "participation_rate": 0.92},
    }


@pytest.fixture
def completed_summary() -> dict:
    return {
        "simulation_id": "sim_done456",
        "scenario": "Will Solana's TVL exceed $20B by Q4 2026?",
        "is_public": True,
        "status": "completed",
        "runner_status": "completed",
        "current_round": 30,
        "total_rounds": 30,
        "profiles_count": 64,
        "belief": {
            "rounds": list(range(1, 31)),
            "bullish": [20] * 29 + [55.0],
            "neutral": [40] * 29 + [25.0],
            "bearish": [40] * 29 + [20.0],
            "final": {"bullish": 55.0, "neutral": 25.0, "bearish": 20.0},
            "consensus_round": 22,
            "consensus_stance": "bullish",
        },
        "quality": {"health": "Good", "participation_rate": 0.81},
    }


@pytest.fixture
def idle_summary() -> dict:
    """Public sim that hasn't started running yet — no belief snapshots."""
    return {
        "simulation_id": "sim_idle789",
        "scenario": 'Will an ETF for "BTC" be approved before 2027?',  # quotes → must be escaped
        "is_public": True,
        "status": "idle",
        "runner_status": "idle",
        "current_round": 0,
        "total_rounds": 0,
        "profiles_count": 0,
        "belief": None,
        "quality": None,
    }


# ── Renderer tests ────────────────────────────────────────────────────────


def _render(summary, simulation_id="sim_test"):
    from app.services.watch_renderer import render_watch_html

    return render_watch_html(
        simulation_id=simulation_id,
        summary=summary,
        spa_url=f"https://example.com/simulation/{simulation_id}/start",
        fork_url=f"https://example.com/simulation/{simulation_id}/start?fork=1",
        card_url=f"https://example.com/api/simulation/{simulation_id}/share-card.png",
        explore_url="https://example.com/explore",
    )


def test_running_simulation_emits_og_and_twitter_tags(running_summary):
    html = _render(running_summary, simulation_id="sim_running123")

    assert 'property="og:type"' in html
    assert 'property="og:title"' in html
    assert 'property="og:image"' in html
    assert (
        'content="https://example.com/api/simulation/sim_running123/share-card.png"'
        in html
    )
    assert 'property="og:image:width"' in html and 'content="1200"' in html
    assert 'property="og:image:height"' in html and 'content="630"' in html
    assert 'name="twitter:card"' in html
    assert 'content="summary_large_image"' in html
    assert 'name="twitter:image"' in html


def test_running_simulation_renders_scenario_and_round_progress(running_summary):
    html = _render(running_summary, simulation_id="sim_running123")

    # Scenario lives in the SSR <h1> so JS-disabled clients still see it.
    assert "Will the Fed cut rates by 25bps at the June 2026 FOMC?" in html
    # Round counter pulls through from current/total.
    assert "12 / 30" in html
    # 60% width on the bullish bar (current/total = 60.00/100 of bar):
    # final.bullish 60 / total 100 ⇒ 60.00% width.
    assert 'style="width:60.00%"' in html
    # Live badge is the in-flight one (no static class modifier).
    assert "<span id=\"live-badge-text\">Live</span>" in html


def test_completed_simulation_shows_final_badge_and_cta(completed_summary):
    html = _render(completed_summary, simulation_id="sim_done456")

    # Terminal-state badge.
    assert 'class="live-badge done"' in html
    assert "<span id=\"live-badge-text\">Final</span>" in html
    # CTA row server-rendered visible (no display:none on the wrapper).
    assert 'id="cta-row" class="cta-row" style=""' in html
    # Both CTAs present.
    assert "View full simulation" in html
    assert "Fork this scenario" in html


def test_in_flight_simulation_hides_cta_until_terminal(running_summary):
    html = _render(running_summary, simulation_id="sim_running123")
    # Server-side: CTA row is hidden until the runner reaches a terminal
    # state. Polling JS reveals it on the client.
    assert 'id="cta-row" class="cta-row" style="display:none"' in html


def test_idle_simulation_shows_empty_belief_note_and_escapes_quotes(idle_summary):
    html = _render(idle_summary, simulation_id="sim_idle789")

    # Empty-belief note is visible (no display:none).
    assert 'id="empty-note" class="empty-note" style=""' in html
    # Quotes in the scenario are HTML-attribute escaped on the OG title.
    assert "&quot;BTC&quot;" in html
    # Idle badge.
    assert 'class="live-badge idle"' in html


def test_private_simulation_omits_scenario_in_meta_tags():
    """Private simulations still render the page (the URL is public),
    but must not leak the scenario through OG / Twitter tags."""
    html = _render(summary=None, simulation_id="sim_private")

    assert "MiroShark · Live simulation" in html  # generic title
    # Card URL still present so the unfurl shows the generic share card.
    assert (
        'content="https://example.com/api/simulation/sim_private/share-card.png"'
        in html
    )
    # No scenario text whatsoever.
    assert "Will the Fed" not in html
    assert "Solana" not in html


def test_bootstrap_blob_round_trips_to_initial_state(running_summary):
    html = _render(running_summary, simulation_id="sim_running123")

    match = re.search(
        r'<script id="watch-bootstrap" type="application/json">(.+?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match, "bootstrap blob script tag not found"
    bootstrap = json.loads(match.group(1))

    assert bootstrap["simulation_id"] == "sim_running123"
    assert bootstrap["is_public"] is True
    assert bootstrap["scenario"].startswith("Will the Fed cut rates")
    assert bootstrap["runner_status"] == "running"
    assert bootstrap["current_round"] == 12
    assert bootstrap["total_rounds"] == 30
    # Final belief percentages exposed for first-frame rendering without
    # a network round-trip.
    assert bootstrap["bullish"] == pytest.approx(60.0)
    assert bootstrap["neutral"] == pytest.approx(18.0)
    assert bootstrap["bearish"] == pytest.approx(22.0)
    assert bootstrap["consensus_round"] == 10
    assert bootstrap["consensus_stance"] == "bullish"
    # Stance threshold is part of the bootstrap so a reader can confirm
    # the page agrees with the share card / replay GIF / transcript /
    # feed / trajectory CSV.
    from app.services.watch_renderer import STANCE_THRESHOLD

    assert bootstrap["stance_threshold"] == STANCE_THRESHOLD == 0.2


def test_stance_threshold_matches_other_surfaces():
    """Centerpiece guard — the watch page must read the same ±0.2
    stance threshold as the share card / replay GIF / transcript /
    feed / trajectory CSV. A drift here would split the bullish-%
    a spectator sees on the live watch page from the value the
    share-card unfurl shows on Twitter moments earlier."""
    from app.services.watch_renderer import STANCE_THRESHOLD

    assert STANCE_THRESHOLD == 0.2


def test_belief_bar_widths_proportional_to_split(running_summary):
    """The SSR bar widths must match the percentages a reader sees in
    the legend — otherwise a JS-disabled viewer would see a misleading
    bar."""
    html = _render(running_summary, simulation_id="sim_test")

    # final = bullish 60 / neutral 18 / bearish 22 ⇒ each becomes its own
    # percentage of a 100-total bar.
    assert 'id="bar-bullish" class="belief-bar bullish" style="width:60.00%"' in html
    assert 'id="bar-neutral" class="belief-bar neutral" style="width:18.00%"' in html
    assert 'id="bar-bearish" class="belief-bar bearish" style="width:22.00%"' in html


def test_zero_belief_renders_zero_width_bars(idle_summary):
    """Empty trajectory ⇒ all bars at 0 width, page still well-formed."""
    html = _render(idle_summary, simulation_id="sim_idle789")
    # Three zero-width bar divs should still be present.
    assert html.count('class="belief-bar') == 3
    assert "width:0%" in html


def test_long_scenario_truncates_with_ellipsis():
    """Title / description must truncate without overflowing the OG
    char budgets that Twitter and Discord enforce."""
    long_scenario = (
        "Will any of the following events happen before the end of Q4 2026: "
        "(a) the SEC approves a spot Solana ETF, (b) the EU finalises MiCA-2 "
        "with a clarified treatment of restaking yields, (c) Tether publishes "
        "a fully audited reserve attestation under PCAOB standards, (d) a "
        "major prime broker offers DeFi-native cash management to U.S. "
        "registered investment advisors at scale?"
    )
    html = _render(
        summary={
            "simulation_id": "sim_long",
            "scenario": long_scenario,
            "is_public": True,
            "runner_status": "running",
            "status": "running",
            "current_round": 1,
            "total_rounds": 5,
            "profiles_count": 12,
            "belief": {"final": {"bullish": 33, "neutral": 34, "bearish": 33}},
            "quality": None,
        },
        simulation_id="sim_long",
    )
    assert "…" in html  # ellipsis marker present
    # The full scenario must not appear verbatim in the OG title — the
    # truncation happens at 200 chars before "MiroShark · " prefix is
    # added.
    assert long_scenario not in html


# ── Module-presence guards ────────────────────────────────────────────────


def test_watch_route_registered_on_watch_blueprint():
    """Sanity guard alongside the OpenAPI drift test — the
    ``/watch/<simulation_id>`` decorator must exist in the blueprint
    file. The drift test in ``test_unit_openapi.py`` validates the spec
    matches; this one just confirms the source side hasn't been
    accidentally renamed."""
    from app.api import watch as watch_module
    import inspect

    src = inspect.getsource(watch_module)
    assert "@watch_bp.route('/watch/<simulation_id>'" in src
    assert "watch_bp = Blueprint('watch'" in src


def test_watch_blueprint_exported_from_api_package():
    """``app/api/__init__.py`` must re-export ``watch_bp`` so the app
    factory in ``app/__init__.py`` can register it alongside the other
    blueprints."""
    from app.api import watch_bp

    assert watch_bp is not None
    assert watch_bp.name == "watch"


def test_meta_description_includes_round_and_split_for_running_sim(running_summary):
    """The OG description should answer 'why click this' in one line:
    which round, and where consensus currently stands."""
    from app.services.watch_renderer import _build_meta_description

    desc = _build_meta_description(running_summary)
    assert "Round 12/30" in desc
    assert "Bullish 60%" in desc
    assert "Neutral 18%" in desc
    assert "Bearish 22%" in desc
    assert "watch live" in desc.lower()


def test_meta_description_for_idle_sim_falls_back_to_scenario(idle_summary):
    """Pre-run sims have no belief data — the description should fall
    back to the scenario text rather than emitting a misleading
    'Round 0' line."""
    from app.services.watch_renderer import _build_meta_description

    desc = _build_meta_description(idle_summary)
    assert "Round 0" not in desc
    assert "BTC" in desc


def test_meta_description_for_missing_summary_uses_generic_string():
    from app.services.watch_renderer import _build_meta_description

    desc = _build_meta_description(None)
    assert "MiroShark" in desc or "round-by-round" in desc
    assert len(desc) <= 280


def test_initial_state_zeroes_bullish_when_belief_absent():
    from app.services.watch_renderer import _build_initial_state

    state = _build_initial_state("sim_x", {"is_public": True, "scenario": "x"})
    assert state["bullish"] == 0.0
    assert state["neutral"] == 0.0
    assert state["bearish"] == 0.0
    assert state["consensus_stance"] is None


def test_initial_state_handles_corrupt_belief_gracefully():
    """A malformed belief block must not raise — the page renders with
    zero bars rather than crashing the route."""
    from app.services.watch_renderer import _build_initial_state

    state = _build_initial_state(
        "sim_x",
        {
            "is_public": True,
            "scenario": "x",
            "belief": {"final": {"bullish": "not-a-number"}},
        },
    )
    assert state["bullish"] == 0.0
    assert state["neutral"] == 0.0
    assert state["bearish"] == 0.0


def test_render_handles_missing_summary_without_crashing():
    """Defensive — passing ``None`` for summary must produce a valid
    HTML document, not a stack trace from the route."""
    from app.services.watch_renderer import render_watch_html

    html = render_watch_html(
        simulation_id="sim_zzz",
        summary=None,
        spa_url="https://example.com/simulation/sim_zzz/start",
        fork_url="https://example.com/simulation/sim_zzz/start?fork=1",
        card_url="https://example.com/api/simulation/sim_zzz/share-card.png",
        explore_url="https://example.com/explore",
    )
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert 'property="og:title"' in html
