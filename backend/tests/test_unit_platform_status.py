"""Unit tests for the platform health probe service + endpoint.

Pure offline — no Flask app spin-up, no Neo4j, no simulation runner.
The tests build minimal sim folders on a ``tmp_path`` and assert
against ``platform_status.build_status`` directly, plus a few static
guards against the route file and the OpenAPI spec.

Covers the properties ``GET /api/status.json`` depends on:

  1. Empty / missing sim_root → all-zero envelope, still ``ok: true``.
  2. Running sims increment ``queue_depth``.
  3. Completed sims within the 24h window count toward ``completed_24h``.
  4. Completed sims older than the 24h window are excluded from the
     window count but still bump ``total_sims`` + ``last_completed_at``.
  5. ``last_completed_at`` is the maximum ``updated_at`` across all
     completed sims.
  6. ``total_sims`` counts only public + completed sims (the probe is
     unauthenticated, so it must not leak private/in-flight volume).
  7. ``surface_count`` is taken verbatim from the injected argument
     (the source of truth is the catalog, not a re-implementation).
  8. ``check_at`` is an ISO-8601 UTC string ending in ``Z``.
  9. Envelope is JSON-serialisable end-to-end.
 10. Service module module-name is importable from the route handler.
 11. Route file declares the endpoint + cache header in the source.
 12. Blueprint is registered + wired in the app factory.
 13. Catalog includes the ``platform_status`` entry.
 14. OpenAPI spec describes ``/api/status.json`` + a ``PlatformStatus``
     schema.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path



_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# Late imports keep the suite collectable even if a future refactor
# moves the service module.
from app.services import platform_status  # noqa: E402
from app.services import surfaces_catalog  # noqa: E402


# ── Fixture builder ───────────────────────────────────────────────────────


def _iso(epoch_seconds: float) -> str:
    """Format ``epoch_seconds`` (UTC) as the naive-local shape
    ``simulation_runner`` writes into ``state.json``."""
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def _write_sim(
    root: Path,
    sim_id: str,
    *,
    status: str,
    created_at: str = "2026-05-01T00:00:00",
    updated_at: str | None = None,
    is_public: bool = True,
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
        "created_at": created_at,
        "updated_at": updated_at or created_at,
    }
    (sim_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return sim_dir


# ── Property 1 — empty / missing / unreadable sim_root ───────────────────


def test_empty_sim_root_returns_ok_zero_envelope(tmp_path: Path):
    payload = platform_status.build_status(str(tmp_path), surface_count=31)
    assert payload["ok"] is True
    assert payload["schema_version"] == "1"
    assert payload["queue_depth"] == 0
    assert payload["completed_24h"] == 0
    assert payload["last_completed_at"] is None
    assert payload["total_sims"] == 0
    assert payload["surface_count"] == 31
    assert payload["check_at"].endswith("Z")


def test_missing_sim_root_returns_ok_zero_envelope(tmp_path: Path):
    nonexistent = tmp_path / "does-not-exist"
    payload = platform_status.build_status(str(nonexistent))
    assert payload["ok"] is True
    assert payload["total_sims"] == 0


def test_blank_sim_root_returns_ok_zero_envelope():
    payload = platform_status.build_status("")
    assert payload["ok"] is True
    assert payload["total_sims"] == 0


# ── Property 2 — running sims bump queue_depth ────────────────────────────


def test_running_sims_increment_queue_depth(tmp_path: Path):
    _write_sim(tmp_path, "sim-run-1", status="running")
    _write_sim(tmp_path, "sim-run-2", status="running")
    _write_sim(tmp_path, "sim-done", status="completed")
    _write_sim(tmp_path, "sim-failed", status="failed")

    payload = platform_status.build_status(str(tmp_path))
    assert payload["queue_depth"] == 2
    # total_sims counts only public + completed sims — here just sim-done.
    assert payload["total_sims"] == 1


def test_status_match_is_case_insensitive(tmp_path: Path):
    """``state.json`` historically lower-cases status, but the service
    must tolerate mixed-case values written by older sims so the
    probe stays accurate against a heterogeneous corpus."""
    _write_sim(tmp_path, "sim-mixed", status="Running")
    _write_sim(tmp_path, "sim-upper", status="RUNNING")

    payload = platform_status.build_status(str(tmp_path))
    assert payload["queue_depth"] == 2


# ── Property 3 — completed_24h window ─────────────────────────────────────


def test_recent_completed_sims_count_toward_window(tmp_path: Path):
    now = datetime.now(tz=timezone.utc).timestamp()
    one_hour_ago = _iso(now - 3600)
    one_day_old = _iso(now - 23 * 3600)  # within window
    two_days_old = _iso(now - 48 * 3600)  # outside window

    _write_sim(
        tmp_path,
        "sim-fresh",
        status="completed",
        created_at=one_hour_ago,
        updated_at=one_hour_ago,
    )
    _write_sim(
        tmp_path,
        "sim-edge",
        status="completed",
        created_at=one_day_old,
        updated_at=one_day_old,
    )
    _write_sim(
        tmp_path,
        "sim-old",
        status="completed",
        created_at=two_days_old,
        updated_at=two_days_old,
    )

    payload = platform_status.build_status(str(tmp_path), now=now)
    assert payload["completed_24h"] == 2
    assert payload["total_sims"] == 3


def test_completed_24h_uses_updated_at_not_created_at(tmp_path: Path):
    """A sim created weeks ago but completed in the last 24 hours
    must count toward the window. ``simulation_runner`` writes the
    completion timestamp to ``updated_at``."""
    now = datetime.now(tz=timezone.utc).timestamp()
    weeks_ago = _iso(now - 14 * 24 * 3600)
    one_hour_ago = _iso(now - 3600)

    _write_sim(
        tmp_path,
        "sim-late-finish",
        status="completed",
        created_at=weeks_ago,
        updated_at=one_hour_ago,
    )

    payload = platform_status.build_status(str(tmp_path), now=now)
    assert payload["completed_24h"] == 1


def test_recent_window_constant_is_24_hours():
    """The window constant must be 24 hours in seconds so a
    Statuspage consumer's daily probe sees the right number."""
    assert platform_status.RECENT_WINDOW_SECONDS == 86400


