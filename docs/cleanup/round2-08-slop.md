# Round 2 — Task 08: Remove AI slop, stubs, larp, unhelpful comments

## Methodology

This is the **second** cleanup round; round 1 (`docs/cleanup/08-slop.md`) already
rewrote 6 change-history comments into durable "why" notes and dropped 2 stale
TODOs. My job was a from-scratch re-sweep of first-party code only
(`backend/app/`, `backend/scripts/`, `frontend/src/`), explicitly **without**
undoing round 1's durable-intent rewrites and **without** touching vendored
`backend/wonderwall/`.

Approach:
1. `rg` sweeps per category across `.py`/`.js`/`.vue` (excluding `wonderwall/`):
   change-history narration, commented-out code, AI filler/marketing/emoji,
   decorative banners, `pass`/`...`/`NotImplementedError` stub bodies, TODO/FIXME/XXX.
2. Two high-precision fan-out passes (Explore agent) to enumerate pure-restatement
   comments and confirm zero commented-out code / zero stub functions.
3. Read every candidate **in context** before editing; kept anything carrying a
   why, an artifact name, an ordering/gotcha, or a domain term.
4. Applied only high-confidence, **low-conflict** removals (see ranking); deferred
   the hot multi-agent files (`simulation.py`, `simulation_runner.py`, the Step*.vue
   wizard) because Task 08 has the highest merge overlap with the other 7 agents.

## Categories found, with counts + examples

### A. Commented-out code — 0 found
No executable lines (assignments/calls/if/for/return/imports) are commented out
anywhere in first-party code. The `#`-prefixed `x = ...` hits are field-doc
comments (`test_pipeline_twitter_polymarket.py:101-102`), not dead code.

### B. Edit-narration / change-history — 0 actionable
The remaining "previously/no longer" hits describe **runtime** state, not edit
history, and are load-bearing:
- `simulation_runner.py:1010` "previously we only advanced on round_end, which lagged…" — explains the WHY of the current advance logic.
- `simulation_runner.py:1159` / `:1646` "process no longer exists" — runtime branch.
- `GraphPanel.vue:379` "track whether simulation was previously running" — runtime ref.
- `EmbedDialog.vue:4937/4968` "previously expanded / previously-403 fetch" — runtime state.
Round 1 already converted the true history-narration ones. None left to fix.

### C. Decorative banners — 0 actionable (KEPT, same as round 1)
Every `# ==== … ====` / `# ---- … ----` carries a real section label
(`dkg_publisher.py` "HTTP defaults / Citation persistence / …",
`text_processor.py` PDF-cleanup stages, `simulation_config_generator.py`
"Step 1 / Step 2 / …"). These are a consistent navigation style with information
content, not filler. The `run_parallel_simulation.py` `====` rows wrap a real
"Fix Windows encoding" explanation. KEPT.

### D. Stub / larp / placeholder functions — 0 found
No function body is just `pass` / `...` / `return None` / `raise NotImplementedError`
pretending to work. All `pass` are real `except: pass` suppressors; all `...` are
inside docstring JSON-schema examples. The `# stub out specific renderers`
(`archive_service.py:221`) and `placeholder`/`temporary` hits are real domain
references (UI placeholder strings, magic-byte sniffing, temp ZIP). Nothing to remove.

### E. AI marketing / emoji filler — 0 found
No emoji, no "seamless/robust/cutting-edge/leverage" slop. One "# Redirect to
insight_forge, as it is more powerful" (`report_agent.py:1421`) is a real
functional comment, KEPT.

### F. TODO/FIXME/XXX — 0 actionable
Only 4 `XXX` hits, all `\uXXXX` JSON-escape references. No stale TODOs remain in
first-party code (round 1 cleared them).

### G. Pure-restatement comments — ~89 found, 11 removed
A comment that only restates the single line below it, adding zero context.
This was the **only** category with real slop. Examples kept vs removed below.

## Ranked table

| Rank | Category | Count | Action |
|------|----------|-------|--------|
| HIGH | Pure restatement, low-conflict files (logger header `# Get logger`/`# Set up logging`/`# Create logger`; `# Create logger`/`# Add handlers`/`# Create default logger` in `logger.py`; `# Save file`/`# Get file size` in `project.py`; `# Build messages`/`# Add chat history`/`# Add user message` in `report_agent.py`; `# Get card style` in `HistoryDatabase.vue`) | 11 | **APPLIED** |
| MED | Pure restatement in HOT multi-agent files (`simulation.py`, `simulation_runner.py:619/631/1038/1557`, `report.py:192`, `api/graph.py` block labels, Step*.vue) | ~40 | DEFERRED (conflict risk) |
| LOW | Block-label restatements in procedural test scripts (`# Save config`, `# Load profiles`, `# Create graph` in `test_*.py`) | ~25 | DEFERRED (low value + low harm; mildly aid skimming) |
| LOW | Borderline labels carrying a sliver of context (`# Close brackets` in JSON-repair flow, `# Initialize logger (agent_log.jsonl)`, `# Helper Methods` section divider) | ~13 | KEPT (genuine context / parallel structure) |

## APPLIED (11 pure-restatement comment removals, comment-only, zero behavior change)

- `backend/app/utils/logger.py` — removed `# Create logger`, `# Add handlers`, `# Create default logger` (each restated the one line below).
- `backend/app/__init__.py` — removed `# Set up logging` above `setup_logger('miroshark')`.
- `backend/app/api/graph.py` — removed `# Get logger` above the module logger.
- `backend/scripts/action_logger.py` — removed `# Create logger` above `getLogger(...)`.
- `backend/app/models/project.py` — removed `# Save file` and `# Get file size`.
- `backend/app/services/report_agent.py` — removed `# Build messages`, `# Add chat history`, `# Add user message` (round 1's own cited example of pure restatement). Kept `# Limit history length` (explains the `[-10:]` slice).
- `frontend/src/components/HistoryDatabase.vue` — removed `// Get card style` above `getCardStyle`.

## DEFERRED (and why)

- **Hot multi-agent files** (`simulation.py`, `simulation_runner.py`, `api/report.py`,
  the Step*.vue wizard): ~40 more pure-restatement comments exist, but these files
  are simultaneously edited by the dead-code / try-except / types agents. Round 1
  deferred them for the same reason. Churning a one-line comment there is not worth
  a merge conflict. Recommend a single-owner sweep after integration.
- **Procedural test scripts** (`backend/scripts/test_*.py`): ~25 `# Save config` /
  `# Load profiles` style labels. Low value but they mildly aid reading a linear
  test; low harm either way. Left to keep the change surface minimal.
- **`# Close brackets`** (`simulation_config_generator.py:534`,
  `wonderwall_profile_generator.py:731`): part of a coherent `count → check strings →
  close` JSON-repair sequence; removing the middle label alone breaks the parallel
  structure. KEPT.

## Cross-cutting notes

- No round-1 durable "why" rewrites were touched or reverted.
- `wonderwall/` left entirely alone per scope.
- The pre-existing `F541` f-string warnings in `report_agent.py` are unrelated and
  belong to a lint pass, not this task.
