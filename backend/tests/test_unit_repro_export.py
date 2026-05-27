"""Unit tests for the reproducibility-config export service.

Pure offline — no Flask, no Wonderwall, no LLM. The
``GET /api/simulation/<id>/reproduce.json`` route is the citation
primitive that academic and quant audiences need before they can cite
a MiroShark sim seriously, so the service powering it is held to the
same correctness bar as ``surface_stats`` / ``transcript`` /
``trajectory_export``: every shape promise + every degradation path
covered.

Coverage:

  1. SCHEMA_VERSION constant is the literal "1" — bumping it is a
     deliberate API break, not a refactor side-effect.
  2. REQUIRED_KEYS contains exactly the v1 keys the route returns; the
     test pins the set so a future rename can't silently drop a field
     a downstream parser depends on.
  3. ``build_repro_config`` round-trips a fully-populated state +
     config dict, hitting every ``REQUIRED_KEYS`` entry.
  4. Scenario falls back to state-level ``simulation_requirement`` when
     the config dict is missing it (matches embed-summary fallback).
  5. ``total_rounds`` derivation: prefers state.total_rounds; falls
     back to ``hours * 60 / minutes`` from time_config; degrades to 0
     when neither is positive.
  6. Platform toggles default to safe values when keys are absent.
  7. ``polymarket_market_count`` clamps to a sensible default when the
     state dict carries garbage.
  8. Lineage shape: ``kind == "original"`` when no parent.
  9. Lineage shape: ``kind == "fork"`` with parent set + no
     counterfactual file on disk.
 10. Lineage shape: ``kind == "counterfactual"`` with parent set + a
     valid ``counterfactual_injection.json`` next to the sim — the
     trigger_round / label / 140-char preview travel along.
 11. Corrupt ``counterfactual_injection.json`` degrades to ``kind ==
     "fork"`` rather than crashing the export.
 12. Director events read from JSONL; sorted by round; bad lines
     skipped without blanking the rest.
 13. Director events read from list-style ``director-events.json``
     (older shape) — equivalent output.
 14. Missing director-events file returns ``None``, not ``[]`` (so the
     v1 consumer doesn't have to special-case empty arrays).
 15. ``render_json_bytes`` emits stable, sorted-key, pretty-printed
     JSON with a trailing newline so a ``curl >`` redirect produces a
     diff-friendly file.
 16. ``validate_blob`` accepts a freshly-built blob with zero errors.
 17. ``validate_blob`` rejects a blob with the wrong schema_version.
 18. ``validate_blob`` rejects bogus types (agent_count as string,
     lineage.kind as garbage).
 19. ``GET /api/simulation/<simulation_id>/reproduce.json`` route
     decorator is registered in ``app/api/simulation.py`` so the
     OpenAPI drift test passes.
 20. ``ReproductionConfig`` schema is declared in ``backend/openapi.yaml``
     so the Swagger UI documents the new endpoint.
 21. ``_safe_int`` clamps negatives to zero (defense-in-depth).
 22. Build composes a complete blob even when ``config_data`` is
     ``None`` (sim that hasn't reached prepared state).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import repro_export  # noqa: E402


# ── Module-level invariants ────────────────────────────────────────────


def test_schema_version_literal_one():
    """v1 is a stable wire contract — bumps must be deliberate."""
    assert repro_export.SCHEMA_VERSION == "1"


def test_required_keys_pinned_set():
    """Pin the v1 key set so downstream parsers see a stable shape."""
    expected = {
        "schema_version",
        "exported_at",
        "simulation_id",
        "scenario",
        "agent_count",
        "total_rounds",
        "platforms",
        "time_config",
        "lineage",
        "director_events",
        "config_reasoning",
    }
    assert set(repro_export.REQUIRED_KEYS) == expected


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def basic_state():
    """A SimulationState dict at the shape ``state.to_dict()`` returns."""
    return {
        "simulation_id": "sim_abcdef123456",
        "project_id": "proj_xyz",
        "graph_id": "miroshark_xyz",
        "enable_twitter": True,
        "enable_reddit": True,
        "enable_polymarket": False,
        "polymarket_market_count": 1,
        "status": "completed",
        "entities_count": 36,
        "profiles_count": 36,
        "entity_types": ["person", "organization"],
        "config_generated": True,
        "config_reasoning": "LLM picked 36 agents to balance cost vs coverage.",
        "current_round": 24,
        "twitter_status": "completed",
        "reddit_status": "completed",
        "created_at": "2026-05-08T12:00:00",
        "updated_at": "2026-05-08T13:00:00",
        "error": None,
        "parent_simulation_id": None,
        "config_diff": None,
        "is_public": True,
    }


@pytest.fixture
def basic_config():
    """A ``simulation_config.json`` dict shape."""
    return {
        "simulation_requirement": "What if Aave's reserve factor doubled overnight?",
        "simulation_id": "sim_abcdef123456",
        "time_config": {
            "minutes_per_round": 60,
            "total_simulation_hours": 24,
            "peak_hours": [9, 10, 11, 17, 18, 19, 20, 21],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
        },
    }


# ── build_repro_config ─────────────────────────────────────────────────


def test_build_repro_config_full_round_trip(basic_state, basic_config, tmp_path):
    blob = repro_export.build_repro_config(
        basic_state, basic_config, str(tmp_path)
    )

    # Every required key present.
    for key in repro_export.REQUIRED_KEYS:
        assert key in blob, f"missing required key: {key}"

    # Top-level shape.
    assert blob["schema_version"] == "1"
    assert blob["simulation_id"] == "sim_abcdef123456"
    assert blob["scenario"] == "What if Aave's reserve factor doubled overnight?"
    assert blob["agent_count"] == 36
    assert blob["total_rounds"] == 24  # 24h * 60min / 60min-per-round
    assert blob["config_reasoning"].startswith("LLM picked 36")

    # exported_at is an ISO-8601 UTC stamp.
    assert blob["exported_at"].endswith("Z")
    assert "T" in blob["exported_at"]
    assert len(blob["exported_at"]) == len("2026-05-08T12:34:56Z")

    # Platforms.
    assert blob["platforms"] == {
        "twitter": True,
        "reddit": True,
        "polymarket": False,
        "polymarket_market_count": 1,
    }

    # Time config carries the four cadence knobs.
    tc = blob["time_config"]
    assert tc["minutes_per_round"] == 60
    assert tc["total_simulation_hours"] == 24
    assert tc["peak_hours"] == [9, 10, 11, 17, 18, 19, 20, 21]
    assert tc["off_peak_hours"] == [0, 1, 2, 3, 4, 5]

    # Lineage default — original sim, no parent.
    assert blob["lineage"] == {
        "parent_simulation_id": None,
        "kind": "original",
        "counterfactual": None,
    }

    # No director events written ⇒ field is None, not [].
    assert blob["director_events"] is None


def test_scenario_falls_back_to_state(basic_state, tmp_path):
    """Older sims wrote ``simulation_requirement`` onto state; fall back."""
    state = dict(basic_state)
    state["simulation_requirement"] = "Legacy state-level scenario text"

    blob = repro_export.build_repro_config(state, None, str(tmp_path))
    assert blob["scenario"] == "Legacy state-level scenario text"


def test_total_rounds_prefers_state(basic_state, basic_config, tmp_path):
    """``state.total_rounds`` wins over the time_config derivation."""
    state = dict(basic_state)
    state["total_rounds"] = 99
    blob = repro_export.build_repro_config(state, basic_config, str(tmp_path))
    assert blob["total_rounds"] == 99


def test_total_rounds_zero_when_neither_path_works(basic_state, tmp_path):
    """No total_rounds + no time_config ⇒ 0 rather than a crash."""
    state = dict(basic_state)
    blob = repro_export.build_repro_config(state, None, str(tmp_path))
    assert blob["total_rounds"] == 0


def test_platforms_default_to_safe_values(tmp_path):
    """Empty state dict still produces a complete platforms block."""
    blob = repro_export.build_repro_config({}, None, str(tmp_path))
    assert blob["platforms"] == {
        "twitter": True,
        "reddit": True,
        "polymarket": False,
        "polymarket_market_count": 1,
    }


def test_polymarket_market_count_clamps_garbage(basic_state, tmp_path):
    state = dict(basic_state)
    state["polymarket_market_count"] = "lots"  # garbage
    blob = repro_export.build_repro_config(state, None, str(tmp_path))
    assert blob["platforms"]["polymarket_market_count"] == 1


def test_build_blob_accepts_none_config(basic_state, tmp_path):
    """A sim without a prepared config still exports a complete blob."""
    blob = repro_export.build_repro_config(basic_state, None, str(tmp_path))
    assert blob["scenario"] == ""  # no config + no state-level fallback
    assert blob["time_config"] == {}
    assert blob["total_rounds"] == 0
    assert blob["lineage"]["kind"] == "original"


# ── Lineage ────────────────────────────────────────────────────────────


def test_lineage_kind_fork(basic_state, basic_config, tmp_path):
    """Parent set + no counterfactual file ⇒ fork."""
    state = dict(basic_state)
    state["parent_simulation_id"] = "sim_parent12345"

    blob = repro_export.build_repro_config(
        state, basic_config, str(tmp_path)
    )
    assert blob["lineage"] == {
        "parent_simulation_id": "sim_parent12345",
        "kind": "fork",
        "counterfactual": None,
    }


def test_lineage_kind_counterfactual(basic_state, basic_config, tmp_path):
    """Parent + counterfactual_injection.json ⇒ counterfactual + preview."""
    state = dict(basic_state)
    state["parent_simulation_id"] = "sim_parent12345"

    cf_path = tmp_path / "counterfactual_injection.json"
    cf_path.write_text(
        json.dumps(
            {
                "parent_simulation_id": "sim_parent12345",
                "trigger_round": 12,
                "injection_text": "CEO resigns under regulatory pressure" * 5,
                "label": "ceo_resigns",
                "branch_id": "ceo_resigns",
                "created_at": "2026-05-08T12:00:00",
            }
        ),
        encoding="utf-8",
    )

    blob = repro_export.build_repro_config(
        state, basic_config, str(tmp_path)
    )
    cf = blob["lineage"]["counterfactual"]
    assert blob["lineage"]["kind"] == "counterfactual"
    assert blob["lineage"]["parent_simulation_id"] == "sim_parent12345"
    assert cf["trigger_round"] == 12
    assert cf["label"] == "ceo_resigns"
    # Preview cap at 140 chars.
    assert isinstance(cf["preview"], str)
    assert len(cf["preview"]) <= 140


def test_lineage_corrupt_counterfactual_degrades_to_fork(
    basic_state, basic_config, tmp_path
):
    """Corrupt counterfactual JSON ⇒ fork, not crash."""
    state = dict(basic_state)
    state["parent_simulation_id"] = "sim_parent12345"

    cf_path = tmp_path / "counterfactual_injection.json"
    cf_path.write_text("not valid json {{{", encoding="utf-8")

    blob = repro_export.build_repro_config(
        state, basic_config, str(tmp_path)
    )
    assert blob["lineage"]["kind"] == "fork"
    assert blob["lineage"]["counterfactual"] is None


# ── Director events ────────────────────────────────────────────────────


def test_director_events_jsonl(basic_state, basic_config, tmp_path):
    """Read director events from JSONL, sort by round, skip bad lines."""
    jsonl_path = tmp_path / "director-events.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                json.dumps({"round": 18, "label": "Regulatory Announcement"}),
                "this line is corrupt {{",
                json.dumps(
                    {
                        "round": 6,
                        "label": "Liquidity Crisis",
                        "description": "Sudden 40% TVL drop",
                    }
                ),
                "",  # blank line
                json.dumps({"round": 12, "label": "Whale Withdrawal"}),
            ]
        ),
        encoding="utf-8",
    )

    blob = repro_export.build_repro_config(
        basic_state, basic_config, str(tmp_path)
    )
    events = blob["director_events"]
    assert isinstance(events, list)
    assert [e["round"] for e in events] == [6, 12, 18]
    assert events[0]["description"] == "Sudden 40% TVL drop"
    # The whale withdrawal didn't carry a description; field is None.
    assert events[2]["description"] is None


def test_director_events_legacy_list_json(basic_state, basic_config, tmp_path):
    """Older list-style ``director-events.json`` is also supported."""
    legacy_path = tmp_path / "director-events.json"
    legacy_path.write_text(
        json.dumps(
            [
                {"round": 15, "label": "Liquidity Crisis"},
                {"round": 5, "label": "Bullish Headline"},
            ]
        ),
        encoding="utf-8",
    )

    blob = repro_export.build_repro_config(
        basic_state, basic_config, str(tmp_path)
    )
    events = blob["director_events"]
    assert [e["label"] for e in events] == ["Bullish Headline", "Liquidity Crisis"]


def test_director_events_missing_returns_none(basic_state, basic_config, tmp_path):
    """No director-events file ⇒ field is None, not []."""
    blob = repro_export.build_repro_config(
        basic_state, basic_config, str(tmp_path)
    )
    assert blob["director_events"] is None


# ── render_json_bytes ──────────────────────────────────────────────────


def test_render_json_bytes_pretty_sorted_with_trailing_newline(
    basic_state, basic_config, tmp_path
):
    blob = repro_export.build_repro_config(
        basic_state, basic_config, str(tmp_path)
    )
    payload = repro_export.render_json_bytes(blob)
    assert isinstance(payload, bytes)
    # Pretty-printed: indent=2 produces multi-line output.
    text = payload.decode("utf-8")
    assert text.endswith("\n")
    assert "  " in text  # 2-space indent
    # Round-trip parses back to an equivalent dict.
    parsed = json.loads(text)
    assert parsed["simulation_id"] == "sim_abcdef123456"
    assert parsed["schema_version"] == "1"
    # sort_keys=True ⇒ deterministic byte output.
    again = repro_export.render_json_bytes(parsed)
    assert again == payload


# ── validate_blob ──────────────────────────────────────────────────────


def test_validate_blob_accepts_built_blob(basic_state, basic_config, tmp_path):
    blob = repro_export.build_repro_config(
        basic_state, basic_config, str(tmp_path)
    )
    assert repro_export.validate_blob(blob) == []


def test_validate_blob_rejects_wrong_schema_version(
    basic_state, basic_config, tmp_path
):
    blob = repro_export.build_repro_config(
        basic_state, basic_config, str(tmp_path)
    )
    blob["schema_version"] = "999"
    errors = repro_export.validate_blob(blob)
    assert any("schema_version" in e for e in errors)


def test_validate_blob_rejects_bogus_types(
    basic_state, basic_config, tmp_path
):
    blob = repro_export.build_repro_config(
        basic_state, basic_config, str(tmp_path)
    )
    blob["agent_count"] = "thirty-six"
    blob["lineage"] = {"parent_simulation_id": None, "kind": "weird", "counterfactual": None}
    errors = repro_export.validate_blob(blob)
    joined = " ".join(errors)
    assert "agent_count" in joined
    assert "lineage.kind" in joined


def test_safe_int_clamps_negatives_to_zero():
    """Defense-in-depth — a hand-edited config can't produce a negative
    agent count or round count in the export."""
    assert repro_export._safe_int(-5) == 0
    assert repro_export._safe_int(-1, default=0) == 0
    assert repro_export._safe_int(42) == 42


# ── Wiring guards ──────────────────────────────────────────────────────


def test_route_decorator_present_in_simulation_api():
    """Ensure ``GET /<simulation_id>/reproduce.json`` is registered."""
    api_path = _BACKEND / "app" / "api" / "simulation.py"
    text = api_path.read_text(encoding="utf-8")
    assert "@simulation_bp.route('/<simulation_id>/reproduce.json'" in text
    assert "def get_reproduce_config(" in text


def test_openapi_schema_declares_reproduction_config():
    """Swagger UI must pick up the new endpoint + payload schema."""
    spec_path = _BACKEND / "openapi.yaml"
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "/api/simulation/{simulation_id}/reproduce.json" in spec_text
    assert "ReproductionConfig:" in spec_text


def test_router_module_imports_repro_export():
    """The route handler must actually import the service we just shipped.

    Catches the failure mode where the route decorator was added but
    the body never got wired up — a class of mistake the existing
    ``surface_stats`` and ``trajectory_export`` patterns are vulnerable
    to.
    """
    api_path = _BACKEND / "app" / "api" / "simulation.py"
    text = api_path.read_text(encoding="utf-8")
    assert "from ..services import repro_export" in text
