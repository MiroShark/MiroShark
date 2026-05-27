"""Unit tests for the platform-level aggregate stats service + endpoints.

Pure offline — no Flask app spin-up, no Neo4j, no simulation runner.
The tests build minimal sim folders on a ``tmp_path`` and assert against
``compute_platform_stats`` directly, plus a few static guards against
the route file and the OpenAPI spec.

Covers the properties ``/api/stats`` + ``/api/stats/badge.svg`` depend on:

  1. Empty / missing sim_root → all-zero envelope, no raise.
  2. Three sims with mixed directions → correct counts + pcts.
  3. Unpublished + incomplete sims excluded from every aggregate.
  4. ``avg_confidence_pct`` rounds to 1 dp.
  5. ``unique_projects`` de-duplicates by ``project_id``.
  6. ``newest_sim_created_at`` is the lexicographic max ISO timestamp.
  7. ``total_surface_views`` sums the on-disk ``surface-stats.json``
     counters and ignores unknown keys.
  8. The 60-second module cache returns identical bytes on second
     read and is bypassed by ``force_refresh=True``.
  9. ``stats_etag`` derives from ``total_sims`` + ``newest_sim_id``.
 10. The route file declares both endpoints with the right
     ``Cache-Control`` + content-type wiring.
 11. The platform badge renderer produces a well-formed SVG with the
     platform-blue colour and the sim count in the right label.
 12. Both routes are documented in ``openapi.yaml``.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Fixture builders ──────────────────────────────────────────────────────


def _write_sim(
    root: Path,
    sim_id: str,
    *,
    is_public: bool,
    status: str,
    project_id: str = "proj-default",
    created_at: str = "2026-05-01T00:00:00",
    final_belief: tuple[float, float, float] | None = None,
    health: str | None = "excellent",
    surface_counts: dict[str, int] | None = None,
) -> Path:
    """Write a fake simulation folder under ``root`` with the minimum
    files ``compute_platform_stats`` reads."""
    sim_dir = root / sim_id
    sim_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "simulation_id": sim_id,
        "project_id": project_id,
        "graph_id": "g-dummy",
        "is_public": is_public,
        "status": status,
        "created_at": created_at,
        "updated_at": created_at,
    }
    (sim_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    if final_belief is not None:
        # Trajectory shape mirrors what _build_embed_summary_payload
        # parses: one snapshot whose belief_positions[*]['x'] averages
        # to the right per-agent stance.
        b, n, be = final_belief

        def _agent_with_stance(stance: float) -> dict:
            return {"only_axis": stance}

        # Build agent population matching the percentages exactly.
        # 100 agents so percentages map cleanly to integer counts.
        population = []
        for _ in range(int(round(b))):
            population.append(_agent_with_stance(0.5))  # > 0.2 → bullish
        for _ in range(int(round(n))):
            population.append(_agent_with_stance(0.0))  # within ±0.2 → neutral
        for _ in range(int(round(be))):
            population.append(_agent_with_stance(-0.5))  # < -0.2 → bearish

        positions = {f"agent_{i}": pos for i, pos in enumerate(population)}
        trajectory = {
            "snapshots": [
                {"round_num": 1, "belief_positions": positions},
            ]
        }
        (sim_dir / "trajectory.json").write_text(
            json.dumps(trajectory), encoding="utf-8"
        )

    if health is not None:
        (sim_dir / "quality.json").write_text(
            json.dumps({"health": health, "participation_rate": 0.9}),
            encoding="utf-8",
        )

    if surface_counts is not None:
        (sim_dir / "surface-stats.json").write_text(
            json.dumps(surface_counts), encoding="utf-8"
        )

    return sim_dir


@pytest.fixture(autouse=True)
def _clear_platform_stats_cache():
    """Drop the module-level cache before and after every test so
    fixture mutations between tests can't leak through."""
    from app.services import platform_stats

    platform_stats.invalidate_cache()
    yield
    platform_stats.invalidate_cache()


# ── Property 1 — empty / missing sim_root ─────────────────────────────────


