"""Unit tests for the filtered RSS / Atom feed surface.

Composes the existing ``gallery_filters`` knobs onto the feed renderer so
a bookmarked ``/api/feed.atom?consensus=bullish&quality=excellent`` URL
answers the same question as the gallery API. The tests are pure offline
checks: they exercise the filter composition + title reflection
contracts through ``select_public_cards`` and ``render_feed`` directly,
matching the style of ``test_unit_feed.py``.

The contracts covered:

  1. ``?consensus=bullish`` keeps only bullish-dominant sims; the same
     ±0.2 threshold the gallery, share card, and webhook all share so
     no surface diverges on a 33.4 / 33.3 / 33.3 split.
  2. ``?quality=excellent`` keeps only excellent-tier sims; matches
     against the lowercased first word of ``quality_health`` so
     ``"Good with caveats"`` slots into ``quality=good``.
  3. Filters combine with logical AND — ``?consensus=bullish&quality=excellent``
     intersects them; an empty intersection serves an empty (but valid)
     feed.
  4. ``?sort=trending`` ranks public sims by their cumulative
     share-surface serves — fed in via the ``surface_stats_reader``
     callback so the helper stays Flask-free.
  5. ``?sort`` with an unknown value falls back to ``date`` (newest
     first), preserving the gallery's graceful-degradation contract.
  6. ``?q=`` does case-insensitive substring matching against the
     scenario text.
  7. ``?limit=`` is honoured up to the feed-specific cap (50) — larger
     values are clamped, non-numeric input falls back to the default.
  8. ``?verified=1`` continues to use the on-disk outcome reader (no
     regression on the existing gate).
  9. The Atom/RSS title + subtitle reflect active filters — a subscriber
     can tell at a glance which slice of the gallery they're on
     ("MiroShark · Public Simulations · Bullish + Excellent").
 10. Unfiltered feeds keep the original title (no surprise change for
     existing subscribers).
 11. The ``rel="self"`` link still carries the full query string so a
     reader auto-discovering a filtered feed re-fetches the same slice.
 12. The route module wires the new query-string knobs through to the
     selection helper (drift guard on the source side).
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


_ATOM_NS = "http://www.w3.org/2005/Atom"


# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_card(
    sim_id: str,
    *,
    scenario: str = "Will the SEC approve a spot Solana ETF before Q3?",
    created_at: str = "2026-05-12T10:12:34",
    bullish: float = 62.0,
    neutral: float = 13.0,
    bearish: float = 25.0,
    quality_health: str = "Excellent",
    outcome_label: str | None = None,
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
        "final_consensus": {
            "bullish": bullish,
            "neutral": neutral,
            "bearish": bearish,
        },
        "resolution_outcome": None,
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
            "outcome_summary": "Resolved.",
            "submitted_at": "2026-05-12T11:00:00Z",
        }
    return card


class _FakeState:
    """Minimal stand-in for SimulationState used by select_public_cards."""

    def __init__(
        self,
        sim_id: str,
        *,
        is_public: bool = True,
        created_at: str = "2026-05-12T10:12:34",
    ):
        self.simulation_id = sim_id
        self.is_public = is_public
        self.created_at = created_at


# ── 1: consensus filter ─────────────────────────────────────────────────────


def test_consensus_bullish_keeps_only_bullish_dominant_cards(tmp_path):
    """``?consensus=bullish`` keeps cards whose dominant stance is
    bullish using the same ±0.2 threshold every other surface uses."""
    from app.services.feed import select_public_cards

    states = [
        _FakeState("sim_bull", created_at="2026-05-12T10:00:00"),
        _FakeState("sim_bear", created_at="2026-05-12T11:00:00"),
        _FakeState("sim_neut", created_at="2026-05-12T12:00:00"),
    ]
    payloads = {
        "sim_bull": (70.0, 10.0, 20.0),
        "sim_bear": (10.0, 20.0, 70.0),
        "sim_neut": (33.4, 33.3, 33.3),
    }

    def card_builder(state, _sim_dir):
        b, n, br = payloads[state.simulation_id]
        return _make_card(
            state.simulation_id,
            created_at=state.created_at,
            bullish=b,
            neutral=n,
            bearish=br,
        )

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=20,
        consensus="bullish",
    )
    assert [c["simulation_id"] for c in cards] == ["sim_bull"]


def test_consensus_filter_excludes_near_tie_runs(tmp_path):
    """A 33.4 / 33.3 / 33.3 split has no dominant stance — it must be
    filtered out by any ``consensus=…`` value, matching the gallery."""
    from app.services.feed import select_public_cards

    states = [_FakeState("sim_split", created_at="2026-05-12T10:00:00")]

    def card_builder(state, _sim_dir):
        return _make_card(
            state.simulation_id,
            created_at=state.created_at,
            bullish=33.4,
            neutral=33.3,
            bearish=33.3,
        )

    for stance in ("bullish", "neutral", "bearish"):
        cards = select_public_cards(
            states,
            sim_data_dir=str(tmp_path),
            card_builder=card_builder,
            outcome_reader=lambda _d: None,
            limit=20,
            consensus=stance,
        )
        assert cards == [], f"near-tie leaked into consensus={stance}"


# ── 2: quality filter ──────────────────────────────────────────────────────


def test_quality_excellent_filters_to_excellent_tier(tmp_path):
    """``?quality=excellent`` keeps only ``quality_health`` rows whose
    lowercased first word is ``excellent`` — case-insensitive."""
    from app.services.feed import select_public_cards

    states = [
        _FakeState("sim_excellent", created_at="2026-05-12T10:00:00"),
        _FakeState("sim_good", created_at="2026-05-12T11:00:00"),
        _FakeState("sim_unknown", created_at="2026-05-12T12:00:00"),
    ]
    qualities = {
        "sim_excellent": "Excellent",
        "sim_good": "Good with caveats",
        "sim_unknown": "",
    }

    def card_builder(state, _sim_dir):
        return _make_card(
            state.simulation_id,
            created_at=state.created_at,
            quality_health=qualities[state.simulation_id],
        )

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=20,
        quality="excellent",
    )
    assert [c["simulation_id"] for c in cards] == ["sim_excellent"]


def test_quality_good_matches_good_with_caveats(tmp_path):
    """``quality_health = 'Good with caveats'`` slots into
    ``quality=good`` — parity with the gallery's first-word match."""
    from app.services.feed import select_public_cards

    states = [_FakeState("sim_good_caveats", created_at="2026-05-12T11:00:00")]

    def card_builder(state, _sim_dir):
        return _make_card(
            state.simulation_id,
            created_at=state.created_at,
            quality_health="Good with caveats",
        )

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=20,
        quality="good",
    )
    assert [c["simulation_id"] for c in cards] == ["sim_good_caveats"]


