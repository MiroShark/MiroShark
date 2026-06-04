"""Unit tests for the per-project aggregate stats service + endpoint.

Pure offline — no Flask app spin-up, no Neo4j, no simulation runner.
The tests build minimal sim folders on a ``tmp_path`` and assert
against ``compute_project_stats`` directly, plus a few static guards
against the route file and the OpenAPI spec.

Covers the properties ``/api/project/<project_id>/stats`` depends on:

  1. Empty / missing sim_root → all-zero envelope, no raise.
  2. Unknown project_id (no matching sims) → all-zero envelope, NOT 404.
  3. Non-matching sims are excluded (different project_id).
  4. Unpublished sims are excluded.
  5. Incomplete sims are excluded.
  6. Three sims with mixed directions → correct counts + pcts.
  7. ``quality_distribution`` buckets ``excellent / good / fair / poor``
     and ignores unrecognised health values.
  8. ``total_surface_views`` sums recognised counters; unknown keys ignored.
  9. ``newest_sim_created_at`` is the lexicographic max ISO timestamp.
 10. ``avg_confidence_pct`` rounds to 1 dp; ``0.0`` when no signal.
 11. ``published_sims`` mirrors ``total_sims`` exactly.
 12. ``schema_version`` is the v1 literal.
 13. 60-second cache returns identical result; ``force_refresh`` bypasses.
 14. Cache is per-project — invalidating one doesn't drop the other.
 15. ``stats_etag`` derives from ``total_sims`` + ``newest_sim_id``.
 16. ``is_valid_project_id`` accepts / rejects the right shapes.
 17. The route file declares the endpoint with the right wiring.
 18. The blueprint is mounted in the app factory.
 19. The endpoint is documented in ``openapi.yaml``.
 20. The openapi drift test knows about the new blueprint prefix.
"""

from __future__ import annotations

