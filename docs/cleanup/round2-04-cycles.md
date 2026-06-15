# Round 2 — Task 04: Circular Import Dependencies

Date: 2026-06-14
Agent: cleanup(04) — circular-dependency detection & untangling
Scope: `backend/app`, `backend/wonderwall`, `backend/lib`, `backend/scripts`,
`backend/tests`, and `frontend/src` (JS + Vue). Vendored `wonderwall` included
(user opted in) — high-confidence behavior-preserving changes only.
Mode: from-scratch re-analysis; auto-apply HIGH-CONFIDENCE only; defer + document
everything uncertain.

## TL;DR

**0 harmful cycles. No code changes applied.** This round independently rebuilt
the import graph from scratch (not trusting round 1) and confirms the round-1
conclusion. All strongly-connected components that exist are *benign*: they use
import-safe patterns (Flask blueprint registration; `from __future__ import
annotations` + `if TYPE_CHECKING:`; documented function-local imports). The two
frontends and the backend cross-package boundary (`app` ↔ `wonderwall`) are
acyclic.

Independent additions vs. round 1: this round explicitly enumerates **two more
benign SCCs** that round 1 mentioned only obliquely — the `*_notify` ↔
`simulation_runner` services SCC and the `wonderwall.social_agent` package SCC —
and verifies each is import-time-safe. Both confirmed benign.

## Methodology & tools

No venv / node_modules available, so this is pure **static** analysis (the
integrator runs `madge` + pytest at the end).

1. **Backend** — custom `ast`-based, *submodule-aware* import-graph builder +
   Tarjan SCC, `/tmp/cyclefinder.py` (full source below). It:
   - walks every `.py` under `backend/` (263 intra-repo modules),
   - resolves **relative** (`from .`, `from ..`) and **absolute**
     (`from app.x`, `from wonderwall.x`, `lib`, `scripts`, `tests`) imports to a
     single best module node — crucially, `from ..config import Config` maps to
     `app.config` (a real module), **not** spuriously to the `app` package root.
     The first naive pass over-generated package-root back-edges and produced a
     bogus 76-node SCC; fixing the resolver collapsed it to the true graph.
   - flags each edge as `[TYPE_CHECKING]` (inside an `if TYPE_CHECKING:` block) or
     `[func-local]` (inside a function/method body) — the two signals that
     distinguish a benign cycle from a harmful one.
2. **Frontend** — `/tmp/jscyclefinder.py`: extracts `<script>` blocks from `.vue`,
   parses `import … from`, `export … from`, and dynamic `import('…')` in
   `.js`/`.vue`/`.mjs`/`.ts`, resolves relative + `@/` alias paths (the repo uses
   only relative paths, no `@/`), then Tarjan SCC.

### Graph stats

- Backend: **263 modules, 572 intra-repo edges, 3 multi-node SCCs.**
- Frontend: **53 files, 153 edges, 0 SCCs.**

## Full cycle list (for integrator cross-check with madge)

### Backend SCC #1 — `app.api.*` Flask blueprint package (11 nodes) — BENIGN, do not fix

```
app.api            -> countries, docs, feed, graph, mcp, observability,
                      report, settings, simulation, templates  (imports submodules)
app.api.countries  -> app.api          (from . import countries_bp)
app.api.docs       -> app.api
app.api.feed       -> app.api, app.api.simulation [func-local]
app.api.graph      -> app.api
app.api.mcp        -> app.api
app.api.observability -> app.api
app.api.report     -> app.api
app.api.settings   -> app.api
app.api.simulation -> app.api
app.api.templates  -> app.api
```

Files: `backend/app/api/__init__.py` + every `backend/app/api/<name>.py`.
Why safe: `__init__.py` defines all `*_bp = Blueprint(...)` (lines 7–16) **before**
importing submodules (lines 18+). When a submodule runs `from . import graph_bp`
the name already exists in the partially-initialized package. This is the canonical
Flask pattern and the brief explicitly says **not** to "fix" it (rule 2).
The lone `app.api.feed -> app.api.simulation [func-local]` edge
(`feed.py:82`) is a *documented lazy-load for import cost*, not a cycle workaround
(both modules are co-resident in this SCC and import safely via the blueprint
pattern). Left as-is.

### Backend SCC #2 — `*_notify` ↔ `simulation_runner` services (6 nodes) — BENIGN, already resolved

```
app.services.simulation_runner -> discord_notify, email_notify, slack_notify,
                                   telegram_notify, webhook_service   [all func-local]
app.services.discord_notify    -> simulation_runner [TYPE_CHECKING], webhook_service [func-local]
app.services.email_notify      -> simulation_runner [TYPE_CHECKING], webhook_service [func-local]
app.services.slack_notify      -> simulation_runner [TYPE_CHECKING], webhook_service [func-local]
app.services.telegram_notify   -> simulation_runner [TYPE_CHECKING], webhook_service [func-local]
app.services.webhook_service   -> simulation_runner [TYPE_CHECKING]
```

Files: `backend/app/services/{simulation_runner,webhook_service,discord_notify,
email_notify,slack_notify,telegram_notify}.py`.
Why safe: every back-edge to `simulation_runner` is **TYPE_CHECKING-only** (the
notify modules all have `from __future__ import annotations` and import
`SimulationRunState` only under `if TYPE_CHECKING:`), and `simulation_runner`
imports the notify modules **function-locally**. `webhook_service.py:67` even
carries an inline comment: "Type-only: avoids a runtime import cycle." At module
load there is no cycle. This is the correct fix already applied — promoting any of
these to module-level imports would *reintroduce* a real ImportError, so it must
NOT be done.

