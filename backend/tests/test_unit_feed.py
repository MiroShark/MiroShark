"""Unit tests for the public-gallery syndication feeds.

Pure offline checks against ``app/services/feed.py`` — no Flask app, no
database, no network. We cover the contracts that matter for a
syndication consumer:

  1. The Atom 1.0 + RSS 2.0 documents parse as valid XML and carry the
     well-known top-level elements (``feed``, ``rss``, etc.).
  2. Every public simulation card produces a corresponding entry; private
     ones are filtered out.
  3. Sort order matches the gallery (newest first by ``created_at``).
  4. Verified-only mode filters to simulations with an outcome record.
  5. Per-entry payload carries the canonical share landing link, the
     scenario as title (truncated when too long), the consensus split
     summary string, and the share-card PNG / replay GIF as media
     enclosures.
  6. Outcome + quality categories appear when the underlying data does.
  7. Corrupt/missing fields degrade gracefully — one bad card never
     blanks the whole feed.

The route layer is exercised indirectly via the same shared selection
helper (``select_public_cards``) the live endpoint plugs into, so
asserting on the helper output is equivalent to asserting on the feed
the endpoint returns.
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


_ATOM_NS = "http://www.w3.org/2005/Atom"
_MEDIA_NS = "http://search.yahoo.com/mrss/"


# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_card(
    sim_id: str = "sim_aaa111",
    *,
    scenario: str = "Will the SEC approve a spot Solana ETF before Q3?",
    created_at: str = "2026-04-29T10:12:34",
    bullish: float = 62.0,
    neutral: float = 13.0,
    bearish: float = 25.0,
    quality_health: str = "Excellent",
    outcome_label: str | None = None,
    resolution: str | None = None,
    agent_count: int = 248,
    current_round: int = 20,
    total_rounds: int = 20,
) -> dict:
    """Mirror the shape ``_build_gallery_card_payload`` returns."""
    card: dict = {
        "simulation_id": sim_id,
        "scenario": scenario,
        "status": "completed",
        "runner_status": "completed",
        "current_round": current_round,
        "total_rounds": total_rounds,
        "agent_count": agent_count,
        "quality_health": quality_health,
        "final_consensus": {"bullish": bullish, "neutral": neutral, "bearish": bearish},
        "resolution_outcome": resolution,
        "outcome": None,
        "created_at": created_at,
        "parent_simulation_id": None,
        "share_card_url": f"/api/simulation/{sim_id}/share-card.png",
        "share_landing_url": f"/share/{sim_id}",
    }
    if outcome_label is not None:
        card["outcome"] = {
            "label": outcome_label,
            "outcome_url": "https://example.com/outcome",
            "outcome_summary": "ETF approved, sim called it 4 days early.",
            "submitted_at": "2026-04-29T11:30:00Z",
        }
    return card


class _FakeState:
    """Lightweight stand-in for SimulationState used by select_public_cards."""

    def __init__(
        self,
        sim_id: str,
        *,
        is_public: bool = True,
        created_at: str = "2026-04-22T10:12:34",
    ):
        self.simulation_id = sim_id
        self.is_public = is_public
        self.created_at = created_at


# ── Atom 1.0 ───────────────────────────────────────────────────────────────


def test_atom_feed_parses_with_required_elements():
    """The rendered Atom XML should parse, declare the Atom namespace,
    and carry the top-level ``id`` / ``title`` / ``updated`` elements
    every reader expects."""
    from app.services.feed import render_atom

    cards = [_make_card("sim_111", created_at="2026-04-29T10:00:00")]
    body = render_atom(
        cards,
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
        title="MiroShark · Public Simulations",
        subtitle="Newest published simulations.",
    )

    root = ET.fromstring(body)
    assert root.tag == f"{{{_ATOM_NS}}}feed"
    assert root.findtext(f"{{{_ATOM_NS}}}title") == "MiroShark · Public Simulations"
    assert root.find(f"{{{_ATOM_NS}}}id") is not None
    assert root.findtext(f"{{{_ATOM_NS}}}updated"), "feed missing required <updated>"

    self_link = root.find(
        f"{{{_ATOM_NS}}}link[@rel='self']",
    )
    assert self_link is not None
    assert self_link.attrib["href"] == "https://demo.miroshark.io/api/feed.atom"

    alternate_link = root.find(f"{{{_ATOM_NS}}}link[@rel='alternate']")
    assert alternate_link is not None
    assert alternate_link.attrib["href"] == "https://demo.miroshark.io/explore"


def test_atom_entry_carries_share_link_and_media_enclosures():
    """Each entry has a clickable share-landing link, the share-card PNG
    as both ``media:thumbnail`` + ``media:content``, and the replay GIF
    as a second ``media:content`` so River-view readers get motion."""
    from app.services.feed import render_atom

    cards = [_make_card("sim_222")]
    body = render_atom(
        cards,
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
        title="t",
        subtitle="s",
    )
    root = ET.fromstring(body)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    assert entry is not None

    share_link = entry.find(f"{{{_ATOM_NS}}}link[@rel='alternate']")
    assert share_link is not None
    assert share_link.attrib["href"] == "https://demo.miroshark.io/share/sim_222"

    thumb = entry.find(f"{{{_MEDIA_NS}}}thumbnail")
    assert thumb is not None
    assert thumb.attrib["url"].endswith("/api/simulation/sim_222/share-card.png")

    media_contents = entry.findall(f"{{{_MEDIA_NS}}}content")
    types = {m.attrib.get("type") for m in media_contents}
    # Both static share card + animated replay GIF should be enclosed.
    assert "image/png" in types
    assert "image/gif" in types


def test_atom_summary_contains_consensus_split():
    """The plain-text summary line shown in River views must spell out
    the bullish/neutral/bearish percentages so readers can scan
    consensus without opening every card."""
    from app.services.feed import render_atom

    cards = [_make_card("sim_333", bullish=62.0, neutral=13.0, bearish=25.0)]
    body = render_atom(
        cards,
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
        title="t",
        subtitle="s",
    )
    root = ET.fromstring(body)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    summary = (entry.findtext(f"{{{_ATOM_NS}}}summary") or "")
    assert "62.0% Bullish" in summary
    assert "25.0% Bearish" in summary
    assert "Quality: Excellent" in summary
    assert "Agents: 248" in summary


def test_atom_long_scenario_truncates_with_ellipsis():
    """A 500-char scenario gets compressed with a unicode ellipsis so
    River-view title strips don't blow out."""
    from app.services.feed import render_atom

    huge = "Scenario " * 80  # ~720 chars
    cards = [_make_card("sim_long", scenario=huge)]
    body = render_atom(
        cards,
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
        title="t",
        subtitle="s",
    )
    root = ET.fromstring(body)
    title = root.find(f"{{{_ATOM_NS}}}entry").findtext(f"{{{_ATOM_NS}}}title")
    assert title is not None
    assert len(title) <= 100
    assert title.endswith("…")


