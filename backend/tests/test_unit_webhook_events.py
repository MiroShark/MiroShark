"""Unit tests for ``WEBHOOK_EVENTS`` — the dispatch-time event filter.

Covers three properties:

  1. The parser normalises a comma-separated env var into a lowercase
     token set, and an empty / unset value yields an empty set
     (= "fire on everything", existing backward-compatible behavior).
  2. ``payload_passes_event_filter`` evaluates the per-category rules
     correctly — direction tokens OR within themselves, confidence
     tokens OR within themselves, quality tokens OR within themselves,
     and the three categories AND across each other.
  3. ``fire_webhook_for_simulation`` short-circuits before the dispatch
     thread when the filter rejects, and proceeds normally when it
     passes, so an integrator wiring ``WEBHOOK_EVENTS=bullish,high_confidence``
     gets exactly the alerts they asked for.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def bullish_high_conf_payload() -> dict:
    """A canonical completed-sim payload: Bullish leader at 75%, excellent quality."""
    return {
        "event": "simulation.completed",
        "sim_id": "sim_bull_high",
        "status": "completed",
        "final_consensus": {"bullish": 75.0, "neutral": 15.0, "bearish": 10.0},
        "quality_health": "Excellent",
    }


@pytest.fixture
def neutral_medium_conf_payload() -> dict:
    return {
        "event": "simulation.completed",
        "sim_id": "sim_neutral_med",
        "status": "completed",
        "final_consensus": {"bullish": 30.0, "neutral": 55.0, "bearish": 15.0},
        "quality_health": "good",
    }


@pytest.fixture
def bearish_low_conf_payload() -> dict:
    return {
        "event": "simulation.completed",
        "sim_id": "sim_bear_low",
        "status": "completed",
        "final_consensus": {"bullish": 30.0, "neutral": 30.0, "bearish": 40.0},
        "quality_health": "fair",
    }


@pytest.fixture
def populated_sim_dir(tmp_path: Path) -> Path:
    """A simulation directory whose trajectory ends bullish at 50%."""
    (tmp_path / "simulation_config.json").write_text(json.dumps({
        "simulation_requirement": "Will the SEC approve a spot Solana ETF?",
        "time_config": {"minutes_per_round": 60, "total_simulation_hours": 20},
    }))
    (tmp_path / "quality.json").write_text(json.dumps({
        "health": "Excellent",
        "participation_rate": 0.92,
    }))
    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {
                "round_num": 1,
                "belief_positions": {
                    "a": {"topic": 0.6},
                    "b": {"topic": 0.4},
                    "c": {"topic": -0.5},
                    "d": {"topic": 0.0},
                },
            },
        ],
    }))
    (tmp_path / "state.json").write_text(json.dumps({
        "profiles_count": 248,
        "created_at": "2026-04-26T10:12:34",
    }))
    return tmp_path


# ── Parser tests ──────────────────────────────────────────────────────────


def test_resolve_event_filter_unset_returns_empty_set(monkeypatch):
    from app.services import webhook_service

    monkeypatch.delenv("WEBHOOK_EVENTS", raising=False)
    assert webhook_service._resolve_event_filter() == set()


def test_resolve_event_filter_blank_returns_empty_set(monkeypatch):
    from app.services import webhook_service

    monkeypatch.setenv("WEBHOOK_EVENTS", "   ")
    assert webhook_service._resolve_event_filter() == set()


def test_resolve_event_filter_normalises_case_and_whitespace(monkeypatch):
    from app.services import webhook_service

    monkeypatch.setenv("WEBHOOK_EVENTS", "  Bullish , HIGH_CONFIDENCE , ,bearish ")
    assert webhook_service._resolve_event_filter() == {
        "bullish", "high_confidence", "bearish",
    }


def test_resolve_event_filter_keeps_unknown_tokens(monkeypatch):
    """The parser is non-judgemental — `payload_passes_event_filter`
    ignores unknowns. Keeping them in the set lets the log entry show
    operators what they typed."""
    from app.services import webhook_service

    monkeypatch.setenv("WEBHOOK_EVENTS", "bullish,vibeshift,high_confidence")
    parsed = webhook_service._resolve_event_filter()
    assert parsed == {"bullish", "vibeshift", "high_confidence"}


# ── Direction-only filter ─────────────────────────────────────────────────


def test_filter_blank_set_dispatches_everything(bullish_high_conf_payload):
    from app.services.webhook_service import payload_passes_event_filter

    passes, trace = payload_passes_event_filter(bullish_high_conf_payload, events=set())
    assert passes is True
    assert trace == {}


def test_filter_bullish_passes_bullish_blocks_bearish(
    bullish_high_conf_payload, bearish_low_conf_payload,
):
    from app.services.webhook_service import payload_passes_event_filter

    passes, _ = payload_passes_event_filter(bullish_high_conf_payload, events={"bullish"})
    assert passes is True

    passes, trace = payload_passes_event_filter(bearish_low_conf_payload, events={"bullish"})
    assert passes is False
    assert trace.get("failed_on") == "direction"
    assert trace.get("direction") == "bearish"


def test_filter_directions_or_within_category(
    bullish_high_conf_payload, neutral_medium_conf_payload, bearish_low_conf_payload,
):
    """`bullish,bearish` = "anything but neutral" — OR within the
    direction category."""
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"bullish", "bearish"}
    assert payload_passes_event_filter(bullish_high_conf_payload, events=rules)[0] is True
    assert payload_passes_event_filter(bearish_low_conf_payload, events=rules)[0] is True
    passes, trace = payload_passes_event_filter(neutral_medium_conf_payload, events=rules)
    assert passes is False
    assert trace.get("direction") == "neutral"


def test_filter_no_consensus_blocks_direction_rule():
    """A missing or all-zero ``final_consensus`` can't satisfy any
    direction rule."""
    from app.services.webhook_service import payload_passes_event_filter

    payload = {"status": "completed", "sim_id": "sim_x", "final_consensus": None}
    passes, trace = payload_passes_event_filter(payload, events={"bullish"})
    assert passes is False
    assert trace.get("direction") is None


# ── Confidence filter ─────────────────────────────────────────────────────


def test_filter_high_confidence_threshold(
    bullish_high_conf_payload, neutral_medium_conf_payload,
):
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"high_confidence"}
    assert payload_passes_event_filter(bullish_high_conf_payload, events=rules)[0] is True
    passes, trace = payload_passes_event_filter(neutral_medium_conf_payload, events=rules)
    assert passes is False
    assert trace.get("failed_on") == "confidence"


def test_filter_medium_confidence_excludes_high(
    bullish_high_conf_payload, neutral_medium_conf_payload,
):
    """`medium_confidence` alone is exclusive of `high_confidence` —
    a 75% payload doesn't satisfy a medium-only rule."""
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"medium_confidence"}
    passes, _ = payload_passes_event_filter(bullish_high_conf_payload, events=rules)
    assert passes is False
    assert payload_passes_event_filter(neutral_medium_conf_payload, events=rules)[0] is True


