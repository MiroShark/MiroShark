"""Machine-readable catalog of every share / platform surface this
deployment exposes.

Every prior share surface ships a single per-simulation payload, image,
or document. Every prior platform surface (``/api/stats``,
``/api/stats/badge.svg``) ships an aggregate. None of them answer the
meta-question an integrator hits on day one: *"what's available on this
deployment?"* — the question that today gets answered by reading
``docs/FEATURES.md`` or grepping the routes.

This module collapses that catalog into a single endpoint payload:
every surface key, the HTTP route it lives at, the method, the type
category, a one-line description, the PR that introduced it, and a
copy-pasteable ``curl`` example. The new ``GET /api/surfaces.json``
endpoint reads from here; integrators query the catalog once on
startup to discover the deployment's capabilities without parsing
docs.

Design notes
------------

* **Static / hardcoded.** The catalog is a literal list at module
  scope; not auto-derived from ``SURFACE_KEYS`` (which only tracks the
  publish-gated per-sim surfaces with serve counters) and not scanned
  off the Flask URL map (which would include private mutation routes
  the catalog must not expose). A new surface ships in three files:
  the route handler, ``SURFACE_KEYS`` if it's per-sim and publish-gated,
  and this catalog. The drift test in
  ``test_unit_surfaces_catalog.py`` guards that the per-sim subset of
  this catalog stays in sync with ``SURFACE_KEYS``.

* **Stable schema.** The catalog is a list of dicts with a locked
  field set — ``key`` (snake_case, matches the ``SURFACE_KEYS`` value
  where applicable), ``endpoint`` (with ``<simulation_id>`` placeholder
  for per-sim surfaces), ``method`` (``GET`` or ``POST``), ``type``
  (one of seven category strings), ``description`` (≤120 chars),
  ``added_in_pr`` (PR number or ``null`` for pre-instrumentation
  surfaces), ``example_curl`` (a single-line ``curl`` invocation
  using ``https://your-host`` and ``<simulation_id>`` placeholders).
  Schema versioned via the response envelope's ``schema_version``.

* **Stdlib only.** ``json`` only when callers want to serialise the
  ETag; the catalog itself is a pure Python list. Zero new
  dependencies — same posture as ``surface_stats``, ``signal_service``,
  ``badge_service``, every other pure-data module in this tree.

* **No PII / no secrets.** The catalog is public by definition; every
  surface listed is itself publicly reachable. No URL contains a
  configured host name or admin token — the ``your-host`` placeholder
  in ``example_curl`` is literal so a caller never accidentally
  copy-pastes an internal URL.
"""

from __future__ import annotations

from typing import Any, Dict, List


# Schema version literal — bump on breaking changes to the entry
# field set. v1 is the only published version.
SCHEMA_VERSION = "1"


# ── Type categories ─────────────────────────────────────────────────────
#
# Seven categories cover every current surface. A consumer can filter
# the catalog by type to scope what they care about ("just give me the
# analytics surfaces"). Adding a category is a non-breaking change.


SURFACE_TYPES: frozenset[str] = frozenset(
    {
        "analytics",
        "visualization",
        "export",
        "embed",
        "integration",
        "platform",
        "discovery",
    }
)


# ── The catalog ────────────────────────────────────────────────────────
#
# Order is rough chronology — earliest surfaces first, with the
# platform-level + meta entries grouped at the end. Order is part of
# the published contract: a consumer iterating in catalog order sees
# the surface evolution from earliest (``signal.json``, share card) to
# latest (this self-referential entry). Adding a new entry appends to
# the end; reordering existing entries is a breaking change.


