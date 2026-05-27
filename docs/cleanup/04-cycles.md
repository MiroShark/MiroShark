# Task 4 — Circular Import Dependencies

Date: 2026-05-27
Scope: `frontend/src` (JS + Vue), `backend/app`, `backend/wonderwall`.
Mode: auto-apply high-confidence, surface risky.

## Summary

**No harmful circular imports exist in the codebase, so no code changes were applied.**

- **Frontend (`frontend/src`):** 0 cycles. Verified across all 52 `.js` and `.vue`
  files, including dynamic `import()` calls.
- **`backend/wonderwall` (38 modules):** 0 import-time cycles. A few defensive
  function-local imports exist but none of them is currently breaking an active
  cycle (promoting them would *not* re-introduce one — see Cross-cutting notes).
- **`backend/app` (115 modules):** exactly **one** structural cycle, the
  `app.api.*` Flask-blueprint package. It is the **idiomatic, import-safe Flask
  blueprint pattern** and is correct as written. Two other SCCs initially reported
  by a naive detector (`app.storage`, `app.services`) were **false positives** —
  artifacts of modeling `from . import <submodule>` as a dependency on the package
  `__init__` rather than on the submodule itself.
- **Cross-package:** `app` does **not** import `wonderwall`; `wonderwall` imports a
  couple of helpers from `app` (one-directional). No `app`↔`wonderwall` cycle.

Tooling note: `npx madge --circular frontend/src` reports clean for `.js`, but its
Babel parser cannot parse `.vue` templates (`--extensions js,vue` throws a JSX
syntax error). `pydeps … --show-cycles` produced no output in this environment
(no `.venv`, no graphviz/`dot`, package not importable). I therefore used a custom
AST-based, **submodule-aware** import-graph + Tarjan SCC detector for an
authoritative result. Frontend was checked with an analogous `.vue`-aware script
that extracts `<script>` blocks.

## Cycles found

### 1. `app.api.*` — Flask blueprint package (REAL, but safe by design)

```
app.api (__init__)  ──[imports submodule]──►  app.api.graph
                    ──[imports submodule]──►  app.api.simulation
                    ──[imports submodule]──►  app.api.report
                    ──[imports submodule]──►  app.api.templates / settings /
                                              observability / mcp / docs /
                                              feed / countries  (+ share, watch,
                                              sitemap, notifications, stats)

app.api.graph  ──[from . import graph_bp]──►  app.api (__init__)
app.api.simulation ──[from . import simulation_bp]──►  app.api (__init__)
…each submodule pulls its own *_bp Blueprint object back from the package.
```

Files: `backend/app/api/__init__.py` plus every `backend/app/api/<name>.py`.

Why it is safe: `backend/app/api/__init__.py` defines all `*_bp = Blueprint(...)`
objects on lines 7–16 **before** importing any submodule on lines 18+. When a
submodule executes `from . import graph_bp`, the `graph_bp` name already exists in
the partially-initialized `app.api` module, so the import resolves without
touching not-yet-defined state. This is the canonical, recommended Flask structure
and runs correctly today. See "NEEDS REVIEW" for the optional (not applied)
refactor.

### False positives (NOT real cycles — documented so the next reader doesn't re-flag them)

- `app.storage` ↔ `app.storage.neo4j_storage`: caused by
  `neo4j_storage.py:30` `from . import neo4j_schema` (a **submodule** import, not a
  re-export from `app/storage/__init__.py`). Submodule imports only require the
  package to be in `sys.modules` (partial init is fine); no ordering deadlock.
  `neo4j_schema` and `reasoning_trace` are leaves w.r.t. the storage package.
- `app.services` SCC (`demographic_sampler`, `simulation_manager`,
  `wonderwall_profile_generator`, …): same artifact — `from . import
  country_registry` / `from . import demographic_sampler` are **submodule** imports.
  Verified `demographic_sampler` and `country_registry` do not import
  `simulation_manager`/`wonderwall_profile_generator` back, so there is no genuine
  sibling-to-sibling cycle.

## Applied fixes

None. There are no harmful cycles to untangle. The only real cycle is correct as
written, and applying a "fix" would touch 15+ files for zero correctness benefit
and a high merge-conflict surface with other agents working in `app/api/`.

## NEEDS REVIEW / not applied

### N1. (Optional) Extract `app.api` blueprints into a leaf module — NOT APPLIED

Proposed structure to make the `app.api` cycle disappear from static analysis:

```
backend/app/api/blueprints.py   # new leaf: graph_bp = Blueprint(...); … (no submodule imports)
backend/app/api/__init__.py     # from .blueprints import *_bp ; then import submodules
backend/app/api/<name>.py       # from .blueprints import <name>_bp   (instead of `from . import …`)
```

- Technique: extract shared symbols into a new leaf module.
- Why deferred: the current code is already import-safe; this is cosmetic. It would
  edit `__init__.py` + ~15 submodules, which strongly overlaps the working set of
  other cleanup tasks (especially anything restructuring `app/api/`). Risk/benefit
  is unfavorable for an isolated agent. Recommend the orchestrator decide whether
  to apply after other `app/api/` cleanups land.

### N2. (Optional) Promote leaf-only deferred imports — NOT APPLIED

These function-local imports are safe to promote to module level (their targets are
leaves and would not create a cycle), but none is currently breaking a cycle, so
promoting them is out of this task's scope and adds conflict risk:

- `app/storage/neo4j_storage.py:696` `from .reasoning_trace import ReasoningTraceRecorder`
  (`reasoning_trace` is pure-stdlib, imports nothing from `app.storage`).
- `wonderwall/social_agent/agent.py:91` `from wonderwall.simulations.base import SimulationConfig`
  and `wonderwall/environment/env.py:94,114` `from wonderwall.simulations.base import …`.
  `simulations.base` only top-level-imports `clock.clock` and
  `social_platform.channel` (both leaves), so promotion would not create a cycle —
  but `wonderwall` is vendored sim-engine code (CAMEL-AI), where lazy imports are
  often intentional. Leave as-is.

## Cross-cutting notes

- **Task 2 (types):** the `app.api` cycle is driven by runtime Blueprint objects,
  not types, so `if TYPE_CHECKING:` does not help here and no type moves are needed
  for cycle reasons. If Task 2 introduces a typing/shared-symbol leaf module, the
  N1 refactor could be folded in there. No TYPE_CHECKING blocks needed to be added
  by this task.
- **Conflict surface for other agents:** I changed **no files**, so this task
  introduces no merge conflicts. The areas I analyzed but deliberately left
  untouched — `backend/app/api/__init__.py` and the `app/api/*` submodule import
  headers, plus `app/storage/neo4j_storage.py` — are the spots most likely to be
  edited by other tasks; if those tasks move blueprint definitions or imports,
  re-run the cycle check afterward.
- **One-directional layering smell (not a cycle, FYI):**
  `backend/wonderwall/simulations/{social_media,polymarket}/prompts.py` import
  `from app.prompts import get_prompt` and `from app.utils.i18n import
  get_active_locale`. The bundled engine reaching up into the host app is a
  layering inversion worth noting for an architecture pass, but it is not a cycle
  (`app` never imports `wonderwall`).
