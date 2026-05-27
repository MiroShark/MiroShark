# Task 3 — Unused Code Cleanup

Branch: `cleanup/code-quality-2026-05` (isolated worktree). Mode: auto-apply
high-confidence, surface risky. No pytest run (no `.venv`); verification via
`ruff check`, `python3 -m py_compile`, `vulture`, `npx knip`, and full-repo grep.

## Summary

- Applied **31 surgical deletions**: 27 unused imports (F401) + 4 unused local
  variables (F841). All confirmed via `ruff check --select F401,F841` (now
  passing clean) and `python3 -m py_compile` on every changed file.
- Nothing in the public API surface, no route handlers, no MCP tools, no CLI
  commands, no pytest fixtures, and no exported library symbols were deleted.
- Frontend: knip ran with an incomplete dependency install (no `node_modules`,
  `vite` unresolved) so its "unused exports" report is unreliable — several
  flagged symbols are demonstrably used. Nothing deleted from the frontend.
- Strongest genuine dead code found but **deferred** (whole-module / public-
  looking surface): `backend/app/utils/retry.py` (238 lines, zero references
  repo-wide).

## Tool output digest

- `ruff check --select F401,F841 backend`: 38 findings (34 F401 + 4 F841).
  34 F401 across 19 files; 4 F841 in 3 files. All actioned (deleted) or were
  the same lines.
- `vulture backend --min-confidence 80`: 6 findings. All are false positives:
  - `i18n.py:113` `exc_type`,`tb` — `__exit__` dunder params (protocol-required).
  - `test_integration_legacy_scripts.py:49` `needs_backend`,`needs_neo4j` —
    `@pytest.mark.parametrize` argument bindings (required by the decorator).
  - `round_analyzer.py:285` `belief_state` — function PARAMETER, passed
    positionally by 2 callers (see below); not dead.
  - `recsys.py:428` `recall_only` — public function parameter of bundled
    CAMEL-derived engine; deferred (see NEEDS REVIEW).
- `vulture backend --min-confidence 60`: ~180 findings, overwhelmingly Flask
  route handlers (`@bp.route`-decorated), which vulture cannot see are
  registered. Treated as false positives. A handful of non-route methods/
  functions/constants surfaced and were investigated (see NEEDS REVIEW).
- `npx knip` (frontend): emitted `ERROR: Error loading vite.config.js (Cannot
  find module 'vite')` — node_modules absent. Reported 25 "unused exports" and
  1 unused file (`public/sw.js`). Grep proved 4 of the flagged i18n exports
  (`isZh`, `showZhWarning`, `dismissZhWarning`, `toggleLocale`) ARE imported by
  Vue components, confirming the report is unreliable. No frontend deletions.

## Applied deletions (file:line + proof-of-dead)

All proven via `ruff` (authoritative scope-aware F401/F841) + targeted grep; re-
run of `ruff check --select F401,F841 backend` afterward = "All checks passed!".

### Unused imports (F401) — 27 removed

Source files:
- `backend/app/prompts/registry.py:12` — `import os` (only ref was the import;
  no `os.` usage).
- `backend/app/services/badge_service.py:68` — `from typing import Optional`
  (no `Optional` usage).
- `backend/app/services/chart_svg.py:40` — `from typing import Iterable`.
- `backend/app/services/notebook_export.py:70` — `import os` (the only other
  `os` token was inside a module docstring, not code).
- `backend/cli.py:24` — `import time` (no `time.` usage).
- `backend/wonderwall/social_agent/agent_environment.py` — removed 6 unused
  names: `datetime` (line 19) and 5 of the 6 `lib.env_compact` imports
  (`_MAX_COMMENTS_PER_POST`, `_compact_comment`, `_compact_post_for_agent`,
  `_comment_score`, `_parse_ts`). Kept `_compact_posts_for_agent` (used at
  line 70). No `__all__` in the file, so not re-exported.

Test files (each had the import as its sole occurrence = unused):
- `tests/test_unit_discord_notify.py:22,24,27` — `os`, `threading`,
  `MagicMock` (kept `patch`, `sys`, `time` — all used); `:29` `pytest`.
- `tests/test_unit_webhook_signature.py:21,22,25` — `hashlib`, `hmac`,
  `threading` (kept `json`, `sys`, `time`, `contextmanager`).
- `tests/test_unit_archive_service.py:45` — `pytest`.
- `tests/test_unit_email_notify.py:28` — `pytest`.
- `tests/test_unit_feed.py:33` — `pytest`.
- `tests/test_unit_lineage.py:50,54` — `os`, `pytest`.
- `tests/test_unit_mcp_bridge.py:8` — `pytest`.
- `tests/test_unit_openapi.py:29,33,35` — `json`, `Iterable`, `pytest`.
- `tests/test_unit_oracle_seed.py:5` — `os`.
- `tests/test_unit_platform_stats.py:31` — `os`.
- `tests/test_unit_repro_export.py:62` — `os`.
- `tests/test_unit_sitemap.py:47` — `pytest`.
- `tests/test_unit_slack_notify.py:25` — `pytest`.
- `tests/test_unit_telegram_notify.py:26` — `pytest`.
- `tests/test_unit_webhook_log.py:22` — `pytest`.

  Each test file: verified `pytest` appears only on the import line (no
  `pytest.mark` / `.raises` / `.fixture` / `.skip` usage), so removing the
  import is safe and does not affect collection.

