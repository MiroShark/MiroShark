"""Unit tests for the public-gallery filter / sort / paginate helpers.

The ``app/services/gallery_filters.py`` module is what gives
``GET /api/simulation/public`` its keyword search, consensus filter,
quality filter, outcome filter, and sort key. These tests run offline
against plain-dict gallery cards — no Flask, no SimulationManager, no
filesystem — so the contract is locked in regardless of how the
endpoint evolves.

We cover:

  1. Param normalisation (limit clamping, offset flooring, page→offset
     conversion, query trimming/capping, enum lookup).
  2. ``dominant_stance`` matches the same ±0.2 threshold the share card,
     replay GIF, transcript, webhook, and feed renderers use.
  3. Each filter (`q`, `consensus`, `quality`, `outcome`,
     `verified_only`) restricts the result set correctly, both alone
     and in combination.
  4. Sort orders are deterministic — newest-first by date, largest-first
     by rounds and agents.
  5. ``select_filtered_cards`` returns the right ``(page_items, total)``
     shape after filter → sort → paginate.
  6. Graceful degradation on corrupt cards (missing fields, wrong
     types, empty consensus) so one bad sim doesn't blank the gallery.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import gallery_filters as gf


# ── Card factory ──────────────────────────────────────────────────────────


def _card(
    sid: str,
    *,
    scenario: str = "",
    bullish: float = 0.0,
    neutral: float = 0.0,
    bearish: float = 0.0,
    quality_health: str | None = None,
    outcome_label: str | None = None,
    outcome_url: str | None = None,
    created_at: str = "2026-04-22T10:12:34",
    current_round: int = 0,
    agent_count: int = 0,
) -> dict:
    consensus: dict | None = None
    if (bullish or neutral or bearish):
        consensus = {"bullish": bullish, "neutral": neutral, "bearish": bearish}
    outcome: dict | None = None
    if outcome_label is not None:
        outcome = {"label": outcome_label}
        if outcome_url:
            outcome["outcome_url"] = outcome_url
    return {
        "simulation_id": sid,
        "scenario": scenario,
        "final_consensus": consensus,
        "quality_health": quality_health,
        "outcome": outcome,
        "created_at": created_at,
        "current_round": current_round,
        "agent_count": agent_count,
    }


# ── Param normalisation ───────────────────────────────────────────────────


class TestNormaliseLimit:
    def test_default_when_missing(self):
        assert gf.normalise_limit(None) == gf.DEFAULT_LIMIT

    def test_clamps_below_one_to_one(self):
        assert gf.normalise_limit(0) == 1
        assert gf.normalise_limit(-5) == 1

    def test_clamps_above_max(self):
        assert gf.normalise_limit(9999) == gf.MAX_LIMIT
        assert gf.normalise_limit(gf.MAX_LIMIT + 1) == gf.MAX_LIMIT

    def test_passes_through_valid(self):
        assert gf.normalise_limit(25) == 25

    def test_garbage_input_falls_back_to_default(self):
        assert gf.normalise_limit("not-a-number") == gf.DEFAULT_LIMIT
        assert gf.normalise_limit(object()) == gf.DEFAULT_LIMIT


class TestNormaliseOffset:
    def test_default_when_missing(self):
        assert gf.normalise_offset(None) == 0

    def test_negative_floors_to_zero(self):
        assert gf.normalise_offset(-1) == 0
        assert gf.normalise_offset(-100) == 0

    def test_passes_through_valid(self):
        assert gf.normalise_offset(50) == 50

    def test_garbage_input_falls_back_to_zero(self):
        assert gf.normalise_offset("nope") == 0


class TestPageToOffset:
    def test_page_one_is_offset_zero(self):
        assert gf.page_to_offset(1, 30) == 0

    def test_page_two_uses_limit(self):
        assert gf.page_to_offset(2, 30) == 30
        assert gf.page_to_offset(3, 50) == 100

    def test_zero_or_negative_clamps_to_page_one(self):
        assert gf.page_to_offset(0, 30) == 0
        assert gf.page_to_offset(-5, 30) == 0

    def test_garbage_input_treated_as_page_one(self):
        assert gf.page_to_offset("oops", 30) == 0
        assert gf.page_to_offset(None, 30) == 0


class TestNormaliseQuery:
    def test_empty_inputs(self):
        assert gf.normalise_query(None) == ""
        assert gf.normalise_query("") == ""
        assert gf.normalise_query("   ") == ""

    def test_trims_whitespace(self):
        assert gf.normalise_query("  aave   ") == "aave"

    def test_caps_long_input(self):
        long = "x" * (gf.MAX_QUERY_CHARS + 50)
        assert len(gf.normalise_query(long)) == gf.MAX_QUERY_CHARS


class TestNormaliseEnums:
    @pytest.mark.parametrize("value", ["bullish", "BULLISH", "  bullish ", "Bullish"])
    def test_consensus_accepts_valid(self, value: str):
        assert gf.normalise_consensus(value) == "bullish"

    @pytest.mark.parametrize("value", ["", None, "moonish", "ish"])
    def test_consensus_rejects_invalid(self, value):
        assert gf.normalise_consensus(value) is None

    @pytest.mark.parametrize("value,expected", [
        ("excellent", "excellent"),
        ("EXCELLENT", "excellent"),
        ("Good", "good"),
        ("nope", None),
        ("", None),
    ])
    def test_quality_normalisation(self, value, expected):
        assert gf.normalise_quality(value) == expected

    @pytest.mark.parametrize("value,expected", [
        ("correct", "correct"),
        ("INCORRECT", "incorrect"),
        ("partial", "partial"),
        ("verified", None),
        ("", None),
    ])
    def test_outcome_normalisation(self, value, expected):
        assert gf.normalise_outcome(value) == expected

    @pytest.mark.parametrize("value,expected", [
        ("date", "date"),
        ("Rounds", "rounds"),
        ("AGENTS", "agents"),
        ("", "date"),
        (None, "date"),
        ("popularity", "date"),
    ])
    def test_sort_falls_back_to_date(self, value, expected):
        assert gf.normalise_sort(value) == expected


# ── dominant_stance — ±0.2 threshold parity ──────────────────────────────


class TestDominantStance:
    def test_picks_bullish_when_dominant(self):
        c = _card("a", bullish=70.0, neutral=20.0, bearish=10.0)
        assert gf.dominant_stance(c) == "bullish"

    def test_picks_bearish_when_dominant(self):
        c = _card("a", bullish=10.0, neutral=20.0, bearish=70.0)
        assert gf.dominant_stance(c) == "bearish"

    def test_picks_neutral_when_dominant(self):
        c = _card("a", bullish=10.0, neutral=80.0, bearish=10.0)
        assert gf.dominant_stance(c) == "neutral"

    def test_none_when_no_consensus(self):
        c = _card("a")
        assert gf.dominant_stance(c) is None

    def test_none_when_consensus_corrupted(self):
        c = _card("a")
        c["final_consensus"] = "not-a-dict"
        assert gf.dominant_stance(c) is None

    def test_none_when_all_zero(self):
        c = _card("a")
        c["final_consensus"] = {"bullish": 0, "neutral": 0, "bearish": 0}
        assert gf.dominant_stance(c) is None

    def test_tie_is_deterministic_lexically(self):
        # 40/40/20 tie — bullish < neutral lexically, so bullish wins.
        c = _card("a", bullish=40.0, neutral=40.0, bearish=20.0)
        assert gf.dominant_stance(c) == "bullish"

    def test_handles_string_percentages(self):
        c = _card("a")
        c["final_consensus"] = {"bullish": "70.0", "neutral": "20", "bearish": "10"}
        assert gf.dominant_stance(c) == "bullish"


# ── filter_cards — each filter alone + combined ──────────────────────────


class TestFilterCards:
    @pytest.fixture
    def corpus(self):
        return [
            _card("a", scenario="Will the SEC approve a spot Aave ETF?",
                  bullish=70, neutral=20, bearish=10,
                  quality_health="Excellent",
                  outcome_label="correct"),
            _card("b", scenario="ETH staking yield in Q3",
                  bullish=10, neutral=20, bearish=70,
                  quality_health="Good"),
            _card("c", scenario="Bitcoin halving impact on AAVE pools",
                  bullish=10, neutral=80, bearish=10,
                  quality_health="Fair",
                  outcome_label="partial"),
            _card("d", scenario="DOGE meme cycle",
                  bullish=33.4, neutral=33.3, bearish=33.3,
                  quality_health="Poor",
                  outcome_label="incorrect"),
            _card("e", scenario="No data yet — fresh sim"),
        ]

    def test_no_filters_returns_everything(self, corpus):
        out = gf.filter_cards(corpus)
        assert {c["simulation_id"] for c in out} == {"a", "b", "c", "d", "e"}

    def test_q_substring_case_insensitive(self, corpus):
        out = gf.filter_cards(corpus, q="aave")
        # Matches 'Aave ETF' and 'AAVE pools'.
        assert {c["simulation_id"] for c in out} == {"a", "c"}

    def test_q_no_match_returns_empty(self, corpus):
        out = gf.filter_cards(corpus, q="xrp moon mission")
        assert out == []

    def test_consensus_bullish_only(self, corpus):
        out = gf.filter_cards(corpus, consensus="bullish")
        assert {c["simulation_id"] for c in out} == {"a"}

    def test_consensus_bearish_only(self, corpus):
        out = gf.filter_cards(corpus, consensus="bearish")
        assert {c["simulation_id"] for c in out} == {"b"}

    def test_consensus_neutral_only(self, corpus):
        out = gf.filter_cards(corpus, consensus="neutral")
        assert {c["simulation_id"] for c in out} == {"c"}

    def test_quality_excellent_only(self, corpus):
        out = gf.filter_cards(corpus, quality="excellent")
        assert {c["simulation_id"] for c in out} == {"a"}

    def test_outcome_partial_only(self, corpus):
        out = gf.filter_cards(corpus, outcome="partial")
        assert {c["simulation_id"] for c in out} == {"c"}

    def test_verified_only_keeps_outcome_set(self, corpus):
        out = gf.filter_cards(corpus, verified_only=True)
        assert {c["simulation_id"] for c in out} == {"a", "c", "d"}

    def test_combined_q_and_consensus(self, corpus):
        # 'aave' matches a + c. consensus=neutral keeps only c.
        out = gf.filter_cards(corpus, q="aave", consensus="neutral")
        assert {c["simulation_id"] for c in out} == {"c"}

    def test_combined_q_and_outcome(self, corpus):
        # 'aave' matches a + c. outcome=correct keeps only a.
        out = gf.filter_cards(corpus, q="aave", outcome="correct")
        assert {c["simulation_id"] for c in out} == {"a"}

    def test_combined_consensus_and_quality(self, corpus):
        out = gf.filter_cards(corpus, consensus="bullish", quality="excellent")
        assert {c["simulation_id"] for c in out} == {"a"}

    def test_garbage_cards_skipped(self, corpus):
        garbage = corpus + ["not-a-dict", None, 42]  # type: ignore[list-item]
        out = gf.filter_cards(garbage, q="aave")
        assert {c["simulation_id"] for c in out} == {"a", "c"}


# ── sort_cards ────────────────────────────────────────────────────────────


class TestSortCards:
    def test_date_desc_default(self):
        cards = [
            _card("old", created_at="2026-01-10T00:00:00"),
            _card("new", created_at="2026-04-30T00:00:00"),
            _card("mid", created_at="2026-03-15T00:00:00"),
        ]
        out = gf.sort_cards(cards, sort="date")
        assert [c["simulation_id"] for c in out] == ["new", "mid", "old"]

    def test_rounds_desc(self):
        cards = [
            _card("a", current_round=10, agent_count=100),
            _card("b", current_round=50, agent_count=100),
            _card("c", current_round=30, agent_count=100),
        ]
        out = gf.sort_cards(cards, sort="rounds")
        assert [c["simulation_id"] for c in out] == ["b", "c", "a"]

    def test_agents_desc(self):
        cards = [
            _card("a", agent_count=20),
            _card("b", agent_count=200),
            _card("c", agent_count=80),
        ]
        out = gf.sort_cards(cards, sort="agents")
        assert [c["simulation_id"] for c in out] == ["b", "c", "a"]

    def test_unknown_sort_falls_back_to_date(self):
        cards = [
            _card("old", created_at="2026-01-01T00:00:00"),
            _card("new", created_at="2026-05-01T00:00:00"),
        ]
        out = gf.sort_cards(cards, sort="rumours")
        assert out[0]["simulation_id"] == "new"

    def test_empty_list_returns_empty(self):
        assert gf.sort_cards([], sort="date") == []
        assert gf.sort_cards([], sort="rounds") == []


# ── select_filtered_cards — end-to-end ────────────────────────────────────


class TestSelectFilteredCards:
    def test_returns_filtered_total_not_corpus_total(self):
        cards = [
            _card("a", bullish=70, scenario="aave"),
            _card("b", bullish=70, scenario="eth"),
            _card("c", bearish=70, scenario="btc"),
        ]
        page, total = gf.select_filtered_cards(cards, consensus="bullish")
        assert total == 2  # filtered, not 3
        assert {c["simulation_id"] for c in page} == {"a", "b"}

    def test_pagination_slices_after_sort(self):
        cards = [
            _card(f"sim_{i:02d}", created_at=f"2026-04-{i+1:02d}T00:00:00")
            for i in range(10)
        ]
        page1, total1 = gf.select_filtered_cards(cards, limit=3, offset=0)
        page2, total2 = gf.select_filtered_cards(cards, limit=3, offset=3)
        assert total1 == total2 == 10
        # Newest first, so page1 = sim_09, sim_08, sim_07.
        assert [c["simulation_id"] for c in page1] == ["sim_09", "sim_08", "sim_07"]
        assert [c["simulation_id"] for c in page2] == ["sim_06", "sim_05", "sim_04"]

    def test_offset_past_total_returns_empty_page(self):
        cards = [_card("a"), _card("b")]
        page, total = gf.select_filtered_cards(cards, limit=10, offset=100)
        assert page == []
        assert total == 2

    def test_q_consensus_quality_combine_correctly(self):
        cards = [
            _card("a", scenario="Aave outlook", bullish=70,
                  quality_health="Excellent"),
            _card("b", scenario="Aave outlook", bullish=70,
                  quality_health="Poor"),
            _card("c", scenario="Aave outlook", bearish=70,
                  quality_health="Excellent"),
            _card("d", scenario="ETH outlook", bullish=70,
                  quality_health="Excellent"),
        ]
        page, total = gf.select_filtered_cards(
            cards,
            q="aave",
            consensus="bullish",
            quality="excellent",
        )
        assert total == 1
        assert [c["simulation_id"] for c in page] == ["a"]

    def test_empty_corpus_returns_empty_page_and_zero_total(self):
        page, total = gf.select_filtered_cards([])
        assert page == []
        assert total == 0
