"""Unit tests for the multi-sim batch-status lookup service + endpoint.

Pure offline — no Flask app spin-up, no Neo4j, no simulation runner.
Tests build minimal sim folders on a ``tmp_path`` and assert against
``batch_status.build_batch_status`` directly, plus static guards
against the route file, the OpenAPI spec, the surfaces catalog, and
the application factory wiring.

Covers the properties ``POST /api/simulation/batch-status`` depends on:

  1. ``MAX_BATCH_SIZE`` is 20 (the documented cap).
  2. ``count`` always equals ``len(sim_ids)``.
  3. ``results`` preserves the input order.
  4. A published completed sim emits the full analytics envelope.
  5. A running public sim emits status + current_round but ``null``
     analytics fields (no signal until completion).
  6. A failed public sim emits ``status: "failed"`` + ``null``
     analytics — terminal-but-not-completed is not a signalled state.
  7. A private sim returns the ``found: false`` envelope (publish gate
     applied per id; the surface is unauthenticated).
  8. An unknown sim id returns the same ``found: false`` envelope so a
     caller cannot distinguish private from non-existent.
  9. A duplicate id in the request emits a duplicate entry (input is a
     list, not a set).
 10. ``is_valid_sim_id`` rejects path-traversal sequences, slashes,
     non-strings, and the empty string.
 11. Empty / missing ``sim_root`` returns ``found: false`` per id
     rather than raising.
 12. Mixed-case ``status`` values are handled (the rest of the
     codebase tolerates ``"Running"`` / ``"RUNNING"``).
 13. Quality bucket is normalised to the lowercase value the per-sim
     signal.json reports.
 14. Catalog includes the ``batch_status`` entry pointing at
     ``POST /api/simulation/batch-status``.
 15. Auth-guard exempts ``/api/simulation/batch-status``.
 16. Route file declares the endpoint + the ``no-store`` Cache-Control.
 17. OpenAPI spec describes ``/api/simulation/batch-status`` + a
     ``BatchStatusResponse`` schema.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# Late imports keep the suite collectable even if a future refactor
# moves the service module.
from app.services import batch_status  # noqa: E402
from app.services import surfaces_catalog  # noqa: E402


# ── Fixture builders ─────────────────────────────────────────────────────


def _iso(epoch_seconds: float) -> str:
    """Format ``epoch_seconds`` (UTC) as the naive-local shape
    ``simulation_runner`` writes into ``state.json``."""
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def _write_state(
    root: Path,
    sim_id: str,
    *,
    status: str,
    is_public: bool = True,
    current_round: int = 0,
    created_at: str = "2026-05-01T00:00:00",
    updated_at: str | None = None,
) -> Path:
    """Write a minimum ``state.json`` for one sim under ``root``."""
    sim_dir = root / sim_id
    sim_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "simulation_id": sim_id,
        "project_id": "proj-default",
        "graph_id": "g-dummy",
        "is_public": is_public,
        "status": status,
        "current_round": current_round,
        "created_at": created_at,
        "updated_at": updated_at or created_at,
    }
    (sim_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return sim_dir


def _write_trajectory(
    sim_dir: Path,
    *,
    final_split: tuple[float, float, float],
    rounds: int = 3,
) -> None:
    """Write a ``trajectory.json`` whose final round produces
    ``final_split`` via the standard ±0.2 stance threshold.

    ``rounds`` controls how many snapshots are emitted. Earlier
    snapshots use a 33/33/33 split so ``total_rounds`` is the
    snapshot count and the final-round derivation lands on
    ``final_split`` exactly.
    """
    bullish_pct, neutral_pct, bearish_pct = final_split

    def _split_to_positions(b: float, n: float, _be: float) -> dict[str, dict]:
        # Build a population of 100 agents whose mean stance produces
        # the requested split under the ±0.2 threshold. Bullish agents
        # get stance +1.0, bearish -1.0, neutral 0.0.
        agents: dict[str, dict] = {}
        idx = 0
        for _ in range(int(round(b))):
            agents[f"a{idx}"] = {"k": 1.0}
            idx += 1
        for _ in range(int(round(n))):
            agents[f"a{idx}"] = {"k": 0.0}
            idx += 1
        while len(agents) < 100:
            agents[f"a{idx}"] = {"k": -1.0}
            idx += 1
        return agents

    snapshots = []
    for r in range(1, rounds):
        snapshots.append({
            "round": r,
            "belief_positions": _split_to_positions(33.0, 34.0, 33.0),
        })
    snapshots.append({
        "round": rounds,
        "belief_positions": _split_to_positions(
            bullish_pct, neutral_pct, bearish_pct
        ),
    })

    (sim_dir / "trajectory.json").write_text(
        json.dumps({"snapshots": snapshots}), encoding="utf-8"
    )


def _write_quality(sim_dir: Path, health: str) -> None:
    (sim_dir / "quality.json").write_text(
        json.dumps({"health": health}), encoding="utf-8"
    )


# ── Property 1 — MAX_BATCH_SIZE constant ────────────────────────────────


def test_max_batch_size_is_twenty():
    """The documented cap is 20 — the route handler returns 400 when
    the request exceeds it, and the OpenAPI spec references the same
    number. The constant is the one source of truth."""
    assert batch_status.MAX_BATCH_SIZE == 20


# ── Property 2 — count equals input length ───────────────────────────────


def test_count_matches_input_length(tmp_path: Path):
    payload = batch_status.build_batch_status(str(tmp_path), ["a", "b", "c"])
    assert payload["count"] == 3
    assert len(payload["results"]) == 3


def test_schema_version_is_present(tmp_path: Path):
    payload = batch_status.build_batch_status(str(tmp_path), ["sim_x"])
    assert payload["schema_version"] == "1"


# ── Property 3 — order is preserved ─────────────────────────────────────


def test_results_preserve_input_order(tmp_path: Path):
    _write_state(tmp_path, "sim_a", status="running")
    _write_state(tmp_path, "sim_b", status="completed")
    _write_state(tmp_path, "sim_c", status="failed")

    payload = batch_status.build_batch_status(
        str(tmp_path), ["sim_c", "sim_a", "sim_b"]
    )
    assert [r["sim_id"] for r in payload["results"]] == ["sim_c", "sim_a", "sim_b"]


# ── Property 4 — published completed sim emits analytics ────────────────


def test_completed_public_sim_emits_full_envelope(tmp_path: Path):
    sim_dir = _write_state(
        tmp_path,
        "sim_done",
        status="completed",
        current_round=5,
        updated_at="2026-06-01T12:00:00",
    )
    _write_trajectory(sim_dir, final_split=(70.0, 20.0, 10.0), rounds=5)
    _write_quality(sim_dir, "excellent")

    payload = batch_status.build_batch_status(str(tmp_path), ["sim_done"])
    entry = payload["results"][0]
    assert entry["sim_id"] == "sim_done"
    assert entry["found"] is True
    assert entry["status"] == "completed"
    assert entry["direction"] == "Bullish"
    assert entry["confidence_pct"] is not None
    assert entry["confidence_pct"] > 0
    assert entry["quality_health"] == "excellent"
    assert entry["total_rounds"] == 5
    assert entry["completed_at"] == "2026-06-01T12:00:00"


# ── Property 5 — running public sim emits null analytics ────────────────


def test_running_public_sim_has_null_analytics(tmp_path: Path):
    _write_state(
        tmp_path, "sim_run", status="running", current_round=3
    )
    # No trajectory.json — a mid-run sim may not have written one yet.

    payload = batch_status.build_batch_status(str(tmp_path), ["sim_run"])
    entry = payload["results"][0]
    assert entry["found"] is True
    assert entry["status"] == "running"
    assert entry["current_round"] == 3
    assert entry["direction"] is None
    assert entry["confidence_pct"] is None
    assert entry["quality_health"] is None
    assert entry["total_rounds"] is None
    assert entry["completed_at"] is None


# ── Property 6 — failed public sim emits status only ────────────────────


def test_failed_public_sim_emits_status_only(tmp_path: Path):
    _write_state(tmp_path, "sim_fail", status="failed")

    payload = batch_status.build_batch_status(str(tmp_path), ["sim_fail"])
    entry = payload["results"][0]
    assert entry["found"] is True
    assert entry["status"] == "failed"
    # Terminal-but-not-completed must not leak signal fields — a
    # consumer rendering "❌ failed" must not also see a direction.
    assert entry["direction"] is None
    assert entry["confidence_pct"] is None
    assert entry["completed_at"] is None


# ── Property 7 — private sim hidden behind found:false ──────────────────


def test_private_sim_returns_found_false(tmp_path: Path):
    sim_dir = _write_state(
        tmp_path, "sim_priv", status="completed", is_public=False
    )
    _write_trajectory(sim_dir, final_split=(80.0, 10.0, 10.0))
    _write_quality(sim_dir, "excellent")

    payload = batch_status.build_batch_status(str(tmp_path), ["sim_priv"])
    entry = payload["results"][0]
    assert entry["found"] is False
    # Every analytics field must be null — the surface is
    # unauthenticated, so the existence-of-a-private-sim signal is
    # itself a leak the API must not emit.
    assert entry["status"] is None
    assert entry["direction"] is None
    assert entry["confidence_pct"] is None
    assert entry["quality_health"] is None
    assert entry["current_round"] is None
    assert entry["total_rounds"] is None
    assert entry["completed_at"] is None


# ── Property 8 — unknown id returns the same found:false shape ──────────


def test_unknown_sim_id_returns_found_false(tmp_path: Path):
    payload = batch_status.build_batch_status(
        str(tmp_path), ["sim_does_not_exist"]
    )
    entry = payload["results"][0]
    assert entry["sim_id"] == "sim_does_not_exist"
    assert entry["found"] is False


def test_private_and_unknown_are_indistinguishable(tmp_path: Path):
    """Both shapes must be byte-identical except for ``sim_id`` so a
    caller cannot probe for the existence of a private sim by
    comparing responses."""
    _write_state(
        tmp_path, "sim_priv", status="completed", is_public=False
    )

    payload = batch_status.build_batch_status(
        str(tmp_path), ["sim_priv", "sim_ghost"]
    )
    priv = dict(payload["results"][0])
    ghost = dict(payload["results"][1])
    del priv["sim_id"]
    del ghost["sim_id"]
    assert priv == ghost


# ── Property 9 — duplicates emit duplicate entries ──────────────────────


def test_duplicate_ids_emit_duplicate_entries(tmp_path: Path):
    _write_state(tmp_path, "sim_a", status="running")
    payload = batch_status.build_batch_status(
        str(tmp_path), ["sim_a", "sim_a", "sim_a"]
    )
    assert payload["count"] == 3
    assert len(payload["results"]) == 3
    assert all(r["sim_id"] == "sim_a" for r in payload["results"])
    assert all(r["found"] is True for r in payload["results"])


# ── Property 10 — id validation ─────────────────────────────────────────


def test_is_valid_sim_id_accepts_typical_id():
    assert batch_status.is_valid_sim_id("sim_abc123-def.xyz")


def test_is_valid_sim_id_rejects_path_traversal():
    assert not batch_status.is_valid_sim_id("../etc/passwd")
    assert not batch_status.is_valid_sim_id("sim/with/slash")
    assert not batch_status.is_valid_sim_id("sim\\back\\slash")


def test_is_valid_sim_id_rejects_empty_and_nonstring():
    assert not batch_status.is_valid_sim_id("")
    assert not batch_status.is_valid_sim_id(None)
    assert not batch_status.is_valid_sim_id(42)
    assert not batch_status.is_valid_sim_id(["sim_a"])


def test_is_valid_sim_id_rejects_special_characters():
    assert not batch_status.is_valid_sim_id("sim with space")
    assert not batch_status.is_valid_sim_id("sim;rm -rf /")
    assert not batch_status.is_valid_sim_id("sim$(whoami)")


# ── Property 11 — empty / missing sim_root ──────────────────────────────


def test_missing_sim_root_returns_found_false_per_id(tmp_path: Path):
    nonexistent = tmp_path / "does-not-exist"
    payload = batch_status.build_batch_status(
        str(nonexistent), ["sim_a", "sim_b"]
    )
    assert payload["count"] == 2
    assert all(r["found"] is False for r in payload["results"])


def test_blank_sim_root_returns_found_false_per_id():
    payload = batch_status.build_batch_status("", ["sim_a"])
    assert payload["results"][0]["found"] is False


# ── Property 12 — mixed-case status ─────────────────────────────────────


def test_mixed_case_status_is_normalised(tmp_path: Path):
    """``state.json`` historically lower-cases status, but the service
    must tolerate mixed-case values written by older sims so a
    heterogeneous corpus still produces accurate batch-status reads.
    Matches ``platform_status``'s posture byte-for-byte."""
    _write_state(tmp_path, "sim_mixed", status="Running")
    _write_state(tmp_path, "sim_upper", status="COMPLETED")

    payload = batch_status.build_batch_status(
        str(tmp_path), ["sim_mixed", "sim_upper"]
    )
    assert payload["results"][0]["status"] == "running"
    assert payload["results"][1]["status"] == "completed"


