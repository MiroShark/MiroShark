"""Unit tests for the belief trajectory CSV / JSONL export service.

Pure offline — no Flask, no network, no simulation runner, no
on-disk state outside ``tmp_path``. Cover the seven properties the
``trajectory.csv`` + ``trajectory.jsonl`` endpoints depend on:

  1. ``compute_stance_split`` uses the same ±0.2 threshold every other
     surface (gallery, share card, replay GIF, transcript, webhook,
     feed) uses — so a "bullish" pct in the CSV matches the same
     round's "bullish" pct on every other surface.
  2. ``build_rows`` produces well-formed analyst rows from the same
     on-disk artifacts the transcript / share card / replay GIF
     consume, and degrades gracefully when files are missing or
     malformed (the route handler must never 500 on the assembly step).
  3. The CSV header column order is locked — column-name-keyed
     consumers (``pandas.read_csv()`` on a notebook) break if a future
     edit reorders fields.
  4. The CSV body is RFC 4180 / ``QUOTE_MINIMAL`` so numeric columns
     stay unquoted (``pd.read_csv()`` infers dtype correctly without a
     converters argument).
  5. The JSONL form emits one JSON object per line in the same field
     order, and an empty trajectory yields zero bytes (no header, no
     spurious newline).
  6. ``participating_agents`` is computed from distinct ``viral_posts``
     posters when present, falling back to ``active_agent_count`` so
     a "no posts" round still has a sensible row.
  7. The route decorators exist in ``app/api/simulation.py`` — the
     OpenAPI drift test will validate spec ↔ route equality, but this
     guards against an accidental decorator removal that the spec test
     wouldn't catch in isolation.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def populated_sim_dir(tmp_path: Path) -> Path:
    """Sim directory with the artifacts the trajectory export reads:
    trajectory (3 snapshots, viral_posts on each) + quality.

    The belief positions are picked so each round has a distinct
    stance split that the tests can assert exactly on:
      - round 1: 1 bullish, 1 bearish, 1 neutral
      - round 2: 0 bullish, 3 bearish, 0 neutral
      - round 3: 0 bullish, 4 bearish, 0 neutral
    """
    (tmp_path / "quality.json").write_text(json.dumps({
        "health": "excellent",
        "participation_rate": 0.91,
    }), encoding="utf-8")
    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {
                "round_num": 1,
                "timestamp": "2026-04-29T10:00:00Z",
                "total_posts_created": 4,
                "total_engagements": 12,
                "active_agent_count": 3,
                "belief_positions": {
                    "1": {"topic_a": 0.0,  "topic_b": -0.1},   # neutral (avg -0.05)
                    "2": {"topic_a": -0.5, "topic_b": -0.4},   # bearish (avg -0.45)
                    "3": {"topic_a": 0.3,  "topic_b": 0.4},    # bullish (avg 0.35)
                },
                "viral_posts": [
                    {"post_id": 11, "user_id": 1, "content": "post one", "num_likes": 4, "num_dislikes": 1},
                    {"post_id": 12, "user_id": 2, "content": "post two", "num_likes": 6, "num_dislikes": 0},
                ],
            },
            {
                "round_num": 2,
                "timestamp": "2026-04-29T10:01:00Z",
                "total_posts_created": 5,
                "total_engagements": 18,
                "active_agent_count": 3,
                "belief_positions": {
                    "1": {"topic_a": -0.4, "topic_b": -0.5},   # bearish
                    "2": {"topic_a": -0.7, "topic_b": -0.6},   # bearish
                    "3": {"topic_a": -0.3, "topic_b": -0.2},   # bearish (avg -0.25)
                },
                "viral_posts": [
                    {"post_id": 21, "user_id": 3, "content": "post three", "num_likes": 9, "num_dislikes": 0},
                ],
            },
            {
                "round_num": 3,
                "timestamp": "2026-04-29T10:02:00Z",
                "total_posts_created": 3,
                "total_engagements": 22,
                "active_agent_count": 4,
                "belief_positions": {
                    "1": {"topic_a": -0.6},
                    "2": {"topic_a": -0.8},
                    "3": {"topic_a": -0.5},
                    "4": {"topic_a": -0.7},
                },
                "viral_posts": [
                    {"post_id": 31, "user_id": 4, "content": "post four", "num_likes": 11, "num_dislikes": 1},
                ],
            },
        ],
    }), encoding="utf-8")
    return tmp_path


# ── Stance threshold (property 1) ──────────────────────────────────────────


def test_stance_threshold_matches_every_other_surface():
    from app.services.trajectory_export import STANCE_THRESHOLD

    assert STANCE_THRESHOLD == 0.2


def test_compute_stance_split_buckets_at_plus_minus_threshold():
    from app.services.trajectory_export import compute_stance_split

    # Three agents, one above +0.2, one below -0.2, one at exactly 0.0.
    split = compute_stance_split({
        "1": {"t": 0.5},
        "2": {"t": -0.5},
        "3": {"t": 0.0},
    })
    # 1 bullish, 1 neutral, 1 bearish ⇒ 33.3% each.
    assert split["bullish"] == pytest.approx(33.3, abs=0.1)
    assert split["bearish"] == pytest.approx(33.3, abs=0.1)
    assert split["neutral"] == pytest.approx(33.3, abs=0.1)


def test_compute_stance_split_threshold_is_strict_inequality():
    """Exactly ±0.2 must bucket as neutral — same convention every
    other surface uses (``> 0.2`` and ``< -0.2``)."""
    from app.services.trajectory_export import compute_stance_split

    split = compute_stance_split({
        "1": {"t": 0.2},   # ≤ +threshold ⇒ neutral
        "2": {"t": -0.2},  # ≥ -threshold ⇒ neutral
    })
    assert split["bullish"] == 0.0
    assert split["bearish"] == 0.0
    assert split["neutral"] == 100.0


def test_compute_stance_split_empty_or_missing_input_yields_zeros():
    """Empty / missing input must still return a complete split — the
    CSV row needs a constant column count even on a no-data round."""
    from app.services.trajectory_export import compute_stance_split

    assert compute_stance_split({}) == {"bullish": 0.0, "neutral": 0.0, "bearish": 0.0}
    assert compute_stance_split(None) == {"bullish": 0.0, "neutral": 0.0, "bearish": 0.0}
    # Agent positions are non-numeric → drop them, return all zeros
    # rather than 500-ing.
    assert compute_stance_split({"1": {"t": "not-a-number"}}) == {
        "bullish": 0.0, "neutral": 0.0, "bearish": 0.0,
    }


# ── build_rows pipeline (property 2) ───────────────────────────────────────


def test_build_rows_full_pipeline(populated_sim_dir):
    from app.services.trajectory_export import build_rows

    rows = build_rows(str(populated_sim_dir))
    assert len(rows) == 3

    # Round 1: 1 bullish (agent 3), 1 bearish (agent 2), 1 neutral (agent 1).
    r1 = rows[0]
    assert r1["round"] == 1
    assert r1["round_timestamp"] == "2026-04-29T10:00:00Z"
    assert r1["bullish_pct"] == pytest.approx(33.3, abs=0.1)
    assert r1["bearish_pct"] == pytest.approx(33.3, abs=0.1)
    assert r1["neutral_pct"] == pytest.approx(33.3, abs=0.1)
    # 2 distinct viral_posts posters (user 1, user 2).
    assert r1["participating_agents"] == 2
    assert r1["total_posts"] == 4
    assert r1["total_engagements"] == 12
    assert r1["quality_health"] == "excellent"
    assert r1["participation_rate"] == 0.91

    # Round 2: all three agents bearish.
    r2 = rows[1]
    assert r2["bullish_pct"] == 0.0
    assert r2["bearish_pct"] == 100.0
    assert r2["neutral_pct"] == 0.0

    # Round 3: all four agents bearish (4 distinct posters? only 1 posted).
    r3 = rows[2]
    assert r3["bullish_pct"] == 0.0
    assert r3["bearish_pct"] == 100.0
    # Only user 4 posted in viral_posts ⇒ 1 participating poster.
    assert r3["participating_agents"] == 1


def test_build_rows_rounds_emit_in_chronological_order(tmp_path):
    """Snapshots written out-of-order on disk must still emit
    chronologically — analysts rely on ``df.iloc[-1]`` for the
    final-round value."""
    from app.services.trajectory_export import build_rows

    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {"round_num": 3, "belief_positions": {"1": {"t": 0.5}}, "viral_posts": []},
            {"round_num": 1, "belief_positions": {"1": {"t": 0.5}}, "viral_posts": []},
            {"round_num": 2, "belief_positions": {"1": {"t": 0.5}}, "viral_posts": []},
        ],
    }), encoding="utf-8")
    rows = build_rows(str(tmp_path))
    assert [r["round"] for r in rows] == [1, 2, 3]


def test_build_rows_missing_trajectory_returns_empty_list(tmp_path):
    """Brand-new published sim with no trajectory.json yet must return
    an empty list (the CSV will be header-only, the JSONL empty)."""
    from app.services.trajectory_export import build_rows

    assert build_rows(str(tmp_path)) == []


def test_build_rows_corrupt_trajectory_degrades_to_empty(tmp_path):
    """A truncated / corrupt trajectory.json must not raise — the
    route handler can't 500 on a bad on-disk artifact."""
    from app.services.trajectory_export import build_rows

    (tmp_path / "trajectory.json").write_text("{not valid json", encoding="utf-8")
    assert build_rows(str(tmp_path)) == []


