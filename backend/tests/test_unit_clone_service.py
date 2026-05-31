"""Unit tests for the clone-payload service + route wiring.

Pure offline — no Flask app, no network, no simulation runner. Covers
the contract the ``GET /api/simulation/<id>/clone.json`` endpoint depends
on:

  1. ``build_clone_payload`` reads ``state.json`` + ``simulation_config.json``
     and assembles a ``POST /api/simulation/create``-shaped body.
  2. Missing ``state.json`` resolves to ``None`` (the route translates
     that to a 404).
  3. Defaults match the create handler (``enable_twitter=True``,
     ``enable_reddit=True``, ``enable_polymarket=False``,
     ``polymarket_market_count=1`` clamped to ``[1, 5]``).
  4. ``country`` normalisation matches manager.create_simulation
     (lowercase + strip + empty→None).
  5. ``demographic_filters`` pass-through for dicts; non-dicts coerce
     to ``None``.
  6. ``simulation_requirement`` falls back to empty string when the
     config file is missing or corrupt; ``scenario_preview`` truncates
     long text with an ellipsis.
  7. ``example_curl`` references the canonical ``your-host`` placeholder
     and carries the JSON body inline.
  8. Route decorator, publish gate, and surface-stat increment exist in
     ``app/api/simulation.py``.
  9. ``clone_json`` is registered in the surface_stats schema.
 10. ``openapi.yaml`` documents the path + ``CloneResponse`` schema.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services import clone_service  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────


def _write_state(sim_dir: Path, **overrides) -> dict:
    """Drop a state.json with the manager-shaped defaults + overrides."""
    state = {
        "simulation_id": sim_dir.name,
        "project_id": "proj_test123",
        "graph_id": "miroshark_graph_test",
        "enable_twitter": True,
        "enable_reddit": True,
        "enable_polymarket": False,
        "polymarket_market_count": 1,
        "status": "completed",
        "current_round": 10,
        "is_public": True,
        "country": None,
        "demographic_filters": None,
    }
    state.update(overrides)
    (sim_dir / "state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    return state


def _write_config(sim_dir: Path, **overrides) -> dict:
    """Drop a simulation_config.json with the LLM-generated shape."""
    config = {
        "simulation_id": sim_dir.name,
        "project_id": "proj_test123",
        "graph_id": "miroshark_graph_test",
        "simulation_requirement": "Will Aave's reserve factor doubling reduce TVL?",
    }
    config.update(overrides)
    (sim_dir / "simulation_config.json").write_text(
        json.dumps(config), encoding="utf-8"
    )
    return config


# ── build_clone_payload — happy path ─────────────────────────────────────


def test_returns_none_on_missing_state(tmp_path: Path):
    sim_dir = tmp_path / "sim_missing"
    sim_dir.mkdir()
    assert clone_service.build_clone_payload("sim_missing", str(sim_dir)) is None


def test_returns_none_on_corrupt_state(tmp_path: Path):
    sim_dir = tmp_path / "sim_corrupt"
    sim_dir.mkdir()
    (sim_dir / "state.json").write_text("{not json", encoding="utf-8")
    assert clone_service.build_clone_payload("sim_corrupt", str(sim_dir)) is None


def test_returns_none_when_state_is_not_a_dict(tmp_path: Path):
    sim_dir = tmp_path / "sim_list"
    sim_dir.mkdir()
    (sim_dir / "state.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert clone_service.build_clone_payload("sim_list", str(sim_dir)) is None


def test_happy_path_payload_shape(tmp_path: Path):
    sim_dir = tmp_path / "sim_happy"
    sim_dir.mkdir()
    _write_state(sim_dir, project_id="proj_happy", graph_id="miroshark_happy")
    _write_config(
        sim_dir,
        project_id="proj_happy",
        graph_id="miroshark_happy",
        simulation_requirement="Bullish on Aave?",
    )

    payload = clone_service.build_clone_payload("sim_happy", str(sim_dir))

    assert payload is not None
    assert payload["schema_version"] == "1"
    assert payload["simulation_id"] == "sim_happy"
    assert payload["project_id"] == "proj_happy"
    assert payload["graph_id"] == "miroshark_happy"
    assert payload["simulation_requirement"] == "Bullish on Aave?"
    assert payload["scenario_preview"] == "Bullish on Aave?"

    body = payload["clone_payload"]
    assert body["project_id"] == "proj_happy"
    assert body["graph_id"] == "miroshark_happy"
    assert body["enable_twitter"] is True
    assert body["enable_reddit"] is True
    assert body["enable_polymarket"] is False
    assert body["polymarket_market_count"] == 1
    assert body["country"] is None
    assert body["demographic_filters"] is None


def test_payload_is_json_serialisable(tmp_path: Path):
    """The route handler dumps the payload with sort_keys=True — a
    non-serialisable value (datetime, Decimal, custom class) would
    crash the response build. Lock that down at the unit level."""
    sim_dir = tmp_path / "sim_ser"
    sim_dir.mkdir()
    _write_state(sim_dir)
    _write_config(sim_dir)

    payload = clone_service.build_clone_payload("sim_ser", str(sim_dir))
    text = json.dumps(payload, sort_keys=True)
    assert "schema_version" in text


# ── Defaults match the create handler ───────────────────────────────────


def test_polymarket_count_is_clamped_to_one_to_five(tmp_path: Path):
    """state.json may have a stale or hand-edited value; ``/create``
    clamps to ``[1, 5]`` so the clone payload must too."""
    sim_dir = tmp_path / "sim_high"
    sim_dir.mkdir()
    _write_state(sim_dir, polymarket_market_count=99)
    payload = clone_service.build_clone_payload("sim_high", str(sim_dir))
    assert payload["clone_payload"]["polymarket_market_count"] == 5

    sim_dir2 = tmp_path / "sim_low"
    sim_dir2.mkdir()
    _write_state(sim_dir2, polymarket_market_count=0)
    payload2 = clone_service.build_clone_payload("sim_low", str(sim_dir2))
    assert payload2["clone_payload"]["polymarket_market_count"] == 1


def test_polymarket_count_falls_back_to_one_on_garbage(tmp_path: Path):
    sim_dir = tmp_path / "sim_garbage"
    sim_dir.mkdir()
    _write_state(sim_dir, polymarket_market_count="three")
    payload = clone_service.build_clone_payload("sim_garbage", str(sim_dir))
    assert payload["clone_payload"]["polymarket_market_count"] == 1


def test_platform_toggles_default_to_manager_defaults(tmp_path: Path):
    """Manager default-loads are: twitter=True, reddit=True, polymarket=False.
    An old state.json missing the toggles must still produce a body that
    matches what /create would have done on a fresh sim."""
    sim_dir = tmp_path / "sim_legacy"
    sim_dir.mkdir()
    (sim_dir / "state.json").write_text(
        json.dumps({
            "project_id": "proj_legacy",
            "graph_id": "miroshark_legacy",
            # no enable_* fields
        }),
        encoding="utf-8",
    )
    payload = clone_service.build_clone_payload("sim_legacy", str(sim_dir))
    body = payload["clone_payload"]
    assert body["enable_twitter"] is True
    assert body["enable_reddit"] is True
    assert body["enable_polymarket"] is False


# ── country / demographic_filters normalisation ─────────────────────────


def test_country_lowercases_and_strips(tmp_path: Path):
    sim_dir = tmp_path / "sim_country"
    sim_dir.mkdir()
    _write_state(sim_dir, country="  SG  ")
    payload = clone_service.build_clone_payload("sim_country", str(sim_dir))
    assert payload["clone_payload"]["country"] == "sg"


def test_country_empty_string_becomes_none(tmp_path: Path):
    sim_dir = tmp_path / "sim_empty_country"
    sim_dir.mkdir()
    _write_state(sim_dir, country="")
    payload = clone_service.build_clone_payload("sim_empty_country", str(sim_dir))
    assert payload["clone_payload"]["country"] is None


def test_demographic_filters_pass_through_for_dicts(tmp_path: Path):
    sim_dir = tmp_path / "sim_demo"
    sim_dir.mkdir()
    filters = {
        "geography_values": ["Tampines", "Bedok"],
        "min_age": 21,
        "max_age": 65,
        "occupations": ["teacher"],
    }
    _write_state(sim_dir, demographic_filters=filters)
    payload = clone_service.build_clone_payload("sim_demo", str(sim_dir))
    assert payload["clone_payload"]["demographic_filters"] == filters


def test_demographic_filters_non_dict_coerces_to_none(tmp_path: Path):
    sim_dir = tmp_path / "sim_demo_bad"
    sim_dir.mkdir()
    _write_state(sim_dir, demographic_filters="not a dict")
    payload = clone_service.build_clone_payload("sim_demo_bad", str(sim_dir))
    assert payload["clone_payload"]["demographic_filters"] is None


def test_demographic_filters_empty_dict_coerces_to_none(tmp_path: Path):
    """An empty filter object is semantically equivalent to ``no filters``;
    /create accepts both, but the clone payload uses ``None`` to avoid
    serialising ``{}`` for what is really "no filtering"."""
    sim_dir = tmp_path / "sim_demo_empty"
    sim_dir.mkdir()
    _write_state(sim_dir, demographic_filters={})
    payload = clone_service.build_clone_payload("sim_demo_empty", str(sim_dir))
    assert payload["clone_payload"]["demographic_filters"] is None


# ── simulation_requirement + scenario_preview ───────────────────────────


def test_simulation_requirement_empty_when_config_missing(tmp_path: Path):
    sim_dir = tmp_path / "sim_no_config"
    sim_dir.mkdir()
    _write_state(sim_dir)
    payload = clone_service.build_clone_payload("sim_no_config", str(sim_dir))
    assert payload["simulation_requirement"] == ""
    assert payload["scenario_preview"] == ""


def test_simulation_requirement_empty_when_config_corrupt(tmp_path: Path):
    sim_dir = tmp_path / "sim_bad_config"
    sim_dir.mkdir()
    _write_state(sim_dir)
    (sim_dir / "simulation_config.json").write_text("{not json", encoding="utf-8")
    payload = clone_service.build_clone_payload("sim_bad_config", str(sim_dir))
    assert payload["simulation_requirement"] == ""


def test_scenario_preview_truncates_long_text_with_ellipsis(tmp_path: Path):
    sim_dir = tmp_path / "sim_long"
    sim_dir.mkdir()
    long_scenario = "A" * 500
    _write_state(sim_dir)
    _write_config(sim_dir, simulation_requirement=long_scenario)
    payload = clone_service.build_clone_payload("sim_long", str(sim_dir))
    assert len(payload["simulation_requirement"]) == 500
    assert payload["scenario_preview"].endswith("…")
    assert len(payload["scenario_preview"]) <= clone_service.SCENARIO_PREVIEW_CHARS


def test_scenario_preview_unicode_survives_unescaped(tmp_path: Path):
    sim_dir = tmp_path / "sim_zh"
    sim_dir.mkdir()
    _write_state(sim_dir)
    _write_config(sim_dir, simulation_requirement="米罗莎要来了吗?")
    payload = clone_service.build_clone_payload("sim_zh", str(sim_dir))
    assert payload["simulation_requirement"] == "米罗莎要来了吗?"
    assert payload["scenario_preview"] == "米罗莎要来了吗?"


# ── example_curl ────────────────────────────────────────────────────────


def test_example_curl_references_create_endpoint(tmp_path: Path):
    sim_dir = tmp_path / "sim_curl"
    sim_dir.mkdir()
    _write_state(sim_dir)
    _write_config(sim_dir)
    payload = clone_service.build_clone_payload("sim_curl", str(sim_dir))
    curl = payload["example_curl"]
    assert curl.startswith("curl ")
    assert "/api/simulation/create" in curl
    assert "POST" in curl
    assert "Content-Type: application/json" in curl


def test_example_curl_uses_your_host_placeholder(tmp_path: Path):
    """A copy-pasted example must never hit an internal URL — same
    posture as surfaces-catalog. Lock the placeholder."""
    sim_dir = tmp_path / "sim_curl_host"
    sim_dir.mkdir()
    _write_state(sim_dir)
    payload = clone_service.build_clone_payload("sim_curl_host", str(sim_dir))
    assert "https://your-host" in payload["example_curl"]


def test_example_curl_inlines_the_clone_payload(tmp_path: Path):
    sim_dir = tmp_path / "sim_curl_body"
    sim_dir.mkdir()
    _write_state(
        sim_dir,
        project_id="proj_inline_unique_xyz",
        graph_id="miroshark_inline_unique",
        enable_polymarket=True,
        polymarket_market_count=3,
    )
    payload = clone_service.build_clone_payload("sim_curl_body", str(sim_dir))
    curl = payload["example_curl"]
    # The body is JSON-encoded and inlined into the -d argument.
    assert "proj_inline_unique_xyz" in curl
    assert "miroshark_inline_unique" in curl
    assert '"polymarket_market_count":3' in curl


# ── build_example_curl unit ─────────────────────────────────────────────


def test_build_example_curl_is_deterministic():
    """Same input → same string. ``json.dumps(..., sort_keys=True)``
    inside ``build_example_curl`` is what makes that hold."""
    body = {
        "project_id": "p",
        "graph_id": "g",
        "enable_twitter": True,
        "enable_reddit": True,
        "enable_polymarket": False,
        "polymarket_market_count": 1,
        "country": None,
        "demographic_filters": None,
    }
    a = clone_service.build_example_curl(body)
    b = clone_service.build_example_curl(body)
    assert a == b


# ── Static wiring guards ───────────────────────────────────────────────────


def _read_simulation_api() -> str:
    return (_BACKEND / "app" / "api" / "simulation.py").read_text(encoding="utf-8")


def test_route_decorator_registered():
    text = _read_simulation_api()
    assert (
        "@simulation_bp.route('/<simulation_id>/clone.json', methods=['GET'])" in text
    ), "GET /<id>/clone.json route decorator missing from simulation.py"
    assert "def get_clone_json" in text, (
        "get_clone_json handler function missing from simulation.py"
    )


def test_route_enforces_publish_gate():
    text = _read_simulation_api()
    assert "_build_embed_summary_payload" in text
    assert "is_public" in text


def test_route_increments_clone_json_surface_stat():
    text = _read_simulation_api()
    assert '"clone_json"' in text, (
        "simulation.py must increment the clone_json counter via "
        "surface_stats.increment_surface_stat(..., \"clone_json\")"
    )
    assert "increment_surface_stat" in text


def test_surface_stats_registers_clone_json_key():
    from app.services import surface_stats

    assert "clone_json" in surface_stats.SURFACE_KEYS


def test_openapi_documents_clone_json_path_and_schema():
    spec_text = (_BACKEND / "openapi.yaml").read_text(encoding="utf-8")
    assert "/api/simulation/{simulation_id}/clone.json:" in spec_text, (
        "openapi.yaml is missing the /clone.json path entry"
    )
    assert "CloneResponse:" in spec_text, (
        "openapi.yaml is missing the CloneResponse schema"
    )
    assert "ClonePayloadBody:" in spec_text, (
        "openapi.yaml is missing the ClonePayloadBody schema"
    )