# ── Property 13 — quality bucket normalisation ──────────────────────────


def test_quality_health_passthrough(tmp_path: Path):
    sim_dir = _write_state(tmp_path, "sim_q", status="completed")
    _write_trajectory(sim_dir, final_split=(60.0, 20.0, 20.0))
    _write_quality(sim_dir, "good")

    payload = batch_status.build_batch_status(str(tmp_path), ["sim_q"])
    assert payload["results"][0]["quality_health"] == "good"


def test_missing_quality_health_defaults_to_na(tmp_path: Path):
    """When ``quality.json`` is missing, ``signal_service.compute_signal``
    falls through to ``"N/A"`` — the same string the per-sim
    signal.json emits in the same case. The batch-status entry must
    mirror that so the two surfaces stay consistent."""
    sim_dir = _write_state(tmp_path, "sim_noq", status="completed")
    _write_trajectory(sim_dir, final_split=(60.0, 20.0, 20.0))

    payload = batch_status.build_batch_status(str(tmp_path), ["sim_noq"])
    assert payload["results"][0]["quality_health"] == "N/A"


# ── Property 14 — catalog discoverability ───────────────────────────────


def test_catalog_includes_batch_status_entry():
    """The catalog is how integrators discover platform endpoints — a
    new surface not in the catalog might as well not exist for machine
    readers."""
    keys = {entry["key"] for entry in surfaces_catalog.get_surfaces_catalog()}
    assert "batch_status" in keys