# ── Property 4 — last_completed_at + total_sims ───────────────────────────


def test_last_completed_at_is_max_updated_at(tmp_path: Path):
    now = datetime.now(tz=timezone.utc).timestamp()
    older = _iso(now - 7200)
    newer = _iso(now - 600)

    _write_sim(
        tmp_path,
        "sim-older",
        status="completed",
        created_at=older,
        updated_at=older,
    )
    _write_sim(
        tmp_path,
        "sim-newer",
        status="completed",
        created_at=newer,
        updated_at=newer,
    )

    payload = platform_status.build_status(str(tmp_path), now=now)
    assert payload["last_completed_at"] is not None
    # last_completed_at is emitted as ``...Z``; the input ``newer``
    # has no suffix. Compare on parsed epoch instead of string equality.
    parsed = datetime.strptime(
        payload["last_completed_at"], "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)
    expected = datetime.strptime(newer, "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=timezone.utc
    )
    # Allow one second of drift since input is naive seconds.
    assert abs((parsed - expected).total_seconds()) <= 1


def test_last_completed_at_is_none_when_no_completions(tmp_path: Path):
    _write_sim(tmp_path, "sim-running", status="running")
    _write_sim(tmp_path, "sim-failed", status="failed")
    payload = platform_status.build_status(str(tmp_path))
    assert payload["last_completed_at"] is None


def test_total_sims_counts_only_public_completed(tmp_path: Path):
    """``total_sims`` counts only public + completed sims — the same
    ``is_public AND status == "completed"`` filter platform_stats uses.
    The probe is unauthenticated, so private / in-flight / failed sims
    must not leak into the cumulative count an anonymous caller reads."""
    _write_sim(tmp_path, "sim-pub", status="completed", is_public=True)
    _write_sim(tmp_path, "sim-priv", status="completed", is_public=False)
    _write_sim(tmp_path, "sim-run", status="running", is_public=True)
    _write_sim(tmp_path, "sim-failed", status="failed", is_public=True)
    _write_sim(tmp_path, "sim-priv-run", status="running", is_public=False)

    payload = platform_status.build_status(str(tmp_path))
    # Only sim-pub is both public and completed.
    assert payload["total_sims"] == 1


# ── Property 5 — surface_count is taken verbatim ─────────────────────────


def test_surface_count_is_injected_from_caller(tmp_path: Path):
    payload = platform_status.build_status(str(tmp_path), surface_count=42)
    assert payload["surface_count"] == 42


def test_surface_count_defaults_to_zero(tmp_path: Path):
    payload = platform_status.build_status(str(tmp_path))
    assert payload["surface_count"] == 0


def test_negative_surface_count_clamps_to_zero(tmp_path: Path):
    """A garbage input must still produce a well-formed envelope."""
    payload = platform_status.build_status(str(tmp_path), surface_count=-5)
    assert payload["surface_count"] == 0


# ── Property 6 — check_at format ─────────────────────────────────────────


def test_check_at_is_iso_utc_with_z_suffix(tmp_path: Path):
    payload = platform_status.build_status(str(tmp_path))
    assert isinstance(payload["check_at"], str)
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", payload["check_at"]
    ), payload["check_at"]


def test_check_at_reflects_injected_now(tmp_path: Path):
    fixed_now = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    payload = platform_status.build_status(str(tmp_path), now=fixed_now)
    assert payload["check_at"] == "2026-06-05T12:00:00Z"


