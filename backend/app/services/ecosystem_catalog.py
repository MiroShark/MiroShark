"""Machine-readable catalog of every external project, agent, and
product publicly identified as built on MiroShark.

``ECOSYSTEM.md`` is the human-facing index: an alphabetised Markdown
table of integrators with logos, links, and a short description.
Curated by the project; rows arrive via PR. It answers the meta-question
*"who else is building on this?"* — but only for human readers.

This module is the machine-readable counterpart. ``GET /api/ecosystem.json``
(served by ``app/api/surfaces.py``) returns the same set of integrators
as a typed JSON envelope so an integrator (or another integrator
building tooling on the ecosystem itself) can iterate the list without
parsing Markdown. Same posture as ``surfaces_catalog.py`` (PR #130):
the catalog ships next to the route handler that serves it, the
underlying data lives as a literal list at module scope, and a drift
test cross-checks the catalog against ``ECOSYSTEM.md``.

Design notes
------------

* **Static / hardcoded.** The catalog is a literal list at module
  scope. NOT auto-derived from a Markdown parse of ``ECOSYSTEM.md`` —
  the Markdown shape is fragile (cells contain links, images, and free
  text) and a silent parser drift would degrade the public contract.
  Adding an entry ships in two files: the row in ``ECOSYSTEM.md`` and
  the entry here. The drift test in ``test_unit_ecosystem_catalog.py``
  cross-checks the project ``name`` set against ``ECOSYSTEM.md`` so
  neither side can drift silently.

* **Stable schema.** Each entry is a dict with a locked field set —
  ``name`` (display string, matches the project's own canonical
  capitalisation), ``url`` (primary public link — repo URL when one
  exists, otherwise the X profile), ``description`` (one short line,
  ≤160 chars), ``category`` (one of five strings — see
  ``ECOSYSTEM_CATEGORIES``), ``x_handle`` (the project's X / Twitter
  handle without the ``@``, or ``null``), ``repo`` (the project's
  public GitHub repo URL, or ``null``). Schema versioned via the
  response envelope's ``schema_version``.

* **Five categories.** ``product`` (a public-facing app or service
  built on MiroShark — Echo Oracle, RootAI, Xerg, ZER0, Capacitr,
  HivemindOS), ``tool`` (operator-facing utilities — Crucible Sim),
  ``integration`` (services that wire MiroShark into another system
  — Monitor), ``agent`` (autonomous bots running MiroShark sims —
  Blue Agent, SyntheticsAI), ``benchmark`` (test / evaluation
  pipelines over the engine — AntFleet). MCP servers and Aeon skill
  packs that wrap MiroShark surfaces fall under ``integration``
  (Noelclaw mcp, Signa signa-miroshark-skills).

* **Alphabetised by ``name``.** Matches the ECOSYSTEM.md ordering
  convention. Order is part of the published contract — a consumer
  iterating the list sees the same order as a human reader scanning
  ECOSYSTEM.md.

* **Stdlib only.** Pure Python list of dicts; no Markdown parsing,
  no disk scan, no outbound network. Same posture as
  ``surfaces_catalog`` — a frozen literal that ships with the code
  revision.

* **No PII / no secrets.** Every link in the catalog is a public URL
  the integrator has themselves published. The catalog never
  contains a contact email, an internal Slack handle, or any other
  non-public artefact.
"""

from __future__ import annotations

from typing import Any, Dict, List


# Schema version literal — bump on breaking changes to the entry
# field set. v1 is the only published version.
SCHEMA_VERSION = "1"


# ── Categories ──────────────────────────────────────────────────────────
#
# Five categories cover every current integrator. A consumer can scope
# its work to a category by filtering on ``category``. Adding a category
# is a non-breaking change; renaming or removing one is breaking and
# bumps ``schema_version``.


ECOSYSTEM_CATEGORIES: frozenset[str] = frozenset(
    {
        "product",
        "tool",
        "integration",
        "agent",
        "benchmark",
    }
)


# ── The catalog ────────────────────────────────────────────────────────
#
# Alphabetised by ``name`` — matches ECOSYSTEM.md ordering. Entries
# mirror the rows in ECOSYSTEM.md one-for-one; drift between the two is
# enforced by ``test_unit_ecosystem_catalog.test_catalog_names_match_ecosystem_md``.