def test_catalog_entry_matches_route():
    entry = next(
        e
        for e in surfaces_catalog.get_surfaces_catalog()
        if e["key"] == "batch_status"
    )
    assert entry["endpoint"] == "/api/simulation/batch-status"
    assert entry["method"] == "POST"
    assert entry["type"] == "integration"


# ── Property 15 — auth-guard exempts the endpoint ───────────────────────


def test_auth_guard_exempts_batch_status_path():
    """Drift guard for ``app/__init__.py`` — the endpoint must be
    listed in the same allow-list block as ``/api/status.json``."""
    init_path = _BACKEND / "app" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    assert "'/api/simulation/batch-status'" in text, (
        "internal_auth_guard must exempt /api/simulation/batch-status — "
        "the endpoint is meant for external keyless polling"
    )


# ── Property 16 — route file declares the endpoint ──────────────────────


def test_route_handler_present_in_simulation_module():
    """Drift guard for ``app/api/simulation.py`` — catches the failure
    mode where the blueprint is registered but the route handler was
    deleted."""
    sim_path = _BACKEND / "app" / "api" / "simulation.py"
    text = sim_path.read_text(encoding="utf-8")
    assert "@simulation_bp.route('/batch-status', methods=['POST'])" in text, (
        "simulation blueprint missing @simulation_bp.route('/batch-status', POST)"
    )


