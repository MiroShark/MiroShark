# Task 8 — Remove AI slop, stubs, larp, and unhelpful comments

## Summary

The MiroShark codebase is, overall, unusually well-commented: the large
majority of comments are genuine WHY/gotcha/ordering explanations or document
real workarounds (Langfuse retry bugs, circular-import shims, token-budget
constraints, stance-threshold cross-surface consistency). There is very little
true AI slop.

The slop that does exist is concentrated in two forms:

1. **Change-history narration** ("Previously…", "No longer…", "was dead code
   and has been removed", "New:") — narrates how the code got here rather than
   stating durable intent.
2. **Stale TODOs** that sit directly above fully-implemented code and so
   contradict it.

All high-confidence fixes (6 comments improved, 2 stale TODOs removed) were
applied. No fake/larp/stub *functions* were found that warranted deletion —
every `pass`/fallback body inspected is real (mostly `except: pass` and
fallback chains). Decorative `# ----` banners were deliberately KEPT because
they carry real section labels and form a consistent navigational style, not
filler.

## Categories found, with examples (file:line)

### A. Change-history narration (improved, not deleted — durable WHY kept)
- `backend/wonderwall/social_agent/agent.py:74` — "Previously this attribute
  was stored but never plumbed to CAMEL…" → trimmed to the durable rule
  (must be plumbed through or runtime is unbounded; why 3).
- `backend/app/services/simulation_manager.py:41` — "A previous local
  PlatformType enum here was dead code and has been removed" → "There is
  intentionally no local PlatformType enum here — add one only when…".
- `backend/app/services/simulation_manager.py:518` — "run scripts remain…/
  no longer copied…" → states the durable fact (scripts run in place from
  backend/scripts/, not copied per-sim).
- `backend/app/services/simulation_runner.py:542` — "No longer need separate
  stderr" → "stderr is merged into the main log".
- `backend/wonderwall/__init__.py:27` — "# New: simulation framework" →
  "Generic simulation framework (MiroShark extension over upstream CAMEL)".
- `backend/wonderwall/social_agent/agent.py:79` — "# --- New: generic
  simulation support ---" → "Generic-simulation support (MiroShark extension)".
- `backend/wonderwall/environment/env.py:67` — "# New: accept a
  SimulationConfig…" → dropped the "New:" framing.

### B. Stale TODOs above already-implemented code (deleted)
- `backend/wonderwall/social_agent/agent_environment.py:81` —
  `# TODO: Implement followers env` sat above a fully-working DB query.
- `backend/wonderwall/social_agent/agent_environment.py:98` —
  `# TODO: Implement follows env` — same.

### C. Decorative banners — KEPT (not slop)
- `# =========== Copyright 2023 @ CAMEL-AI.org … ===========` — license
  headers, KEPT per rules.
- `# ----------------…` section banners in `wonderwall/simulations/base.py`,
  `backend/mcp_server.py`, `agent_sparklines_service.py`, etc. carry real
  labels ("Database helpers", "Tool handlers (sync … run in a thread to avoid
  blocking the event loop)", "Stance helpers"). They are a consistent
  navigation style with information content; removing them would be
  cosmetic reformatting. KEPT.

### D. Restatement comments — mostly KEPT (see NEEDS REVIEW)
Many one-line verb comments (`# Save file`, `# Build messages`, `# Get card
style`, `// Format date/time`, `# Initialize`) lightly restate the code. Most
of the ones inspected actually carry a sliver of context (ordering, "sorted by
time", "fixed filenames, clean up old logs", token bounds). The pure ones are
low-value but live in very hot, multi-agent-touched files (report_agent.py,
Step*.vue, GraphPanel.vue), so churning them risks merge conflicts for
marginal benefit. Deferred — see NEEDS REVIEW.

## Applied removals / improvements (counts)

- Comments improved (history-narration → durable WHY): **6**
- Stale TODOs removed: **2**
- Stub/larp functions removed: **0** (none found that were truly dead;
  inspected bodies are all real)

Representative diffs:

```
- # CAMEL ReAct iteration cap. Previously this attribute
- # was stored but never plumbed to CAMEL, so runtime was
- # unbounded (and idempotent tool errors looped 4+ times).
- # 3 covers observe → tool → synthesize while bounding the
- # blast radius of any future loop bug.
+ # CAMEL ReAct iteration cap — must be plumbed through to
+ # CAMEL or runtime is unbounded. 3 covers observe → tool →
+ # synthesize while bounding the blast radius of a loop bug.
```

```
- # Note: run scripts remain in backend/scripts/ directory, no longer copied to simulation directory
- # When starting simulation, simulation_runner will run scripts from the scripts/ directory
+ # Run scripts live in backend/scripts/ and are executed in place;
+ # they are not copied into the per-simulation directory.
```

```
-     async def get_followers_env(self) -> str:
-         # TODO: Implement followers env
+     async def get_followers_env(self) -> str:
```

## NEEDS REVIEW / not applied

- **report_agent.py low-value restatement comments** (file ~3500 lines):
  `# Format 1`/`# Format 2` (KEEP — they label two parse strategies and an
  ordering constraint), but `# Initialize` (`:2579`), `# Add empty line`
  (`:3247`), `# Save file` (`:3195`), `# Build messages` (`:2883`),
  `# Add chat history` (`:2886`), `# Add user message` (`:2890`) are pure
  restatement. Not applied — high merge-conflict risk; recommend a single
  owner sweep this file.
- **Frontend one-liner restatements** in `GraphPanel.vue`, `Step5Interaction.vue`,
  `HistoryDatabase.vue`, `Step2EnvSetup.vue` (e.g. `// Get card style`,
  `// Helper Methods`, `// Format date (date part only)`). Pure restatement but
  scattered across hot Vue files; deferred to avoid conflicts.
- **`agents_generator.py` TODOs** (`:104`, `:207`, `:239`, `:263`, `:287`) —
  KEPT. These are genuine upstream CAMEL forward-looking scalability notes
  ("if you simulate one million agents…"), not stale/done work, and the code
  paths they annotate are real.

## Cross-cutting notes (overlap with Task 3 / Task 7)

- `backend/wonderwall/social_agent/agent_environment.py` has **pre-existing**
  `ruff F401` unused-import warnings (`_MAX_COMMENTS_PER_POST`, `_compact_*`,
  `_parse_ts`) — present on the base commit, NOT introduced here. These belong
  to **Task 3 (unused)**.
- `backend/app/services/simulation_manager.py:41` note already documents that a
  dead local `PlatformType` enum was removed — relevant context for **Task 3/7**
  (no enum to re-add unless needed).
- The `wonderwall/` tree is largely vendored from upstream CAMEL/oasis; its
  forward-looking TODOs and section banners were intentionally left intact to
  minimize fork drift. Coordinate with **Task 7 (legacy)** before deeper edits
  there.
- No genuine stub/larp implementations were found wired into real call paths
  that needed removal.