def test_filter_confidence_tokens_or_within_category(
    bullish_high_conf_payload, neutral_medium_conf_payload, bearish_low_conf_payload,
):
    """`medium_confidence,high_confidence` = "any sim that crossed 50%"."""
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"medium_confidence", "high_confidence"}
    assert payload_passes_event_filter(bullish_high_conf_payload, events=rules)[0] is True
    assert payload_passes_event_filter(neutral_medium_conf_payload, events=rules)[0] is True
    passes, _ = payload_passes_event_filter(bearish_low_conf_payload, events=rules)
    assert passes is False


# ── Quality filter ────────────────────────────────────────────────────────


def test_filter_excellent_quality_excludes_good(
    bullish_high_conf_payload, neutral_medium_conf_payload,
):
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"excellent_quality"}
    assert payload_passes_event_filter(bullish_high_conf_payload, events=rules)[0] is True
    passes, trace = payload_passes_event_filter(neutral_medium_conf_payload, events=rules)
    assert passes is False
    assert trace.get("quality_health") == "good"


def test_filter_good_quality_includes_excellent(
    bullish_high_conf_payload, neutral_medium_conf_payload, bearish_low_conf_payload,
):
    """`good_quality` = "good or better" — excellent counts."""
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"good_quality"}
    assert payload_passes_event_filter(bullish_high_conf_payload, events=rules)[0] is True
    assert payload_passes_event_filter(neutral_medium_conf_payload, events=rules)[0] is True
    assert payload_passes_event_filter(bearish_low_conf_payload, events=rules)[0] is False


# ── Cross-category AND logic ──────────────────────────────────────────────


def test_filter_ands_across_categories(
    bullish_high_conf_payload, neutral_medium_conf_payload,
):
    """`bullish,high_confidence` = "bullish AND >=75%"."""
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"bullish", "high_confidence"}
    assert payload_passes_event_filter(bullish_high_conf_payload, events=rules)[0] is True
    # Neutral leader fails the direction rule even though confidence > 50.
    passes, _ = payload_passes_event_filter(neutral_medium_conf_payload, events=rules)
    assert passes is False


def test_filter_all_three_categories_together(bullish_high_conf_payload):
    """Direction + confidence + quality — every category must pass."""
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"bullish", "high_confidence", "excellent_quality"}
    assert payload_passes_event_filter(bullish_high_conf_payload, events=rules)[0] is True

    # Swap to good quality → fails quality category, even though direction
    # + confidence pass.
    payload = dict(bullish_high_conf_payload, quality_health="good")
    passes, trace = payload_passes_event_filter(payload, events=rules)
    assert passes is False
    assert trace.get("failed_on") == "quality"


# ── Misc edge cases ──────────────────────────────────────────────────────