def test_build_rows_skips_snapshots_with_unparseable_round_num(tmp_path):
    from app.services.trajectory_export import build_rows

    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            # Missing round_num ⇒ skipped.
            {"belief_positions": {"1": {"t": 0.5}}},
            # Non-numeric round_num ⇒ skipped.
            {"round_num": "round-zero", "belief_positions": {"1": {"t": 0.5}}},
            # Valid.
            {"round_num": 5, "belief_positions": {"1": {"t": 0.5}}, "viral_posts": []},
        ],
    }), encoding="utf-8")
    rows = build_rows(str(tmp_path))
    assert len(rows) == 1
    assert rows[0]["round"] == 5


def test_build_rows_handles_missing_quality_json(tmp_path):
    """quality.json is optional. Without it ``quality_health`` must be
    an empty string (CSV-friendly) and ``participation_rate`` must be
    an empty string (so the column count stays constant)."""
    from app.services.trajectory_export import build_rows

    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {"round_num": 1, "belief_positions": {"1": {"t": 0.0}}, "viral_posts": []},
        ],
    }), encoding="utf-8")
    rows = build_rows(str(tmp_path))
    assert rows[0]["quality_health"] == ""
    assert rows[0]["participation_rate"] == ""


# ── participating_agents fallback (property 6) ─────────────────────────────


