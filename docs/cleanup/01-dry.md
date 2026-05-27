# Task 1 — Deduplicate & consolidate (DRY)

## Summary

Ran `npx jscpd --min-lines 8 --min-tokens 70 backend frontend/src` (103 clones, ~4% of
codebase) plus targeted `rg`/`grep` for repeated literals and helper signatures.

Most of the raw duplication is either (a) **deliberately decoupled** with explicit
"re-implemented here rather than imported" design notes (the notify-channel cluster),
(b) **coincidentally similar but semantically divergent** (e.g. four different
`_avg_position` bool-handling variants), or (c) large **CSS/Vue `<script>`** blocks
across full-page views whose consolidation is behaviour-affecting and would collide with
the frontend cleanup agents.

Two consolidations were genuinely safe (single-module, byte-output-verified) and have
been **applied**. The remaining high-line-count candidates are documented under NEEDS
REVIEW with the specific semantic obstacle for each, rather than risk a behaviour change.

- Applied consolidations: **2**
- Lines of duplication removed: ~100 (badge: ~85, event_logger: ~15)
- Files changed: `backend/app/services/badge_service.py`,
  `backend/app/utils/event_logger.py`

## Applied changes

### 1. `backend/app/services/badge_service.py` — extract `_build_badge_document(...)`
- `build_badge_svg()` (per-sim belief badge) and `build_platform_badge_svg()`
  (platform-stats badge) contained two ~90-line near-identical SVG document builders
  (`jscpd`: 205-231 vs 367-393, 273-304 vs 426-457). They differ **only** in the
  right-hand label, the right-half fill colour, and the `clipPath` id.
- Extracted a private `_build_badge_document(right_label, right_color, clip_id)` that
  both public functions now call. Element insertion order and
  `short_empty_elements=True` preserved exactly so the output stays
  **bytewise-deterministic** (the module docstring requires this for HTTP caching /
  hash-based ETags).
- **Verified**: loaded the pre-edit (HEAD) and post-edit modules side-by-side and
  compared output across 9 badge cases + 7 platform cases (incl. edge cases: `None`,
  empty string, out-of-range confidence, non-numeric, negative count) — **byte-identical
  for both `build_*` and `render_*_bytes`**, and `PLATFORM_COLOR` unchanged. Public
  signatures and the `PLATFORM_COLOR` constant (asserted in
  `tests/test_unit_platform_stats.py`) are untouched.

### 2. `backend/app/utils/event_logger.py` — extract `_build_event(...)`
- The standalone subprocess writer `write_simulation_event()` and the singleton
  `EventLogger.emit()` built the **identical** 9-field event dict
  (`event_id`/`event_type`/`timestamp`/`simulation_id`/`trace_id`/`round_num`/
  `agent_id`/`agent_name`/`platform`/`data`) (`jscpd`: 46-58 vs 124-136).
- Extracted `_build_event(event_type, data, *, ...)` as the single source of truth for
  the on-disk JSONL event shape. `emit()` still does its `TraceContext` auto-fill first,
  then calls the helper with the resolved values; `write_simulation_event()` calls it
  with the explicit args.
- **Verified**: key list and order unchanged
  (`['event_id','event_type','timestamp','simulation_id','trace_id','round_num',
  'agent_id','agent_name','platform','data']`), `event_id` still `evt_<12 hex>`,
  timestamp still ISO-8601 millisecond UTC with trailing `Z`. JSONL byte-shape preserved.

Both files: `python3 -m py_compile` OK; `ruff check` clean for `event_logger.py`.
`badge_service.py` ruff reports only a **pre-existing** unused `typing.Optional` import
(present unchanged at HEAD, unrelated to this task — left for the dead-code/lint agent).

## Findings (file:line evidence) — duplication that was reviewed