# ── 3: combined filters (logical AND) ─────────────────────────────────────


def test_consensus_and_quality_combine_with_logical_and(tmp_path):
    """``?consensus=bullish&quality=excellent`` returns the intersection
    of both filters — not the union."""
    from app.services.feed import select_public_cards

    states = [
        _FakeState("sim_bull_exc", created_at="2026-05-12T10:00:00"),
        _FakeState("sim_bull_fair", created_at="2026-05-12T11:00:00"),
        _FakeState("sim_bear_exc", created_at="2026-05-12T12:00:00"),
    ]
    table = {
        "sim_bull_exc": (70.0, 10.0, 20.0, "Excellent"),
        "sim_bull_fair": (70.0, 10.0, 20.0, "Fair"),
        "sim_bear_exc": (10.0, 20.0, 70.0, "Excellent"),
    }

    def card_builder(state, _sim_dir):
        b, n, br, q = table[state.simulation_id]
        return _make_card(
            state.simulation_id,
            created_at=state.created_at,
            bullish=b,
            neutral=n,
            bearish=br,
            quality_health=q,
        )

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=20,
        consensus="bullish",
        quality="excellent",
    )
    assert [c["simulation_id"] for c in cards] == ["sim_bull_exc"]


def test_empty_intersection_serves_empty_feed(tmp_path):
    """Filters that exclude everything still produce a clean empty
    selection — no exception, no fallback to "show all"."""
    from app.services.feed import select_public_cards

    states = [_FakeState("sim_x", created_at="2026-05-12T10:00:00")]

    def card_builder(state, _sim_dir):
        return _make_card(
            state.simulation_id,
            created_at=state.created_at,
            bullish=70.0,
            neutral=10.0,
            bearish=20.0,
            quality_health="Fair",
        )

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=20,
        consensus="bearish",
        quality="excellent",
    )
    assert cards == []


# ── 4: trending sort wired through callback ───────────────────────────────


