"""Unit tests for the Farcaster Frame v2 metadata builder.

Pure offline — no Flask, no network, no simulation runner, no on-disk
state outside ``tmp_path``. Covers the properties the
``/api/simulation/<id>/frame-metadata`` endpoint and the share-page
Frame tag block both depend on:

  1. ``build_frame_metadata`` returns a stable shape with every field
     a Farcaster Frame v2 consumer expects — ``fc:frame``,
     ``fc:frame:image``, ``fc:frame:image:aspect_ratio``, plus the
     single link-action button.
  2. The image URL is the chart SVG (2:1) for sims with trajectory
     data, and the share-card PNG (1.91:1) for sims that haven't
     recorded any rounds yet — both aspect ratios are values the
     Frame spec explicitly honours.
  3. ``has_trajectory`` flips based on the actual trajectory file —
     a sim with no recorded rounds yet exits cleanly with the
     share-card fallback rather than emitting a Frame pointing at a
     blank SVG.
  4. The base URL is normalized so a caller that passes a trailing
     slash matches what the share blueprint produces.
  5. The scenario title is truncated to ``SIM_TITLE_MAX_CHARS`` —
     the chart SVG title cap is the same value, so a 200-char
     scenario yields the same truncated string in both surfaces.
  6. The Warpcast compose URL helper produces a valid URL with the
     share link URL-encoded inside ``?embeds[]=`` so the operator
     opens the Warpcast composer with the share URL pre-populated.
  7. The route decorator exists on the simulation blueprint — the
     OpenAPI drift test catches spec ↔ route mismatches, but this
     guards against an accidental decorator removal that the spec
     test wouldn't catch in isolation.
  8. The share-page renderer suppresses the Frame block for private
     sims even when a frame_meta dict is supplied — the gate sits in
     the HTML renderer so a future caller can't accidentally leak a
     private scenario title through Farcaster.
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
def empty_sim_dir(tmp_path: Path) -> Path:
    """Sim directory with no trajectory.json — fresh sim, no rounds yet."""
    return tmp_path


@pytest.fixture
def populated_sim_dir(tmp_path: Path) -> Path:
    """Sim directory with a 2-round trajectory the chart can render."""
    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {
                "round_num": 1,
                "timestamp": "2026-05-17T10:00:00Z",
                "total_posts_created": 4,
                "total_engagements": 8,
                "active_agent_count": 3,
                "belief_positions": {
                    "1": {"topic_a": 0.4, "topic_b": 0.5},
                    "2": {"topic_a": 0.3, "topic_b": 0.2},
                    "3": {"topic_a": -0.1, "topic_b": 0.0},
                },
                "viral_posts": [],
            },
            {
                "round_num": 2,
                "timestamp": "2026-05-17T10:01:00Z",
                "total_posts_created": 5,
                "total_engagements": 11,
                "active_agent_count": 3,
                "belief_positions": {
                    "1": {"topic_a": 0.5, "topic_b": 0.6},
                    "2": {"topic_a": 0.4, "topic_b": 0.5},
                    "3": {"topic_a": 0.2, "topic_b": 0.3},
                },
                "viral_posts": [],
            },
        ],
    }), encoding="utf-8")
    return tmp_path


# ── 1. Shape of the metadata dict ─────────────────────────────────────────


def test_build_frame_metadata_returns_complete_shape(populated_sim_dir: Path) -> None:
    from app.services import frame_metadata as fm

    payload = fm.build_frame_metadata(
        sim_id="sim_abc123",
        scenario="What happens to USDC if the Treasury yield curve inverts in Q3?",
        sim_dir=str(populated_sim_dir),
        base_url="https://miroshark.io",
        is_public=True,
    )

    # Every key the share blueprint and the EmbedDialog read.
    expected_keys = {
        "sim_id",
        "sim_title",
        "is_publishable",
        "has_trajectory",
        "frame_version",
        "image_url",
        "image_aspect_ratio",
        "share_url",
        "buttons",
    }
    assert set(payload) >= expected_keys

    assert payload["sim_id"] == "sim_abc123"
    assert payload["is_publishable"] is True
    assert payload["frame_version"] == "next"
    assert payload["share_url"] == "https://miroshark.io/share/sim_abc123"


# ── 2. Image URL switches based on trajectory ─────────────────────────────


def test_image_url_is_chart_svg_when_trajectory_present(populated_sim_dir: Path) -> None:
    from app.services import frame_metadata as fm

    payload = fm.build_frame_metadata(
        sim_id="sim_xyz",
        scenario="A scenario",
        sim_dir=str(populated_sim_dir),
        base_url="https://miroshark.io",
        is_public=True,
    )

    assert payload["has_trajectory"] is True
    assert payload["image_url"] == "https://miroshark.io/api/simulation/sim_xyz/chart.svg"
    # 2:1 matches the chart-SVG viewBox 800×400 and is one of the two
    # aspect ratios the Frame spec honours across every client.
    assert payload["image_aspect_ratio"] == "2:1"


def test_image_url_falls_back_to_share_card_when_no_trajectory(empty_sim_dir: Path) -> None:
    from app.services import frame_metadata as fm

    payload = fm.build_frame_metadata(
        sim_id="sim_xyz",
        scenario="A scenario",
        sim_dir=str(empty_sim_dir),
        base_url="https://miroshark.io",
        is_public=True,
    )

    assert payload["has_trajectory"] is False
    assert payload["image_url"] == "https://miroshark.io/api/simulation/sim_xyz/share-card.png"
    # 1.91:1 matches the share-card PNG 1200×630 and is the OG-image
    # aspect ratio every other unfurler renders identically.
    assert payload["image_aspect_ratio"] == "1.91:1"


def test_image_url_falls_back_when_sim_dir_missing() -> None:
    from app.services import frame_metadata as fm

    payload = fm.build_frame_metadata(
        sim_id="sim_xyz",
        scenario="A scenario",
        sim_dir="/var/no-such-directory-12345",
        base_url="https://miroshark.io",
        is_public=True,
    )

    assert payload["has_trajectory"] is False
    assert "share-card.png" in payload["image_url"]


def test_image_url_falls_back_when_sim_dir_none() -> None:
    from app.services import frame_metadata as fm

    payload = fm.build_frame_metadata(
        sim_id="sim_xyz",
        scenario="A scenario",
        sim_dir=None,
        base_url="https://miroshark.io",
        is_public=True,
    )

    assert payload["has_trajectory"] is False
    assert "share-card.png" in payload["image_url"]


# ── 3. Button shape ───────────────────────────────────────────────────────


def test_button_is_single_link_action(populated_sim_dir: Path) -> None:
    from app.services import frame_metadata as fm

    payload = fm.build_frame_metadata(
        sim_id="sim_xyz",
        scenario="A scenario",
        sim_dir=str(populated_sim_dir),
        base_url="https://miroshark.io",
        is_public=True,
    )

    buttons = payload["buttons"]
    assert isinstance(buttons, list)
    assert len(buttons) == 1
    btn = buttons[0]
    assert btn["action"] == "link"
    assert btn["label"] == "View Simulation →"
    # The button target lands the reader on the SPA simulation view,
    # not the OG-tag landing page (which would just JS-redirect to
    # the same URL — saving a hop).
    assert btn["target"] == "https://miroshark.io/simulation/sim_xyz/start"


# ── 4. Base URL normalization ─────────────────────────────────────────────


def test_base_url_trailing_slash_stripped(populated_sim_dir: Path) -> None:
    from app.services import frame_metadata as fm

    payload = fm.build_frame_metadata(
        sim_id="sim_xyz",
        scenario="A scenario",
        sim_dir=str(populated_sim_dir),
        base_url="https://miroshark.io/",  # trailing slash
        is_public=True,
    )

    # No double-slash anywhere in the assembled URLs.
    assert payload["share_url"] == "https://miroshark.io/share/sim_xyz"
    assert payload["image_url"] == "https://miroshark.io/api/simulation/sim_xyz/chart.svg"
    assert payload["buttons"][0]["target"] == "https://miroshark.io/simulation/sim_xyz/start"


# ── 5. Title truncation ───────────────────────────────────────────────────


def test_sim_title_truncated_to_80_chars(populated_sim_dir: Path) -> None:
    from app.services import frame_metadata as fm

    long_scenario = "x" * 200
    payload = fm.build_frame_metadata(
        sim_id="sim_xyz",
        scenario=long_scenario,
        sim_dir=str(populated_sim_dir),
        base_url="https://miroshark.io",
        is_public=True,
    )

    # Title is capped at SIM_TITLE_MAX_CHARS (80) with an ellipsis on
    # overflow — same cap the chart SVG title uses, so the Frame
    # metadata title and the image title agree.
    assert len(payload["sim_title"]) <= fm.SIM_TITLE_MAX_CHARS
    assert payload["sim_title"].endswith("…")


def test_sim_title_empty_for_blank_scenario(populated_sim_dir: Path) -> None:
    from app.services import frame_metadata as fm

    payload = fm.build_frame_metadata(
        sim_id="sim_xyz",
        scenario="",
        sim_dir=str(populated_sim_dir),
        base_url="https://miroshark.io",
        is_public=True,
    )

    assert payload["sim_title"] == ""


# ── 6. Warpcast compose URL ───────────────────────────────────────────────


def test_warpcast_compose_url_encodes_share_url() -> None:
    from app.services import frame_metadata as fm
    from urllib.parse import urlparse, parse_qs

    share = "https://miroshark.io/share/sim_xyz"
    url = fm.warpcast_compose_url(share)

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "warpcast.com"
    assert parsed.path == "/~/compose"

    qs = parse_qs(parsed.query)
    # ``embeds[]`` decodes back to the original share URL — the
    # operator lands in Warpcast with the share link pre-populated.
    assert qs.get("embeds[]") == [share]


def test_warpcast_compose_url_fallback_when_blank() -> None:
    from app.services import frame_metadata as fm

    url = fm.warpcast_compose_url("")
    assert url == "https://warpcast.com/~/compose"


# ── 7. Route decoration ───────────────────────────────────────────────────


def test_frame_metadata_route_exists_on_simulation_bp() -> None:
    """The OpenAPI drift test catches spec ↔ route mismatches, but this
    test guards against an accidental decorator removal that the spec
    test wouldn't catch in isolation (e.g. the function is left in
    the module but the decorator gets dropped). Inspecting the source
    directly avoids spinning up a Flask app and a SimulationManager.
    """
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    src = api_file.read_text(encoding="utf-8")

    assert "/<simulation_id>/frame-metadata" in src
    assert "def get_frame_metadata" in src


# ── 8. Share-page Frame block gating ─────────────────────────────────────


def test_share_landing_emits_frame_meta_for_public_sim() -> None:
    """The Frame block lands in the head only when ``is_public`` is True.

    The share blueprint passes the frame_meta dict to
    ``_render_landing_html`` for every sim it can look up; the renderer
    itself enforces the publish gate. This test invokes the renderer
    directly so we don't need a Flask test client.
    """
    from app.api.share import _render_landing_html

    frame_meta = {
        "image_url": "https://miroshark.io/api/simulation/sim_x/chart.svg",
        "image_aspect_ratio": "2:1",
        "frame_version": "next",
        "buttons": [
            {
                "label": "View Simulation →",
                "action": "link",
                "target": "https://miroshark.io/simulation/sim_x/start",
            }
        ],
    }

    public_html = _render_landing_html(
        simulation_id="sim_x",
        scenario="A scenario",
        is_public=True,
        spa_url="https://miroshark.io/simulation/sim_x/start",
        card_url="https://miroshark.io/api/simulation/sim_x/share-card.png",
        frame_meta=frame_meta,
    )

    assert 'property="fc:frame"' in public_html
    assert 'content="next"' in public_html
    assert 'property="fc:frame:image"' in public_html
    assert "chart.svg" in public_html
    assert 'property="fc:frame:image:aspect_ratio"' in public_html
    assert 'content="2:1"' in public_html
    assert 'property="fc:frame:button:1"' in public_html
    assert "View Simulation" in public_html


def test_share_landing_suppresses_frame_meta_for_private_sim() -> None:
    """Private sims must not leak the scenario title through a Farcaster
    cast preview — the renderer drops the entire Frame block when
    ``is_public`` is False, even if the caller passes frame_meta."""
    from app.api.share import _render_landing_html

    frame_meta = {
        "image_url": "https://miroshark.io/api/simulation/sim_x/chart.svg",
        "image_aspect_ratio": "2:1",
        "frame_version": "next",
        "buttons": [
            {
                "label": "View Simulation →",
                "action": "link",
                "target": "https://miroshark.io/simulation/sim_x/start",
            }
        ],
    }

    private_html = _render_landing_html(
        simulation_id="sim_x",
        scenario="A confidential scenario",
        is_public=False,
        spa_url="https://miroshark.io/simulation/sim_x/start",
        card_url="https://miroshark.io/api/simulation/sim_x/share-card.png",
        frame_meta=frame_meta,
    )

    assert 'property="fc:frame"' not in private_html
    assert 'fc:frame:image' not in private_html
    # The OG/Twitter generic fallback still renders.
    assert 'property="og:image"' in private_html
