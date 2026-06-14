# Round 2 — Task 07 — Legacy / deprecated / fallback / back-compat code paths

Agent 07 of 8. Own worktree branch. Static analysis only (no venv/node_modules);
the integrator runs the full test + build at the end.

## Methodology

Independent from-scratch sweep of the **entire** tree (`backend/app/`,
`backend/wonderwall/` (vendored CAMEL fork), `backend/scripts/`, `backend/lib/`,
`backend/cli.py`, `backend/mcp_server.py`, `frontend/src/`).

Marker set searched (identifiers, comments, strings):
`legacy`, `deprecated`/`deprecate`, `obsolete`, `back-compat`/`backward[- ]compat`,
`"for backwards"`, `"no longer"`, `"remove later"`/`"remove this"`/`"to be removed"`,
`"kept for"`, `"old format"`/`"old layout"`, `_old`, `_v1`/`_v2`, `shim`, `polyfill`,
`superseded`, `"for now"`, `temporary`, `v1`/`v2`, plus structural patterns:
version/format `if/elif` dual-paths, always-on/always-off feature flags,
`if False:`/`if True:`/`and False` dead branches, format adapters/shims, and
name-based old-version functions/constants.

For each hit the verdict was decided by **grep-verifying live callers / persisted
data dependence / env-flag reachability** — never by the label alone.

Cross-checked against the round-1 report (`docs/cleanup/07-legacy.md`); my fresh
pass independently reproduced its conclusions and added new verification evidence
(MCP-server liveness of `search_graph`/`get_graph_statistics`; the
`browse_clusters` prompt still emits `search_graph`; `wait_for_processing` has two
live callers; `_FARCASTER_USERNAME` and the settings namespace import are provably
unused).

## Headline finding

**This codebase is genuinely clean of removable legacy code.** Every marker hit is
one of these intentional, must-keep categories:

1. **Persisted-data on-disk format fallbacks** — read/list/delete paths that still
   consume sim/report directories written by older runs (safety rule 1: keep).
2. **Runtime error / LLM fallbacks** — `try/except` and "LLM-failed → degrade"
   branches; live defensive code, not dead.
3. **Live multi-mode engine paths mislabeled "legacy"** — vendored Wonderwall's
   `DefaultPlatformType`/`SocialEnvironment` Twitter/Reddit paths are exercised by
   `backend/scripts/run_twitter_simulation.py` & `run_parallel_simulation.py`
   (safety rule 1: keep).
4. **Optional features / operator toggles** — webhook HMAC signing, gallery
   `verified=1` compat, `*_ENABLED` env flags (both states reachable, documented in
   `.env.example`).
5. **Live public-API contracts** — `search_graph` / `get_graph_statistics` are
   first-class **MCP server tools** (`backend/mcp_server.py`, `backend/app/api/mcp.py`),
   not merely report-agent redirects.
6. **Live frontend field aliases** — the `episodes` edge alias rendered by
   `GraphPanel.vue`.

**APPLIED: no source changes.** The two provably-dead micro-items found
(below) are author-documented intentional keeps whose removal is near-zero value
and would raise needless conflict with the imports/config agents; both are
DEFERRED with evidence.

## Inventory — every site, with LIVE/DEAD verdict + evidence

### A. Persisted-data on-disk format fallbacks — LIVE (protected by safety rule 1) → KEEP
| File:line | Site | Evidence |
|---|---|---|
| `backend/app/services/report_agent.py:3522,3581,3604,3630` | `ReportManager` get/list/delete handle new per-report **folder** layout *and* old flat `<id>.json`/`<id>.md` | Reads/deletes real user data on disk; old layout still produced before folder migration. |
| `backend/app/services/simulation_runner.py:1395-1409` | `# Fallback: legacy single file` → reads `actions.jsonl` when no per-platform `<platform>/actions.jsonl` | Persisted run state from older sims. |
| `backend/app/services/lineage_service.py:144-153` | `_scenario_for` falls back to state-level `simulation_requirement` | Older sims wrote the requirement onto state. |
| `backend/app/services/repro_export.py:250-291,414` | `_read_director_events` parses persisted `director_events` (list *or* dict shape) from sim dir | Reads on-disk sim artifacts. |
| `backend/app/storage/neo4j_schema.py:75-92` | Backfill `valid_at=created_at`, `kind='fact'` onto NULL legacy edges | Migrates real persisted edges in Neo4j; runs against live data. |
| `backend/wonderwall/social_platform/platform.py:1396-1413` | `interview_data` old-string vs new-dict isinstance dual-path | Vendored engine; handles two live input shapes (conservative — keep). |

