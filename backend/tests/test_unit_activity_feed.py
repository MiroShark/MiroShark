"""Unit tests for the activity-feed service + endpoint.

Pure offline — no Flask app spin-up, no Neo4j, no simulation runner.
The tests build minimal sim folders on a ``tmp_path`` and assert
against ``activity_feed.build_activity_feed`` directly, plus a few
static guards against the route file and the OpenAPI spec.

Covers the properties ``GET /api/activity.json`` depends on:

  1. Empty / missing sim_root → ``{count: 0, results: []}``.
  2. Only ``is_public=true`` AND ``status="completed"`` sims appear.
  3. Results are ordered by ``completed_at`` descending.
  4. ``limit`` clamps into ``[1, 50]`` (typo'd inputs don't 400).
  5. ``scenario_title`` is truncated to 100 chars with ellipsis.
  6. ``direction`` / ``confidence_pct`` / ``quality_health`` derive
     from the same signal pipeline the per-sim ``signal.json`` uses.
  7. ``total_rounds`` matches the trajectory snapshot count.
  8. Completed sim with no trajectory still appears, analytics null.
  9. Sim without ``updated_at`` falls back to ``created_at``.
 10. Sim without either timestamp is excluded (would be unsortable).
 11. Corrupt ``state.json`` is skipped, doesn't tank the response.
 12. Envelope is JSON-serialisable.
 13. ``feed_etag`` derives from ``count`` + newest ``completed_at``.
 14. Catalog includes the ``activity_feed`` entry.
 15. OpenAPI spec describes ``/api/activity.json`` + the
     ``ActivityFeed`` + ``ActivityFeedEntry`` schemas.
 16. Blueprint is registered + mounted in the app factory.
 17. Route is added to the ``internal_auth_guard`` allow-list.
 18. Route file declares the endpoint + cache header + ETag handling.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path



_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# Late imports keep the suite collectable even if a future refactor
# moves the service module.
from app.services import activity_feed  # noqa: E402
from app.services import surfaces_catalog  # noqa: E402


# ── Fixture builder ───────────────────────────────────────────────────────


def _iso(epoch_seconds: float) -> str:
    """Format ``epoch_seconds`` as the naive-local ISO shape
    ``simulation_runner`` writes into ``state.json``."""
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def _write_sim(
    root: Path,
    sim_id: str,
    *,
    status: str = "completed",
    created_at: str = "2026-05-01T00:00:00",
    updated_at: str | None = "2026-05-01T00:00:00",
    is_public: bool = True,
    project_id: str | None = "proj-default",
    scenario: str | None = "Will the Fed cut rates in June?",
    snapshots: list | None = None,
    quality_health: str | None = "Excellent",
) -> Path:
    """Build a minimum sim folder under ``root``.

    Snapshots defaults to a one-round bullish trajectory so the signal
    pipeline yields a non-null direction; pass ``snapshots=[]`` for a
    completed sim with no derivable analytics.
    """
    sim_dir = root / sim_id
    sim_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "simulation_id": sim_id,
        "project_id": project_id,
        "is_public": is_public,
        "status": status,
        "created_at": created_at,
    }
    if updated_at is not None:
        state["updated_at"] = updated_at
    (sim_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    if scenario is not None:
        config = {"simulation_requirement": scenario}
        (sim_dir / "simulation_config.json").write_text(
            json.dumps(config), encoding="utf-8"
        )

    if snapshots is None:
        # Default to a single bullish snapshot — every agent stance > 0.2
        # → direction "Bullish" / non-zero confidence.
        snapshots = [
            {
                "belief_positions": {
                    "agent_a": {"a": 0.9, "b": 0.8},
                    "agent_b": {"a": 0.7, "b": 0.6},
                    "agent_c": {"a": 0.5, "b": 0.4},
                }
            }
        ]
    traj = {"snapshots": snapshots}
    (sim_dir / "trajectory.json").write_text(json.dumps(traj), encoding="utf-8")

    if quality_health is not None:
        (sim_dir / "quality.json").write_text(
            json.dumps({"health": quality_health}), encoding="utf-8"
        )

    return sim_dir


# ── Property 1 — empty / missing sim_root ────────────────────────────────


def test_empty_sim_root_returns_well_formed_envelope(tmp_path: Path):
    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["schema_version"] == "1"
    assert payload["count"] == 0
    assert payload["results"] == []


def test_missing_sim_root_returns_well_formed_envelope(tmp_path: Path):
    nonexistent = tmp_path / "does-not-exist"
    payload = activity_feed.build_activity_feed(str(nonexistent))
    assert payload["count"] == 0
    assert payload["results"] == []


def test_blank_sim_root_returns_well_formed_envelope():
    payload = activity_feed.build_activity_feed("")
    assert payload["count"] == 0
    assert payload["results"] == []


# ── Property 2 — publish gate ────────────────────────────────────────────


def test_only_public_completed_sims_appear(tmp_path: Path):
    _write_sim(tmp_path, "pub-done", is_public=True, status="completed")
    _write_sim(tmp_path, "priv-done", is_public=False, status="completed")
    _write_sim(tmp_path, "pub-running", is_public=True, status="running")
    _write_sim(tmp_path, "pub-failed", is_public=True, status="failed")
    _write_sim(tmp_path, "priv-running", is_public=False, status="running")

    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["count"] == 1
    assert payload["results"][0]["sim_id"] == "pub-done"


def test_status_match_is_case_insensitive(tmp_path: Path):
    """``state.json`` historically lower-cases status, but the service
    must tolerate mixed-case values written by older sims."""
    _write_sim(tmp_path, "sim-mixed", status="Completed")
    _write_sim(tmp_path, "sim-upper", status="COMPLETED")
    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["count"] == 2


# ── Property 3 — ordering ────────────────────────────────────────────────


def test_results_ordered_by_completed_at_descending(tmp_path: Path):
    _write_sim(
        tmp_path,
        "sim-oldest",
        updated_at="2026-05-01T00:00:00",
        created_at="2026-05-01T00:00:00",
    )
    _write_sim(
        tmp_path,
        "sim-middle",
        updated_at="2026-05-15T12:00:00",
        created_at="2026-05-15T12:00:00",
    )
    _write_sim(
        tmp_path,
        "sim-newest",
        updated_at="2026-06-01T08:30:00",
        created_at="2026-06-01T08:30:00",
    )

    payload = activity_feed.build_activity_feed(str(tmp_path))
    ids = [entry["sim_id"] for entry in payload["results"]]
    assert ids == ["sim-newest", "sim-middle", "sim-oldest"]


def test_ties_break_on_sim_id_descending(tmp_path: Path):
    """Same completed_at → sim_id descending so the order is
    deterministic across calls (useful for ETag + tests)."""
    same_ts = "2026-06-01T12:00:00"
    _write_sim(tmp_path, "sim-aaa", updated_at=same_ts, created_at=same_ts)
    _write_sim(tmp_path, "sim-bbb", updated_at=same_ts, created_at=same_ts)
    _write_sim(tmp_path, "sim-ccc", updated_at=same_ts, created_at=same_ts)

    payload = activity_feed.build_activity_feed(str(tmp_path))
    ids = [entry["sim_id"] for entry in payload["results"]]
    assert ids == ["sim-ccc", "sim-bbb", "sim-aaa"]


# ── Property 4 — limit clamping ──────────────────────────────────────────


def test_clamp_limit_defaults():
    assert activity_feed.clamp_limit(None) == 20
    assert activity_feed.clamp_limit("") == 20
    assert activity_feed.clamp_limit("not a number") == 20


def test_clamp_limit_clamps_low():
    assert activity_feed.clamp_limit(0) == 1
    assert activity_feed.clamp_limit(-5) == 1


def test_clamp_limit_clamps_high():
    assert activity_feed.clamp_limit(100) == 50
    assert activity_feed.clamp_limit(1000000) == 50


def test_clamp_limit_passes_in_range_values():
    assert activity_feed.clamp_limit(1) == 1
    assert activity_feed.clamp_limit(20) == 20
    assert activity_feed.clamp_limit(50) == 50


def test_clamp_limit_rejects_booleans():
    """``True`` / ``False`` are rejected explicitly — a stray boolean
    from a misparse should not masquerade as ``1`` / ``0``."""
    assert activity_feed.clamp_limit(True) == 20
    assert activity_feed.clamp_limit(False) == 20


def test_limit_caps_result_count(tmp_path: Path):
    for i in range(30):
        # Distinct timestamps so ordering is well-defined.
        ts = f"2026-06-01T{i:02d}:00:00"
        _write_sim(tmp_path, f"sim-{i:03d}", updated_at=ts, created_at=ts)

    payload = activity_feed.build_activity_feed(str(tmp_path), limit=5)
    assert payload["count"] == 5
    assert len(payload["results"]) == 5
    # Newest five should be sim-029 .. sim-025.
    assert [e["sim_id"] for e in payload["results"]] == [
        "sim-029",
        "sim-028",
        "sim-027",
        "sim-026",
        "sim-025",
    ]


def test_build_activity_feed_clamps_internally(tmp_path: Path):
    """Calling with a raw out-of-range ``limit`` still produces a sane
    response (the service applies the clamp defensively)."""
    for i in range(3):
        ts = f"2026-06-01T{i:02d}:00:00"
        _write_sim(tmp_path, f"sim-{i:03d}", updated_at=ts, created_at=ts)

    # limit=0 clamps up to 1 → only newest sim returned.
    payload = activity_feed.build_activity_feed(str(tmp_path), limit=0)
    assert payload["count"] == 1


# ── Property 5 — scenario title truncation ───────────────────────────────


def test_scenario_title_under_cap_passes_through(tmp_path: Path):
    _write_sim(tmp_path, "sim-short", scenario="Short scenario.")
    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["results"][0]["scenario_title"] == "Short scenario."


def test_scenario_title_truncated_with_ellipsis(tmp_path: Path):
    long_scenario = "A" * 200
    _write_sim(tmp_path, "sim-long", scenario=long_scenario)
    payload = activity_feed.build_activity_feed(str(tmp_path))
    title = payload["results"][0]["scenario_title"]
    assert len(title) == activity_feed.SCENARIO_TITLE_MAX_CHARS
    assert title.endswith("…")
    assert title[:-1] == "A" * (activity_feed.SCENARIO_TITLE_MAX_CHARS - 1)


def test_scenario_title_max_chars_is_100():
    """Document the constant — a future change to the cap should be
    deliberate, not accidental."""
    assert activity_feed.SCENARIO_TITLE_MAX_CHARS == 100


def test_scenario_title_empty_when_config_missing(tmp_path: Path):
    """Sim with no simulation_config.json still appears, with an empty
    title — the route emits the raw value rather than ``"(untitled)"``
    so a consumer can render its own placeholder."""
    _write_sim(tmp_path, "sim-noconfig", scenario=None)
    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["count"] == 1
    assert payload["results"][0]["scenario_title"] == ""


# ── Property 6 — analytics derive from the signal pipeline ───────────────


def test_bullish_trajectory_yields_bullish_direction(tmp_path: Path):
    _write_sim(
        tmp_path,
        "sim-bull",
        snapshots=[
            {
                "belief_positions": {
                    "a": {"x": 0.9, "y": 0.8},
                    "b": {"x": 0.7, "y": 0.6},
                    "c": {"x": 0.5, "y": 0.4},
                }
            }
        ],
    )
    payload = activity_feed.build_activity_feed(str(tmp_path))
    entry = payload["results"][0]
    assert entry["direction"] == "Bullish"
    assert entry["confidence_pct"] is not None
    assert entry["confidence_pct"] > 0


def test_bearish_trajectory_yields_bearish_direction(tmp_path: Path):
    _write_sim(
        tmp_path,
        "sim-bear",
        snapshots=[
            {
                "belief_positions": {
                    "a": {"x": -0.9, "y": -0.8},
                    "b": {"x": -0.7, "y": -0.6},
                    "c": {"x": -0.5, "y": -0.4},
                }
            }
        ],
    )
    payload = activity_feed.build_activity_feed(str(tmp_path))
    entry = payload["results"][0]
    assert entry["direction"] == "Bearish"


def test_quality_health_passes_through(tmp_path: Path):
    _write_sim(tmp_path, "sim-good", quality_health="Good")
    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["results"][0]["quality_health"] == "Good"


# ── Property 7 — total_rounds matches trajectory ─────────────────────────


def test_total_rounds_matches_trajectory_snapshot_count(tmp_path: Path):
    snapshots = [
        {
            "belief_positions": {
                "a": {"x": 0.5},
                "b": {"x": 0.4},
            }
        }
        for _ in range(7)
    ]
    _write_sim(tmp_path, "sim-7rounds", snapshots=snapshots)
    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["results"][0]["total_rounds"] == 7


# ── Property 8 — degraded trajectory still appears ───────────────────────


def test_completed_sim_without_trajectory_still_appears(tmp_path: Path):
    """A completed sim with no trajectory file still appears (the
    completion is real); analytics fields are ``null``."""
    sim_dir = tmp_path / "sim-no-traj"
    sim_dir.mkdir()
    state = {
        "simulation_id": "sim-no-traj",
        "project_id": "proj",
        "is_public": True,
        "status": "completed",
        "created_at": "2026-06-01T00:00:00",
        "updated_at": "2026-06-01T00:00:00",
    }
    (sim_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["count"] == 1
    entry = payload["results"][0]
    assert entry["sim_id"] == "sim-no-traj"
    assert entry["direction"] is None
    assert entry["confidence_pct"] is None
    assert entry["quality_health"] is None
    assert entry["total_rounds"] == 0


def test_completed_sim_with_empty_snapshots_still_appears(tmp_path: Path):
    _write_sim(tmp_path, "sim-empty-traj", snapshots=[])
    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["count"] == 1
    entry = payload["results"][0]
    assert entry["direction"] is None
    assert entry["total_rounds"] == 0


# ── Property 9 — updated_at fallback to created_at ───────────────────────


def test_completed_at_uses_updated_at(tmp_path: Path):
    _write_sim(
        tmp_path,
        "sim-with-updated",
        created_at="2026-05-01T00:00:00",
        updated_at="2026-06-01T12:00:00",
    )
    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["results"][0]["completed_at"] == "2026-06-01T12:00:00"


def test_completed_at_falls_back_to_created_at_when_updated_at_missing(
    tmp_path: Path,
):
    """Older sims wrote ``state.json`` before the ``updated_at`` field
    was instrumented — they still need to appear in the feed."""
    sim_dir = tmp_path / "sim-no-updated"
    sim_dir.mkdir()
    state = {
        "simulation_id": "sim-no-updated",
        "project_id": "proj",
        "is_public": True,
        "status": "completed",
        "created_at": "2026-04-01T00:00:00",
        # No updated_at key at all
    }
    (sim_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (sim_dir / "trajectory.json").write_text(
        json.dumps({"snapshots": []}), encoding="utf-8"
    )

    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["count"] == 1
    assert payload["results"][0]["completed_at"] == "2026-04-01T00:00:00"


# ── Property 10 — unsortable sims excluded ───────────────────────────────


def test_sim_without_any_timestamp_is_excluded(tmp_path: Path):
    """A completed sim with neither updated_at nor created_at can't be
    placed in the reverse-chronological ordering. Skip it rather than
    let it float to an arbitrary slot."""
    sim_dir = tmp_path / "sim-no-ts"
    sim_dir.mkdir()
    state = {
        "simulation_id": "sim-no-ts",
        "project_id": "proj",
        "is_public": True,
        "status": "completed",
        # No created_at, no updated_at
    }
    (sim_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    _write_sim(
        tmp_path,
        "sim-with-ts",
        created_at="2026-06-01T00:00:00",
        updated_at="2026-06-01T00:00:00",
    )

    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["count"] == 1
    assert payload["results"][0]["sim_id"] == "sim-with-ts"


# ── Property 11 — corrupt sim folders tolerated ──────────────────────────


def test_corrupt_state_json_is_skipped(tmp_path: Path):
    sim_dir = tmp_path / "sim-corrupt"
    sim_dir.mkdir()
    (sim_dir / "state.json").write_text("not json at all", encoding="utf-8")

    _write_sim(tmp_path, "sim-ok")

    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["count"] == 1
    assert payload["results"][0]["sim_id"] == "sim-ok"


def test_dotfile_directories_are_skipped(tmp_path: Path):
    """A stray ``.DS_Store`` or ``.git`` folder under the sim root
    must not be counted as a sim."""
    (tmp_path / ".DS_Store").mkdir()
    (tmp_path / ".cache").mkdir()
    _write_sim(tmp_path, "sim-real")

    payload = activity_feed.build_activity_feed(str(tmp_path))
    assert payload["count"] == 1
    assert payload["results"][0]["sim_id"] == "sim-real"


# ── Property 12 — envelope is JSON-serialisable ──────────────────────────


def test_envelope_is_json_serialisable(tmp_path: Path):
    _write_sim(tmp_path, "sim-a")
    _write_sim(
        tmp_path,
        "sim-b",
        updated_at="2026-06-02T00:00:00",
        created_at="2026-06-02T00:00:00",
    )

    payload = activity_feed.build_activity_feed(str(tmp_path))
    serialised = json.dumps(payload, sort_keys=True)
    assert serialised
    roundtripped = json.loads(serialised)
    assert roundtripped["count"] == 2
    assert isinstance(roundtripped["results"], list)


def test_entry_has_locked_field_set(tmp_path: Path):
    """The per-sim entry schema is the public contract — adding /
    removing a field is a breaking change."""
    _write_sim(tmp_path, "sim-shape")
    payload = activity_feed.build_activity_feed(str(tmp_path))
    entry = payload["results"][0]
    expected_keys = {
        "sim_id",
        "scenario_title",
        "direction",
        "confidence_pct",
        "quality_health",
        "total_rounds",
        "completed_at",
        "project_id",
    }
    assert set(entry.keys()) == expected_keys


# ── Property 13 — ETag derivation ────────────────────────────────────────


def test_etag_format(tmp_path: Path):
    _write_sim(tmp_path, "sim-etag", updated_at="2026-06-09T12:34:56")
    payload = activity_feed.build_activity_feed(str(tmp_path))
    etag = activity_feed.feed_etag(payload)
    assert etag.startswith('"activity-1-2026-06-09T12:34:56')
    assert etag.endswith('"')


def test_etag_empty_envelope():
    """Empty envelope still produces a well-formed ETag string."""
    etag = activity_feed.feed_etag(
        {"schema_version": "1", "count": 0, "results": []}
    )
    assert etag == '"activity-0-"'


def test_etag_changes_on_new_completion(tmp_path: Path):
    _write_sim(tmp_path, "sim-old", updated_at="2026-06-01T00:00:00")
    payload_a = activity_feed.build_activity_feed(str(tmp_path))
    etag_a = activity_feed.feed_etag(payload_a)

    _write_sim(tmp_path, "sim-new", updated_at="2026-06-09T00:00:00")
    payload_b = activity_feed.build_activity_feed(str(tmp_path))
    etag_b = activity_feed.feed_etag(payload_b)

    assert etag_a != etag_b


# ── Property 14 — catalog discoverability ────────────────────────────────


def test_catalog_includes_activity_feed_entry():
    keys = {entry["key"] for entry in surfaces_catalog.get_surfaces_catalog()}
    assert "activity_feed" in keys


def test_catalog_entry_matches_route():
    entry = next(
        e
        for e in surfaces_catalog.get_surfaces_catalog()
        if e["key"] == "activity_feed"
    )
    assert entry["endpoint"] == "/api/activity.json"
    assert entry["method"] == "GET"
    assert entry["type"] == "discovery"


# ── Property 15 — OpenAPI spec coverage ──────────────────────────────────


def test_openapi_spec_includes_activity_feed_path():
    spec_path = _BACKEND / "openapi.yaml"
    assert spec_path.exists(), f"openapi.yaml missing at {spec_path}"
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "/api/activity.json:" in spec_text, (
        "openapi.yaml missing /api/activity.json path entry"
    )
    assert "ActivityFeed" in spec_text, (
        "openapi.yaml missing ActivityFeed schema reference"
    )
    assert "ActivityFeedEntry" in spec_text, (
        "openapi.yaml missing ActivityFeedEntry schema reference"
    )


# ── Property 16 — blueprint registration ─────────────────────────────────


def test_activity_blueprint_is_exported():
    from app import api

    assert hasattr(api, "activity_bp"), (
        "activity_bp not exported from app.api — register it in app/api/__init__.py"
    )


def test_activity_blueprint_is_mounted_on_the_app():
    """Static check on the application factory rather than spinning up
    ``create_app``."""
    init_path = _BACKEND / "app" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    assert "activity_bp" in text, (
        "activity_bp not referenced in app/__init__.py — register it in create_app"
    )
    assert "app.register_blueprint(activity_bp, url_prefix='/api')" in text, (
        "activity_bp must be mounted at '/api' so GET /api/activity.json resolves"
    )


# ── Property 17 — auth-guard allow-list ──────────────────────────────────


def test_activity_endpoint_is_added_to_auth_allowlist():
    """The endpoint is public-keyless by design; the auth guard must
    let it through alongside ``/api/status.json`` and
    ``/api/simulation/batch-status``."""
    init_path = _BACKEND / "app" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    assert "request.path == '/api/activity.json'" in text, (
        "internal_auth_guard missing '/api/activity.json' allow-list entry"
    )


# ── Property 18 — route file drift guards ────────────────────────────────


def test_activity_route_decorator_present():
    activity_path = _BACKEND / "app" / "api" / "activity.py"
    text = activity_path.read_text(encoding="utf-8")
    assert '@activity_bp.route("/activity.json"' in text, (
        "activity blueprint missing @activity_bp.route(\"/activity.json\", ...) decorator"
    )


def test_activity_route_sets_cache_control_header():
    activity_path = _BACKEND / "app" / "api" / "activity.py"
    text = activity_path.read_text(encoding="utf-8")
    assert "public, max-age=30" in text, (
        "activity route must set Cache-Control: public, max-age=30"
    )


def test_activity_route_handles_if_none_match():
    """ETag 304 short-circuit must be wired so polling consumers
    don't pay the JSON body cost on every request."""
    activity_path = _BACKEND / "app" / "api" / "activity.py"
    text = activity_path.read_text(encoding="utf-8")
    assert "If-None-Match" in text, (
        "activity route must honour If-None-Match → 304 short-circuit"
    )


def test_activity_route_documents_auth_posture():
    """The PR #149 lesson: surface the auth posture decision in the
    handler so reviewers see it was deliberate."""
    activity_path = _BACKEND / "app" / "api" / "activity.py"
    text = activity_path.read_text(encoding="utf-8")
    assert "Auth posture: public" in text, (
        "activity route must document the auth-posture decision near the handler"
    )