### Unused local variables (F841) — 4 removed

- `backend/app/services/chart_svg.py:198` — `grid = ET.SubElement(...)` →
  `ET.SubElement(...)`. The element is attached to `svg` by side effect; the
  `grid` binding was never read. Behavior preserved.
- `backend/app/services/share_card.py:251` — removed `f_section = _load_font(...)`
  (font never drawn with).
- `backend/app/services/share_card.py:257` — removed `f_pct_label = _load_font(...)`
  (font never drawn with).
- `backend/app/api/simulation.py:10405` — removed `user_name = display_name or
  handle` (assigned, never read in the loop body; `display_name`/`handle`
  remain and are used elsewhere — ruff only flagged `user_name`).

## NEEDS REVIEW / suspected-but-not-deleted

Listed strongest-first. Not applied because each is either public-looking
surface, a documented constant, a function parameter (contract), or flagged by
a tool whose analysis was incomplete here.

1. **`backend/app/utils/retry.py` (entire module, 238 lines)** — vulture@60
   flags `retry_with_backoff` (L15), `retry_with_backoff_async` (L80),
   `RetryableAPIClient` (L132), `call_batch_with_retry` (L195). Full-repo grep
   (`.py`, `.yaml`, `.md`) finds ZERO references; the module is never imported;
   no `__all__` re-export. This is genuinely dead. Deferred because deleting a
   whole utility module = removing intended-reusable public surface; recommend
   orchestrator confirm it isn't a planned/external util before removal.

2. **`backend/wonderwall/social_platform/recsys.py:428` `recall_only`** —
   unused default kwarg of `rec_sys_personalized_twh`; the sole caller
   (`platform.py:362`) doesn't pass it. Bundled CAMEL-derived engine; this is
   an upstream public API parameter. Removing changes a public signature —
   defer.

3. **`backend/app/services/text_processor.py`** — `extract_from_files` (L12),
   `get_text_stats` (L175): no external refs found. Public-looking methods on a
   service class; defer.

4. **`backend/app/services/telegram_notify.py:411` `send_telegram_message`** —
   module-level function, no external refs. Possibly public notify helper;
   defer.

5. **`backend/app/utils/i18n.py:19` `SUPPORTED`** — vulture@60. Referenced only
   in docstrings (`i18n.py` and `app/prompts/__init__.py` instruct devs to
   append locales to it). Documented config constant — keep.

6. **Frontend `src/api/*.js` exports** (knip): `getCountryFilterSchema`,
   `getEvents`, `getLlmCalls`, `getReportStatus`, `getSimulationProfiles`,
   `getSimulationPosts`, `getSimulationTimeline`, `getAgentStats`, `restartEnv`,
   `getVapidPublicKey`, `subscribePush`, `testPushNotification`, `getOEmbedUrl`,
   `getSimulationFrame`, plus `src/i18n.js` `setLocale`/`SUPPORTED_LOCALES`,
   `src/utils/urlParams.js` `PREFILL_LIMITS`/`sanitizeScenarioText`/
   `sanitizeAskText`/`sanitizeTemplateSlug`/`isValidHttpUrl`. Grep shows no
   external importers for these specific symbols, BUT knip ran without
   `node_modules` (vite unresolved) and mis-flagged sibling exports that ARE
   used (`isZh`, `dismissZhWarning`, etc.), so its output is untrustworthy here.
   These form a coherent API-client / util library surface — defer pending a
   knip run with deps installed.

7. **`public/sw.js`** (knip "unused file") — a service worker, loaded by URL at
   runtime (`navigator.serviceWorker.register`), not via JS import graph. Almost
   certainly a knip false positive — keep.

8. **~110 Flask route handlers across `app/api/*.py`** flagged by vulture@60
   (e.g. `list_countries`, `get_settings`, all `simulation.py` endpoints) —
   decorator-registered, not dead. Ignored.

## Cross-cutting notes

- Vulture is near-useless for this Flask app at any confidence: route handlers,
  CLI commands, and MCP tools are all decorator-registered and appear "unused."
  The trustworthy signal was `ruff` (F401/F841, scope-aware) plus manual grep.
- Files touched are spread (tests, services, api, wonderwall, cli, prompts).
  Edits are single-line import/var removals — low merge-conflict risk, but
  `backend/app/api/simulation.py` and `backend/app/services/share_card.py` /
  `chart_svg.py` are large hot files other cleanup tasks (formatting, dead-
  branch, dup-removal) are likely to also touch. Conflicts, if any, will be
  trivial localized hunks.
- The two `share_card.py` font removals and the `chart_svg.py` `grid` change are
  the only edits that alter a statement (not just an import) — both verified to
  preserve runtime behavior (fonts unused; SubElement side effect retained).