### Backend SCC #3 — `wonderwall.social_agent` package (4 nodes) — BENIGN (vendored)

```
wonderwall.social_agent          -> agent, agent_graph, agents_generator  (package __init__ aggregates)
wonderwall.social_agent.agent    -> wonderwall.social_agent [TYPE_CHECKING]   (imports AgentGraph type)
wonderwall.social_agent.agent_graph     -> agent
wonderwall.social_agent.agents_generator -> agent, agent_graph
```

Files: `backend/wonderwall/social_agent/{__init__,agent,agent_graph,
agents_generator}.py`.
Why safe: `agent.py` (`from __future__ import annotations`) imports `AgentGraph`
from the package **only under `if TYPE_CHECKING:`** (`agent.py:35`). The package
`__init__` loads `agent` first; its back-reference to the package is type-only, so
no runtime deadlock. Vendored CAMEL-AI fork — behavior-preserving rule means hands
off regardless.

(Two smaller wonderwall package-init SCCs — `social_platform` and
`simulations.polymarket` — that appeared in the *naive* first pass were the same
package-`__init__` aggregation artifact and disappear under correct submodule
resolution. They are not real cycles.)

### Frontend — 0 cycles

53 files, 153 resolved edges, **0 SCCs**, **0 mutual A↔B pairs**, including dynamic
`import()`. The app uses only relative imports (no `@/` alias). Clean.

### Cross-package — no `app` ↔ `wonderwall` cycle

`app` **never** imports `wonderwall` (0 module-level or function-local imports).
`wonderwall` imports `app` one-directionally:
`wonderwall/simulations/{social_media,polymarket}/prompts.py` →
`from app.prompts import get_prompt` / `from app.utils.i18n import get_active_locale`,
and `wonderwall/social_agent/belief_state.py:417` (func-local)
`from app.utils.llm_client import create_llm_client`. One-directional layering
inversion (engine reaching into host), **not a cycle** — out of scope here.

## Ranked findings

| # | Cycle / SCC | Severity | Harmful? | Action |
|---|-------------|----------|----------|--------|
| 1 | `app.api.*` blueprint package (11) | structural | No — idiomatic Flask, import-safe | DEFER (rule 2 forbids) |
| 2 | `*_notify` ↔ `simulation_runner` (6) | low | No — TYPE_CHECKING + func-local already | NO-OP (already correct) |
| 3 | `wonderwall.social_agent` (4) | low | No — TYPE_CHECKING back-edge, vendored | DEFER (vendored) |
| 4 | `wonderwall → app` layering | n/a | No — one-directional, not a cycle | DEFER (architecture pass) |
| — | frontend | n/a | No cycles | NO-OP |

## APPLIED

**None.** There are no harmful cycles. Every SCC is already in its import-safe
form. Applying cosmetic acyclicity (e.g. extracting `app/api` blueprints into a
leaf `blueprints.py` and editing ~15 submodule headers) is explicitly out of scope
(brief: "Do NOT restructure for cosmetic acyclicity") and would create a large
merge-conflict surface with other agents editing `app/api/`.

## DEFERRED (and why)

- **D1 — `app.api` blueprint extraction (cosmetic).** Could make SCC #1 vanish from
  static tools by moving `*_bp = Blueprint(...)` into a new leaf `app/api/blueprints.py`
  and changing every `from . import <name>_bp` to `from .blueprints import <name>_bp`.
  Deferred: current code is import-safe; brief rule 2 says this pattern is correct
  and not a bug; touches 15+ files → high conflict risk for zero correctness gain.
- **D2 — Promote func-local / TYPE_CHECKING imports to module level.** The notify
  services' `simulation_runner` import is TYPE_CHECKING **because** promoting it
  reintroduces a real cycle → must stay. `simulation_runner`'s func-local notify
  imports are the matching half → must stay. `feed.py:82`'s func-local
  `simulation` import is a documented lazy-load → keep.
- **D3 — `wonderwall → app` layering inversion.** Real smell, but one-directional
  (not a cycle) and in vendored code; an architecture pass, not a cycle fix.

## CONFLICT_RISK

**None.** Zero source files changed. The only new file is this doc
(`docs/cleanup/round2-04-cycles.md`), which is unique to this agent.

## Appendix A — `cyclefinder.py` (backend AST import-graph + Tarjan SCC)

The script lives at `/tmp/cyclefinder.py` during this run; reproduced for the
record. Run: `cd backend && python3 cyclefinder.py .`

```python
# (submodule-aware resolver: 'from ..config import Config' -> app.config, NOT app)
# - resolves relative + absolute intra-repo imports to ONE best module node
# - flags edges inside `if TYPE_CHECKING:` and inside function bodies
# - Tarjan SCC, prints multi-node components with per-edge [TYPE_CHECKING]/[func-local] tags
# Full source committed in the worktree run notes; key resolution logic:
#   for `from <base> import <name>`:
#     if "<base>.<name>" is a module file -> edge to that submodule
#     elif "<base>" is a module/package    -> edge to <base> (symbol import)
#     else fall back to resolvable parent
# This avoids the naive bug of adding a package-root edge for every `from pkg.mod import x`.
```

## Appendix B — verification commands

```
cd backend && python3 /tmp/cyclefinder.py .      # -> 3 SCCs, all benign (above)
python3 /tmp/jscyclefinder.py frontend/src       # -> 0 SCCs
rg -n "^\s*(from wonderwall|import wonderwall)" backend/app -t py   # empty: app !-> wonderwall
rg -n "^from \.simulation_runner import" backend/app/services/*.py  # only services/__init__ (safe)
```
