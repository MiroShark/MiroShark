"""Unit tests for the per-share-surface usage counter service.

Pure offline — no Flask, no network, no simulation runner, no on-disk
state outside ``tmp_path``. Cover the properties the
``GET /api/simulation/<id>/surface-stats`` endpoint and every
``_serve_X`` handler depend on:

  1. Increment from a fresh sim_dir creates the file with a single
     counter at 1.
  2. Repeated increments climb monotonically.
  3. ``read_surface_stats`` zero-defaults every key in ``SURFACE_KEYS``
     and exposes a synthetic ``total``.
  4. The atomic write contract — staging file + ``os.replace`` — keeps
     the on-disk file from ever being half-written.
  5. Unknown surface keys are silently dropped at increment time so a
     rogue caller can't pollute the schema.
  6. A falsy ``sim_dir`` is a graceful no-op (private sim, missing
     directory) — never raises.
  7. A corrupt JSON file is silently reset to zeros rather than 500ing
     the read.
  8. Negative on-disk values are clamped to zero (defense-in-depth
     against a hand-edited file producing a negative ``total``).
  9. Two same-process increments to the same key produce a +2 net
     change — the read-modify-write gates against losing a count under
     normal serial load.
 10. The route decorator for ``GET /<id>/surface-stats`` is registered
     in ``app/api/simulation.py`` so the OpenAPI drift test passes.
 11. Each ``_serve_X`` handler in ``app/api/simulation.py`` is wired
     to the matching surface key — increment line presence guard.
 12. ``increment_surface_stat`` is fire-and-forget — never raises even
     when ``os.replace`` fails partway through (we patch it to throw).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Iterable
from unittest import mock

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# Late import — keeps the suite collectable even if a future refactor
# moves the module, the failure surfaces as a single import error
# rather than an opaque NameError everywhere.
from app.services import surface_stats  # noqa: E402


# ── Module-level invariants ────────────────────────────────────────────


def test_surface_keys_includes_every_serve_handler():
    """The locked set of keys must cover every share surface that has a
    ``_serve_X`` handler today. New surfaces must be added here AND in
    the matching handler — failing this test means the analytics layer
    silently drops a counter."""
    expected = {
        "share_card",
        "replay_gif",
        "transcript_md",
        "transcript_json",
        "trajectory_csv",
        "trajectory_jsonl",
        "thread_txt",
        "thread_json",
        "watch_page",
        "feed_atom",
        "feed_rss",
        "reproduce_json",
        "lineage",
        "notebook_ipynb",
        "chart_svg",
        "signal_json",
        "archive_zip",
        "badge_svg",
        "cite_bib",
        "polymarket_json",
        "oembed",
        "peak_round",
        "agent_sparklines",
        "volatility",
        "clone_json",
        "agents_json",
        "signed_result",
    }
    assert set(surface_stats.SURFACE_KEYS) == expected


def test_surface_stats_path_is_pure_join(tmp_path: Path):
    """Pure path join — must not touch the filesystem."""
    path = surface_stats.surface_stats_path(str(tmp_path))
    assert path == str(tmp_path / "surface-stats.json")
    # And the file does NOT exist after a path lookup.
    assert not os.path.exists(path)


# ── Increment + read happy path ───────────────────────────────────────


def test_increment_creates_file_at_one(tmp_path: Path):
    surface_stats.increment_surface_stat(str(tmp_path), "share_card")

    on_disk = json.loads(
        (tmp_path / "surface-stats.json").read_text(encoding="utf-8")
    )
    # Only the incremented key needs to be present on disk; missing
    # keys are zero-defaulted on read. (We don't assert exact dict
    # equality here so adding a new SURFACE_KEY in the future doesn't
    # break this test.)
    assert on_disk["share_card"] == 1


def test_repeated_increments_climb_monotonically(tmp_path: Path):
    for _ in range(7):
        surface_stats.increment_surface_stat(str(tmp_path), "replay_gif")

    stats = surface_stats.read_surface_stats(str(tmp_path))
    assert stats["replay_gif"] == 7
    # Other keys remain zero.
    assert stats["share_card"] == 0
    assert stats["transcript_md"] == 0
    # Total reflects only the actually-incremented surface.
    assert stats["total"] == 7


def test_read_zero_defaults_every_key_and_total(tmp_path: Path):
    """A sim_dir with no stats file produces a fully-zeroed dict so the
    frontend never has to special-case a missing field."""
    stats = surface_stats.read_surface_stats(str(tmp_path))

    for key in surface_stats.SURFACE_KEYS:
        assert stats[key] == 0, f"key {key!r} should default to zero"
    assert stats["total"] == 0
    # Every documented frontend key must be present.
    assert set(stats.keys()) >= set(surface_stats.SURFACE_KEYS) | {"total"}


def test_increment_preserves_other_surfaces(tmp_path: Path):
    """A new increment to one key must not zero out another key — the
    on-disk file is read, mutated in place, then re-written."""
    surface_stats.increment_surface_stat(str(tmp_path), "transcript_md")
    surface_stats.increment_surface_stat(str(tmp_path), "transcript_md")
    surface_stats.increment_surface_stat(str(tmp_path), "trajectory_csv")
    surface_stats.increment_surface_stat(str(tmp_path), "feed_rss")

    stats = surface_stats.read_surface_stats(str(tmp_path))
    assert stats["transcript_md"] == 2
    assert stats["trajectory_csv"] == 1
    assert stats["feed_rss"] == 1
    assert stats["total"] == 4


# ── Edge cases / failure modes ────────────────────────────────────────


def test_unknown_surface_key_is_silently_dropped(tmp_path: Path):
    """Defense-in-depth on the schema: a rogue caller passing a key not
    in ``SURFACE_KEYS`` must not write that key to disk."""
    surface_stats.increment_surface_stat(str(tmp_path), "totally_made_up")

    # No file written — the increment short-circuited.
    assert not os.path.exists(tmp_path / "surface-stats.json")
    stats = surface_stats.read_surface_stats(str(tmp_path))
    assert "totally_made_up" not in stats
    assert stats["total"] == 0


def test_falsy_sim_dir_is_a_no_op():
    """Private sim / missing dir / None — must never raise. This is the
    posture every ``_serve_X`` handler relies on so a peripheral failure
    can't 500 a successful share-card serve."""
    surface_stats.increment_surface_stat(None, "share_card")
    surface_stats.increment_surface_stat("", "share_card")

    stats = surface_stats.read_surface_stats(None)
    assert stats["total"] == 0
    for key in surface_stats.SURFACE_KEYS:
        assert stats[key] == 0