def test_atom_outcome_categorizes_entry():
    """Outcome and quality fields surface as Atom ``<category>`` elements
    so subscribers can filter on them in their reader."""
    from app.services.feed import render_atom

    cards = [_make_card("sim_cat", outcome_label="correct", quality_health="Good")]
    body = render_atom(
        cards,
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
        title="t",
        subtitle="s",
    )
    root = ET.fromstring(body)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    categories = {c.attrib["term"] for c in entry.findall(f"{{{_ATOM_NS}}}category")}
    assert "verified-correct" in categories
    assert "quality-good" in categories


def test_atom_empty_card_list_still_renders_valid_feed():
    """No public sims → an empty but valid feed (parses, has updated)."""
    from app.services.feed import render_atom

    body = render_atom(
        [],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
        title="t",
        subtitle="s",
    )
    root = ET.fromstring(body)
    assert root.findall(f"{{{_ATOM_NS}}}entry") == []
    assert root.findtext(f"{{{_ATOM_NS}}}updated"), "feed missing <updated>"


def test_atom_handles_missing_optional_fields():
    """A card built from an in-progress sim (no consensus, no quality)
    must still produce a valid entry — graceful degradation matches the
    gallery card helper's contract."""
    from app.services.feed import render_atom

    cards = [
        {
            "simulation_id": "sim_minimal",
            "scenario": "",
            "status": "running",
            "runner_status": "running",
            "current_round": 4,
            "total_rounds": 0,
            "agent_count": 0,
            "quality_health": None,
            "final_consensus": None,
            "resolution_outcome": None,
            "outcome": None,
            "created_at": "2026-04-29T08:00:00",
            "parent_simulation_id": None,
            "share_card_url": "/api/simulation/sim_minimal/share-card.png",
            "share_landing_url": "/share/sim_minimal",
        }
    ]
    body = render_atom(
        cards,
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
        title="t",
        subtitle="s",
    )
    root = ET.fromstring(body)
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    assert entry is not None
    title = entry.findtext(f"{{{_ATOM_NS}}}title")
    assert title == "(untitled scenario)"


