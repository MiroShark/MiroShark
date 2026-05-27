# Task 7 — Legacy / superseded / backward-compat code paths

## Summary

I hunted the full backend (`backend/app`, `backend/wonderwall`, `backend/cli.py`,
`backend/mcp_server.py`, `backend/scripts`) and frontend (`frontend/src`) for the
marker set (`deprecat`, `legacy`, `backward`, `back-compat`, `superseded`,
`no longer`, `_old`, `_legacy`, `shim`, `polyfill`, `for now`, `temporary`,
`v1`, version-branching, commented-out replaced code, always-on/off env flags).

**Finding: this codebase is genuinely clean of removable legacy code.** Nearly
every match is one of four intentional categories that the task brief tells us
to KEEP:

1. **Data-format fallbacks for persisted user data** — read paths that handle
   sim/report directories written by older runs that may still exist on disk.
2. **Live multi-mode engine paths mislabeled "legacy"** — the bundled Wonderwall
   engine supports several construction styles; the ones commented "legacy" are
   the ones MiroShark's own scripts actively use.
3. **Optional features** — webhook HMAC signing (off by default), gallery
   `verified=1` filter compat, configurable `*_ENABLED` env flags.
4. **Live frontend field aliases** — e.g. the `episodes` edge field the graph
   panel renders.

Only **one** zero-risk change was applied: removal of a stale tombstone comment
in the frontend that documented an already-completed removal. No Python source
was modified.

## Applied removals

| File:line | What | Why singular path is now correct |
|---|---|---|
| `frontend/src/components/Step4Report.vue:3340` | Removed the dangling comment `/* Legacy toggle-raw removed - using unified .action-btn */` inside the `<style>` block | The code it referenced was already deleted in a prior change; the comment is pure noise (a tombstone), not a code path. Removing it leaves the unified `.action-btn` styling as the single path with no dead reference. Change is inside a CSS `<style>` block — cannot affect JS/template behavior. |

Diff: 1 file, -2 lines.

## Legacy/fallback findings investigated — KEPT (intentional, NOT legacy)

### Persisted-data format fallbacks (cannot prove no old on-disk data exists → KEEP)
- `backend/app/services/report_agent.py:3522,3581,3604,3630` — `ReportManager`
  read/list/delete handle both the new per-report **folder** layout and the old
  flat `<id>.json` / `<id>.md` files. These read/delete real user data on disk;
  removing them would orphan reports created before the folder migration.
- `backend/app/services/simulation_runner.py:1392-1408` — `_scan_jsonl_raw`
  falls back to a single `actions.jsonl` when no per-platform
  `<platform>/actions.jsonl` files exist. Reads persisted run state from older
  sims. KEEP.
- `backend/app/services/lineage_service.py:144-153` — `_scenario_for` reads the
  scenario from `simulation_config.json`, then falls back to the state-level
  `simulation_requirement` "when older sims wrote the requirement onto state."
  Persisted-data fallback. KEEP.

### Live multi-mode engine paths (labeled "legacy" but actively used → KEEP)
- `backend/wonderwall/environment/env.py:126-179` — the "Legacy path:
  DefaultPlatformType enum" and "Legacy path: custom Platform instance" are the
  paths **`backend/scripts/run_twitter_simulation.py` and
  `run_parallel_simulation.py` actually exercise** via
  `wonderwall.make(platform=wonderwall.DefaultPlatformType.TWITTER/REDDIT, ...)`
  (Twitter/Reddit sims). The "New path: SimulationConfig" is used for Polymarket.
  Both live. Removing the "legacy" branch would break Twitter/Reddit simulation.
- `backend/wonderwall/social_agent/agent.py:111-119` — "Legacy path: social
  media" (`SocialEnvironment`/`SocialAction`) is the path taken whenever
  `simulation=None`, i.e. the Twitter/Reddit engine entry above. Live.
- `backend/wonderwall/social_agent/agent.py:463,502` — "NOTE: this is a temporary
  solution" — vendored-engine workaround for CAMEL memory behavior; live code.
- Vendored `backend/wonderwall/` is a bundled sim engine (oasis/CAMEL-style). Its
  TODOs and public multi-entry API are out of scope for legacy removal.

