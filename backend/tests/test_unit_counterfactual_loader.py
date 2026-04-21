"""Unit tests for scripts/counterfactual_loader.py — the prefix that the
runner prepends to agent observations when a branched sim reaches its
trigger round.
"""

from __future__ import annotations

import json
from pathlib import Path

from counterfactual_loader import (
    injection_prefix_for_round,
    load_counterfactual,
)


def test_load_returns_none_when_file_absent(tmp_path: Path):
    assert load_counterfactual(str(tmp_path)) is None


def test_load_returns_none_when_invalid_json(tmp_path: Path):
    (tmp_path / "counterfactual_injection.json").write_text("not json")
    assert load_counterfactual(str(tmp_path)) is None


def test_load_rejects_missing_trigger_round(tmp_path: Path):
    (tmp_path / "counterfactual_injection.json").write_text(
        json.dumps({"injection_text": "hi"})
    )
    assert load_counterfactual(str(tmp_path)) is None


def test_load_returns_spec_when_valid(tmp_path: Path):
    (tmp_path / "counterfactual_injection.json").write_text(
        json.dumps({
            "trigger_round": 4,
            "injection_text": "CEO resigns",
            "label": "ceo_resigns",
        })
    )
    spec = load_counterfactual(str(tmp_path))
    assert spec is not None
    assert spec["trigger_round"] == 4
    assert spec["injection_text"] == "CEO resigns"


def test_prefix_empty_before_trigger():
    spec = {"trigger_round": 5, "injection_text": "news", "label": "x"}
    assert injection_prefix_for_round(spec, round_num=4) == ""


def test_prefix_includes_text_at_trigger():
    spec = {"trigger_round": 5, "injection_text": "breaking news here", "label": "my_label"}
    out = injection_prefix_for_round(spec, round_num=5)
    assert "BREAKING COUNTERFACTUAL EVENT" in out
    assert "my_label" in out
    assert "breaking news here" in out


def test_prefix_persists_after_trigger():
    spec = {"trigger_round": 2, "injection_text": "event", "label": "l"}
    assert "event" in injection_prefix_for_round(spec, round_num=2)
    assert "event" in injection_prefix_for_round(spec, round_num=10)


def test_prefix_none_spec():
    assert injection_prefix_for_round(None, round_num=3) == ""