### B. Runtime error / LLM-failure fallbacks — LIVE → KEEP
| File:line | Site | Evidence |
|---|---|---|
| `backend/app/services/ontology_generator.py:174-219` | Fallback Person/Organization entity types when LLM omits them | Runtime guard; always reachable. |
| `backend/app/services/graph_tools.py:586,1288-1530` | `_fallback_interview` (LLM-direct) when structured interview path unavailable | Live alternate path, exercised on failure. |
| `backend/app/utils/file_parser.py:10-53` | `_read_text_with_fallback` multi-encoding chain | Live decode strategy. |
| `backend/app/services/wonderwall_profile_generator.py:1171-1242` | Fallback persona profile on per-agent LLM failure | Live, written to disk in real time. |
| `backend/app/services/bibtex_service.py:72-199` | `_KEY_FALLBACK` / `_TITLE_FALLBACK` placeholders | Ensure valid BibTeX; live. |

### C. Live multi-mode / public-API paths mislabeled "legacy" → KEEP
| File:line | Site | Evidence |
|---|---|---|
| `backend/wonderwall/environment/env.py` (DefaultPlatformType / custom Platform) | "Legacy path" branches | Exercised by `run_twitter_simulation.py` / `run_parallel_simulation.py` (safety rule 1). |
| `backend/wonderwall/social_agent/agent.py:58,~461-501` | "legacy social-media workflow", "temporary solution" CAMEL memory note | Vendored upstream; live whenever `simulation=None` (Twitter/Reddit). |
| `backend/app/services/report_agent.py:1401-1434` | "Backward compatible legacy tools" redirect (`search_graph`→`quick_search`, `get_simulation_context`→`insight_forge`, `get_graph_statistics`, `get_entity_summary`, `get_entities_by_type`) | **LIVE.** The `browse_clusters` prompt at `report_agent.py:714` still instructs the model to use `search_graph`; the redirect catches that emission. `search_graph` & `get_graph_statistics` are also live **MCP tools** (`mcp_server.py:105,270`; `api/mcp.py:50`; debug routes `api/report.py:825,884`). Frontend keeps display badges `Step4Report.vue:629,635`. Safety rule 1: removable only as a SET with the prompt + badges → **DEFER**. |
| `backend/app/storage/graph_storage.py:wait_for_processing` ("Kept for API compatibility with Zep-era callers") | Abstract no-op for Neo4j | **LIVE** — called at `graph_builder.py:168` and `api/graph.py:484`. |
| `backend/app/storage/neo4j_storage.py:849` `ed["episodes"]=ed.get("episode_ids",[])` ("Legacy alias") | Edge field alias | **LIVE** — `GraphPanel.vue` renders `episodes`, never `episode_ids`. |

### D. Optional features / operator toggles — LIVE (both states reachable) → KEEP
| File:line | Site | Evidence |
|---|---|---|
| `backend/app/config.py:68,83,90,99,112,145,179,283` (+`ORACLE_SEED_ENABLED`,`MCP_AGENT_TOOLS_ENABLED`) | `*_ENABLED` env flags | Read from env, documented in `.env.example`; not always-on/off constants. |
| `backend/app/services/webhook_service.py:~86,~655-661` | HMAC signing omitted when `WEBHOOK_SECRET` unset; blank `WEBHOOK_EVENTS` fires on all | Optional-signing feature = the "backward-compatible" behavior itself. |
| `backend/app/services/gallery_filters.py:15,43` | `verified=1` query compat + `DEFAULT_LIMIT=50` | Active public-API contract for `GET /api/simulation/public`. |
| `backend/app/services/feed.py:14-19` | Atom 1.0 + RSS 2.0 both rendered | Intentional reader-parity feature. |
| `backend/app/services/frame_metadata.py:80-83` | `FRAME_VERSION="next"` (`"vNext"` legacy noted) | Single value, no dual code path. |
| `backend/app/utils/run_summary.py:30` | "Tracked for mixed / legacy setups" pricing rows | Additive lookup table; no branch. |