def test_route_handler_sets_no_store_cache_header():
    """The response depends on live per-sim state; a cached response
    would defeat the polling use case the surface is built for. The
    route handler must set ``Cache-Control: no-store`` explicitly so
    a misconfigured reverse proxy doesn't cache by default."""
    sim_path = _BACKEND / "app" / "api" / "simulation.py"
    text = sim_path.read_text(encoding="utf-8")
    # Anchor on the surrounding context so the assertion doesn't match
    # an unrelated no-store usage elsewhere in the file.
    snippet = text.split("def batch_status_lookup(", 1)
    assert len(snippet) == 2, "batch_status_lookup handler not found"
    handler_body = snippet[1].split("\n@simulation_bp.route", 1)[0]
    assert '"no-store"' in handler_body, (
        "batch_status_lookup must set Cache-Control: no-store"
    )


# ── Property 17 — OpenAPI spec coverage ─────────────────────────────────


def test_openapi_spec_includes_batch_status_endpoint():
    """The endpoint must be discoverable from the live OpenAPI document
    at ``/api/openapi.yaml`` — the same surface ``/api/docs`` consumes."""
    spec_path = _BACKEND / "openapi.yaml"
    assert spec_path.exists(), f"openapi.yaml missing at {spec_path}"
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "/api/simulation/batch-status:" in spec_text, (
        "openapi.yaml missing /api/simulation/batch-status path entry"
    )
    assert "BatchStatusResponse" in spec_text, (
        "openapi.yaml missing BatchStatusResponse schema reference"
    )
    assert "BatchStatusEntry" in spec_text, (
        "openapi.yaml missing BatchStatusEntry schema reference"
    )


# ── Property 18 — schema integrity ──────────────────────────────────────


def test_envelope_is_json_serialisable(tmp_path: Path):
    sim_dir = _write_state(tmp_path, "sim_done", status="completed")
    _write_trajectory(sim_dir, final_split=(60.0, 20.0, 20.0))
    _write_quality(sim_dir, "good")
    _write_state(tmp_path, "sim_run", status="running")

    payload = batch_status.build_batch_status(
        str(tmp_path), ["sim_done", "sim_run", "sim_ghost"]
    )
    serialised = json.dumps(payload, sort_keys=True)
    assert serialised
    roundtripped = json.loads(serialised)
    assert roundtripped["count"] == 3
    assert roundtripped["schema_version"] == "1"


def test_corrupt_state_json_is_treated_as_unknown(tmp_path: Path):
    """A malformed ``state.json`` must degrade to ``found: false``
    rather than tank the whole batch response."""
    sim_dir = tmp_path / "sim_corrupt"
    sim_dir.mkdir()
    (sim_dir / "state.json").write_text("not json at all", encoding="utf-8")

    _write_state(tmp_path, "sim_ok", status="running")

    payload = batch_status.build_batch_status(
        str(tmp_path), ["sim_corrupt", "sim_ok"]
    )
    assert payload["results"][0]["found"] is False
    assert payload["results"][1]["found"] is True
    assert payload["results"][1]["status"] == "running"