def test_trending_sort_uses_surface_stats_reader(tmp_path):
    """``sort=trending`` calls the supplied callback for each card and
    orders highest-serves-first; ties break on ``created_at`` so the
    most-recent-of-the-tied lands first."""
    from app.services.feed import select_public_cards

    states = [
        _FakeState("sim_a", created_at="2026-05-12T10:00:00"),
        _FakeState("sim_b", created_at="2026-05-12T11:00:00"),
        _FakeState("sim_c", created_at="2026-05-12T12:00:00"),
    ]
    serves = {
        "sim_a": 7,
        "sim_b": 42,
        "sim_c": 0,
    }

    def card_builder(state, _sim_dir):
        return _make_card(state.simulation_id, created_at=state.created_at)

    def reader(sim_dir: str) -> int:
        sim_id = sim_dir.rsplit("/", 1)[-1]
        return serves.get(sim_id, 0)

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=20,
        sort="trending",
        surface_stats_reader=reader,
    )
    assert [c["simulation_id"] for c in cards] == ["sim_b", "sim_a", "sim_c"]
    # Transient trending field must be stripped from the card payload —
    # it's a sort key, not part of the public response.
    for card in cards:
        assert "_serves_total" not in card


# ── 5: graceful degradation on bad sort key ───────────────────────────────


def test_unknown_sort_falls_back_to_date(tmp_path):
    """``?sort=invalid`` falls back to ``date`` — preserves the
    gallery's graceful-degradation contract for typo'd inputs."""
    from app.services.feed import select_public_cards

    states = [
        _FakeState("sim_old", created_at="2026-05-10T10:00:00"),
        _FakeState("sim_new", created_at="2026-05-12T10:00:00"),
    ]

    def card_builder(state, _sim_dir):
        return _make_card(state.simulation_id, created_at=state.created_at)

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=20,
        sort="this-is-not-a-valid-sort-key",
    )
    assert [c["simulation_id"] for c in cards] == ["sim_new", "sim_old"]


# ── 6: case-insensitive scenario search ───────────────────────────────────


def test_q_does_case_insensitive_scenario_substring_match(tmp_path):
    """``?q=`` matches the scenario substring case-insensitively — the
    same behaviour the gallery has."""
    from app.services.feed import select_public_cards

    states = [
        _FakeState("sim_etf", created_at="2026-05-12T10:00:00"),
        _FakeState("sim_election", created_at="2026-05-12T11:00:00"),
    ]
    scenarios = {
        "sim_etf": "Will the SEC approve a spot Solana ETF before Q3?",
        "sim_election": "Will turnout exceed 60% in the November vote?",
    }

    def card_builder(state, _sim_dir):
        return _make_card(
            state.simulation_id,
            created_at=state.created_at,
            scenario=scenarios[state.simulation_id],
        )

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=20,
        q="etf",
    )
    assert [c["simulation_id"] for c in cards] == ["sim_etf"]


# ── 7: limit clamping ─────────────────────────────────────────────────────


def test_limit_above_feed_cap_clamps_to_max(tmp_path):
    """``?limit=999`` must clamp to ``MAX_FEED_LIMIT`` — protects bots
    from extracting the whole gallery in one fetch."""
    from app.services.feed import MAX_FEED_LIMIT, select_public_cards

    states = [
        _FakeState(f"sim_{i:03d}", created_at=f"2026-05-12T{i:02d}:00:00")
        for i in range(MAX_FEED_LIMIT + 10)
    ]

    def card_builder(state, _sim_dir):
        return _make_card(state.simulation_id, created_at=state.created_at)

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=999,
    )
    assert len(cards) == MAX_FEED_LIMIT


def test_default_limit_unchanged_for_legacy_callers(tmp_path):
    """The pre-existing default (20) stays the same — no regression for
    callers that don't pass ``limit=``."""
    from app.services.feed import DEFAULT_FEED_LIMIT, select_public_cards

    states = [
        _FakeState(f"sim_{i:03d}", created_at=f"2026-05-12T{i:02d}:00:00")
        for i in range(DEFAULT_FEED_LIMIT + 5)
    ]

    def card_builder(state, _sim_dir):
        return _make_card(state.simulation_id, created_at=state.created_at)

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
    )
    assert len(cards) == DEFAULT_FEED_LIMIT


# ── 8: verified gate composes with on-disk outcome reader ────────────────