### E. Frontend "old format" / cosmetic-tombstone markers → KEEP
All verified live or harmless:
- `Step4Report.vue:765,967-992` — parses both old/new report header & platform-marker
  formats (consumes live report markdown that may use either) → KEEP.
- `Step4Report.vue:4542` "Legacy entity card styles for backwards compatibility" —
  CSS still applied to rendered cards → KEEP.
- `CountryPicker.vue:100`, `MainView.vue:102` (`stepNames = stepNamesEn // legacy ref`
  still used by `addLog`), `TemplateGallery.vue:137`, `TrendingTopics.vue:288`,
  `ExploreView.vue:1241`, `ZhWarningBanner.vue:98` — descriptive comments about prior
  visual states; the referenced code is live or the comment is pure prose.

### F. Provably-DEAD micro-items found — DEFERRED (see rationale below)
| File:line | Site | Verdict + evidence |
|---|---|---|
| `backend/app/api/settings.py:14` | `from ..services import webhook_service  # noqa: F401 — kept for namespace-style access` | **DEAD binding.** Zero `webhook_service.<attr>` access in the file; line 15 already imports the three needed funcs directly; no external module imports the binding from `api.settings`. The `# noqa` justification is contradicted by the code. Removal is behavior-neutral. **DEFERRED** — belongs to the unused-imports/config agent's surface; removing it here for ~0 value would only manufacture a merge conflict on a hot file. |
| `backend/app/services/frame_metadata.py:235` | `_FARCASTER_USERNAME = re.compile(...)` "Currently unused at runtime — kept here for the future... so the tests can re-import it" | **DEAD constant.** Zero usages in `backend/`, `frontend/`, or `backend/tests/` (the comment's "tests can re-import it" claim is false). **DEFERRED** — the author explicitly retained it as a documented placeholder for a planned "@operator on Farcaster" attribution surface; deleting a deliberate future-feature hook is a product/owner decision, not a clear-cut dead-code removal. |

## Ranked table

| Rank | Item | Action | Confidence |
|---|---|---|---|
| — | All Category A–E sites | KEEP (live / persisted-data / optional / vendored) | High |
| Med | report_agent legacy-tool redirect SET (1401-1434) + prompt:714 + Step4Report badges | DEFER (cross-cutting; prompt still emits `search_graph`; MCP-live names) | High it's live |
| Low | `settings.py:14` redundant namespace import | DEFER (unused-imports agent; conflict-avoidance) | High it's dead |
| Low | `frame_metadata.py:235` `_FARCASTER_USERNAME` | DEFER (documented future-use placeholder; owner call) | High it's dead |

## APPLIED

None. No source file modified. Rationale: the only provably-dead items are two
author-documented micro-keeps whose removal is near-zero value and would raise
conflict risk on files other agents own; correctness/behavior preservation and
conflict-avoidance outrank tidying two trivial lines.

## DEFERRED (with why)

1. **`report_agent.py:1401-1434` legacy-tool redirect set** — LIVE: `browse_clusters`
   prompt (`:714`) still tells the model to use `search_graph`, and `search_graph` /
   `get_graph_statistics` are live MCP tools. Removable only as a SET with the prompt
   rewrite + `Step4Report.vue:629,635` badge removal — a product decision (safety rule 1).
2. **`settings.py:14` redundant `webhook_service` namespace import** — provably dead but
   trivial; defer to the unused-imports/config agent to avoid a hot-file conflict.
3. **`frame_metadata.py:235` `_FARCASTER_USERNAME`** — provably unused, but a deliberately
   documented future-feature placeholder; deletion is an owner decision.

## CONFLICT_RISK

None from this agent (no source files changed). Documentation-only addition of this file.

## Verification

- `git status` clean at start; only `docs/cleanup/round2-07-legacy.md` added.
- No Python edited → no ruff delta (baseline ≈166 errors unchanged).
- No behavior change → pytest baseline (≈971 pass / 2 known-fail / 17 skip) unaffected.