# ── Property 7 — envelope is JSON-serialisable ───────────────────────────


def test_envelope_is_json_serialisable(tmp_path: Path):
    _write_sim(tmp_path, "sim-run", status="running")
    payload = platform_status.build_status(str(tmp_path), surface_count=10)
    serialised = json.dumps(payload, sort_keys=True)
    assert serialised
    roundtripped = json.loads(serialised)
    assert roundtripped["ok"] is True
    assert roundtripped["queue_depth"] == 1


# ── Property 8 — corrupt sim folders are tolerated ───────────────────────


def test_corrupt_state_json_is_skipped(tmp_path: Path):
    """A malformed ``state.json`` must not tank the whole probe."""
    sim_dir = tmp_path / "sim-corrupt"
    sim_dir.mkdir()
    (sim_dir / "state.json").write_text("not json at all", encoding="utf-8")

    _write_sim(tmp_path, "sim-ok", status="running")

    payload = platform_status.build_status(str(tmp_path))
    assert payload["ok"] is True
    # The valid sim is processed (queue_depth proves it); it's running,
    # not public+completed, so it doesn't count toward total_sims.
    assert payload["queue_depth"] == 1
    assert payload["total_sims"] == 0


def test_dotfile_directories_are_skipped(tmp_path: Path):
    """A stray ``.DS_Store`` or ``.git`` folder under the sim root
    must not be counted as a sim."""
    (tmp_path / ".DS_Store").mkdir()
    (tmp_path / ".cache").mkdir()
    _write_sim(tmp_path, "sim-ok", status="completed")

    payload = platform_status.build_status(str(tmp_path))
    assert payload["total_sims"] == 1


# ── Property 9 — wiring guards ───────────────────────────────────────────


def test_status_blueprint_is_registered_in_api_module():
    """The blueprint must be importable from ``app.api`` so the app
    factory can register it. Drift guard for ``app/api/__init__.py``."""
    from app import api  # noqa: F401

    assert hasattr(api, "status_bp"), (
        "status_bp not exported from app.api — register it in app/api/__init__.py"
    )


def test_status_blueprint_is_mounted_on_the_app():
    """Static check on the application factory rather than spinning up
    ``create_app`` — matches the posture of ``test_unit_sitemap.py``
    and ``test_unit_surfaces_catalog.py``."""
    init_path = _BACKEND / "app" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    assert "status_bp" in text, (
        "status_bp not referenced in app/__init__.py — register it in create_app"
    )
    assert "app.register_blueprint(status_bp, url_prefix='/api')" in text, (
        "status_bp must be mounted at '/api' so GET /api/status.json resolves"
    )


def test_status_route_decorator_present():
    """Drift guard for ``app/api/status.py`` — catches the failure mode
    where the blueprint is registered but its route handler was
    deleted."""
    status_path = _BACKEND / "app" / "api" / "status.py"
    text = status_path.read_text(encoding="utf-8")
    assert '@status_bp.route("/status.json"' in text, (
        "status blueprint missing @status_bp.route(\"/status.json\", ...) decorator"
    )


def test_status_route_sets_cache_control_header():
    """The route handler must set ``Cache-Control`` so external monitors
    polling at ~30s cadence don't multiply the scan cost."""
    status_path = _BACKEND / "app" / "api" / "status.py"
    text = status_path.read_text(encoding="utf-8")
    assert "public, max-age=30" in text, (
        "status route must set Cache-Control: public, max-age=30"
    )


# ── Property 10 — catalog discoverability ────────────────────────────────


def test_catalog_includes_platform_status_entry():
    """The catalog is how integrators discover platform endpoints — a
    new platform surface that's not in the catalog might as well not
    exist for machine readers."""
    keys = {entry["key"] for entry in surfaces_catalog.get_surfaces_catalog()}
    assert "platform_status" in keys


def test_catalog_entry_endpoint_matches_route():
    entry = next(
        e
        for e in surfaces_catalog.get_surfaces_catalog()
        if e["key"] == "platform_status"
    )
    assert entry["endpoint"] == "/api/status.json"
    assert entry["method"] == "GET"
    assert entry["type"] == "platform"


# ── Property 11 — OpenAPI spec coverage ──────────────────────────────────


def test_openapi_spec_includes_platform_status_endpoint():
    """The endpoint must be discoverable from the live OpenAPI document
    at ``/api/openapi.yaml`` — the same surface ``/api/docs`` consumes."""
    spec_path = _BACKEND / "openapi.yaml"
    assert spec_path.exists(), f"openapi.yaml missing at {spec_path}"
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "/api/status.json:" in spec_text, (
        "openapi.yaml missing /api/status.json path entry"
    )
    assert "PlatformStatus" in spec_text, (
        "openapi.yaml missing PlatformStatus schema reference"
    )