def test_participating_agents_falls_back_to_active_agent_count(tmp_path):
    """When viral_posts is empty (a quiet round) we fall back to
    ``active_agent_count`` so the row still carries a meaningful
    agent count."""
    from app.services.trajectory_export import build_rows

    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {
                "round_num": 1,
                "belief_positions": {"1": {"t": 0.5}},
                "viral_posts": [],            # empty
                "active_agent_count": 12,
            },
        ],
    }), encoding="utf-8")
    rows = build_rows(str(tmp_path))
    assert rows[0]["participating_agents"] == 12


# ── CSV renderer (properties 3 + 4) ────────────────────────────────────────


def test_render_csv_header_column_order_is_locked():
    """Column-name-keyed consumers ((``df["bullish_pct"]`` etc) break
    if a future edit reorders fields. Lock the header explicitly."""
    from app.services.trajectory_export import render_csv

    payload = render_csv([])
    text = payload.decode("utf-8")
    header = text.splitlines()[0].split(",")
    assert header == [
        "round",
        "round_timestamp",
        "bullish_pct",
        "neutral_pct",
        "bearish_pct",
        "participating_agents",
        "total_posts",
        "total_engagements",
        "quality_health",
        "participation_rate",
    ]


def test_render_csv_emits_header_even_on_empty_input():
    """Empty trajectories still emit the header row so downstream
    consumers don't have to special-case zero-row files."""
    from app.services.trajectory_export import render_csv

    text = render_csv([]).decode("utf-8")
    assert text.startswith("round,round_timestamp,")
    assert text.count("\n") == 1   # one header line, no body rows


def test_render_csv_round_trips_through_python_csv_reader(populated_sim_dir):
    """The CSV emitted by ``render_csv`` must parse cleanly back through
    ``csv.DictReader`` — same path ``pandas.read_csv`` uses."""
    from app.services.trajectory_export import build_rows, render_csv

    rows = build_rows(str(populated_sim_dir))
    payload = render_csv(rows).decode("utf-8")

    reader = csv.DictReader(io.StringIO(payload))
    parsed = list(reader)
    assert len(parsed) == 3
    assert parsed[0]["round"] == "1"
    assert parsed[2]["bearish_pct"] == "100.0"
    # Numeric columns are unquoted (QUOTE_MINIMAL) — the underlying
    # field has no commas/quotes/newlines so they round-trip as
    # bare strings, which is exactly what pandas dtype inference wants.
    assert '"' not in payload.splitlines()[1]


# ── JSONL renderer (property 5) ────────────────────────────────────────────


def test_render_jsonl_one_object_per_line(populated_sim_dir):
    from app.services.trajectory_export import build_rows, render_jsonl

    rows = build_rows(str(populated_sim_dir))
    payload = render_jsonl(rows).decode("utf-8")
    lines = payload.splitlines()
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["round"] == 1
    assert parsed[2]["bearish_pct"] == 100.0
    # Field set must match the locked CSV column list — same shape on
    # both surfaces so a consumer can switch formats without rewiring.
    from app.services.trajectory_export import CSV_COLUMNS
    for row in parsed:
        assert tuple(row.keys()) == CSV_COLUMNS


def test_render_jsonl_empty_input_yields_zero_bytes():
    """JSONL has no header concept, so empty input must produce an
    empty document — not a stray newline that would parse as an empty
    object somewhere downstream."""
    from app.services.trajectory_export import render_jsonl

    assert render_jsonl([]) == b""


# ── Route decorator presence (property 7) ──────────────────────────────────


def test_simulation_routes_have_trajectory_decorators():
    """Guard against an accidental decorator removal that the OpenAPI
    drift test wouldn't catch in isolation (drift compares spec ↔
    Flask routes — both need to exist)."""
    sim_py = (_BACKEND / "app" / "api" / "simulation.py").read_text(encoding="utf-8")
    assert re.search(
        r"@simulation_bp\.route\(\s*['\"]/<simulation_id>/trajectory\.csv['\"]",
        sim_py,
    ), "trajectory.csv route decorator missing"
    assert re.search(
        r"@simulation_bp\.route\(\s*['\"]/<simulation_id>/trajectory\.jsonl['\"]",
        sim_py,
    ), "trajectory.jsonl route decorator missing"
    # Shared body presence — the wrappers should delegate to it.
    assert "_serve_trajectory" in sim_py