import json
import sys
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
    files ``compute_project_stats`` reads."""
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
        b, n, be = final_belief

        def _agent_with_stance(stance: float) -> dict:
            return {"only_axis": stance}

        population = []
        for _ in range(int(round(b))):
            population.append(_agent_with_stance(0.5))
        for _ in range(int(round(n))):
            population.append(_agent_with_stance(0.0))
        for _ in range(int(round(be))):
            population.append(_agent_with_stance(-0.5))

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
def _clear_project_stats_cache():
    """Drop the module-level cache before and after every test."""
    from app.services import project_stats

    project_stats.invalidate_cache()
    yield
    project_stats.invalidate_cache()


# ── Property 1 — empty / missing sim_root ─────────────────────────────────


def test_empty_sim_root_returns_all_zero_envelope(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["project_id"] == "proj-x"
    assert stats["total_sims"] == 0
    assert stats["published_sims"] == 0
    assert stats["consensus_distribution"]["bullish"] == 0
    assert stats["consensus_distribution"]["neutral"] == 0
    assert stats["consensus_distribution"]["bearish"] == 0
    assert stats["consensus_distribution"]["bullish_pct"] == 0.0
    assert stats["avg_confidence_pct"] == 0.0
    assert stats["quality_distribution"] == {
        "excellent": 0, "good": 0, "fair": 0, "poor": 0,
    }
    assert stats["total_surface_views"] == 0
    assert stats["newest_sim_id"] is None
    assert stats["newest_sim_created_at"] is None
    assert stats["schema_version"] == "1"


def test_missing_sim_root_returns_all_zero_envelope(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    nonexistent = tmp_path / "does-not-exist"
    stats = compute_project_stats(str(nonexistent), "proj-x", force_refresh=True)
    assert stats["total_sims"] == 0
    assert stats["project_id"] == "proj-x"


def test_blank_sim_root_returns_all_zero_envelope():
    from app.services.project_stats import compute_project_stats

    stats = compute_project_stats("", "proj-x", force_refresh=True)
    assert stats["total_sims"] == 0


def test_blank_project_id_returns_all_zero_envelope(tmp_path: Path):
    """Defensive default: an empty project_id never aggregates anything,
    even if sims with empty project_ids existed on disk. The route
    rejects this case with a 400 first; the service is the last line
    of defence."""
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed", project_id="",
        final_belief=(70.0, 15.0, 15.0),
    )
    stats = compute_project_stats(str(tmp_path), "", force_refresh=True)
    assert stats["total_sims"] == 0


# ── Property 2 — unknown project_id → all-zero, not 404 ──────────────────


def test_unknown_project_id_returns_zero_envelope(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed", project_id="proj-real",
        final_belief=(70.0, 15.0, 15.0),
    )

    stats = compute_project_stats(str(tmp_path), "proj-missing", force_refresh=True)
    assert stats["total_sims"] == 0
    assert stats["project_id"] == "proj-missing"


# ── Property 3 — non-matching sims excluded ──────────────────────────────


def test_non_matching_project_id_sims_excluded(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed", project_id="proj-target",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed", project_id="proj-other",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-c",
        is_public=True, status="completed", project_id="proj-target",
        final_belief=(70.0, 15.0, 15.0),
    )

    stats = compute_project_stats(str(tmp_path), "proj-target", force_refresh=True)
    assert stats["total_sims"] == 2
    assert stats["consensus_distribution"]["bullish"] == 2


def test_project_id_match_is_case_sensitive(tmp_path: Path):
    """project_id is a routing identifier — case-insensitive matching
    would let two distinct workspaces collide."""
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-lower",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-upper",
        is_public=True, status="completed", project_id="PROJ-X",
        final_belief=(70.0, 15.0, 15.0),
    )

    stats_lower = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    stats_upper = compute_project_stats(str(tmp_path), "PROJ-X", force_refresh=True)
    assert stats_lower["total_sims"] == 1
    assert stats_upper["total_sims"] == 1


# ── Property 4 — unpublished sims excluded ────────────────────────────────


def test_unpublished_sims_are_excluded(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-private",
        is_public=False, status="completed", project_id="proj-x",
        final_belief=(80.0, 10.0, 10.0),
    )
    _write_sim(
        tmp_path, "sim-public",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(80.0, 10.0, 10.0),
    )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["total_sims"] == 1


# ── Property 5 — incomplete sims excluded ────────────────────────────────


def test_incomplete_sims_are_excluded(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    for status in ("running", "preparing", "failed", "stopped", "created"):
        _write_sim(
            tmp_path, f"sim-{status}",
            is_public=True, status=status, project_id="proj-x",
            final_belief=(80.0, 10.0, 10.0),
        )
    _write_sim(
        tmp_path, "sim-done",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(80.0, 10.0, 10.0),
    )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["total_sims"] == 1
    assert stats["newest_sim_id"] == "sim-done"


# ── Property 6 — mixed directions count correctly ────────────────────────


def test_mixed_directions_count_correctly(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-bull",
        is_public=True, status="completed", project_id="proj-x",
        created_at="2026-05-01T00:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-neut",
        is_public=True, status="completed", project_id="proj-x",
        created_at="2026-05-02T00:00:00",
        final_belief=(20.0, 60.0, 20.0),
    )
    _write_sim(
        tmp_path, "sim-bear",
        is_public=True, status="completed", project_id="proj-x",
        created_at="2026-05-03T00:00:00",
        final_belief=(15.0, 15.0, 70.0),
    )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["total_sims"] == 3
    dist = stats["consensus_distribution"]
    assert dist["bullish"] == 1
    assert dist["neutral"] == 1
    assert dist["bearish"] == 1
    assert dist["bullish_pct"] == pytest.approx(33.3, abs=0.1)
    assert dist["neutral_pct"] == pytest.approx(33.3, abs=0.1)
    assert dist["bearish_pct"] == pytest.approx(33.3, abs=0.1)


# ── Property 7 — quality_distribution ────────────────────────────────────


def test_quality_distribution_buckets_correctly(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    for sim_id, health in [
        ("sim-e1", "excellent"),
        ("sim-e2", "excellent"),
        ("sim-g1", "good"),
        ("sim-f1", "fair"),
        ("sim-p1", "poor"),
    ]:
        _write_sim(
            tmp_path, sim_id,
            is_public=True, status="completed", project_id="proj-x",
            final_belief=(70.0, 15.0, 15.0),
            health=health,
        )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    qd = stats["quality_distribution"]
    assert qd == {"excellent": 2, "good": 1, "fair": 1, "poor": 1}
    assert stats["total_sims"] == 5


def test_quality_distribution_ignores_unknown_values(tmp_path: Path):
    """A sim whose quality.health is missing or unrecognised is still
    counted in total_sims but excluded from the four-bucket
    distribution — so the bucket sum can be < total_sims."""
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
        health="excellent",
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
        health="maybe-okay-ish",  # not in {excellent, good, fair, poor}
    )
    _write_sim(
        tmp_path, "sim-c",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
        health=None,  # no quality.json written
    )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["total_sims"] == 3
    qd = stats["quality_distribution"]
    assert qd == {"excellent": 1, "good": 0, "fair": 0, "poor": 0}
    assert sum(qd.values()) == 1


def test_quality_distribution_case_insensitive(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    for sim_id, health in [
        ("sim-1", "Excellent"),
        ("sim-2", "EXCELLENT"),
        ("sim-3", "  good  "),  # whitespace-padded
    ]:
        _write_sim(
            tmp_path, sim_id,
            is_public=True, status="completed", project_id="proj-x",
            final_belief=(70.0, 15.0, 15.0),
            health=health,
        )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    qd = stats["quality_distribution"]
    assert qd["excellent"] == 2
    assert qd["good"] == 1


# ── Property 8 — total_surface_views sums recognised counters ────────────


def test_total_surface_views_sums_counters(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
        surface_counts={
            "share_card": 10,
            "replay_gif": 5,
            "badge_svg": 100,
            "made_up_surface": 999,  # unknown → ignored
        },
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
        surface_counts={
            "signal_json": 3,
            "polymarket_json": 7,
        },
    )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    # 10 + 5 + 100 + 3 + 7 = 125. The unknown key is dropped.
    assert stats["total_surface_views"] == 125


def test_surface_views_zero_when_no_stats_file(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-no-stats",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
    )
    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["total_surface_views"] == 0


def test_surface_views_only_count_project_sims(tmp_path: Path):
    """Surface views from sims in other projects must NOT contribute
    to this project's total — same boundary as the count fields."""
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-in",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
        surface_counts={"share_card": 11},
    )
    _write_sim(
        tmp_path, "sim-out",
        is_public=True, status="completed", project_id="proj-y",
        final_belief=(70.0, 15.0, 15.0),
        surface_counts={"share_card": 9999},
    )
    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["total_surface_views"] == 11