def test_atom_self_link_includes_query_string():
    """``feed_path`` is the exact request path that produced the feed —
    when a reader subscribed via ``?verified=1``, the rel=self link must
    echo that query string so re-fetches stay scoped to the verified
    set."""
    from app.services.feed import render_atom

    body = render_atom(
        [],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom?verified=1",
        title="t",
        subtitle="s",
        verified_only=True,
    )
    root = ET.fromstring(body)
    self_link = root.find(f"{{{_ATOM_NS}}}link[@rel='self']")
    assert self_link is not None
    assert self_link.attrib["href"].endswith("?verified=1")
    alt = root.find(f"{{{_ATOM_NS}}}link[@rel='alternate']")
    assert alt.attrib["href"].endswith("/verified")


def test_atom_skips_entries_without_simulation_id():
    """A corrupted card with a missing sim_id should be skipped rather
    than render an entry with a broken ``<id>`` (which would shadow real
    entries in feed-reader caches keyed by id)."""
    from app.services.feed import render_atom

    body = render_atom(
        [
            _make_card("sim_ok"),
            {"simulation_id": "", "scenario": "broken"},
        ],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
        title="t",
        subtitle="s",
    )
    root = ET.fromstring(body)
    entries = root.findall(f"{{{_ATOM_NS}}}entry")
    assert len(entries) == 1


# ── RSS 2.0 ────────────────────────────────────────────────────────────────


def test_rss_feed_parses_with_required_elements():
    """RSS 2.0 ``<rss version="2.0"><channel>...`` shape with
    ``<title>``, ``<link>``, ``<description>``, ``<lastBuildDate>``."""
    from app.services.feed import render_rss

    cards = [_make_card("sim_rss")]
    body = render_rss(
        cards,
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.rss",
        title="MiroShark · Public Simulations",
        subtitle="s",
    )
    root = ET.fromstring(body)
    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"
    channel = root.find("channel")
    assert channel is not None
    assert channel.findtext("title") == "MiroShark · Public Simulations"
    assert channel.findtext("link") == "https://demo.miroshark.io/explore"
    assert channel.findtext("description")
    assert channel.findtext("lastBuildDate")


def test_rss_item_uses_stable_guid_independent_of_link():
    """``<guid isPermaLink="false">`` must carry our stable identifier so
    a deployment URL change doesn't invalidate every reader's seen-item
    cache."""
    from app.services.feed import render_rss

    cards = [_make_card("sim_guid")]
    body = render_rss(
        cards,
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.rss",
        title="t",
        subtitle="s",
    )
    root = ET.fromstring(body)
    item = root.find("channel/item")
    guid = item.find("guid")
    assert guid is not None
    assert guid.attrib.get("isPermaLink") == "false"
    assert "sim_guid" in (guid.text or "")


def test_rss_includes_share_card_enclosure():
    """RSS readers (and podcatchers) read ``<enclosure>`` for media."""
    from app.services.feed import render_rss

    cards = [_make_card("sim_enc")]
    body = render_rss(
        cards,
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.rss",
        title="t",
        subtitle="s",
    )
    root = ET.fromstring(body)
    item = root.find("channel/item")
    enclosure = item.find("enclosure")
    assert enclosure is not None
    assert enclosure.attrib["type"] == "image/png"
    assert enclosure.attrib["url"].endswith("/share-card.png")


# ── render_feed dispatcher ─────────────────────────────────────────────────


def test_render_feed_dispatcher_picks_format_and_mime():
    """``render_feed("atom"|"rss")`` returns the correct MIME and
    falls back to Atom on unknown input."""
    from app.services.feed import render_feed

    body_atom, mime_atom = render_feed(
        "atom",
        [_make_card("sim_a")],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
    )
    body_rss, mime_rss = render_feed(
        "rss",
        [_make_card("sim_r")],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.rss",
    )
    body_unknown, mime_unknown = render_feed(
        "garbage",
        [_make_card("sim_g")],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
    )

    assert mime_atom.startswith("application/atom+xml")
    assert mime_rss.startswith("application/rss+xml")
    assert mime_unknown.startswith("application/atom+xml")  # fallback

    # Each body parses cleanly.
    assert ET.fromstring(body_atom).tag.endswith("feed")
    assert ET.fromstring(body_rss).tag == "rss"
    assert ET.fromstring(body_unknown).tag.endswith("feed")