_CATALOG: List[Dict[str, Any]] = [
    # ── Per-simulation share surfaces ───────────────────────────────
    {
        "key": "signal_json",
        "endpoint": "/api/simulation/<simulation_id>/signal.json",
        "method": "GET",
        "type": "analytics",
        "description": "Direction + confidence + quality_health JSON — the trading-signal core payload.",
        "added_in_pr": 60,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/signal.json'",
    },
    {
        "key": "share_card",
        "endpoint": "/api/simulation/<simulation_id>/share-card.png",
        "method": "GET",
        "type": "visualization",
        "description": "1200x630 OG share card PNG with stance, scenario, and confidence.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/share-card.png' -o share.png",
    },
    {
        "key": "replay_gif",
        "endpoint": "/api/simulation/<simulation_id>/replay.gif",
        "method": "GET",
        "type": "visualization",
        "description": "Animated GIF of the per-round belief curve evolution.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/replay.gif' -o replay.gif",
    },
    {
        "key": "transcript_md",
        "endpoint": "/api/simulation/<simulation_id>/transcript.md",
        "method": "GET",
        "type": "export",
        "description": "Markdown transcript of every round's posts and engagements.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/transcript.md'",
    },
    {
        "key": "transcript_json",
        "endpoint": "/api/simulation/<simulation_id>/transcript.json",
        "method": "GET",
        "type": "export",
        "description": "Structured JSON transcript — every round, post, agent state.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/transcript.json'",
    },
    {
        "key": "trajectory_csv",
        "endpoint": "/api/simulation/<simulation_id>/trajectory.csv",
        "method": "GET",
        "type": "export",
        "description": "Per-round belief percentages and quality metrics as CSV (locked column order).",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/trajectory.csv' -o trajectory.csv",
    },
    {
        "key": "trajectory_jsonl",
        "endpoint": "/api/simulation/<simulation_id>/trajectory.jsonl",
        "method": "GET",
        "type": "export",
        "description": "Per-round belief percentages and quality metrics as JSONL — one round per line.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/trajectory.jsonl'",
    },
    {
        "key": "thread_txt",
        "endpoint": "/api/simulation/<simulation_id>/thread.txt",
        "method": "GET",
        "type": "export",
        "description": "Plain-text X/Twitter thread (5 tweets, <=280 chars each) summarising the run.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/thread.txt'",
    },
    {
        "key": "thread_json",
        "endpoint": "/api/simulation/<simulation_id>/thread.json",
        "method": "GET",
        "type": "export",
        "description": "Same thread as thread.txt in structured JSON (per-tweet char counts + body).",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/thread.json'",
    },
    {
        "key": "watch_page",
        "endpoint": "/watch/<simulation_id>",
        "method": "GET",
        "type": "embed",
        "description": "Spectator-watch broadcast HTML page — polls every 15s, OG+Twitter unfurl.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/watch/<simulation_id>'",
    },
    {
        "key": "feed_atom",
        "endpoint": "/api/feed.atom",
        "method": "GET",
        "type": "discovery",
        "description": "Atom 1.0 syndication feed of the public-simulation gallery.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/feed.atom'",
    },
    {
        "key": "feed_rss",
        "endpoint": "/api/feed.rss",
        "method": "GET",
        "type": "discovery",
        "description": "RSS 2.0 syndication feed of the public-simulation gallery.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/feed.rss'",
    },
    {
        "key": "reproduce_json",
        "endpoint": "/api/simulation/<simulation_id>/reproduce.json",
        "method": "GET",
        "type": "export",
        "description": "Reproducibility config blob — every parameter needed to re-run the simulation.",
        "added_in_pr": 79,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/reproduce.json'",
    },
    {
        "key": "lineage",
        "endpoint": "/api/simulation/<simulation_id>/lineage",
        "method": "GET",
        "type": "analytics",
        "description": "Parent + public-children lineage graph slice (forks + counterfactual branches).",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/lineage'",
    },
    {
        "key": "notebook_ipynb",
        "endpoint": "/api/simulation/<simulation_id>/notebook.ipynb",
        "method": "GET",
        "type": "export",
        "description": "Jupyter notebook with the trajectory CSV embedded inline — runs air-gapped.",
        "added_in_pr": 80,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/notebook.ipynb' -o sim.ipynb",
    },
    {
        "key": "chart_svg",
        "endpoint": "/api/simulation/<simulation_id>/chart.svg",
        "method": "GET",
        "type": "visualization",
        "description": "SVG chart of the per-round belief trajectory — embeddable in any HTML page.",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/chart.svg' -o chart.svg",
    },
    {
        "key": "archive_zip",
        "endpoint": "/api/simulation/<simulation_id>/archive.zip",
        "method": "GET",
        "type": "export",
        "description": "ZIP bundle of every per-sim share surface (manifest.json + SHA-256 fingerprints).",
        "added_in_pr": None,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/archive.zip' -o sim.zip",
    },
    {
        "key": "badge_svg",
        "endpoint": "/api/simulation/<simulation_id>/badge.svg",
        "method": "GET",
        "type": "visualization",
        "description": "Per-sim Shields.io-compatible badge — MiroShark | <direction> <confidence>%.",
        "added_in_pr": 94,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/badge.svg' -o badge.svg",
    },
    {
        "key": "cite_bib",
        "endpoint": "/api/simulation/<simulation_id>/cite.bib",
        "method": "GET",
        "type": "export",
        "description": "BibTeX @misc{} citation with reproduce.json SHA-256 + DKG UAL in the annotations.",
        "added_in_pr": 96,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/cite.bib'",
    },
    {
        "key": "polymarket_json",
        "endpoint": "/api/simulation/<simulation_id>/polymarket.json",
        "method": "GET",
        "type": "integration",
        "description": "Polymarket-shaped trading signal — direction-aware yes/no probability + tier.",
        "added_in_pr": 99,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/polymarket.json'",
    },
    {
        "key": "oembed",
        "endpoint": "/oembed",
        "method": "GET",
        "type": "embed",
        "description": "oEmbed 1.0 provider — auto-unfurls a /share/<id> link into a rich card on Notion/Ghost.",
        "added_in_pr": 107,
        "example_curl": "curl -fsSL 'https://your-host/oembed?url=https://your-host/share/<simulation_id>'",
    },
    {
        "key": "peak_round",
        "endpoint": "/api/simulation/<simulation_id>/peak-round",
        "method": "GET",
        "type": "analytics",
        "description": "Per-stance peak round + max_swing inflection summary — when consensus turned.",
        "added_in_pr": 108,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/peak-round'",
    },
    {
        "key": "agent_sparklines",
        "endpoint": "/api/simulation/<simulation_id>/agents/sparklines",
        "method": "GET",
        "type": "analytics",
        "description": "Per-agent belief sparkline series — agent-level companion to chart.svg.",
        "added_in_pr": 115,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/agents/sparklines'",
    },
    {
        "key": "volatility",
        "endpoint": "/api/simulation/<simulation_id>/volatility",
        "method": "GET",
        "type": "analytics",
        "description": "Belief-swing distribution — mean/std/max delta + 0-100 volatility index + trend label.",
        "added_in_pr": 124,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/volatility'",
    },
    {
        "key": "clone_json",
        "endpoint": "/api/simulation/<simulation_id>/clone.json",
        "method": "GET",
        "type": "export",
        "description": "Clone payload — the sim's inputs in POST /api/simulation/create shape; re-run or fork with one curl.",
        "added_in_pr": 131,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/clone.json'",
    },
    {
        "key": "agents_json",
        "endpoint": "/api/simulation/<simulation_id>/agents.json",
        "method": "GET",
        "type": "export",
        "description": "Agent roster — per-agent identity, persona preview, demographics + final stance. The participants surface.",
        "added_in_pr": 137,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/agents.json'",
    },
    # ── Platform-level surfaces ─────────────────────────────────────
    {
        "key": "platform_stats",
        "endpoint": "/api/stats",
        "method": "GET",
        "type": "platform",
        "description": "Aggregate platform stats — total_sims, consensus_distribution, avg_confidence, surface_views.",
        "added_in_pr": 105,
        "example_curl": "curl -fsSL 'https://your-host/api/stats'",
    },
    {
        "key": "platform_stats_badge",
        "endpoint": "/api/stats/badge.svg",
        "method": "GET",
        "type": "platform",
        "description": "Flat Shields.io-compatible platform badge — MiroShark | N simulations.",
        "added_in_pr": 105,
        "example_curl": "curl -fsSL 'https://your-host/api/stats/badge.svg' -o platform-badge.svg",
    },
    {
        "key": "project_stats",
        "endpoint": "/api/project/<project_id>/stats",
        "method": "GET",
        "type": "platform",
        "description": "Per-project aggregate stats — total_sims, consensus + quality distributions, surface_views.",
        "added_in_pr": 147,
        "example_curl": "curl -fsSL 'https://your-host/api/project/<project_id>/stats'",
    },
    # ── Meta — the catalog endpoint itself ───────────────────────────
    {
        "key": "surfaces_catalog",
        "endpoint": "/api/surfaces.json",
        "method": "GET",
        "type": "platform",
        "description": "This catalog — every surface this deployment exposes (machine-readable).",
        "added_in_pr": 127,
        "example_curl": "curl -fsSL 'https://your-host/api/surfaces.json'",
    },
    {
        "key": "ecosystem_catalog",
        "endpoint": "/api/ecosystem.json",
        "method": "GET",
        "type": "platform",
        "description": "Machine-readable ecosystem registry — every public project, agent, product built on MiroShark.",
        "added_in_pr": 145,
        "example_curl": "curl -fsSL 'https://your-host/api/ecosystem.json'",
    },
]