def test_verified_only_still_uses_outcome_reader(tmp_path):
    """The existing ``verified_only`` gate must keep working even after
    the new query knobs land — no regression on PR #60's contract."""
    from app.services.feed import select_public_cards

    states = [
        _FakeState("sim_with_outcome", created_at="2026-05-12T10:00:00"),
        _FakeState("sim_no_outcome", created_at="2026-05-12T11:00:00"),
    ]

    def card_builder(state, _sim_dir):
        return _make_card(state.simulation_id, created_at=state.created_at)

    def outcome_reader(sim_dir):
        return {"label": "correct"} if sim_dir.endswith("sim_with_outcome") else None

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=outcome_reader,
        limit=20,
        verified_only=True,
    )
    assert [c["simulation_id"] for c in cards] == ["sim_with_outcome"]


# ── 9 & 10: render_feed reflects active filters in title/subtitle ────────


def test_render_feed_title_reflects_active_consensus_and_quality_filters():
    """Active filters surface in the channel title + subtitle so a
    subscriber can tell which slice they're on at a glance."""
    from app.services.feed import render_feed

    body, _mime = render_feed(
        "atom",
        [_make_card("sim_z")],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom?consensus=bullish&quality=excellent",
        consensus="bullish",
        quality="excellent",
    )
    root = ET.fromstring(body)
    title = root.findtext(f"{{{_ATOM_NS}}}title") or ""
    subtitle = root.findtext(f"{{{_ATOM_NS}}}subtitle") or ""
    assert "Bullish" in title
    assert "Excellent" in title
    assert "Filtered" in subtitle


def test_render_feed_title_unchanged_when_no_filters_active():
    """No filters → original title (no surprise change for existing
    subscribers of ``/api/feed.atom``)."""
    from app.services.feed import render_feed

    body, _mime = render_feed(
        "atom",
        [_make_card("sim_y")],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom",
    )
    root = ET.fromstring(body)
    title = root.findtext(f"{{{_ATOM_NS}}}title") or ""
    assert title == "MiroShark · Public Simulations"


# ── 11: rel="self" carries the query string ──────────────────────────────


def test_render_feed_self_link_preserves_filter_query_string():
    """A reader auto-discovering a filtered feed (Substack `<link
    rel="self">` discovery) must re-fetch the same slice, so the
    ``rel="self"`` link has to echo the full query string."""
    from app.services.feed import render_feed

    body, _mime = render_feed(
        "atom",
        [],
        base_url="https://demo.miroshark.io",
        feed_path="/api/feed.atom?consensus=bullish&sort=trending",
        consensus="bullish",
        sort="trending",
    )
    root = ET.fromstring(body)
    self_link = root.find(f"{{{_ATOM_NS}}}link[@rel='self']")
    assert self_link is not None
    href = self_link.attrib["href"]
    assert "consensus=bullish" in href
    assert "sort=trending" in href


# ── 12: route source drift guard ─────────────────────────────────────────


def test_feed_route_wires_all_new_filter_params():
    """Source-side guard — the feed route must read every new query
    knob so the OpenAPI spec stays honest about what the endpoint
    accepts. The drift test pairs with the unit-test coverage above
    (which exercises the helper directly)."""
    feed_module = (_BACKEND / "app" / "api" / "feed.py").read_text(encoding="utf-8")
    for param in ("consensus", "quality", "outcome", "sort", "limit"):
        assert (
            f'request.args.get("{param}")' in feed_module
            or f"request.args.get('{param}')" in feed_module
        ), f"feed route never reads ?{param}="
    # Surface-stats reader is only wired for the trending sort path —
    # guard the source so a future refactor doesn't accidentally drop it.
    assert "_read_serves_total" in feed_module
    assert "surface_stats_reader" in feed_module


# ── Sanity: an unknown filter value falls back to "ignore filter" ─────────


def test_unknown_consensus_value_is_treated_as_no_filter(tmp_path):
    """A typo like ``?consensus=bullsih`` must NOT empty the feed — the
    gallery's normalise_* helpers return ``None`` for unknown values, so
    the corresponding card filter degrades to a no-op."""
    from app.services.feed import select_public_cards

    states = [_FakeState("sim_any", created_at="2026-05-12T10:00:00")]

    def card_builder(state, _sim_dir):
        return _make_card(
            state.simulation_id,
            created_at=state.created_at,
            bullish=70.0,
            neutral=10.0,
            bearish=20.0,
        )

    cards = select_public_cards(
        states,
        sim_data_dir=str(tmp_path),
        card_builder=card_builder,
        outcome_reader=lambda _d: None,
        limit=20,
        # gallery_filters.normalise_consensus returns None for unknowns;
        # we pass None directly to mirror what the route layer hands in
        # after normalisation.
        consensus=None,
    )
    assert [c["simulation_id"] for c in cards] == ["sim_any"]