# ── Property 9 — newest_sim_created_at is max ISO timestamp ──────────────


def test_newest_sim_is_max_iso_timestamp(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-older",
        is_public=True, status="completed", project_id="proj-x",
        created_at="2026-04-15T12:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-newest",
        is_public=True, status="completed", project_id="proj-x",
        created_at="2026-05-22T18:30:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-middle",
        is_public=True, status="completed", project_id="proj-x",
        created_at="2026-05-01T09:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["newest_sim_id"] == "sim-newest"
    assert stats["newest_sim_created_at"] == "2026-05-22T18:30:00"


def test_newest_sim_ignores_other_projects(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-other-newer",
        is_public=True, status="completed", project_id="proj-other",
        created_at="2026-05-30T00:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-target-older",
        is_public=True, status="completed", project_id="proj-x",
        created_at="2026-05-01T00:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["newest_sim_id"] == "sim-target-older"


# ── Property 10 — avg_confidence_pct ─────────────────────────────────────


def test_avg_confidence_rounds_to_one_decimal(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(80.0, 10.0, 10.0),
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(50.0, 25.0, 25.0),
    )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    avg = stats["avg_confidence_pct"]
    assert float(f"{avg:.1f}") == avg
    assert 0.0 <= avg <= 100.0


def test_avg_confidence_zero_when_no_signal(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["avg_confidence_pct"] == 0.0


# ── Property 11 — published_sims mirrors total_sims ──────────────────────


def test_published_sims_equals_total_sims(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    for sim_id in ("sim-1", "sim-2", "sim-3"):
        _write_sim(
            tmp_path, sim_id,
            is_public=True, status="completed", project_id="proj-x",
            final_belief=(70.0, 15.0, 15.0),
        )
    _write_sim(
        tmp_path, "sim-private",
        is_public=False, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
    )

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["total_sims"] == stats["published_sims"] == 3


# ── Property 12 — schema_version literal ─────────────────────────────────


def test_schema_version_is_literal_one(tmp_path: Path):
    from app.services.project_stats import compute_project_stats

    stats = compute_project_stats(str(tmp_path), "proj-x", force_refresh=True)
    assert stats["schema_version"] == "1"


# ── Property 13 — 60-second cache ────────────────────────────────────────


def test_cache_serves_stale_result_within_ttl(tmp_path: Path):
    from app.services import project_stats

    _write_sim(
        tmp_path, "sim-one",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
    )
    first = project_stats.compute_project_stats(str(tmp_path), "proj-x", now=1000.0)
    assert first["total_sims"] == 1

    _write_sim(
        tmp_path, "sim-two",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
    )
    cached = project_stats.compute_project_stats(str(tmp_path), "proj-x", now=1030.0)
    assert cached["total_sims"] == 1, "cache must serve the prior result within TTL"

    fresh = project_stats.compute_project_stats(
        str(tmp_path), "proj-x", now=1030.0, force_refresh=True
    )
    assert fresh["total_sims"] == 2


def test_cache_expires_past_ttl(tmp_path: Path):
    from app.services import project_stats

    _write_sim(
        tmp_path, "sim-one",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
    )
    first = project_stats.compute_project_stats(str(tmp_path), "proj-x", now=1000.0)
    assert first["total_sims"] == 1

    _write_sim(
        tmp_path, "sim-two",
        is_public=True, status="completed", project_id="proj-x",
        final_belief=(70.0, 15.0, 15.0),
    )
    refreshed = project_stats.compute_project_stats(str(tmp_path), "proj-x", now=1100.0)
    assert refreshed["total_sims"] == 2


# ── Property 14 — cache is per-project ───────────────────────────────────


def test_cache_is_per_project(tmp_path: Path):
    """Caching one project must not invalidate or pollute another."""
    from app.services import project_stats

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed", project_id="proj-a",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed", project_id="proj-b",
        final_belief=(15.0, 15.0, 70.0),
    )

    a = project_stats.compute_project_stats(str(tmp_path), "proj-a", now=1000.0)
    b = project_stats.compute_project_stats(str(tmp_path), "proj-b", now=1000.0)

    assert a["total_sims"] == 1
    assert a["consensus_distribution"]["bullish"] == 1
    assert b["total_sims"] == 1
    assert b["consensus_distribution"]["bearish"] == 1
    # Caches must not collide.
    assert a["project_id"] != b["project_id"]


def test_invalidate_cache_per_project(tmp_path: Path):
    from app.services import project_stats

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed", project_id="proj-a",
        final_belief=(70.0, 15.0, 15.0),
    )
    project_stats.compute_project_stats(str(tmp_path), "proj-a", now=1000.0)
    project_stats.compute_project_stats(str(tmp_path), "proj-b", now=1000.0)

    # Drop only proj-a; proj-b stays cached.
    project_stats.invalidate_cache(str(tmp_path), "proj-a")

    # Add a new sim — only proj-a sees it on next call (proj-b is still cached).
    _write_sim(
        tmp_path, "sim-a2",
        is_public=True, status="completed", project_id="proj-a",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-b2",
        is_public=True, status="completed", project_id="proj-b",
        final_belief=(70.0, 15.0, 15.0),
    )
    a = project_stats.compute_project_stats(str(tmp_path), "proj-a", now=1010.0)
    b = project_stats.compute_project_stats(str(tmp_path), "proj-b", now=1010.0)
    assert a["total_sims"] == 2  # fresh scan
    assert b["total_sims"] == 0  # cache still holds the empty result


# ── Property 15 — stats_etag ────────────────────────────────────────────


def test_stats_etag_changes_when_total_changes():
    from app.services.project_stats import stats_etag

    a = stats_etag({"total_sims": 1, "newest_sim_id": "sim-x"})
    b = stats_etag({"total_sims": 2, "newest_sim_id": "sim-x"})
    assert a != b


def test_stats_etag_changes_when_newest_changes():
    from app.services.project_stats import stats_etag

    a = stats_etag({"total_sims": 5, "newest_sim_id": "sim-old"})
    b = stats_etag({"total_sims": 5, "newest_sim_id": "sim-new"})
    assert a != b


def test_stats_etag_is_quoted_string():
    from app.services.project_stats import stats_etag

    e = stats_etag({"total_sims": 7, "newest_sim_id": "sim-x"})
    assert e.startswith('"') and e.endswith('"')


def test_stats_etag_distinct_from_platform_etag():
    """A consumer polling both `/api/stats` and the per-project endpoint
    must not get caches confused by identical ETags."""
    from app.services.project_stats import stats_etag as proj_etag
    from app.services.platform_stats import stats_etag as plat_etag

    p = plat_etag({"total_sims": 1, "newest_sim_id": "sim-x"})
    q = proj_etag({"total_sims": 1, "newest_sim_id": "sim-x"})
    assert p != q


# ── Property 16 — is_valid_project_id ────────────────────────────────────


def test_is_valid_project_id_accepts_common_shapes():
    from app.services.project_stats import is_valid_project_id

    for valid in [
        "proj_abc",
        "proj-research-q2",
        "ProjectX",
        "a",
        "a" * 120,
        "proj.v1.2",
        "9-digit-leading",
    ]:
        assert is_valid_project_id(valid), f"should accept {valid!r}"


def test_is_valid_project_id_rejects_invalid_shapes():
    from app.services.project_stats import is_valid_project_id

    for invalid in [
        "",
        None,
        123,
        "has space",
        "has/slash",
        "has\nnewline",
        "has\x00null",
        "a" * 121,  # too long
        "../etc/passwd",
    ]:
        assert not is_valid_project_id(invalid), f"should reject {invalid!r}"


# ── Property 17 — route file wiring ──────────────────────────────────────


def test_project_stats_route_declaration_exists():
    route_file = _BACKEND / "app" / "api" / "stats.py"
    text = route_file.read_text(encoding="utf-8")
    assert "@project_stats_bp.route(\"/<project_id>/stats\", methods=[\"GET\"])" in text \
        or "@project_stats_bp.route('/<project_id>/stats', methods=['GET'])" in text
    assert "def get_project_stats" in text


def test_project_stats_route_sets_cache_and_etag():
    route_file = _BACKEND / "app" / "api" / "stats.py"
    text = route_file.read_text(encoding="utf-8")
    assert "max-age=60" in text
    assert "ETag" in text
    assert "is_valid_project_id" in text


# ── Property 18 — blueprint registered ────────────────────────────────────


def test_project_stats_blueprint_registered_in_app():
    init_file = _BACKEND / "app" / "__init__.py"
    text = init_file.read_text(encoding="utf-8")
    assert "project_stats_bp" in text
    assert "url_prefix='/api/project'" in text or "url_prefix=\"/api/project\"" in text


def test_project_stats_blueprint_exported_from_api_package():
    init_file = _BACKEND / "app" / "api" / "__init__.py"
    text = init_file.read_text(encoding="utf-8")
    assert "project_stats_bp" in text


# ── Property 19 — openapi documents the endpoint ─────────────────────────


def test_project_stats_endpoint_documented_in_openapi():
    import yaml  # type: ignore[import-untyped]

    spec_path = _BACKEND / "openapi.yaml"
    with spec_path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    paths = set(spec.get("paths", {}).keys())
    assert "/api/project/{project_id}/stats" in paths


def test_project_stats_schema_defined_in_openapi():
    import yaml  # type: ignore[import-untyped]

    spec_path = _BACKEND / "openapi.yaml"
    with spec_path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    schemas = (spec.get("components") or {}).get("schemas") or {}
    assert "ProjectStats" in schemas
    props = schemas["ProjectStats"].get("properties") or {}
    for required in (
        "schema_version",
        "project_id",
        "total_sims",
        "published_sims",
        "consensus_distribution",
        "avg_confidence_pct",
        "quality_distribution",
        "total_surface_views",
        "newest_sim_id",
        "newest_sim_created_at",
    ):
        assert required in props, f"ProjectStats missing property {required!r}"


# ── Property 20 — openapi drift test knows the new prefix ─────────────────


def test_openapi_drift_test_maps_project_stats_blueprint():
    test_file = _BACKEND / "tests" / "test_unit_openapi.py"
    text = test_file.read_text(encoding="utf-8")
    assert "project_stats_bp" in text
    assert "/api/project" in text
