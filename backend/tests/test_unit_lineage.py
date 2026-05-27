"""Unit tests for the simulation-lineage navigator service.

Pure offline — no Flask, no Wonderwall, no LLM. The
``GET /api/simulation/<id>/lineage`` endpoint surfaces fork /
counterfactual graph navigation by reading on-disk state.json files,
so the test surface mirrors the on-disk contract:

  1. ``MAX_CHILDREN`` is the documented 50-entry cap — a future
     refactor must not silently lift it.
  2. ``SCENARIO_PREVIEW_CHARS`` truncates long scenarios with an
     ellipsis at 80 chars.
  3. A simulation with no parent and no children produces a coherent
     payload (``parent=None``, ``children=[]``,
     ``lineage_kind="original"``).
  4. A fork sim's payload has ``lineage_kind="fork"`` and the parent
     entry is populated when the parent state.json is on disk.
  5. A counterfactual sim's payload has ``lineage_kind="counterfactual"``
     and the top-level ``counterfactual`` block carries trigger_round
     + label.
  6. Public children are discovered by reverse pointer — three branches
     of one parent appear in the response with the right kind for each.
  7. Private children are silently excluded — operators forking
     privately don't leak in-progress branches into a tweeted parent.
  8. Missing ``simulation_config.json`` falls back to state-level
     ``simulation_requirement``; missing both ⇒ empty preview.
  9. Children sort by ``created_at`` ascending (oldest fork first —
     natural narrative order).
 10. Corrupt child state.json is silently skipped without blanking the
     rest of the children list.
 11. ``total_children`` reflects the uncapped scan count even when the
     children list was truncated by ``max_children``.
 12. Parent unpublished after the fact: parent entry exists, but
     ``is_public=False`` and ``scenario_preview=""`` so the SPA can
     render a bare placeholder.
 13. Children list excludes the requested sim itself (a future
     hand-edited state file with a self-pointer would otherwise produce
     an infinite-recursion bug).
 14. Route is registered in ``app/api/simulation.py`` (drift-detection
     guard against the route decorator going missing).
 15. ``SimulationLineage`` schema is declared in ``backend/openapi.yaml``
     so Swagger UI documents the new endpoint.
 16. The route handler imports the service module — catches the failure
     mode where the route decorator was added but the body was never
     wired up.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path



_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import lineage_service  # noqa: E402


# ── Module-level invariants ────────────────────────────────────────────


def test_max_children_cap_is_pinned():
    """50 is the documented cap — future bumps must be deliberate."""
    assert lineage_service.MAX_CHILDREN == 50


def test_scenario_preview_chars_pinned():
    """80 chars matches the YAML front-matter cap on the transcript export."""
    assert lineage_service.SCENARIO_PREVIEW_CHARS == 80


def test_truncate_scenario_preserves_short_text():
    text = "A short scenario."
    assert lineage_service._truncate_scenario(text) == text


def test_truncate_scenario_appends_ellipsis_on_long_text():
    text = "x" * 200
    truncated = lineage_service._truncate_scenario(text)
    assert len(truncated) == lineage_service.SCENARIO_PREVIEW_CHARS
    assert truncated.endswith("…")


# ── Fixture helpers ────────────────────────────────────────────────────


def _write_state(
    data_dir: Path,
    sim_id: str,
    *,
    parent_id: str | None = None,
    is_public: bool = True,
    created_at: str = "2026-05-09T10:00:00",
    extra: dict | None = None,
) -> Path:
    """Create a sim directory with a minimal state.json."""
    sim_dir = data_dir / sim_id
    sim_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "simulation_id": sim_id,
        "is_public": is_public,
        "parent_simulation_id": parent_id,
        "created_at": created_at,
        "profiles_count": 12,
    }
    if extra:
        state.update(extra)
    (sim_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return sim_dir


def _write_config(sim_dir: Path, scenario: str) -> None:
    """Drop a minimal simulation_config.json with the given scenario."""
    config = {"simulation_requirement": scenario, "time_config": {"minutes_per_round": 60, "total_simulation_hours": 24}}
    (sim_dir / "simulation_config.json").write_text(
        json.dumps(config), encoding="utf-8"
    )


def _write_counterfactual(
    sim_dir: Path,
    *,
    parent_id: str,
    trigger_round: int,
    label: str,
    injection_text: str = "Breaking news: regulator opens probe.",
) -> None:
    """Drop a counterfactual_injection.json file."""
    payload = {
        "parent_simulation_id": parent_id,
        "trigger_round": trigger_round,
        "label": label,
        "injection_text": injection_text,
    }
    (sim_dir / "counterfactual_injection.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


# ── Core lineage payload ───────────────────────────────────────────────


def test_lineage_payload_for_original_with_no_children(tmp_path):
    """Standalone sim ⇒ lineage_kind=original, parent=None, children=[]."""
    _write_state(tmp_path, "sim_root123", is_public=True)

    payload = lineage_service.build_lineage_payload(
        "sim_root123", str(tmp_path)
    )
    assert payload["simulation_id"] == "sim_root123"
    assert payload["lineage_kind"] == "original"
    assert payload["parent"] is None
    assert payload["children"] == []
    assert payload["total_children"] == 0
    assert payload["counterfactual"] is None


def test_lineage_payload_for_fork_returns_parent_entry(tmp_path):
    """Fork sim ⇒ parent entry populated with scenario + created_at."""
    parent_dir = _write_state(
        tmp_path,
        "sim_parentABC",
        is_public=True,
        created_at="2026-04-29T10:00:00",
    )
    _write_config(parent_dir, "What if Aave's reserve factor doubled overnight?")

    _write_state(
        tmp_path,
        "sim_forkXYZ",
        parent_id="sim_parentABC",
        is_public=True,
        created_at="2026-05-01T10:00:00",
    )

    payload = lineage_service.build_lineage_payload(
        "sim_forkXYZ", str(tmp_path)
    )
    assert payload["lineage_kind"] == "fork"
    assert payload["counterfactual"] is None
    parent = payload["parent"]
    assert parent is not None
    assert parent["simulation_id"] == "sim_parentABC"
    assert parent["is_public"] is True
    assert parent["scenario_preview"].startswith("What if Aave")
    assert parent["created_at"] == "2026-04-29T10:00:00"


def test_lineage_payload_for_counterfactual_carries_trigger_metadata(tmp_path):
    """Counterfactual sim ⇒ top-level counterfactual block has trigger + label."""
    _write_state(tmp_path, "sim_parentABC", is_public=True)
    child_dir = _write_state(
        tmp_path,
        "sim_cf123",
        parent_id="sim_parentABC",
        is_public=True,
    )
    _write_counterfactual(
        child_dir,
        parent_id="sim_parentABC",
        trigger_round=12,
        label="ceo_resigns",
    )

    payload = lineage_service.build_lineage_payload(
        "sim_cf123", str(tmp_path)
    )
    assert payload["lineage_kind"] == "counterfactual"
    assert payload["counterfactual"] == {
        "trigger_round": 12,
        "label": "ceo_resigns",
    }


# ── Children discovery ─────────────────────────────────────────────────


def test_children_discovered_by_reverse_pointer(tmp_path):
    """Three forks of one parent appear in the children list."""
    parent_dir = _write_state(
        tmp_path,
        "sim_parent000",
        is_public=True,
        created_at="2026-04-25T08:00:00",
    )
    _write_config(parent_dir, "Base Aave scenario.")

    # Three branches: a plain fork + two counterfactuals.
    _write_state(
        tmp_path,
        "sim_fork111",
        parent_id="sim_parent000",
        is_public=True,
        created_at="2026-04-26T09:00:00",
    )

    cf1_dir = _write_state(
        tmp_path,
        "sim_cf222",
        parent_id="sim_parent000",
        is_public=True,
        created_at="2026-04-27T10:00:00",
    )
    _write_counterfactual(
        cf1_dir, parent_id="sim_parent000", trigger_round=12, label="ceo_resigns"
    )

    cf2_dir = _write_state(
        tmp_path,
        "sim_cf333",
        parent_id="sim_parent000",
        is_public=True,
        created_at="2026-04-28T11:00:00",
    )
    _write_counterfactual(
        cf2_dir, parent_id="sim_parent000", trigger_round=18, label="whale_withdraws"
    )

    # Add an unrelated sim — should not appear.
    _write_state(tmp_path, "sim_unrelated444", is_public=True)

    payload = lineage_service.build_lineage_payload(
        "sim_parent000", str(tmp_path)
    )
    assert payload["lineage_kind"] == "original"
    assert payload["parent"] is None
    assert payload["total_children"] == 3
    assert len(payload["children"]) == 3

    kinds = {c["simulation_id"]: c["kind"] for c in payload["children"]}
    assert kinds == {
        "sim_fork111": "fork",
        "sim_cf222": "counterfactual",
        "sim_cf333": "counterfactual",
    }

    cf_entry = next(c for c in payload["children"] if c["simulation_id"] == "sim_cf222")
    assert cf_entry["counterfactual"] == {
        "trigger_round": 12,
        "label": "ceo_resigns",
    }


def test_private_children_are_excluded(tmp_path):
    """Operators forking privately don't leak into a public parent's lineage."""
    _write_state(tmp_path, "sim_parent555", is_public=True)

    _write_state(
        tmp_path,
        "sim_privateFork",
        parent_id="sim_parent555",
        is_public=False,
    )
    _write_state(
        tmp_path,
        "sim_publicFork",
        parent_id="sim_parent555",
        is_public=True,
    )

    payload = lineage_service.build_lineage_payload(
        "sim_parent555", str(tmp_path)
    )
    ids = [c["simulation_id"] for c in payload["children"]]
    assert ids == ["sim_publicFork"]
    assert payload["total_children"] == 1


def test_children_sorted_by_created_at_ascending(tmp_path):
    """Oldest fork first — natural narrative order for the lineage view."""
    _write_state(tmp_path, "sim_parent777", is_public=True)

    _write_state(
        tmp_path,
        "sim_forkLATE",
        parent_id="sim_parent777",
        is_public=True,
        created_at="2026-05-09T12:00:00",
    )
    _write_state(
        tmp_path,
        "sim_forkEARLY",
        parent_id="sim_parent777",
        is_public=True,
        created_at="2026-05-01T08:00:00",
    )
    _write_state(
        tmp_path,
        "sim_forkMID",
        parent_id="sim_parent777",
        is_public=True,
        created_at="2026-05-05T09:00:00",
    )

    payload = lineage_service.build_lineage_payload(
        "sim_parent777", str(tmp_path)
    )
    ids = [c["simulation_id"] for c in payload["children"]]
    assert ids == ["sim_forkEARLY", "sim_forkMID", "sim_forkLATE"]


# ── Resilience ─────────────────────────────────────────────────────────


def test_corrupt_child_state_skipped(tmp_path):
    """A child with corrupt state.json is silently skipped."""
    _write_state(tmp_path, "sim_parent888", is_public=True)
    _write_state(
        tmp_path,
        "sim_goodChild",
        parent_id="sim_parent888",
        is_public=True,
    )

    # Hand-write a directory with corrupt state.json.
    bad_dir = tmp_path / "sim_corrupt999"
    bad_dir.mkdir()
    (bad_dir / "state.json").write_text("not valid json {{{", encoding="utf-8")

    payload = lineage_service.build_lineage_payload(
        "sim_parent888", str(tmp_path)
    )
    ids = [c["simulation_id"] for c in payload["children"]]
    assert ids == ["sim_goodChild"]


def test_max_children_cap_truncates_but_total_reflects_uncapped(tmp_path):
    """Capped response keeps total_children honest for a "view all" hint."""
    _write_state(tmp_path, "sim_parent999", is_public=True)

    for idx in range(7):
        _write_state(
            tmp_path,
            f"sim_child{idx:02d}",
            parent_id="sim_parent999",
            is_public=True,
            created_at=f"2026-05-0{idx + 1}T10:00:00",
        )

    payload = lineage_service.build_lineage_payload(
        "sim_parent999",
        str(tmp_path),
        max_children=3,
    )
    assert len(payload["children"]) == 3
    assert payload["total_children"] == 7


def test_scenario_falls_back_to_state_level_requirement(tmp_path):
    """Older sims wrote ``simulation_requirement`` onto state — fall back."""
    parent_dir = _write_state(
        tmp_path,
        "sim_legacyParent",
        is_public=True,
        extra={"simulation_requirement": "Legacy scenario from state.json"},
    )
    # Note: no simulation_config.json written.
    _ = parent_dir

    _write_state(
        tmp_path,
        "sim_legacyFork",
        parent_id="sim_legacyParent",
        is_public=True,
    )

    payload = lineage_service.build_lineage_payload(
        "sim_legacyFork", str(tmp_path)
    )
    parent = payload["parent"]
    assert parent is not None
    assert parent["scenario_preview"].startswith("Legacy scenario")


def test_unpublished_parent_renders_bare_entry(tmp_path):
    """Parent unpublished after the fact ⇒ entry exists but no preview."""
    parent_dir = _write_state(
        tmp_path,
        "sim_silentParent",
        is_public=False,  # unpublished
    )
    _write_config(parent_dir, "Was once public, now hidden.")

    _write_state(
        tmp_path,
        "sim_orphanFork",
        parent_id="sim_silentParent",
        is_public=True,
    )

    payload = lineage_service.build_lineage_payload(
        "sim_orphanFork", str(tmp_path)
    )
    parent = payload["parent"]
    assert parent is not None
    assert parent["simulation_id"] == "sim_silentParent"
    assert parent["is_public"] is False
    assert parent["scenario_preview"] == ""


def test_self_pointer_does_not_recurse(tmp_path):
    """A hand-edited sim that points at itself must not appear as its own child."""
    _write_state(
        tmp_path,
        "sim_loop123",
        parent_id="sim_loop123",
        is_public=True,
    )
    payload = lineage_service.build_lineage_payload(
        "sim_loop123", str(tmp_path)
    )
    assert payload["children"] == []
    assert payload["total_children"] == 0


def test_missing_data_dir_returns_empty_payload(tmp_path):
    """A non-existent data dir doesn't crash the lookup."""
    missing = tmp_path / "does-not-exist"
    payload = lineage_service.build_lineage_payload(
        "sim_ghost", str(missing)
    )
    assert payload["lineage_kind"] == "original"
    assert payload["children"] == []
    assert payload["total_children"] == 0


# ── Wiring guards ──────────────────────────────────────────────────────


def test_route_decorator_present_in_simulation_api():
    """Ensure ``GET /<simulation_id>/lineage`` is registered."""
    api_path = _BACKEND / "app" / "api" / "simulation.py"
    text = api_path.read_text(encoding="utf-8")
    assert "@simulation_bp.route('/<simulation_id>/lineage'" in text
    assert "def get_simulation_lineage(" in text


def test_router_module_imports_lineage_service():
    """The route handler must import the service it's wiring up.

    Catches the failure mode where the route decorator is added but
    the body never gets wired up — same class of mistake the existing
    surface-stats / repro-export tests guard against.
    """
    api_path = _BACKEND / "app" / "api" / "simulation.py"
    text = api_path.read_text(encoding="utf-8")
    assert "from ..services import lineage_service" in text


def test_openapi_schema_declares_simulation_lineage():
    """Swagger UI must document the new endpoint + payload schema."""
    spec_path = _BACKEND / "openapi.yaml"
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "/api/simulation/{simulation_id}/lineage" in spec_text
    assert "SimulationLineage:" in spec_text