_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "AntFleet",
        "url": "https://github.com/AntFleet/miroshark-bench",
        "description": "Security and capability benchmark suite over the MiroShark engine — first integrator-product feedback loop.",
        "category": "benchmark",
        "x_handle": "AntFleetDev",
        "repo": "https://github.com/AntFleet/miroshark-bench",
    },
    {
        "name": "Blue Agent",
        "url": "https://github.com/madebyshun/blue-agent",
        "description": "Autonomous agent harness wrapping MiroShark for unattended scenario simulations.",
        "category": "agent",
        "x_handle": "blueagent_",
        "repo": "https://github.com/madebyshun/blue-agent",
    },
    {
        "name": "Capacitr",
        "url": "https://capacitr.xyz/",
        "description": "Capacity-planning platform with a public MiroShark integration spec citing the /x402/run surface by name.",
        "category": "product",
        "x_handle": "capacitr_xyz",
        "repo": None,
    },
    {
        "name": "Crucible Sim",
        "url": "https://github.com/wshuyi/crucible-sim",
        "description": "Operator-facing scenario crucible built on the MiroShark simulation engine.",
        "category": "tool",
        "x_handle": None,
        "repo": "https://github.com/wshuyi/crucible-sim",
    },
    {
        "name": "Echo Oracle",
        "url": "https://www.builtbyecho.xyz/",
        "description": "Oracle product that surfaces MiroShark consensus signals into downstream consumers.",
        "category": "product",
        "x_handle": "BuiltByEcho",
        "repo": None,
    },
    {
        "name": "HivemindOS",
        "url": "https://hivemindos.liamvisionary.com",
        "description": "Collective-intelligence OS layer that orchestrates MiroShark simulations as a primitive.",
        "category": "product",
        "x_handle": "thehivemindos",
        "repo": "https://github.com/LiamVisionary/hivemindos",
    },
    {
        "name": "Monitor",
        "url": "https://github.com/Zoidberg-eternal/monitor-the-situation-bags",
        "description": "Bags-flavoured monitor that pipes MiroShark signal events into a market-side feed.",
        "category": "integration",
        "x_handle": None,
        "repo": "https://github.com/Zoidberg-eternal/monitor-the-situation-bags",
    },
    {
        "name": "Noelclaw",
        "url": "https://noelclaw.com",
        "description": "MCP server exposing MiroShark surfaces to MCP-aware assistants and agents.",
        "category": "integration",
        "x_handle": "noelclawfun",
        "repo": "https://github.com/noelclaw/mcp",
    },
    {
        "name": "RootAI",
        "url": "https://rootai.wtf",
        "description": "Edge-AI product built on MiroShark agent-debate primitives.",
        "category": "product",
        "x_handle": "Root_Edge",
        "repo": None,
    },
    {
        "name": "Signa",
        "url": "https://github.com/codexvritra/signa-miroshark-skills",
        "description": "Aeon skill pack that wraps MiroShark surfaces as autonomous-agent skills.",
        "category": "integration",
        "x_handle": "Signa_Agent",
        "repo": "https://github.com/codexvritra/signa-miroshark-skills",
    },
    {
        "name": "SyntheticsAI",
        "url": "https://syntheticuser.org",
        "description": "Synthetic-user pipeline that runs MiroShark sims as the underlying behavioural engine.",
        "category": "agent",
        "x_handle": "SyntheticsAI_",
        "repo": None,
    },
    {
        "name": "Xerg",
        "url": "https://xerg.ai/",
        "description": "Agentic product layer consuming MiroShark consensus signals for decision automation.",
        "category": "product",
        "x_handle": "xerg_AI",
        "repo": None,
    },
    {
        "name": "ZER0",
        "url": "https://www.atzer0.xyz/",
        "description": "Public-facing product that surfaces MiroShark simulation outputs to end users.",
        "category": "product",
        "x_handle": "atzer0_BOT",
        "repo": None,
    },
]


# ── Public API ─────────────────────────────────────────────────────────


def get_ecosystem_catalog() -> List[Dict[str, Any]]:
    """Return a freshly-copied list of every catalogued integrator.

    Each call returns a new outer list and a new inner dict per entry
    so a caller mutating the response can't affect subsequent reads.
    Bytewise-deterministic across calls — the same Python interpreter
    invocation returns the same JSON when ``json.dumps(..., sort_keys=True)``
    is applied to the result.
    """
    return [dict(entry) for entry in _CATALOG]


def catalog_count() -> int:
    """Number of ecosystem entries currently catalogued."""
    return len(_CATALOG)


def catalog_etag() -> str:
    """Short ETag derived from the catalog length + schema version.

    Changes whenever a new integrator is appended — same posture as the
    ``surfaces_catalog`` ETag. A consumer's ``If-None-Match`` GET
    short-circuits to ``304`` until a new entry ships.
    """
    return f"ecosystem-v{SCHEMA_VERSION}-{len(_CATALOG)}"


def build_response_payload() -> Dict[str, Any]:
    """Build the full envelope returned by ``GET /api/ecosystem.json``.

    Shape::

        {
          "schema_version": "1",
          "count": <int>,
          "ecosystem": [
            { "name": ..., "url": ..., "description": ...,
              "category": ..., "x_handle": ..., "repo": ... },
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
        "ecosystem": get_ecosystem_catalog(),
    }