# Keys that should also appear in ``surface_stats.SURFACE_KEYS``. The
# per-sim share surfaces that increment a counter when served; the
# drift test cross-checks this set against the live ``SURFACE_KEYS``
# so a new per-sim surface can't ship without an entry here.
_PER_SIM_TRACKED_KEYS: frozenset[str] = frozenset(
    {
        "signal_json",
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
    }
)


# ── Public API ─────────────────────────────────────────────────────────


def get_surfaces_catalog() -> List[Dict[str, Any]]:
    """Return a freshly-copied list of every catalogued surface.

    Each call returns a new outer list and a new inner dict per entry
    so a caller mutating the response can't affect subsequent reads.
    Bytewise-deterministic across calls — the same Python interpreter
    invocation returns the same JSON when ``json.dumps(..., sort_keys=True)``
    is applied to the result.
    """
    return [dict(entry) for entry in _CATALOG]


def catalog_count() -> int:
    """Number of surfaces currently catalogued."""
    return len(_CATALOG)


def catalog_etag() -> str:
    """Short ETag derived from the catalog length.

    Changes whenever a new surface is appended — same posture as the
    ``/api/stats`` ETag (derived from ``total_sims`` + ``newest_sim_id``).
    A consumer's ``If-None-Match`` GET short-circuits to ``304`` until
    a new surface ships.
    """
    return f"surfaces-v{SCHEMA_VERSION}-{len(_CATALOG)}"


def build_response_payload() -> Dict[str, Any]:
    """Build the full envelope returned by ``GET /api/surfaces.json``.

    Shape::

        {
          "schema_version": "1",
          "count": <int>,
          "surfaces": [
            { "key": ..., "endpoint": ..., "method": ...,
              "type": ..., "description": ..., "added_in_pr": ...,
              "example_curl": ... },
            ...
          ]
        }

    The same envelope is returned to every caller; no per-request
    state, no caching of mutable state. Two consecutive calls produce
    bytewise-identical JSON.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "count": catalog_count(),
        "surfaces": get_surfaces_catalog(),
    }