def test_corrupt_json_file_resets_to_zeros(tmp_path: Path):
    """A half-written / hand-edited / truncated stats file must read as
    zeros rather than 500ing the GET endpoint."""
    (tmp_path / "surface-stats.json").write_text(
        '{"share_card": 12, "replay_gif"',  # truncated mid-key
        encoding="utf-8",
    )

    stats = surface_stats.read_surface_stats(str(tmp_path))
    assert stats["share_card"] == 0
    assert stats["total"] == 0

    # And a subsequent increment must succeed — the corrupt file is
    # rewritten with a clean schema.
    surface_stats.increment_surface_stat(str(tmp_path), "share_card")
    stats = surface_stats.read_surface_stats(str(tmp_path))
    assert stats["share_card"] == 1


def test_negative_on_disk_values_clamped_to_zero(tmp_path: Path):
    """A hand-edited file with a negative count would otherwise produce
    a negative ``total`` — clamp at read time and on the next write."""
    (tmp_path / "surface-stats.json").write_text(
        json.dumps({"share_card": -5, "replay_gif": 3}),
        encoding="utf-8",
    )

    stats = surface_stats.read_surface_stats(str(tmp_path))
    assert stats["share_card"] == 0
    assert stats["replay_gif"] == 3
    assert stats["total"] == 3


def test_atomic_write_uses_os_replace(tmp_path: Path):
    """The write path must go through ``os.replace`` so a concurrent
    reader either sees the old file or the new one — never a partial
    write. We patch ``os.replace`` and assert it was invoked."""
    with mock.patch.object(
        surface_stats.os, "replace", wraps=surface_stats.os.replace
    ) as replace_spy:
        surface_stats.increment_surface_stat(str(tmp_path), "watch_page")

    assert replace_spy.called, "increment must use os.replace, not a naive open()"
    # Final state still ends up correct.
    stats = surface_stats.read_surface_stats(str(tmp_path))
    assert stats["watch_page"] == 1


def test_increment_swallows_replace_failure(tmp_path: Path):
    """A filesystem error during ``os.replace`` (read-only mount, full
    disk, antivirus lock) must never bubble out — the analytics layer
    is best-effort. The serve path that called us already returned a
    successful response."""
    with mock.patch.object(
        surface_stats.os, "replace", side_effect=OSError("disk full")
    ):
        # Must not raise.
        surface_stats.increment_surface_stat(str(tmp_path), "thread_txt")

    # No partial file left behind, no count persisted.
    assert not os.path.exists(tmp_path / "surface-stats.json")