### Intentional optional features (graceful degradation / config → KEEP)
- `backend/app/services/webhook_service.py:82` — webhook HMAC signing is omitted
  when `WEBHOOK_SECRET` is unset; "backward compatible" = the optional-signing
  feature itself. KEEP (matches the brief's "intentional graceful-degradation").
- `backend/app/services/gallery_filters.py:15,43` — `verified=1` query-param
  compat and the `DEFAULT_LIMIT=50` "legacy clients keep prior behaviour" are an
  active public-API contract for `GET /api/simulation/public`. KEEP.
- `backend/app/config.py` `*_ENABLED` env flags (`RERANKER_ENABLED`,
  `GRAPH_SEARCH_ENABLED`, `ENTITY_RESOLUTION_ENABLED`,
  `CONTRADICTION_DETECTION_ENABLED`, `WEB_ENRICHMENT_ENABLED`,
  `LLM_PROMPT_CACHING_ENABLED`, `ENABLE_SITEMAP`, `ORACLE_SEED_ENABLED`,
  `MCP_AGENT_TOOLS_ENABLED`, etc.) — real operator toggles with both states
  reachable (documented in `.env.example`). Not always-on/off dead switches.

### "Superseded" = a live feature, not dead code → KEEP
- `backend/app/storage/contradiction_detector.py`,
  `backend/app/storage/search_service.py:188`,
  `backend/app/storage/neo4j_storage.py:593,628`, `backend/mcp_server.py:134` —
  "superseded edges" is the Graphiti-style temporal edge-invalidation FEATURE
  (edges get `invalid_at`/`expired_at` when contradicted; `include_invalidated`
  surfaces them). Live functionality, not legacy code.

### Live frontend field alias → KEEP
- `backend/app/storage/neo4j_storage.py:851` — `ed["episodes"] = ed.get("episode_ids", [])`
  is labeled "Legacy alias" but `frontend/src/components/GraphPanel.vue`
  (lines 220-258) renders `loop.episodes` / `selectedItem.data.episodes`, never
  `episode_ids`. The alias is the field the frontend reads. KEEP.

### Stale-but-functional / no-op (left as-is)
- `backend/app/services/frame_metadata.py:80-83` — `FRAME_VERSION = "next"` is a
  single value; the comment merely notes the spec's old `"vNext"` literal. No
  dual code path.
- `backend/app/utils/run_summary.py:30` — "Tracked for mixed / legacy setups" is
  a pricing-table lookup with current entries; no branch.
- `frontend/src/components/Step3Simulation.vue:2090` —
  `.action-btn.secondary { /* inherits */ }` is an empty no-op rule but the
  `action-btn secondary` class is applied to ~10 live template buttons; the rule
  documents intent. Removing it changes nothing and isn't a dead path. Left.
- `frontend/src/views/MainView.vue:99` — `const stepNames = stepNamesEn // legacy
  ref` is still referenced at lines 174/186 (`addLog`). Not dead; removing it
  would break those handlers. (Minor i18n smell — those two log lines are always
  English — but that's a behavior nuance, not legacy-removal scope.) Left.

## NEEDS REVIEW / not-applied

1. **`backend/app/services/report_agent.py:1401-1433` — "Backward compatible
   legacy tools (internally redirected to new tools)".** The agent's
   `_execute_tool` still handles `search_graph`, `get_graph_statistics`,
   `get_entity_summary`, `get_simulation_context`, `get_entities_by_type` even
   though the **advertised** tool schema (lines 1178-1261) no longer lists them.
   - Evidence it *could* be dead: the LLM is never told these tools exist.
   - Evidence it is NOT safely removable:
     (a) the `browse_clusters` tool-description prompt at line 714 still tells
         the model to "drill into specific facts with **search_graph** /
         panorama_search / quick_search", so the model can still emit
         `search_graph`; the redirect catches that hallucination.
     (b) `frontend/src/components/Step4Report.vue:629,635` keeps display
         badges (`get_graph_statistics`, `get_entities_by_type`) for these names
         in report tool-call logs.
     (c) Overlaps Task 6 — it is also a defensive guard against bad LLM tool
         names.
   - Recommendation: if removed, also fix the prompt at line 714 and the
     frontend `toolConfig` entries together. Deferred as risky / cross-cutting.

2. **`backend/app/api/report.py:824-919` — debug tool endpoints**
   (`POST /tools/search`, `POST /tools/statistics`). Explicitly labeled "Tool
   Call Endpoints (for debugging)". Registered Flask routes, not consumed by the
   frontend, not in `backend/openapi.yaml`. They are an intentional ops/debug
   surface rather than superseded legacy, and removing registered routes exceeds
   the "prove dead" bar. Deferred.

## Cross-cutting notes (overlap with other tasks)

- **Overlap with Task 6 (defensive try/except):** the report_agent legacy-tool
  redirect block (finding #1) doubles as a defensive guard against LLM
  hallucinated tool names. Per the brief, when a fallback is try/except-shaped or
  defensive, defer — done.
- **Overlap with Task 3 (unused code):** if Task 3 proves `graph_tools`
  methods `get_entities_by_type` / `get_entity_summary` / `get_simulation_context`
  unused, that would strengthen the case to also drop the report_agent redirects
  (#1) and the report.py debug endpoints (#2). They should be evaluated together.
- **Likely conflict files** (other agents may also touch):
  - `backend/app/services/report_agent.py` (large, central; Tasks 3/6 likely
    touch it).
  - `frontend/src/components/Step4Report.vue` (I edited the `<style>` block only,
    a comment line — low conflict surface).
  - `backend/app/config.py` (env flags — Task on config/unused may touch).