def test_render_feed_verified_only_changes_title_and_alternate_path():
    """The verified variant sets a different feed title + maps the
    ``rel="alternate"`` link to ``/verified`` instead of ``/explore``."""
    from app.services.feed import render_feed

    body, _mime = render_feed(
        "atom",
        [_make_card("sim_v", outcome_label="correct")],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom?verified=1",
        verified_only=True,
    )
    root = ET.fromstring(body)
    title = root.findtext(f"{{{_ATOM_NS}}}title") or ""
    assert "Verified" in title
    alt = root.find(f"{{{_ATOM_NS}}}link[@rel='alternate']")
    assert alt is not None
    assert alt.attrib["href"].endswith("/verified")


# ── select_public_cards (selection helper) ─────────────────────────────────


def test_select_public_cards_filters_and_sorts(tmp_path):
    """Mirrors GET /api/simulation/public selection: drops private,
    sorts newest-first, applies the limit, gracefully skips bad sims."""
    from app.services.feed import select_public_cards

    states = [
        _FakeState("sim_old", is_public=True, created_at="2026-04-20T10:00:00"),
        _FakeState("sim_private", is_public=False, created_at="2026-04-29T10:00:00"),
        _FakeState("sim_new", is_public=True, created_at="2026-04-29T10:00:00"),
        _FakeState("sim_broken", is_public=True, created_at="2026-04-28T10:00:00"),
    ]

    def card_builder(state, sim_dir):
        if state.simulation_id == "sim_broken":
            raise RuntimeError("simulated artifact corruption")
        return _make_card(state.simulation_id, created_at=state.created_at)

    def outcome_reader(_sim_dir):
        return None

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=outcome_reader,
        limit=10,
        verified_only=False,
    )

    sim_ids = [c["simulation_id"] for c in cards]
    # Private is filtered, broken is skipped, newest first.
    assert sim_ids == ["sim_new", "sim_old"]


def test_select_public_cards_verified_only_filters_to_outcome_records(tmp_path):
    """Verified-only selection must only emit cards for sims whose
    ``outcome.json`` is readable — even if the gallery card itself
    builds successfully without one."""
    from app.services.feed import select_public_cards

    states = [
        _FakeState("sim_with_outcome", is_public=True, created_at="2026-04-29T10:00:00"),
        _FakeState("sim_no_outcome", is_public=True, created_at="2026-04-29T11:00:00"),
    ]

    def card_builder(state, sim_dir):
        return _make_card(state.simulation_id, created_at=state.created_at)

    def outcome_reader(sim_dir):
        if sim_dir.endswith("sim_with_outcome"):
            return {"label": "correct"}
        return None

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=outcome_reader,
        limit=10,
        verified_only=True,
    )
    assert [c["simulation_id"] for c in cards] == ["sim_with_outcome"]


def test_select_public_cards_caps_at_default_limit(tmp_path):
    """The 20-entry cap is enforced by the helper so the route layer
    can't accidentally serve a 1MB feed."""
    from app.services.feed import DEFAULT_FEED_LIMIT, select_public_cards

    states = [
        _FakeState(f"sim_{i:03d}", is_public=True, created_at=f"2026-04-29T{i:02d}:00:00")
        for i in range(40)
    ]

    def card_builder(state, _sim_dir):
        return _make_card(state.simulation_id, created_at=state.created_at)

    def outcome_reader(_sim_dir):
        return None

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=outcome_reader,
        limit=DEFAULT_FEED_LIMIT,
        verified_only=False,
    )
    assert len(cards) == DEFAULT_FEED_LIMIT


# ── Route presence (drift guard) ───────────────────────────────────────────


def test_feed_routes_registered_on_feed_blueprint():
    """Sanity check on the blueprint wiring — the OpenAPI drift test
    is the one that fails loud on a missing spec entry, but it relies on
    the routes existing in source. This guards the source side."""
    feed_module = (_BACKEND / "app" / "api" / "feed.py").read_text(encoding="utf-8")
    assert "@feed_bp.route(\"/feed.atom\"" in feed_module
    assert "@feed_bp.route(\"/feed.rss\"" in feed_module