| Clone | Lines | Disposition |
|---|---|---|
| `badge_service.py` 205-231/273-304 vs 367-393/426-457 | ~85 | **Applied** (helper) |
| `event_logger.py` 46-58 vs 124-136 | ~15 | **Applied** (helper) |
| `slack/discord/email/telegram_notify.py` (`_truncate`, `_env`, `belief_bar`, `_consensus_direction`, `_status_verb`, `BAR_*`) | ~250 cumulative | **Deferred** — documented intentional decoupling |
| `run_reddit_simulation.py` vs `run_twitter_simulation.py` (`run()`, `main()`, `setup_signal_handlers()`) | ~600 | **Deferred** — divergent entry-point scripts |
| `transcript.py`/`thread_formatter.py`/`trajectory_export.py`/`agent_sparklines_service.py`/`watch_renderer.py` (`STANCE_THRESHOLD`, `_avg_position`, `_round_stance_split`) | ~70 | **Deferred** — `_avg_position` bool handling differs |
| `dkg_publisher.py` vs `waybackclaw_publisher.py` (`_request`, `_parse_body`) | ~63 | **Deferred** — `_request` headers differ; tiny private helpers |
| `replay_gif.py` vs `share_card.py` (`_find_font`, `_load_font`, `_text_width`, `_wrap_text`, `_FONT_*`) | ~55 | **Deferred** — `_FONT_CANDIDATES` differ (regular vs bold-first) |
| `SimulationView/SimulationRunView/ReportView/InteractionView/MainView.vue` (CSS + `<script>` helpers) | ~1000 CSS + ~150 JS | **Deferred** — `.vue`, behaviour-affecting, frontend-agent conflict |
| Stance colours `#22c55e`/`#6b7280`/`#ef4444` across `badge_service`/`chart_svg`/`email_notify`/`agent_sparklines`/`watch_renderer`/`notebook_export` | many | **Deferred** — documented lockstep constants; several are in generated CSS / code-gen strings |
| `api/feed.py` & `api/sitemap.py` `_resolve_base_url()` (identical) | 14 | **Deferred** — needs a new shared module; `watch.py` + `webhook_service.py` variants deliberately differ |
| `tests/test_unit_*` (`sys.path` bootstrap, `_summary()` fixtures) | ~150 | **Deferred** — per-file test fixtures kept for isolation/readability |

## NEEDS REVIEW (risky — not applied)

1. **Notify-channel helper cluster** —
   `backend/app/services/{slack,discord,email,telegram}_notify.py`.
   `_truncate`, `_env`, `belief_bar`, `_consensus_direction`, `_status_verb`, and the
   `BAR_FILLED/BAR_EMPTY/BAR_WIDTH` constants recur across all four.
   **Do not auto-merge.** `email_notify.py:255-261` and `telegram_notify.py:188`
   explicitly document the duplication as intentional: *"Re-implemented here rather than
   imported so a future change to the Slack bar width / glyphs doesn't silently re-flow
   every queued plain-text email."* The `_truncate` bodies also differ slightly between
   files. Consolidating would couple four intentionally-independent transports. If a
   shared `notify_common.py` is ever desired it should be a conscious architectural
   decision, not a DRY sweep.

2. **`_avg_position` / `_round_stance_split` belief math** —
   `transcript.py:66`, `trajectory_export.py:80`, `thread_formatter.py:78`,
   `agent_sparklines_service.py:117` (+ `STANCE_THRESHOLD = 0.2` in 5 files).
   The bodies look mergeable but are **semantically divergent**:
   `transcript.py`'s `_avg_position` filters `isinstance(v, (int, float))` and therefore
   **counts `True` as `1.0`**, whereas the other three explicitly exclude `bool`;
   `agent_sparklines_service.py` additionally guards `isinstance(positions, dict)`.
   Merging into one helper would change `transcript.py` output for any snapshot
   containing a boolean position. Reconcile the bool/type-guard semantics first (likely
   adopt the bool-excluding variant everywhere), then a single `belief_math.py` is
   worthwhile. High conflict risk with whatever agent touches these services.

3. **`run_reddit_simulation.py` ↔ `run_twitter_simulation.py`** (~600 dup lines).
   `run()`, `main()`, and `setup_signal_handlers()` are near-identical, differing in
   class name, platform enum (`DefaultPlatformType.REDDIT` vs `TWITTER`), agent-graph
   generator, action handling, the argparse description, and trailing whitespace. These
   are standalone executables launched as subprocesses. A shared base runner is a real
   improvement but is a substantial, behaviour-sensitive refactor of process entry
   points — out of scope for a surgical DRY pass.

