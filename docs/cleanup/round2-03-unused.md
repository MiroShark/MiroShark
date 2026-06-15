# Round 2 — Cleanup 03: Unused Code

Agent: code-quality agent 03 (unused code).
Branch: `worktree-agent-a11180dffa5dfabc0`.
Date: 2026-06-14.

## Scope & concern

Find and remove code that is provably unreferenced anywhere in the repo:
unused imports / redefinitions / unused locals (ruff F401/F811/F841), then
unused functions, classes, constants, whole modules, and (frontend) unreferenced
`.js`/`.vue`/`.css` files. Entire tree in scope incl. `backend/wonderwall/`
(vendored upstream — extra conservative).

## Methodology / tools

- `ruff check --select F401,F811,F841 backend` — unused imports, redefinitions,
  unused locals. Applied `--fix` only after manually confirming each flagged
  import had zero other usages in its file.
- Manual import-graph (`rg`/`git grep`) for whole-module and symbol reachability,
  since no venv/node_modules is available (static analysis only).
- Parallel Explore sub-agents to fan out the backend symbol hunt and the frontend
  file-reachability graph, then **re-verified every candidate by hand** repo-wide
  (code + tests + `wonderwall` + frontend + dynamic `get_prompt()` string keys +
  Flask blueprint registration).
- `python3 -m py_compile` on every changed file.

Baseline: `ruff check backend` = 166 errors before, 156 after (10 fixed). No
behavioural code touched, so pytest baseline (≈971 pass) is unaffected.

## Findings

### APPLIED — unused imports in tests (ruff F401), HIGH confidence

All 10 F401 hits were in `backend/tests/`. Each was confirmed (via `rg`) to appear
**only** on its own import line — no fixtures, no decorators, no string use.
`pytest` was only flagged where the file uses neither `@pytest.*` nor `pytest.*`
(e.g. `test_unit_webhook_events.py` keeps `pytest` because it has `@pytest.fixture`).

| file | removed import |
|---|---|
| `backend/tests/test_unit_activity_feed.py` | `re`, `pytest` |
| `backend/tests/test_unit_agent_export.py` | `pytest` |
| `backend/tests/test_unit_batch_status.py` | `pytest` |
| `backend/tests/test_unit_clone_service.py` | `pytest` |
| `backend/tests/test_unit_platform_status.py` | `timedelta`, `pytest` (kept `re` — used at line 290 `re.fullmatch`) |
| `backend/tests/test_unit_share_link.py` | `os`, `pytest` |
| `backend/tests/test_unit_webhook_events.py` | `os` (kept `pytest` — `@pytest.fixture`) |

F811 (redefinitions) and F841 (unused locals): **0 hits** repo-wide.

### DEFERRED / NOT REMOVED — false positives (dynamic dispatch), HIGH confidence they are LIVE

A sub-agent (correctly excluding `wonderwall` from *its* analysis, but `wonderwall`
is **in scope** here) flagged 4 prompt-locale modules as "never imported". They are
**LIVE** via dynamic string-key dispatch and must NOT be deleted:

- `backend/app/prompts/locales/en/social_simulations.py`
- `backend/app/prompts/locales/zh_CN/social_simulations.py`
- `backend/app/prompts/locales/en/profile_generator.py`
- `backend/app/prompts/locales/zh_CN/profile_generator.py`

Why they are live:
- `backend/app/prompts/registry.py` `_load_module()` does
  `importlib.import_module(f"app.prompts.locales.{dirname}.{module}")` where
  `module` is the **prefix of a string key** passed to `get_prompt("<module>.<key>")`.
- `social_simulations.*` keys are requested by `backend/wonderwall/simulations/
  social_media/prompts.py` and `.../polymarket/prompts.py` (e.g.
  `get_prompt("social_simulations.twitter_system", ...)`), and by
  `backend/tests/test_unit_prompt_registry.py`.
- `profile_generator.system_individual` / `system_group` are requested by
  `backend/app/services/wonderwall_profile_generator.py:808` (core production code).
- Verified the keys actually exist in the `PROMPTS` dicts of those modules.

This is the exact dynamic-import trap the safety rules warn about — flagging on
direct `import` grep alone is wrong here.

### Frontend — CLEAN, no dead files

Manual import graph over `frontend/src` (49 non-entry files: 9 `api/`, 25
`components/`, 4 `utils/`, 10 `views/`, `store/pendingUpload.js`):
- All `views/*.vue` are reachable via `router/index.js` (eager + lazy
  `() => import()`).
- All `components/*.vue` are imported and used (checked PascalCase **and**
  kebab-case tag usage).
- All `api/*.js` and `utils/*.js` are imported by views/components.
- No `.css` files exist under `frontend/src`.
- Entry points (`main.js`, `App.vue`, `i18n.js`, `index.html`) not flagged.

A full `knip` run is **DEFERRED to the integrator** (needs `node_modules`).
Manual candidates to confirm: **none** — every file has an inbound reference.
The integrator's `knip`/`madge` pass is the authoritative confirmation.

### Backend modules/symbols — no removable items

- All 18 non-`__init__` modules under `backend/app/api/` are registered in
  `backend/app/api/__init__.py` (`from . import X` / `from .X import X_bp`). No
  orphan blueprints.
- `backend/lib/env_compact.py` is LIVE (imported by
  `backend/wonderwall/social_agent/agent_environment.py` and a unit test).
- No HIGH-CONFIDENCE fully-unreferenced module found in `backend/app/` or
  `backend/lib/`. Heavy dynamic dispatch (prompt registry, blueprint
  auto-import) makes most "unused-looking" symbols actually live; per safety
  rule 3, anything uncertain was DEFERRED rather than removed.

## Ranked table

| item | risk | action | note |
|---|---|---|---|
| 10 unused test imports (F401) | high (safe) | APPLIED | grep-verified zero other usage per file |
| 4 prompt-locale modules | n/a | DEFERRED (KEEP) | live via dynamic `get_prompt()` string keys; deleting breaks simulations + profile gen |
| frontend dead files | n/a | none found | manual graph clean; full `knip` deferred to integrator |
| backend dead modules/symbols | n/a | none found | dynamic dispatch everywhere; deferred per rule 3 |

## Verification

- `ruff check backend`: 166 → 156 (10 F401 fixed), no new errors.
- `ruff check` on the 7 changed test files: "All checks passed!"
- `python3 -m py_compile` on all 7 changed files: OK.
- No production/behavioural code changed → pytest baseline unaffected.

## Conflict risk

Very low. Changes are import-line deletions in 7 distinct test files; no shared
files with typical other-agent edits, no signature/behaviour changes.
