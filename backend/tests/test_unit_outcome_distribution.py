"""Unit tests for the platform-wide outcome distribution service +
endpoint.

Pure offline — no Flask app spin-up, no Neo4j, no simulation runner.
The tests build minimal sim folders on a ``tmp_path`` and assert
against ``build_distribution`` directly, plus a few static guards
against the route file, the catalog, and the OpenAPI spec.

Covers the properties ``/api/stats/distribution.json`` depends on:

  1. Empty / missing sim_root → all-zero envelope, no raise.
  2. ``total_analyzed`` counts only public + completed sims.
  3. Direction buckets follow the per-sim signal.json plurality rules.
  4. Confidence tier boundaries are inclusive on the lower edge.
  5. Quality bucket sourced from quality.json.health, case-insensitive.
  6. Quality bucket sums ``<= total_analyzed`` (unknown values dropped).
  7. Round-count buckets follow the short/medium/long thresholds.
  8. ``by_*`` pct fields sum to 100 (within rounding) when populated.
  9. ``avg_confidence_pct`` rounds to 1 dp; ``0.0`` when no signal.
 10. ``avg_total_rounds`` rounds to 1 dp; ``0.0`` when no trajectory.
 11. ``newest_completed_at`` is the lexicographic max ISO timestamp.
 12. ``schema_version`` is the v1 literal.
 13. ``generated_at`` is ISO-8601 UTC with trailing Z.
 14. JSON-serialisable end-to-end.
 15. 5-minute cache returns identical result; ``force_refresh`` bypasses.
 16. ``distribution_etag`` derives from ``total_analyzed`` + year-month.
 17. ETag is distinct from the platform stats / project stats ETags.
 18. The route file declares the endpoint with the right wiring.
 19. The catalog includes the distribution entry.
 20. The OpenAPI spec documents the endpoint and the schema.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Fixture builder ───────────────────────────────────────────────────────


def _write_sim(
    root: Path,
    sim_id: str,
    *,
    is_public: bool,
    status: str,
    created_at: str = "2026-05-01T00:00:00",
    completed_at: str | None = None,
    final_belief: tuple[float, float, float] | None = None,
    health: str | None = "excellent",
    round_count: int = 1,
) -> Path:
    """Write a fake simulation folder under ``root`` with the minimum
    files ``build_distribution`` reads.

    ``final_belief`` is the per-stance percentage triple — the helper
    builds a population whose plurality lands on the requested
    direction. ``round_count`` controls how many trajectory snapshots
    are written.
    """
    sim_dir = root / sim_id
    sim_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "simulation_id": sim_id,
        "project_id": "proj-default",
        "graph_id": "g-dummy",
        "is_public": is_public,
        "status": status,
        "created_at": created_at,
        "updated_at": completed_at or created_at,
    }
    if completed_at is not None:
        state["completed_at"] = completed_at
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
        snapshots = [
            {"round_num": i + 1, "belief_positions": positions}
            for i in range(round_count)
        ]
        (sim_dir / "trajectory.json").write_text(
            json.dumps({"snapshots": snapshots}), encoding="utf-8"
        )

    if health is not None:
        (sim_dir / "quality.json").write_text(
            json.dumps({"health": health, "participation_rate": 0.9}),
            encoding="utf-8",
        )

    return sim_dir


@pytest.fixture(autouse=True)
def _clear_distribution_cache():
    """Drop the module-level cache before and after every test."""
    from app.services import outcome_distribution

    outcome_distribution.invalidate_cache()
    yield
    outcome_distribution.invalidate_cache()


# ── Property 1 — empty / missing sim_root ─────────────────────────────────


def test_empty_sim_root_returns_all_zero_envelope(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["total_analyzed"] == 0
    assert payload["by_direction"] == {
        "bullish": 0, "neutral": 0, "bearish": 0,
        "bullish_pct": 0.0, "neutral_pct": 0.0, "bearish_pct": 0.0,
    }
    assert payload["by_confidence"] == {
        "high": 0, "medium": 0, "low": 0,
        "high_pct": 0.0, "medium_pct": 0.0, "low_pct": 0.0,
    }
    assert payload["by_quality"] == {
        "excellent": 0, "good": 0, "fair": 0, "poor": 0,
        "excellent_pct": 0.0, "good_pct": 0.0, "fair_pct": 0.0, "poor_pct": 0.0,
    }
    assert payload["by_round_count"] == {
        "short": 0, "medium": 0, "long": 0,
        "short_pct": 0.0, "medium_pct": 0.0, "long_pct": 0.0,
    }
    assert payload["avg_confidence_pct"] == 0.0
    assert payload["avg_total_rounds"] == 0.0
    assert payload["newest_completed_at"] is None
    assert payload["schema_version"] == "1"
    assert isinstance(payload["generated_at"], str)


def test_missing_sim_root_returns_all_zero_envelope(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    nonexistent = tmp_path / "does-not-exist"
    payload = build_distribution(str(nonexistent), force_refresh=True)
    assert payload["total_analyzed"] == 0


def test_blank_sim_root_returns_all_zero_envelope():
    from app.services.outcome_distribution import build_distribution

    payload = build_distribution("", force_refresh=True)
    assert payload["total_analyzed"] == 0


# ── Property 2 — publish gate (public + completed only) ──────────────────


def test_unpublished_sims_excluded(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    _write_sim(
        tmp_path, "sim-private",
        is_public=False, status="completed",
        final_belief=(80.0, 10.0, 10.0),
    )
    _write_sim(
        tmp_path, "sim-public",
        is_public=True, status="completed",
        final_belief=(80.0, 10.0, 10.0),
    )

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["total_analyzed"] == 1


def test_incomplete_sims_excluded(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    for status in ("running", "preparing", "failed", "stopped", "created"):
        _write_sim(
            tmp_path, f"sim-{status}",
            is_public=True, status=status,
            final_belief=(80.0, 10.0, 10.0),
        )
    _write_sim(
        tmp_path, "sim-done",
        is_public=True, status="completed",
        final_belief=(80.0, 10.0, 10.0),
    )

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["total_analyzed"] == 1


def test_status_match_is_case_insensitive(tmp_path: Path):
    """Older sims may have written ``Completed`` instead of ``completed``;
    the status check must normalise."""
    from app.services.outcome_distribution import build_distribution

    _write_sim(
        tmp_path, "sim-mixed-case",
        is_public=True, status="Completed",
        final_belief=(80.0, 10.0, 10.0),
    )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["total_analyzed"] == 1


# ── Property 3 — direction buckets follow plurality rules ────────────────


def test_mixed_directions_count_correctly(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    _write_sim(
        tmp_path, "sim-bull",
        is_public=True, status="completed",
        completed_at="2026-05-01T00:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-neut",
        is_public=True, status="completed",
        completed_at="2026-05-02T00:00:00",
        final_belief=(20.0, 60.0, 20.0),
    )
    _write_sim(
        tmp_path, "sim-bear",
        is_public=True, status="completed",
        completed_at="2026-05-03T00:00:00",
        final_belief=(15.0, 15.0, 70.0),
    )

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["total_analyzed"] == 3
    direction = payload["by_direction"]
    assert direction["bullish"] == 1
    assert direction["neutral"] == 1
    assert direction["bearish"] == 1
    assert direction["bullish_pct"] == pytest.approx(33.3, abs=0.1)
    assert direction["neutral_pct"] == pytest.approx(33.3, abs=0.1)
    assert direction["bearish_pct"] == pytest.approx(33.3, abs=0.1)


# ── Property 4 — confidence tier boundaries inclusive on lower edge ──────


def test_confidence_high_tier_at_seventy(tmp_path: Path):
    """A sim with confidence_pct == 70 must classify as ``high``, not
    ``medium`` — the threshold is inclusive on the lower edge."""
    from app.services.outcome_distribution import build_distribution

    # A 100/0/0 split produces confidence_pct == 100 (high)
    # A 78/22/0 split produces confidence_pct ≈ 67 (medium)
    # Test the boundary with a population that lands close to 70.
    _write_sim(
        tmp_path, "sim-high",
        is_public=True, status="completed",
        final_belief=(100.0, 0.0, 0.0),  # confidence_pct == 100
    )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["by_confidence"]["high"] == 1
    assert payload["by_confidence"]["medium"] == 0


def test_confidence_low_tier_for_close_split(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    # 40/30/30 split produces confidence_pct ≈ 10 (low)
    _write_sim(
        tmp_path, "sim-low",
        is_public=True, status="completed",
        final_belief=(40.0, 30.0, 30.0),
    )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["by_confidence"]["low"] == 1
    assert payload["by_confidence"]["medium"] == 0
    assert payload["by_confidence"]["high"] == 0


def test_confidence_medium_tier_for_solid_lead(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    # 65/20/15 split produces confidence_pct ≈ 47 (medium)
    _write_sim(
        tmp_path, "sim-medium",
        is_public=True, status="completed",
        final_belief=(65.0, 20.0, 15.0),
    )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["by_confidence"]["medium"] == 1
    assert payload["by_confidence"]["high"] == 0
    assert payload["by_confidence"]["low"] == 0


# ── Property 5 — quality buckets case-insensitive ────────────────────────


def test_quality_buckets_correctly(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    for sim_id, h in [
        ("sim-e1", "excellent"),
        ("sim-e2", "Excellent"),
        ("sim-g1", "good"),
        ("sim-f1", "fair"),
        ("sim-p1", "poor"),
    ]:
        _write_sim(
            tmp_path, sim_id,
            is_public=True, status="completed",
            final_belief=(70.0, 15.0, 15.0),
            health=h,
        )

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["by_quality"]["excellent"] == 2
    assert payload["by_quality"]["good"] == 1
    assert payload["by_quality"]["fair"] == 1
    assert payload["by_quality"]["poor"] == 1


# ── Property 6 — quality bucket sum may be < total_analyzed ──────────────


def test_quality_unknown_values_excluded_from_buckets(tmp_path: Path):
    """A sim whose quality.health is missing or unrecognised is still
    counted in total_analyzed but excluded from the four-bucket
    distribution."""
    from app.services.outcome_distribution import build_distribution

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
        health="excellent",
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
        health="maybe-okay-ish",  # unrecognised
    )
    _write_sim(
        tmp_path, "sim-c",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
        health=None,  # no quality.json
    )

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["total_analyzed"] == 3
    quality = payload["by_quality"]
    bucket_sum = quality["excellent"] + quality["good"] + quality["fair"] + quality["poor"]
    assert bucket_sum == 1
    assert bucket_sum < payload["total_analyzed"]


# ── Property 7 — round-count buckets ────────────────────────────────────


def test_round_count_buckets(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    _write_sim(
        tmp_path, "sim-short-3",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0), round_count=3,
    )
    _write_sim(
        tmp_path, "sim-short-9",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0), round_count=9,
    )
    _write_sim(
        tmp_path, "sim-medium-10",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0), round_count=10,
    )
    _write_sim(
        tmp_path, "sim-medium-20",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0), round_count=20,
    )
    _write_sim(
        tmp_path, "sim-long-21",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0), round_count=21,
    )

    payload = build_distribution(str(tmp_path), force_refresh=True)
    buckets = payload["by_round_count"]
    assert buckets["short"] == 2     # 3 + 9
    assert buckets["medium"] == 2    # 10 + 20
    assert buckets["long"] == 1      # 21


def test_round_count_missing_trajectory_skipped(tmp_path: Path):
    """A sim with no parseable trajectory is counted in total_analyzed
    but contributes to no round-count bucket."""
    from app.services.outcome_distribution import build_distribution

    sim_dir = tmp_path / "sim-no-traj"
    sim_dir.mkdir()
    (sim_dir / "state.json").write_text(
        json.dumps({
            "simulation_id": "sim-no-traj",
            "is_public": True,
            "status": "completed",
            "created_at": "2026-05-01T00:00:00",
            "updated_at": "2026-05-01T00:00:00",
        }),
        encoding="utf-8",
    )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["total_analyzed"] == 1
    rc = payload["by_round_count"]
    assert rc["short"] + rc["medium"] + rc["long"] == 0


# ── Property 8 — pct fields sum to 100 when populated ────────────────────


def test_direction_pcts_sum_to_one_hundred(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    for sim_id, belief in [
        ("sim-1", (70.0, 15.0, 15.0)),
        ("sim-2", (15.0, 70.0, 15.0)),
        ("sim-3", (15.0, 15.0, 70.0)),
        ("sim-4", (70.0, 15.0, 15.0)),
    ]:
        _write_sim(
            tmp_path, sim_id,
            is_public=True, status="completed",
            final_belief=belief,
        )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    d = payload["by_direction"]
    total_pct = d["bullish_pct"] + d["neutral_pct"] + d["bearish_pct"]
    assert total_pct == pytest.approx(100.0, abs=0.5)


# ── Property 9 — avg_confidence_pct ─────────────────────────────────────


def test_avg_confidence_rounds_to_one_decimal(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed",
        final_belief=(80.0, 10.0, 10.0),
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed",
        final_belief=(50.0, 25.0, 25.0),
    )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    avg = payload["avg_confidence_pct"]
    assert float(f"{avg:.1f}") == avg
    assert 0.0 <= avg <= 100.0


def test_avg_confidence_zero_when_no_signal(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["avg_confidence_pct"] == 0.0


# ── Property 10 — avg_total_rounds ──────────────────────────────────────


def test_avg_total_rounds_rounds_to_one_decimal(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0), round_count=10,
    )
    _write_sim(
        tmp_path, "sim-b",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0), round_count=15,
    )
    _write_sim(
        tmp_path, "sim-c",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0), round_count=12,
    )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    # (10 + 15 + 12) / 3 = 12.333... → 12.3
    assert payload["avg_total_rounds"] == pytest.approx(12.3, abs=0.05)


def test_avg_total_rounds_zero_when_no_trajectory(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["avg_total_rounds"] == 0.0


# ── Property 11 — newest_completed_at is lexicographic max ──────────────


def test_newest_completed_at_is_max(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    _write_sim(
        tmp_path, "sim-old",
        is_public=True, status="completed",
        completed_at="2026-03-15T12:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-newest",
        is_public=True, status="completed",
        completed_at="2026-06-07T18:30:00",
        final_belief=(70.0, 15.0, 15.0),
    )
    _write_sim(
        tmp_path, "sim-middle",
        is_public=True, status="completed",
        completed_at="2026-04-22T09:00:00",
        final_belief=(70.0, 15.0, 15.0),
    )

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["newest_completed_at"] == "2026-06-07T18:30:00"


def test_newest_falls_back_to_updated_at(tmp_path: Path):
    """Older sims may have no ``completed_at`` field; fall back to
    ``updated_at`` so the field is non-null on legacy data."""
    from app.services.outcome_distribution import build_distribution

    # _write_sim only writes completed_at when explicitly passed —
    # so calling with completed_at=None leaves only updated_at set
    # (and updated_at defaults to created_at).
    _write_sim(
        tmp_path, "sim-legacy",
        is_public=True, status="completed",
        created_at="2026-05-15T10:00:00",
        completed_at=None,
        final_belief=(70.0, 15.0, 15.0),
    )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["newest_completed_at"] == "2026-05-15T10:00:00"


# ── Property 12 — schema_version literal ────────────────────────────────


def test_schema_version_is_one(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    payload = build_distribution(str(tmp_path), force_refresh=True)
    assert payload["schema_version"] == "1"


# ── Property 13 — generated_at is ISO UTC ───────────────────────────────


def test_generated_at_is_iso_utc(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    payload = build_distribution(str(tmp_path), force_refresh=True)
    ga = payload["generated_at"]
    assert isinstance(ga, str)
    assert ga.endswith("Z")
    # YYYY-MM-DDTHH:MM:SSZ — 20 chars exactly
    assert len(ga) == 20


# ── Property 14 — JSON serialisable end-to-end ──────────────────────────


def test_envelope_is_json_serialisable(tmp_path: Path):
    from app.services.outcome_distribution import build_distribution

    _write_sim(
        tmp_path, "sim-a",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
        round_count=5,
    )
    payload = build_distribution(str(tmp_path), force_refresh=True)
    serialised = json.dumps(payload)
    reloaded = json.loads(serialised)
    assert reloaded == payload


# ── Property 15 — 5-minute cache ────────────────────────────────────────


def test_cache_serves_stale_result_within_ttl(tmp_path: Path):
    from app.services import outcome_distribution

    _write_sim(
        tmp_path, "sim-one",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
    )
    first = outcome_distribution.build_distribution(str(tmp_path), now=1000.0)
    assert first["total_analyzed"] == 1

    _write_sim(
        tmp_path, "sim-two",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
    )
    cached = outcome_distribution.build_distribution(str(tmp_path), now=1100.0)
    assert cached["total_analyzed"] == 1, "cache must serve prior result within TTL"

    fresh = outcome_distribution.build_distribution(
        str(tmp_path), now=1100.0, force_refresh=True,
    )
    assert fresh["total_analyzed"] == 2


def test_cache_expires_past_ttl(tmp_path: Path):
    from app.services import outcome_distribution

    _write_sim(
        tmp_path, "sim-one",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
    )
    first = outcome_distribution.build_distribution(str(tmp_path), now=1000.0)
    assert first["total_analyzed"] == 1

    _write_sim(
        tmp_path, "sim-two",
        is_public=True, status="completed",
        final_belief=(70.0, 15.0, 15.0),
    )
    refreshed = outcome_distribution.build_distribution(str(tmp_path), now=1400.0)
    assert refreshed["total_analyzed"] == 2


# ── Property 16 — distribution_etag derives from total + month ──────────


def test_etag_changes_when_total_changes():
    from app.services.outcome_distribution import distribution_etag

    a = distribution_etag({"total_analyzed": 5, "newest_completed_at": "2026-05-01T00:00:00"})
    b = distribution_etag({"total_analyzed": 6, "newest_completed_at": "2026-05-01T00:00:00"})
    assert a != b


def test_etag_changes_when_month_changes():
    from app.services.outcome_distribution import distribution_etag

    a = distribution_etag({"total_analyzed": 5, "newest_completed_at": "2026-05-01T00:00:00"})
    b = distribution_etag({"total_analyzed": 5, "newest_completed_at": "2026-06-01T00:00:00"})
    assert a != b


def test_etag_stable_within_month_and_total():
    from app.services.outcome_distribution import distribution_etag

    a = distribution_etag({"total_analyzed": 5, "newest_completed_at": "2026-05-01T00:00:00"})
    b = distribution_etag({"total_analyzed": 5, "newest_completed_at": "2026-05-30T23:59:59"})
    assert a == b


def test_etag_is_quoted_string():
    from app.services.outcome_distribution import distribution_etag

    e = distribution_etag({"total_analyzed": 7, "newest_completed_at": "2026-05-01T00:00:00"})
    assert e.startswith('"') and e.endswith('"')


# ── Property 17 — ETag distinct from sibling surfaces ───────────────────


def test_distribution_etag_distinct_from_platform_and_project():
    """A polling consumer hitting `/api/stats`, `/api/project/.../stats`,
    and `/api/stats/distribution.json` must not confuse caches across
    the three surfaces via identical ETags."""
    from app.services.outcome_distribution import distribution_etag
    from app.services.platform_stats import stats_etag as plat_etag
    from app.services.project_stats import stats_etag as proj_etag

    payload = {"total_sims": 1, "total_analyzed": 1, "newest_sim_id": "sim-x",
               "newest_completed_at": "2026-05-01T00:00:00"}
    d = distribution_etag(payload)
    p = plat_etag(payload)
    q = proj_etag(payload)
    assert d != p
    assert d != q


# ── Property 18 — route file wiring ─────────────────────────────────────


def test_distribution_route_declaration_exists():
    route_file = _BACKEND / "app" / "api" / "stats.py"
    text = route_file.read_text(encoding="utf-8")
    assert "@stats_bp.route(\"/distribution.json\", methods=[\"GET\"])" in text \
        or "@stats_bp.route('/distribution.json', methods=['GET'])" in text
    assert "def get_outcome_distribution" in text


def test_distribution_route_sets_cache_and_etag():
    route_file = _BACKEND / "app" / "api" / "stats.py"
    text = route_file.read_text(encoding="utf-8")
    assert "max-age=300" in text
    assert "distribution_etag" in text


# ── Property 19 — catalog includes the entry ────────────────────────────


def test_distribution_in_surfaces_catalog():
    from app.services.surfaces_catalog import get_surfaces_catalog

    keys = {entry["key"] for entry in get_surfaces_catalog()}
    assert "outcome_distribution" in keys


def test_distribution_catalog_entry_shape():
    from app.services.surfaces_catalog import get_surfaces_catalog

    entry = next(
        e for e in get_surfaces_catalog() if e["key"] == "outcome_distribution"
    )
    assert entry["endpoint"] == "/api/stats/distribution.json"
    assert entry["method"] == "GET"
    assert entry["type"] == "analytics"
    assert isinstance(entry["description"], str) and entry["description"]
    assert len(entry["description"]) <= 120
    assert isinstance(entry["added_in_pr"], int) and entry["added_in_pr"] > 0
    assert "curl" in entry["example_curl"]
    assert "/api/stats/distribution.json" in entry["example_curl"]


# ── Property 20 — openapi documents endpoint + schema ───────────────────


def test_distribution_endpoint_documented_in_openapi():
    import yaml  # type: ignore[import-untyped]

    spec_path = _BACKEND / "openapi.yaml"
    with spec_path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    paths = set(spec.get("paths", {}).keys())
    assert "/api/stats/distribution.json" in paths


def test_distribution_schema_defined_in_openapi():
    import yaml  # type: ignore[import-untyped]

    spec_path = _BACKEND / "openapi.yaml"
    with spec_path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    schemas = (spec.get("components") or {}).get("schemas") or {}
    assert "OutcomeDistribution" in schemas
    props = schemas["OutcomeDistribution"].get("properties") or {}
    for required in (
        "schema_version",
        "generated_at",
        "total_analyzed",
        "by_direction",
        "by_confidence",
        "by_quality",
        "by_round_count",
        "avg_confidence_pct",
        "avg_total_rounds",
        "newest_completed_at",
    ):
        assert required in props, f"OutcomeDistribution missing property {required!r}"


# ── Extra — frontend helper guard ───────────────────────────────────────


def test_frontend_helper_exported():
    """The SPA bundle uses ``getOutcomeDistribution`` — guard against
    accidental deletion."""
    fe_file = _BACKEND.parent / "frontend" / "src" / "api" / "simulation.js"
    if not fe_file.exists():
        pytest.skip("frontend bundle not present in this checkout")
    text = fe_file.read_text(encoding="utf-8")
    assert "getOutcomeDistributionUrl" in text
    assert "getOutcomeDistribution" in text
    assert "/api/stats/distribution.json" in text
