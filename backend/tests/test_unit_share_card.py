"""Unit tests for the share-card renderer.

Pure offline tests — no backend, no network. Verifies that:

  - the renderer returns valid PNG bytes for both fully-populated and
    minimal summary dicts,
  - the cache key is deterministic and changes only when render-affecting
    fields change,
  - text wrapping doesn't crash on empty / oversize / single-word input,
  - the published landing HTML carries the right Open Graph + Twitter card
    meta tags.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
import sys

if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Renderer tests ─────────────────────────────────────────────────────────


def _is_png(data: bytes) -> bool:
    """The PNG signature is fixed at 8 bytes: 89 50 4e 47 0d 0a 1a 0a."""
    return len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n"


def _png_size(data: bytes) -> tuple[int, int]:
    """Read width/height from the PNG IHDR chunk (bytes 16-24)."""
    assert _is_png(data)
    width = struct.unpack(">I", data[16:20])[0]
    height = struct.unpack(">I", data[20:24])[0]
    return width, height


@pytest.fixture
def full_summary() -> dict:
    return {
        "simulation_id": "sim_abc123def456",
        "scenario": "Will the SEC approve a spot Solana ETF before the end of Q3 2026?",
        "status": "completed",
        "runner_status": "completed",
        "current_round": 20,
        "total_rounds": 20,
        "profiles_count": 248,
        "created_date": "2026-04-22",
        "is_public": True,
        "belief": {
            "rounds": list(range(20)),
            "bullish": [10] * 19 + [62.0],
            "neutral": [10] * 19 + [13.0],
            "bearish": [80] * 19 + [25.0],
            "final": {"bullish": 62.0, "neutral": 13.0, "bearish": 25.0},
            "consensus_round": 14,
            "consensus_stance": "bullish",
        },
        "quality": {"health": "Excellent", "participation_rate": 0.92},
        "resolution": {
            "actual_outcome": "YES",
            "predicted_consensus": "YES",
            "accuracy_score": 1.0,
        },
    }


def test_renders_png_for_full_summary(full_summary):
    from app.services.share_card import render_share_card

    png = render_share_card(full_summary)
    assert _is_png(png)
    w, h = _png_size(png)
    assert (w, h) == (1200, 630)
    # Sanity floor — a blank-rendered PNG would be tiny.
    assert len(png) > 5000


def test_renders_png_for_minimal_summary():
    """Even with almost no data, the renderer must produce a valid PNG —
    this guards against the unfurler getting a 500 on a brand-new
    simulation that hasn't run yet."""
    from app.services.share_card import render_share_card

    png = render_share_card({"simulation_id": "sim_x"})
    assert _is_png(png)
    assert _png_size(png) == (1200, 630)


def test_renders_with_only_scenario():
    from app.services.share_card import render_share_card

    png = render_share_card(
        {
            "simulation_id": "sim_x",
            "scenario": "A" * 600,  # extreme-length scenario forces wrap+truncate
        }
    )
    assert _is_png(png)


def test_renders_with_long_single_word():
    """Single-word scenarios that exceed the line width must character-chop
    instead of looping forever."""
    from app.services.share_card import render_share_card

    png = render_share_card(
        {
            "simulation_id": "sim_x",
            "scenario": "Supercalifragilisticexpialidocious" * 20,
        }
    )
    assert _is_png(png)


def test_handles_failed_status():
    from app.services.share_card import render_share_card

    png = render_share_card(
        {
            "simulation_id": "sim_x",
            "scenario": "Failed run",
            "runner_status": "failed",
        }
    )
    assert _is_png(png)


# ── Cache-key tests ────────────────────────────────────────────────────────


def test_cache_key_stable_across_calls(full_summary):
    from app.services.share_card import summary_cache_key

    a = summary_cache_key(full_summary)
    b = summary_cache_key(dict(full_summary))
    assert a == b
    assert len(a) == 16


def test_cache_key_changes_when_render_inputs_change(full_summary):
    from app.services.share_card import summary_cache_key

    base = summary_cache_key(full_summary)

    # Mutating a render-affecting field should change the key.
    s2 = {**full_summary, "scenario": full_summary["scenario"] + "?"}
    assert summary_cache_key(s2) != base

    s3 = {**full_summary, "current_round": 19}
    assert summary_cache_key(s3) != base

    s4 = {
        **full_summary,
        "belief": {
            **full_summary["belief"],
            "final": {"bullish": 50.0, "neutral": 25.0, "bearish": 25.0},
        },
    }
    assert summary_cache_key(s4) != base


def test_cache_key_ignores_non_render_fields(full_summary):
    from app.services.share_card import summary_cache_key

    base = summary_cache_key(full_summary)

    # Adding fields the renderer doesn't read shouldn't bust the cache.
    extra = {**full_summary, "parent_simulation_id": "sim_zzz", "extra_unused": [1, 2, 3]}
    assert summary_cache_key(extra) == base


# ── Helper tests ───────────────────────────────────────────────────────────


def test_short_sim_id():
    from app.services.share_card import _short_sim_id

    assert _short_sim_id("sim_abc123def456") == "SIM_ABC123"
    assert _short_sim_id("") == ""
    assert _short_sim_id("sim_x") == "SIM_X"


def test_format_date_round_trip():
    from app.services.share_card import _format_date

    out = _format_date("2026-04-22")
    assert "2026" in out
    assert "Apr" in out
    # Garbage in → graceful fallback (no crash, no traceback).
    assert _format_date("") == ""
    assert _format_date("not-a-date").startswith("not-a-da")


# ── Landing-page meta-tag test ─────────────────────────────────────────────


def test_landing_html_includes_og_and_twitter_tags():
    from app.api.share import _render_landing_html

    html = _render_landing_html(
        simulation_id="sim_xyz789",
        scenario='Will "X" happen?',  # quotes → must be escaped
        is_public=True,
        spa_url="https://example.com/simulation/sim_xyz789/start",
        card_url="https://example.com/api/simulation/sim_xyz789/share-card.png",
    )

    # Required OG tags
    assert 'property="og:title"' in html
    assert 'property="og:image"' in html
    assert 'content="https://example.com/api/simulation/sim_xyz789/share-card.png"' in html
    assert 'property="og:image:width"' in html and 'content="1200"' in html
    assert 'property="og:image:height"' in html and 'content="630"' in html

    # Twitter card
    assert 'name="twitter:card"' in html
    assert 'content="summary_large_image"' in html
    assert 'name="twitter:image"' in html

    # Quote-escape must turn the inner " into &quot; — otherwise the
    # content="..." attribute would terminate early and the scraper would
    # see a broken tag.
    assert "&quot;X&quot;" in html

    # Both redirect mechanisms present
    assert 'http-equiv="refresh"' in html
    assert "window.location.replace" in html


def test_landing_html_for_private_sim_omits_scenario():
    """Private simulations should still render the landing page (the URL
    is public), but must not leak the scenario through OG tags."""
    from app.api.share import _render_landing_html

    html = _render_landing_html(
        simulation_id="sim_private",
        scenario="",  # caller passes empty when is_public is False
        is_public=False,
        spa_url="https://example.com/simulation/sim_private/start",
        card_url="https://example.com/api/simulation/sim_private/share-card.png",
    )

    assert "MiroShark Simulation" in html  # generic title
    assert 'property="og:image"' in html  # card URL still present