# ── Route + handler wiring guards ─────────────────────────────────────


def _read_simulation_api() -> str:
    return (_BACKEND / "app" / "api" / "simulation.py").read_text(
        encoding="utf-8"
    )


def test_surface_stats_route_decorator_registered():
    """The ``GET /<id>/surface-stats`` route must exist in
    simulation.py — the OpenAPI drift test will surface a missing path
    on the spec side, but the decorator scan here catches an
    accidental decorator removal that wouldn't show up on the spec
    test in isolation."""
    text = _read_simulation_api()
    assert (
        "@simulation_bp.route('/<simulation_id>/surface-stats', methods=['GET'])"
        in text
    ), "GET /<id>/surface-stats route decorator missing from simulation.py"
    assert "def get_surface_stats" in text, (
        "get_surface_stats handler function missing from simulation.py"
    )


@pytest.mark.parametrize(
    "surface_key",
    [
        "share_card",
        "replay_gif",
        "transcript_md",
        "transcript_json",
        "trajectory_csv",
        "trajectory_jsonl",
        "thread_txt",
        "thread_json",
        "reproduce_json",
        "lineage",
        "notebook_ipynb",
        "chart_svg",
        "signal_json",
        "archive_zip",
        "peak_round",
    ],
)
def test_serve_handlers_increment_their_surface_key(surface_key: str):
    """Every share-surface handler must increment its matching counter.
    Static guard against an accidental removal of the increment line —
    the handler itself stays green if the increment is missing, but
    the analytics layer goes silent for that surface."""
    text = _read_simulation_api()
    needle = f'"{surface_key}"'
    assert needle in text, (
        f"surface key {surface_key!r} not referenced in simulation.py — "
        f"the matching _serve_X handler must call "
        f"surface_stats.increment_surface_stat(..., {needle})"
    )


def test_watch_handler_increments_watch_page():
    text = (_BACKEND / "app" / "api" / "watch.py").read_text(encoding="utf-8")
    assert '"watch_page"' in text, (
        "watch.py must increment the watch_page counter via "
        "surface_stats.increment_surface_stat(..., \"watch_page\")"
    )
    assert "surface_stats.increment_surface_stat" in text


def test_feed_handler_increments_per_card():
    text = (_BACKEND / "app" / "api" / "feed.py").read_text(encoding="utf-8")
    assert "surface_stats.increment_surface_stat" in text, (
        "feed.py must increment a feed counter for every sim that "
        "appears in a served feed render"
    )
    # Both Atom and RSS surface keys must be referenced.
    assert '"feed_atom"' in text
    assert '"feed_rss"' in text


def test_openapi_spec_documents_surface_stats_path():
    """End-to-end paranoia: the YAML spec must list the new path so
    the drift test passes. Independent from the regex scan above."""
    spec_text = (_BACKEND / "openapi.yaml").read_text(encoding="utf-8")
    assert "/api/simulation/{simulation_id}/surface-stats:" in spec_text, (
        "openapi.yaml is missing the /surface-stats path entry"
    )
    assert "SimulationSurfaceStats:" in spec_text, (
        "openapi.yaml is missing the SimulationSurfaceStats schema"
    )


# ── Composite integration-style guard ─────────────────────────────────


def test_full_distribution_table_round_trips(tmp_path: Path):
    """A realistic operator session: PNG served 4×, replay GIF 2×,
    transcript Markdown 1×, trajectory CSV 3×, watch page 1×. The
    response shape is exactly what the EmbedDialog Distribution panel
    consumes — column order doesn't matter, but every key must be
    present."""
    plan: Iterable[tuple[str, int]] = [
        ("share_card", 4),
        ("replay_gif", 2),
        ("transcript_md", 1),
        ("trajectory_csv", 3),
        ("watch_page", 1),
    ]
    for key, n in plan:
        for _ in range(n):
            surface_stats.increment_surface_stat(str(tmp_path), key)

    stats = surface_stats.read_surface_stats(str(tmp_path))
    assert stats["share_card"] == 4
    assert stats["replay_gif"] == 2
    assert stats["transcript_md"] == 1
    assert stats["trajectory_csv"] == 3
    assert stats["watch_page"] == 1
    assert stats["total"] == 4 + 2 + 1 + 3 + 1
    # Untouched surfaces are zero, not absent.
    assert stats["thread_txt"] == 0
    assert stats["feed_atom"] == 0
