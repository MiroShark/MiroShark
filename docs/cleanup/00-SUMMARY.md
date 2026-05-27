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

## Deferred — needs human decision (NOT applied)

1. **Dead module `backend/app/utils/retry.py` (238 lines)** — `retry_with_backoff`,
   `retry_with_backoff_async`, `RetryableAPIClient`, `call_batch_with_retry`. Zero references
   repo-wide (verified). Likely safe to delete; held back because deleting a whole
   intended-reusable utility module is a judgment call. *(Task 3)*
2. **`report_agent.py:1401-1433` "backward compatible legacy tools" redirect** — removable
   only as a set, *with* the `browse_clusters` prompt (line 714) and frontend tool badges
   (Step4Report.vue:629/635) updated together; also doubles as a guard against
   LLM-hallucinated tool names. *(Task 7 + Task 3 + Task 6)*
3. **Broad `except Exception: pass` on the hot path** — `simulation.py` (~7334, ~10078),
   `simulation_runner.py` (375, 723, 1683) wrap multi-line file/JSON I/O. Could narrow to
   `(OSError, json.JSONDecodeError)` + a debug log, but that is behavior-adjacent. *(Task 6)*
4. **Pre-existing latent bug — `'GraphStorage'` forward ref** in `simulation_manager.py:294`
   and `simulation_runner.py:337`: annotation references a name never imported (ruff F821).
   Harmless today (never evaluated), breaks on `get_type_hints()`. *(found by Task 5)*
5. **Type-consolidation follow-ups** *(Task 2 + Task 5)* — a shared `WebhookPayload` TypedDict
   and a `Protocol` for the duck-typed `SimulationRunState` passed to notify/webhook services;
   ~5 fixed-shape `Dict[str, Any]` returns are TypedDict candidates. Intentionally not done to
   avoid creating a parallel type fleet.
6. **Frontend dead-code pass** — `npx knip` could not resolve imports without `node_modules`,
   so no frontend deletions were made. A real pass needs `cd frontend && npm install` first.

## Explicitly preserved (intentional, do NOT "clean up")

- Notify-channel duplication (`slack/discord/email/telegram_notify.py`) — documented decoupling.
- Persisted-data format fallbacks (old on-disk layouts) and the Twitter/Reddit `DefaultPlatformType`
  simulation paths (mislabelled "legacy" but live).
- Optional-import / graceful-degradation guards (demographic grounding, etc.).
- Vendored CAMEL-AI tree under `backend/wonderwall/` (upstream code; left near-untouched).