4. **`replay_gif.py` ↔ `share_card.py`** font/text helpers (~55 lines).
   `_text_width`/`_wrap_text` are identical, but `_load_font`/`_find_font` depend on
   `_FONT_CANDIDATES`, which **differ** (`replay_gif` lists regular DejaVu first;
   `share_card` lists DejaVu-Bold first and has extra Windows entries) — so
   `_load_font(size, bold=False)` resolves to different fonts. These render the PNG/GIF
   share images; a shared `image_text.py` for just `_text_width`/`_wrap_text` is possible
   but the visual-regression risk + new-module overhead make it a deliberate-review item.

5. **`api/feed.py:46` ↔ `api/sitemap.py:46` `_resolve_base_url()`** (byte-identical,
   14 lines). Safe to share, but the only clean home is a new web-helpers module, and the
   sibling `watch.py:204` / `webhook_service.py:656` variants are deliberately different
   (no `PUBLIC_BASE_URL` preference / no request context respectively). Low value (2
   callers) vs new-indirection + conflict cost. Recommend deferring to whoever owns the
   `api/` package layout.

6. **Stance-colour constants** (`#22c55e`/`#6b7280`/`#ef4444`, `#f59e0b`). Pinned as
   module constants in `badge_service`, `chart_svg`, `agent_sparklines_service`,
   `email_notify`, and embedded in generated CSS (`watch_renderer`) and generated Python
   (`notebook_export`). Docstrings say *"Don't change without updating chart_svg /
   share_card / EmbedDialog in lockstep"* — i.e. the duplication is a documented,
   accepted coupling. Note the PNG/GIF palette `(14,165,160)`/`(154,160,166)`/
   `(240,120,103)` in `replay_gif`/`share_card` is a **different** palette, not the same
   constant. A `belief_colors.py` would only help the hex group and can't reach the
   code-gen string literals. Defer.

7. **Vue view duplication** — `SimulationView.vue` / `SimulationRunView.vue` /
   `ReportView.vue` / `InteractionView.vue` / `MainView.vue`. ~300+ lines of shared
   scoped CSS and ~150 lines of shared `<script>` helpers (`addLog`,
   `left/rightPanelStyle` computeds, `toggleMaximize`, status text, data-load fetch
   chains). A composable + shared stylesheet would help, but it is behaviour-affecting,
   cannot be compile-verified for `.vue`, the panel-style/`viewMode` semantics vary per
   view, and these files are prime targets for the frontend cleanup agents. Defer to the
   frontend owner.

## Cross-cutting notes for other cleanup tasks

- **Dead-code / lint agent**: `backend/app/services/badge_service.py:68` has a
  pre-existing unused `from typing import ... Optional` import (`ruff F401`). I left it
  untouched to stay within the DRY scope — please remove it there.
- **Conflict-risk files I expect other agents to also edit**:
  - `frontend/src/views/{SimulationView,SimulationRunView,ReportView,InteractionView,MainView}.vue`
    — large shared CSS/JS; frontend-style/structure agent will likely touch these.
  - `backend/app/services/{slack,discord,email,telegram}_notify.py`,
    `webhook_service.py` — common target for any notification/refactor work.
  - `backend/app/services/{transcript,thread_formatter,trajectory_export,
    agent_sparklines_service,watch_renderer}.py` — the belief-math helpers; if another
    agent unifies `_avg_position`, coordinate so the bool-handling decision (item 2) is
    made once.
  - `backend/app/api/{feed,sitemap,watch}.py`, `webhook_service.py` — the
    `_resolve_base_url()` variants (item 5).
- **My applied edits are narrow** (two private-helper extractions inside
  `badge_service.py` and `event_logger.py`); they touch no public API, no constants
  other agents are likely to depend on, and no `.vue` / test / notify files, so overlap
  with other tasks should be minimal.