def test_empty_sim_root_returns_all_zero_envelope(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    stats = compute_platform_stats(str(tmp_path), force_refresh=True)
    assert stats["total_sims"] == 0
    assert stats["consensus_distribution"]["bullish"] == 0
    assert stats["consensus_distribution"]["neutral"] == 0
    assert stats["consensus_distribution"]["bearish"] == 0
    assert stats["consensus_distribution"]["bullish_pct"] == 0.0
    assert stats["avg_confidence_pct"] == 0.0
    assert stats["total_surface_views"] == 0
    assert stats["unique_projects"] == 0
    assert stats["newest_sim_id"] is None
    assert stats["newest_sim_created_at"] is None
    assert stats["schema_version"] == "1"


def test_missing_sim_root_returns_all_zero_envelope(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    nonexistent = tmp_path / "does-not-exist"
    stats = compute_platform_stats(str(nonexistent), force_refresh=True)
    assert stats["total_sims"] == 0


def test_blank_sim_root_returns_all_zero_envelope():
    from app.services.platform_stats import compute_platform_stats

    stats = compute_platform_stats("", force_refresh=True)
    assert stats["total_sims"] == 0


# ── Property 2 — three sims with mixed directions ─────────────────────────


def test_mixed_directions_count_correctly(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    # Three completed, public sims — one of each stance.
    _write_sim(
        tmp_path, "sim-bull",
        is_public=True, status="completed", project_id="p-1",
        created_at="2026-05-01T00:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-neut",
        is_public=True, status="completed", project_id="p-2",
        created_at="2026-05-02T00:00:00",
        final_belief=(20.0, 60.0, 20.0),
    )
    _write_sim(
        tmp_path, "sim-bear",
        is_public=True, status="completed", project_id="p-3",
        created_at="2026-05-03T00:00:00",
        final_belief=(15.0, 15.0, 70.0),
    )

    stats = compute_platform_stats(str(tmp_path), force_refresh=True)
    assert stats["total_sims"] == 3
    dist = stats["consensus_distribution"]
    assert dist["bullish"] == 1
    assert dist["neutral"] == 1
    assert dist["bearish"] == 1
    assert dist["bullish_pct"] == pytest.approx(33.3, abs=0.1)
    assert dist["neutral_pct"] == pytest.approx(33.3, abs=0.1)
    assert dist["bearish_pct"] == pytest.approx(33.3, abs=0.1)


# ── Property 3 — unpublished + incomplete sims excluded ───────────────────


def test_unpublished_sims_are_excluded(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    _write_sim(
        tmp_path, "sim-private",
        is_public=False, status="completed", project_id="p-private",
        final_belief=(80.0, 10.0, 10.0),
    )
    _write_sim(
        tmp_path, "sim-public",
        is_public=True, status="completed", project_id="p-public",
        final_belief=(80.0, 10.0, 10.0),
    )

    stats = compute_platform_stats(str(tmp_path), force_refresh=True)
    assert stats["total_sims"] == 1
    assert stats["consensus_distribution"]["bullish"] == 1
    assert stats["unique_projects"] == 1


def test_incomplete_sims_are_excluded(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    for status in ("running", "preparing", "failed", "stopped", "created"):
        _write_sim(
            tmp_path, f"sim-{status}",
            is_public=True, status=status, project_id=f"p-{status}",
            final_belief=(80.0, 10.0, 10.0),
        )
    _write_sim(
        tmp_path, "sim-done",
        is_public=True, status="completed", project_id="p-done",
        final_belief=(80.0, 10.0, 10.0),
    )

    stats = compute_platform_stats(str(tmp_path), force_refresh=True)
    assert stats["total_sims"] == 1
    assert stats["newest_sim_id"] == "sim-done"


# ── Property 4 — avg_confidence_pct rounds to 1 dp ────────────────────────


def test_avg_confidence_rounds_to_one_decimal(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    # Two sims with confidence values that average to a non-trivial decimal.
    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed", project_id="p-a",
        final_belief=(80.0, 10.0, 10.0),  # confidence ~70%
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed", project_id="p-b",
        final_belief=(50.0, 25.0, 25.0),  # confidence ~25%
    )

    stats = compute_platform_stats(str(tmp_path), force_refresh=True)
    avg = stats["avg_confidence_pct"]
    # Re-format to 1 dp — round-trip must equal the stored value.
    assert float(f"{avg:.1f}") == avg
    assert 0.0 <= avg <= 100.0


# ── Property 5 — unique_projects de-duplicates ────────────────────────────


def test_unique_projects_de_duplicates(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    # Three sims, two share the same project_id.
    _write_sim(
        tmp_path, "sim-1",
        is_public=True, status="completed", project_id="proj-shared",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-2",
        is_public=True, status="completed", project_id="proj-shared",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-3",
        is_public=True, status="completed", project_id="proj-other",
        final_belief=(70.0, 15.0, 15.0),
    )

    stats = compute_platform_stats(str(tmp_path), force_refresh=True)
    assert stats["total_sims"] == 3
    assert stats["unique_projects"] == 2


# ── Property 6 — newest_sim_created_at is the max ISO timestamp ───────────


def test_newest_sim_is_max_iso_timestamp(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    _write_sim(
        tmp_path, "sim-older",
        is_public=True, status="completed",
        created_at="2026-04-15T12:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-newest",
        is_public=True, status="completed",
        created_at="2026-05-22T18:30:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-middle",
        is_public=True, status="completed",
        created_at="2026-05-01T09:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )

    stats = compute_platform_stats(str(tmp_path), force_refresh=True)
    assert stats["newest_sim_id"] == "sim-newest"
    assert stats["newest_sim_created_at"] == "2026-05-22T18:30:00"


# ── Property 7 — total_surface_views sums on-disk counters ────────────────


def test_total_surface_views_sums_counters(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
        surface_counts={
            "share_card": 10,
            "replay_gif": 5,
            "badge_svg": 100,
            # Unknown keys must be ignored, not added.
            "made_up_surface": 999,
        },
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
        surface_counts={
            "signal_json": 3,
            "polymarket_json": 7,
        },
    )

    stats = compute_platform_stats(str(tmp_path), force_refresh=True)
    # 10 + 5 + 100 + 3 + 7 = 125. The unknown "made_up_surface" key is
    # filtered out by the surface_stats SURFACE_KEYS schema.
    assert stats["total_surface_views"] == 125


def test_surface_views_zero_when_no_stats_file(tmp_path: Path):
    from app.services.platform_stats import compute_platform_stats

    _write_sim(
        tmp_path, "sim-no-stats",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
        # No surface-stats.json written.
    )
    stats = compute_platform_stats(str(tmp_path), force_refresh=True)
    assert stats["total_surface_views"] == 0


# ── Property 8 — 60-second cache ──────────────────────────────────────────


def test_cache_serves_stale_result_within_ttl(tmp_path: Path):
    from app.services import platform_stats

    _write_sim(
        tmp_path, "sim-one",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
    )
    first = platform_stats.compute_platform_stats(str(tmp_path), now=1000.0)
    assert first["total_sims"] == 1

    # Add a second sim, then re-call within the TTL window — the cache
    # must serve the old (1-sim) answer.
    _write_sim(
        tmp_path, "sim-two",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
    )
    cached = platform_stats.compute_platform_stats(str(tmp_path), now=1030.0)
    assert cached["total_sims"] == 1, "cache must serve the prior result within TTL"

    # Pass force_refresh=True to bypass the cache.
    fresh = platform_stats.compute_platform_stats(
        str(tmp_path), now=1030.0, force_refresh=True
    )
    assert fresh["total_sims"] == 2


def test_cache_expires_past_ttl(tmp_path: Path):
    from app.services import platform_stats

    _write_sim(
        tmp_path, "sim-one",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
    )
    first = platform_stats.compute_platform_stats(str(tmp_path), now=1000.0)
    assert first["total_sims"] == 1

    _write_sim(
        tmp_path, "sim-two",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
    )
    # Past the 60s TTL — the cache must re-scan.
    refreshed = platform_stats.compute_platform_stats(str(tmp_path), now=1100.0)
    assert refreshed["total_sims"] == 2


# ── Property 9 — stats_etag derives from total + newest_sim_id ────────────


def test_stats_etag_changes_when_total_changes():
    from app.services.platform_stats import stats_etag

    a = stats_etag({"total_sims": 1, "newest_sim_id": "sim-x"})
    b = stats_etag({"total_sims": 2, "newest_sim_id": "sim-x"})
    assert a != b


def test_stats_etag_changes_when_newest_changes():
    from app.services.platform_stats import stats_etag

    a = stats_etag({"total_sims": 5, "newest_sim_id": "sim-old"})
    b = stats_etag({"total_sims": 5, "newest_sim_id": "sim-new"})
    assert a != b


def test_stats_etag_is_quoted_string():
    from app.services.platform_stats import stats_etag

    e = stats_etag({"total_sims": 7, "newest_sim_id": "sim-x"})
    assert e.startswith('"') and e.endswith('"')


# ── Property 10 — route file wiring ───────────────────────────────────────


def test_stats_route_declarations_exist():
    """Static guard: a future refactor that removes the routes must
    fail this test before reaching the live-server suite."""
    route_file = _BACKEND / "app" / "api" / "stats.py"
    text = route_file.read_text(encoding="utf-8")
    assert "@stats_bp.route(\"\", methods=[\"GET\"])" in text or \
           "@stats_bp.route('', methods=['GET'])" in text
    assert "/badge.svg" in text
    assert "def get_platform_stats" in text
    assert "def get_platform_stats_badge" in text


def test_stats_routes_set_cache_and_content_type():
    route_file = _BACKEND / "app" / "api" / "stats.py"
    text = route_file.read_text(encoding="utf-8")
    assert "max-age=60" in text
    assert "image/svg+xml" in text
    assert "ETag" in text


def test_stats_blueprint_registered_in_app():
    """Verify the blueprint is mounted in the app factory."""
    init_file = _BACKEND / "app" / "__init__.py"
    text = init_file.read_text(encoding="utf-8")
    assert "stats_bp" in text
    assert "url_prefix='/api/stats'" in text or "url_prefix=\"/api/stats\"" in text


# ── Property 11 — platform badge renderer ─────────────────────────────────


def test_platform_badge_is_well_formed_svg():
    from app.services.badge_service import build_platform_badge_svg

    body = build_platform_badge_svg(42)
    root = ET.fromstring(body)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib.get("role") == "img"


def test_platform_badge_carries_count_in_label():
    from app.services.badge_service import build_platform_badge_svg

    body = build_platform_badge_svg(1234)
    assert "1234 simulations" in body
    # And the aria label echoes it for screen readers.
    root = ET.fromstring(body)
    aria = root.attrib.get("aria-label", "")
    assert "1234 simulations" in aria
    assert "MiroShark" in aria


def test_platform_badge_uses_platform_blue():
    from app.services.badge_service import build_platform_badge_svg, PLATFORM_COLOR

    body = build_platform_badge_svg(42)
    assert PLATFORM_COLOR in body
    # Must NOT contain a stance colour — distinct from per-sim badges.
    assert "#22c55e" not in body  # bullish green
    assert "#ef4444" not in body  # bearish red


def test_platform_badge_zero_count_still_renders():
    from app.services.badge_service import build_platform_badge_svg

    body = build_platform_badge_svg(0)
    assert "0 simulations" in body
    # Well-formed XML even on a fresh deployment.
    ET.fromstring(body)


def test_platform_badge_handles_non_numeric_count():
    from app.services.badge_service import build_platform_badge_svg

    body = build_platform_badge_svg("not-a-number")
    assert "0 simulations" in body
    ET.fromstring(body)


def test_platform_badge_handles_negative_count():
    from app.services.badge_service import build_platform_badge_svg

    body = build_platform_badge_svg(-5)
    assert "0 simulations" in body


def test_platform_badge_is_bytewise_deterministic():
    from app.services.badge_service import build_platform_badge_svg

    a = build_platform_badge_svg(42)
    b = build_platform_badge_svg(42)
    assert a == b


def test_platform_badge_bytes_includes_xml_declaration():
    from app.services.badge_service import render_platform_badge_svg_bytes

    blob = render_platform_badge_svg_bytes(42)
    assert blob.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')


# ── Property 12 — openapi.yaml documents both routes ──────────────────────


def test_stats_endpoints_documented_in_openapi():
    import yaml  # type: ignore[import-untyped]

    spec_path = _BACKEND / "openapi.yaml"
    with spec_path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    paths = set(spec.get("paths", {}).keys())
    assert "/api/stats" in paths
    assert "/api/stats/badge.svg" in paths


def test_stats_blueprint_in_openapi_test_prefixes():
    """The openapi drift test maps blueprint name → URL prefix; the new
    stats_bp must be in the table or the drift assertion will flag the
    two new routes as orphan Flask routes."""
    test_file = _BACKEND / "tests" / "test_unit_openapi.py"
    text = test_file.read_text(encoding="utf-8")
    assert "stats_bp" in text
    assert "/api/stats" in text
