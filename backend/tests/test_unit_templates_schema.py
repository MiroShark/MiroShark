"""Validate that every preset template JSON is parseable and has the
minimum fields the frontend + API assume.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "preset_templates"


_REQUIRED_FIELDS = (
    "id",
    "name",
    "category",
    "description",
    "simulation_requirement",
    "seed_document",
)


def _all_templates():
    return sorted(TEMPLATES_DIR.glob("*.json"))


@pytest.mark.parametrize("path", _all_templates(), ids=lambda p: p.name)
def test_template_parses_and_has_required_fields(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for field in _REQUIRED_FIELDS:
        assert field in data, f"{path.name} missing required field: {field}"
        assert data[field], f"{path.name} has empty required field: {field}"


@pytest.mark.parametrize("path", _all_templates(), ids=lambda p: p.name)
def test_counterfactual_branches_well_formed(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    branches = data.get("counterfactual_branches") or []
    assert isinstance(branches, list)
    for b in branches:
        assert isinstance(b, dict)
        assert b.get("id"), f"{path.name}: branch missing id"
        assert b.get("label"), f"{path.name}: branch missing label"
        # injection is the preferred field; fall back to description
        assert b.get("injection") or b.get("description"), (
            f"{path.name}: branch {b.get('id')} missing injection/description"
        )
        # trigger_round is optional but if set must be int >= 0
        tr = b.get("trigger_round")
        if tr is not None:
            assert isinstance(tr, int) and tr >= 0, (
                f"{path.name}: branch {b.get('id')} has bad trigger_round: {tr}"
            )


@pytest.mark.parametrize("path", _all_templates(), ids=lambda p: p.name)
def test_oracle_tools_well_formed(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data.get("oracle_tools") or []:
        assert isinstance(entry, dict)
        assert entry.get("tool"), f"{path.name}: oracle entry missing tool name"
        args = entry.get("args", {})
        assert isinstance(args, dict), f"{path.name}: oracle args must be dict"
