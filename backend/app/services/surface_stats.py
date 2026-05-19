"""Per-share-surface request counters.

Closes the **inbound** observability gap that paired with the outbound
webhook delivery log (PR #73). Every public share surface
(``share-card.png``, ``replay.gif``, ``transcript.md`` / ``.json``,
``trajectory.csv`` / ``.jsonl``, ``thread.txt`` / ``.json``,
``/watch/<id>``, ``/api/feed.atom`` + ``feed.rss``, ``reproduce.json``,
``/lineage``) increments a counter on disk after it serves a successful
response. The counts are returned by
``GET /api/simulation/<id>/surface-stats`` so an operator running
MiroShark for a DeFi fund or research group can see which surfaces
their audience actually uses — the first operator-side feedback loop on
distribution.

Design notes
------------

* **Fire-and-forget.** Increment never raises; a corrupt counter file
  is reset to zeros, never propagated. The serve path must always
  succeed even if the analytics layer is broken.
* **Atomic.** Read-modify-write goes through a tempfile + ``os.replace``
  so two concurrent requests can't truncate the JSON to ``{`` and lose
  every prior count.
* **Bounded.** The counter file is a single small JSON object — only
  the keys in ``SURFACE_KEYS`` are persisted; an unknown key from a
  rogue caller is rejected at the API boundary, not silently written.
* **Stdlib only.** ``json`` + ``os``, plus the standard ``tempfile``
  module for the staging file. No new dependencies.

Schema::

    {
      "share_card": 0,
      "replay_gif": 0,
      "transcript_md": 0,
      "transcript_json": 0,
      "trajectory_csv": 0,
      "trajectory_jsonl": 0,
      "thread_txt": 0,
      "thread_json": 0,
      "watch_page": 0,
      "feed_atom": 0,
      "feed_rss": 0,
      "reproduce_json": 0,
      "lineage": 0,
      "notebook_ipynb": 0,
      "chart_svg": 0,
      "signal_json": 0
    }

The ``read_surface_stats`` helper returns the same dict with every key
present (zero-defaulted) plus a synthetic ``total`` key, so the frontend
doesn't have to special-case missing fields.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Dict, Optional


SURFACE_STATS_FILENAME = "surface-stats.json"


# Locked set of recognized surface keys. The route handlers + the
# unit tests both read from this set, so adding a new share surface is
# a one-line change here.
SURFACE_KEYS: frozenset[str] = frozenset(
    {
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
    }
)


def surface_stats_path(sim_dir: str) -> str:
    """Return the on-disk path to the surface-stats file for a sim.

    Pure path join — never touches the filesystem. ``sim_dir`` is
    expected to be an absolute path (the route handlers resolve it via
    ``Config.WONDERWALL_SIMULATION_DATA_DIR / simulation_id``).
    """
    return os.path.join(sim_dir or "", SURFACE_STATS_FILENAME)


def _empty_stats() -> Dict[str, int]:
    """Return a dict with every key in ``SURFACE_KEYS`` set to zero.

    The dict is fresh on every call — callers mutate the result without
    affecting subsequent reads.
    """
    return {key: 0 for key in SURFACE_KEYS}


def _load_raw(path: str) -> Dict[str, int]:
    """Read the on-disk JSON, coerce to integer counters, drop unknown
    keys, and silently reset on corrupt input.

    Returns a dict containing only keys from ``SURFACE_KEYS`` — values
    coerced to ``int`` (negative values are clamped to zero so a hand-
    edited file can't produce a negative ``total``).
    """
    if not path or not os.path.exists(path):
        return _empty_stats()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception:
        # Corrupt file — reset to zeros rather than 500ing the read.
        return _empty_stats()

    if not isinstance(raw, dict):
        return _empty_stats()

    stats = _empty_stats()
    for key in SURFACE_KEYS:
        value = raw.get(key, 0)
        try:
            ivalue = int(value)
        except (TypeError, ValueError):
            ivalue = 0
        stats[key] = max(0, ivalue)
    return stats


def _atomic_write(path: str, payload: Dict[str, int]) -> None:
    """Write ``payload`` to ``path`` atomically.

    A ``tempfile.NamedTemporaryFile`` in the same directory plus
    ``os.replace`` so the canonical file is either fully present or
    fully absent — never half-written. Same pattern the webhook log
    uses, kept local here so this module stays self-contained.
    """
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".surface-stats-", suffix=".tmp", dir=parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup of the staging file. The serve path
        # already returned a successful response by the time we get
        # here — failing to persist a counter must never crash.
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def increment_surface_stat(sim_dir: Optional[str], surface_key: str) -> None:
    """Increment the counter for ``surface_key`` in the sim's stats file.

    Fire-and-forget. Never raises. No-op when:

    * ``sim_dir`` is falsy (private sim, missing directory) — the route
      handlers already short-circuit on the publish gate, but we
      double-check here so a future caller that forgets the gate can't
      crash on a ``None`` sim_dir.
    * ``surface_key`` isn't in ``SURFACE_KEYS`` — protects the file
      schema; the bad key is silently dropped.
    * the parent directory doesn't exist and can't be created — the
      sim might have been pruned between the publish check and the
      increment; better to lose one count than to 500 a downloaded
      share card.
    """
    if not sim_dir:
        return
    if surface_key not in SURFACE_KEYS:
        return

    path = surface_stats_path(sim_dir)

    try:
        if not os.path.isdir(sim_dir):
            return
        stats = _load_raw(path)
        stats[surface_key] = max(0, int(stats.get(surface_key, 0))) + 1
        _atomic_write(path, stats)
    except Exception:
        # Any failure (permission denied, disk full, race with a sim
        # cleanup) is swallowed — the analytics layer is best-effort.
        return


def read_surface_stats(sim_dir: Optional[str]) -> Dict[str, int]:
    """Return ``{key: count, ..., total: sum}`` for the sim's stats file.

    Every key in ``SURFACE_KEYS`` is present (zero-defaulted) plus a
    synthetic ``total`` key whose value is the sum of all surface
    counts. This shape lets the frontend render the table without
    special-casing missing fields, and makes ``"Total serves: N"``
    a free read.

    Falls back to all-zeros when ``sim_dir`` is falsy or the file is
    missing / corrupt — never raises.
    """
    if not sim_dir:
        result = _empty_stats()
        result["total"] = 0
        return result

    stats = _load_raw(surface_stats_path(sim_dir))
    total = sum(stats.values())
    result = dict(stats)
    result["total"] = total
    return result