def test_filter_unknown_token_only_dispatches(bullish_high_conf_payload):
    """A filter with only unknown tokens is the same as no filter — a
    typo never silently turns the webhook off."""
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"vibe", "unrecognised"}
    passes, trace = payload_passes_event_filter(bullish_high_conf_payload, events=rules)
    assert passes is True
    assert trace.get("no_recognized_tokens") is True
    assert trace.get("ignored_tokens") == ["unrecognised", "vibe"]


def test_filter_unknown_token_mixed_does_not_break_recognized_rules(
    bullish_high_conf_payload, bearish_low_conf_payload,
):
    """Unknown tokens are skipped; recognized ones still rule."""
    from app.services.webhook_service import payload_passes_event_filter

    rules = {"bullish", "vibe"}
    assert payload_passes_event_filter(bullish_high_conf_payload, events=rules)[0] is True
    passes, trace = payload_passes_event_filter(bearish_low_conf_payload, events=rules)
    assert passes is False
    assert trace.get("ignored_tokens") == ["vibe"]


def test_filter_failed_status_always_dispatches():
    """A filter shouldn't swallow the alert an operator most needs to see —
    failures bypass every category check."""
    from app.services.webhook_service import payload_passes_event_filter

    payload = {
        "event": "simulation.failed",
        "sim_id": "sim_failed",
        "status": "failed",
        "final_consensus": None,
        "quality_health": None,
        "error": "runner crashed",
    }
    # Even a tight filter that wouldn't ordinarily match still lets
    # failures through.
    rules = {"bullish", "high_confidence", "excellent_quality"}
    passes, trace = payload_passes_event_filter(payload, events=rules)
    assert passes is True
    assert trace.get("bypass") == "failed_status"


def test_filter_quality_missing_blocks_quality_rule():
    """A payload without quality_health can't satisfy a quality rule."""
    from app.services.webhook_service import payload_passes_event_filter

    payload = {
        "status": "completed",
        "sim_id": "sim_no_quality",
        "final_consensus": {"bullish": 80.0, "neutral": 10.0, "bearish": 10.0},
        "quality_health": None,
    }
    passes, trace = payload_passes_event_filter(payload, events={"good_quality"})
    assert passes is False
    assert trace.get("failed_on") == "quality"


# ── End-to-end: fire_webhook_for_simulation honours the filter ────────────


def test_fire_skips_dispatch_when_filter_rejects(populated_sim_dir: Path, monkeypatch):
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()
    # populated_sim_dir's trajectory ends at 50% bullish → fails a
    # high_confidence rule (75% floor).
    monkeypatch.setenv("WEBHOOK_EVENTS", "high_confidence")

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json') as mock_post:
        webhook_service.fire_webhook_for_simulation(
            "sim_filtered_out",
            "completed",
            sim_dir=str(populated_sim_dir),
        )
    assert mock_post.call_count == 0


def test_fire_dispatches_when_filter_passes(populated_sim_dir: Path, monkeypatch):
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()
    # The fixture's trajectory ends at 50% bullish leader →
    # bullish + medium_confidence both pass.
    monkeypatch.setenv("WEBHOOK_EVENTS", "bullish,medium_confidence")

    fired = threading.Event()
    captured: dict = {}

    def record(url, payload, timeout):
        captured["payload"] = payload
        fired.set()
        return True, "HTTP 200"

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json', side_effect=record):
        webhook_service.fire_webhook_for_simulation(
            "sim_filter_pass",
            "completed",
            sim_dir=str(populated_sim_dir),
        )
        assert fired.wait(timeout=2.0), "Filter rejected a payload that should have passed"

    assert captured["payload"]["sim_id"] == "sim_filter_pass"


def test_fire_failed_sim_bypasses_filter(populated_sim_dir: Path, monkeypatch):
    """A failed sim always fires even when the filter wouldn't otherwise
    match — that's the alert the operator added the webhook for."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()
    # A tight filter that wouldn't match the populated sim's trajectory.
    monkeypatch.setenv("WEBHOOK_EVENTS", "bearish,excellent_quality")

    fired = threading.Event()

    def record(url, payload, timeout):
        fired.set()
        return True, "HTTP 200"

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json', side_effect=record):
        webhook_service.fire_webhook_for_simulation(
            "sim_failed_bypass",
            "failed",
            sim_dir=str(populated_sim_dir),
            error="runner crashed",
        )
        assert fired.wait(timeout=2.0), "Failed sim was filtered out"


def test_fire_blank_filter_keeps_existing_behavior(populated_sim_dir: Path, monkeypatch):
    """When WEBHOOK_EVENTS is unset, dispatch is unconditional — the
    explicit backward-compatibility guarantee."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()
    monkeypatch.delenv("WEBHOOK_EVENTS", raising=False)

    fired = threading.Event()

    def record(url, payload, timeout):
        fired.set()
        return True, "HTTP 200"

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json', side_effect=record):
        webhook_service.fire_webhook_for_simulation(
            "sim_no_filter",
            "completed",
            sim_dir=str(populated_sim_dir),
        )
        assert fired.wait(timeout=2.0), "Blank filter should have dispatched"
