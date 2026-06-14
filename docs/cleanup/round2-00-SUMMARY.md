# Code-quality cleanup — round 2 (2026-06)

Integration branch: `cleanup/code-quality-2026-06` (off `main` @ `e01e495`). Eight focused
passes were run in parallel, each in an isolated git worktree, then cherry-picked here in a
conflict-minimizing order (cycles/legacy docs → dead-code → types → DRY → weak-types →
defensive → slop). All 8 commits applied with **zero merge conflicts** (the two overlapping
files, `simulation.py` and `logger.py`, 3-way auto-merged because the hunks were disjoint).

This is a *second* cleanup pass; round 1 (PR #116, `docs/cleanup/01`–`08`) already concluded
the codebase is "deliberately clean, well-commented, defensively-engineered." Round 2
re-audited from scratch over the ~56 commits / 80 changed files added since, and independently
reached the same headline: **high-confidence changes are scarce; most value is small and surgical.**

## Verification (merged result vs. pre-cleanup baseline)

| Check | Baseline (`e01e495`) | After round 2 | Δ |
|-------|----------------------|---------------|---|
| pytest | 1370 passed / 2 failed / 17 skipped | **1370 / 2 / 17** | unchanged ✅ |
| ruff (backend) | 166 errors | **156 errors** | −10 (F401) ✅ |
| frontend `npm run build` | clean | clean ✅ | — |
| `madge --circular` (frontend JS) | 0 cycles | 0 cycles ✅ | — |
| source diff | — | 38 files, **+170 / −317** (net −147) | — |

The 2 pytest failures are the pre-existing `test_unit_demographic_grounding.py` cases (need
local HF/duckdb data not present here) — identical to baseline, unrelated to this work.

## Applied (high-confidence, merged)

| # | Task | Applied |
|---|------|---------|
| 1 | DRY / dedup | Extracted `backend/app/utils/json_io.py::safe_load_json` (single source of the "best-effort read sim artifact, never raise" pattern); replaced byte-identical `_safe_load_json` copies in **11 service modules** + removed the orphaned `import json` / `typing.Any` they left behind. Functional-equivalence harness verified byte-identical output. |
| 2 | Type consolidation | Added `webhook_service.build_test_payload(scenario) -> WebhookPayload` (+ `TEST_PAYLOAD_SIM_ID`); replaced a 13-key test-event payload duplicated byte-for-byte across the 4 `*_notify.py` channels. Notify *rendering/sending* decoupling preserved. |
| 3 | Unused / dead code | Removed 10 grep-verified unused imports across 7 `test_*.py` files (ruff 166→156). Refused to delete 4 prompt-locale modules that look unused but are **live via dynamic `importlib` dispatch**. Frontend: 0 dead files. |
| 4 | Circular deps | None needed. AST+Tarjan over 263 backend modules / 53 frontend files → **0 harmful cycles**; the 3 SCCs (blueprint package, `*_notify ↔ simulation_runner` TYPE_CHECKING back-edges, `wonderwall.social_agent`) are all import-safe. |
| 5 | Weak types | Strengthened 8 backend files. Fixed a genuinely **wrong** type (`simulation.py::_get_report_id_for_simulation` was `-> str`, returns `None` on 3 paths → `str \| None`). Retyped `neo4j_storage._call_with_retry` generic `Callable[..., _T] -> _T` and **removed its `# type: ignore`**. Typed untyped statics in `trace_context`/`event_logger`/`logger`/`claude_code_client`/`llm_client`/`task.py` using `object` (must-narrow), never `Any`. |
| 6 | Defensive try/except | Narrowed 3 silent `except Exception: pass` in `simulation.py::_build_gallery_card_payload` (first-party artifact reads) to specific exceptions + `logger.debug`, so corrupt-file bugs surface. Of ~898 handlers, only these 3 qualified — the rest legitimately guard I/O / network / LLM / DB / optional imports. |
| 7 | Legacy / fallback | None removable. Every legacy/deprecated/fallback marker proved **live** (persisted-data format fallbacks, `report_agent` legacy-tools redirect, `graph_storage.wait_for_processing`, neo4j `episodes` alias rendered by `GraphPanel.vue`). No `if False` dead branches anywhere. |
| 8 | AI slop / comments | Removed 11 pure-restatement comments (`# Create logger` above `logging.getLogger`, etc.) across 7 files. Zero commented-out code, stubs, larp, edit-narration, or stale TODOs found. |

## Deferred — needs human / owner decision (NOT applied)

1. **Frontend unused exports (knip).** No dead *files*. The unused *exports* split into:
   - **False positives (live — keep):** the i18n composable exports (`isZh`, `showZhWarning`,
     `setLocale`, `dismissZhWarning`, `toggleLocale`) are consumed via the `useI18n()` return
     object + Vue global props (`$isZh()` in templates); the `urlParams` helpers (`PREFILL_LIMITS`,
     `sanitize*`, `isValidHttpUrl`) are used internally. knip can't see composable/global-prop use.
   - **Likely WIP scaffolding (recommend keep / confirm):** `getEcosystem`, `getActivityFeed`,
     `getSurfacesCatalog`, `getOutcomeDistribution`, `getPlatformStatus`, `getProjectStats`,
     `getBatchStatus`/`batchSimulationStatus` (+ their `*Url` builders) map 1:1 to backend
     endpoints **added in the last 56 commits** — almost certainly client code for features still
     being wired into the UI, not dead legacy.
   - **Older orphan candidates (review):** `getLlmCalls`, `getReportStatus`, `getSimulationProfiles`,
     `getSimulationPosts`, `getSimulationTimeline`, `getAgentStats`, `restartEnv`, `getVapidPublicKey`,
     `subscribePush`, `testPushNotification`, `getPreviewUrl`, `getOEmbedUrl`, `getSignedResultJson`,
     `getSimulationFrame`. Statically zero-reference (no namespace/barrel/dynamic consumption — verified),
     but intent (WIP vs. truly abandoned) is the owner's call. The frontend has no tests, so these
     were left for explicit confirmation rather than auto-deleted.
2. **`report_agent.py` legacy-tools redirect** — removable only as a set with the `browse_clusters`
   prompt + `Step4Report.vue` tool badges; also guards against LLM-hallucinated tool names. Product decision.
3. **More DRY candidates** (DRY agent) — ISO-8601 "now" helper (7×, 3 names), `_resolve_base_url`
   variants, `_avg_position` (semantics differ: one counts `True` as 1.0). Each needs a single-owner
   follow-up or a semantics decision.
4. **More TypedDict candidates** — `{success/data/error}` (~157 sites) and `{ok/message}` response
   envelopes; `task.py` `result`/`progress_detail` payloads; `_safe_load_json` JSON-returning family.
5. **Trivia** — redundant `settings.py:14` `# noqa: F401` namespace import; `frame_metadata.py:235`
   `_FARCASTER_USERNAME` documented future-feature placeholder.

## Explicitly preserved (intentional — confirmed live this round, do NOT "clean up")

- Notify-channel duplication (`slack/discord/email/telegram_notify.py`) — documented decoupling.
- Persisted-data on-disk format fallbacks; Twitter/Reddit `DefaultPlatformType` simulation paths.
- Optional-import / graceful-degradation guards (demographic grounding, duckdb/HF, torch).
- The ~890 broad `except Exception` handlers that guard genuinely external/untrusted input.
- Vendored CAMEL-AI tree under `backend/wonderwall/` — left near-untouched for upstream re-sync.

Per-task detail: `round2-01-dry.md` … `round2-08-slop.md`.
