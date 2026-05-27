# Code-quality cleanup — consolidated summary

Branch: `cleanup/code-quality-2026-05` (off `main`). Eight focused passes were run in
isolated worktrees, then merged here. After all merges:

- **Tests:** `971 passed, 2 failed, 17 skipped` — identical to the pre-cleanup baseline.
  The 2 failures (`test_unit_demographic_grounding.py`) are **pre-existing** and unrelated
  (the optional demographic-grounding fallback needs local HF/duckdb data not present here).
- **Lint (ruff):** `193 → 158` errors. All 34 unused-import (F401) and 4 unused-var (F841)
  findings eliminated. Remainder (F541 f-strings, E402, E701, E741, F821) is pre-existing.
- **Net source impact:** 47 files, +183 / −268 lines.

The headline finding across every pass: **this is a deliberately clean, well-commented,
defensively-engineered codebase.** High-confidence changes were scarce; most agents applied
1–2 surgical changes and deferred the rest as intentional. The detail per task is in the
sibling docs (`01`–`08`).

## Applied (high-confidence, merged)

| # | Task | Applied |
|---|------|---------|
| 1 | DRY / dedup | Extracted `_build_badge_document` (badge_service) and `_build_event` (event_logger); ~100 dup lines removed, byte-identical output verified |
| 2 | Type consolidation | Collapsed a triplicated `CommandType` enum in the three `run_*_simulation.py` scripts onto the canonical `simulation_ipc.CommandType` |
| 3 | Unused / dead code | Removed 27 unused imports + 4 unused locals (grep-verified) |
| 4 | Circular deps | None needed — 0 harmful cycles (the `app.api` blueprint "cycle" is the correct import-safe pattern) |
| 5 | Weak types | Strengthened 32 annotations across 15 files; fixed a genuinely **wrong** type (`LLMClient.chat` was `-> str`, actually returns `None`) |
| 6 | Defensive try/except | Removed 1 redundant `except Exception: raise` in the neo4j retry loop (only 1 of ~898 handlers qualified) |
| 7 | Legacy / fallback | Removed 1 dead CSS tombstone comment; proved several "legacy"-labelled branches are actually live and must stay |
| 8 | AI slop / comments | Rewrote 6 change-history comments into durable "why"; dropped 2 stale TODOs above working code |

## Resolved in follow-up (commit `fb40a77`)

After review, four deferred items were implemented (tests still 971-pass, ruff 158→156):

1. **Deleted dead `backend/app/utils/retry.py` (238 lines)** — confirmed zero references
   repo-wide. *(Task 3)*
2. **Fixed the `'GraphStorage'` F821 latent bug** — added a `TYPE_CHECKING` import in
   `simulation_manager.py` and `simulation_runner.py`. *(found by Task 5)*
3. **Added the `WebhookPayload` TypedDict** and typed the webhook/notify `state` param as
   `Optional[SimulationRunState]` (was `Optional[Any]`) via `TYPE_CHECKING`. Chose the
   concrete type over a Protocol — it's the only non-`None` value any caller passes, and the
   `getattr(..., default)` reads for `profiles_count`/`created_at`/`parent_simulation_id` are
   deliberate "live object lacks these → fall back to state.json" probes. *(Task 2 + Task 5)*
4. **Narrowed 5 hot-path `except Exception: pass`** — `simulation_runner.py` (clear
   director-events write, error-log read) and `simulation.py` (quality.json read, and *both*
   cache-write sites) now catch `(OSError[, JSONDecodeError | UnicodeDecodeError])` + a
   `debug` log, so I/O failures surface instead of hiding. *(Task 6)*

## Still deferred — needs human decision (NOT applied)

1. **`report_agent.py:1401-1433` "backward compatible legacy tools" redirect** — removable
   only as a set, *with* the `browse_clusters` prompt (line 714) and frontend tool badges
   (Step4Report.vue:629/635) updated together; also doubles as a guard against
   LLM-hallucinated tool names. *(Task 7 + Task 3 + Task 6)*
2. **Remaining broad `except Exception` blocks** — the ~890 handlers Task 6 kept (and the
   `simulation.py:7317` run-state read, left untouched because it wraps a method call, not
   pure I/O). Most genuinely guard external input; a fuller narrowing pass is a separate effort.
3. **More TypedDict candidates** — ~5 other fixed-shape `Dict[str, Any]` returns flagged by
   Task 5; not done to avoid a large parallel type fleet in one pass. *(Task 2 + Task 5)*
4. **Frontend dead-code pass** — `npx knip` could not resolve imports without `node_modules`,
   so no frontend deletions were made. A real pass needs `cd frontend && npm install` first.

## Explicitly preserved (intentional, do NOT "clean up")

- Notify-channel duplication (`slack/discord/email/telegram_notify.py`) — documented decoupling.
- Persisted-data format fallbacks (old on-disk layouts) and the Twitter/Reddit `DefaultPlatformType`
  simulation paths (mislabelled "legacy" but live).
- Optional-import / graceful-degradation guards (demographic grounding, etc.).
- Vendored CAMEL-AI tree under `backend/wonderwall/` (upstream code; left near-untouched).
