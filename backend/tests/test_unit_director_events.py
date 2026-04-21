"""Tests for the counterfactual → director-event promotion in
``scripts/director_events.py``. No network.
"""

from __future__ import annotations

import json
from pathlib import Path

import director_events as de


def test_counterfactual_does_not_fire_before_trigger(tmp_path: Path):
    (tmp_path / "counterfactual_injection.json").write_text(json.dumps({
        "trigger_round": 5,
        "injection_text": "event X",
        "label": "x",
    }))
    consumed = de.consume_pending_events(str(tmp_path), current_round=3)
    assert consumed == []
    # Spec untouched (not yet consumed).
    spec = json.loads((tmp_path / "counterfactual_injection.json").read_text())
    assert spec.get("consumed") is not True


def test_counterfactual_fires_at_trigger(tmp_path: Path):
    (tmp_path / "counterfactual_injection.json").write_text(json.dumps({
        "trigger_round": 2,
        "injection_text": "event Y",
        "label": "ceo_exits",
    }))
    consumed = de.consume_pending_events(str(tmp_path), current_round=2)
    assert len(consumed) == 1
    evt = consumed[0]
    assert "COUNTERFACTUAL" in evt["event_text"]
    assert "ceo_exits" in evt["event_text"]
    assert "event Y" in evt["event_text"]

    # Idempotent: second call at a later round does NOT re-fire.
    consumed2 = de.consume_pending_events(str(tmp_path), current_round=3)
    assert consumed2 == []
    spec = json.loads((tmp_path / "counterfactual_injection.json").read_text())
    assert spec.get("consumed") is True


def test_counterfactual_skipped_if_malformed(tmp_path: Path):
    (tmp_path / "counterfactual_injection.json").write_text("not json")
    # Should not raise and should not return any events.
    consumed = de.consume_pending_events(str(tmp_path), current_round=1)
    assert consumed == []


def test_add_and_consume_plain_director_event(tmp_path: Path):
    evt = de.add_event(str(tmp_path), "Breaking: thing happened", round_num=0)
    assert evt["event_text"] == "Breaking: thing happened"

    consumed = de.consume_pending_events(str(tmp_path), current_round=1)
    assert len(consumed) == 1
    assert consumed[0]["injected_at_round"] == 1

    # Queue cleared.
    assert de.consume_pending_events(str(tmp_path), current_round=2) == []
