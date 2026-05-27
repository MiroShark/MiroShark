# Task 5 — Replace weak/loose types with strong, specific types

Branch worktree off `cleanup/code-quality-2026-05`. Python-only pass over
`backend/app/`, `backend/wonderwall/`, `backend/cli.py`, `backend/mcp_server.py`,
`backend/scripts/`. No pytest / uv (verified with `python3 -m py_compile` +
`ruff check` only).

## Summary

- **Strengthened: 32 annotations across 15 files**, all verified against real
  producer/consumer code.
- **Deferred: ~10 high-value-but-uncertain sites** recorded under NEEDS REVIEW.
- Net new lint errors introduced: **0** (per-file `ruff` delta vs `HEAD` is
  zero on every changed file; the handful of pre-existing `F541`/`E741`/`F821`
  warnings in these files are untouched and not at any changed line).
- All changed files compile under `python3 -m py_compile`. All new
  runtime-evaluated annotations (files without `from __future__ import
  annotations`) were independently confirmed to evaluate on Python 3.11
  (`Literal[...]`, `tuple[int, X, str | None]`, `Callable[[float], None]`,
  `dict[int, set[int]]`).

### Key finding about the codebase

This codebase is **already disciplined** about `Dict[str, Any]`: it is used
deliberately at genuine JSON / duck-typed boundaries (neo4j property bags,
webhook payloads, MCP tool args/results, IPC command args, country-pack JSON,
LLM `response_format`). Where shapes are uniform the author already uses
concrete generics (`surface_stats.py` → `Dict[str, int]`,
`webhook_service._final_consensus_from_trajectory` → `Optional[Dict[str,
float]]`, the `graph_tools.py` dataclasses). So the raw "~486 markers" count
massively overstates the number of *fixable* sites — most `Dict[str, Any]` are
honest. The real wins were: missing return annotations, bare un-parameterized
generics (`Dict`, `List[Dict]`, `set`, `tuple`, `list`), `Literal` for known
fixed string sets, and one genuinely **wrong** annotation (`LLMClient.chat`).

## Weak-type inventory by area

| Area | Pattern | Disposition |
|---|---|---|
| `app/utils/llm_client.py`, `claude_code_client.py` | factory return `None`; `chat()` mis-typed `-> str` | **Fixed** (highest value — wrong type) |
| `app/storage/` (graph_storage, neo4j_storage, community_builder) | bare `Callable`, missing `search` return, `List[Dict]`, `Optional[Dict]` | **Fixed** |
| `app/services/signal_service.py` | known string sets typed `str` | **Fixed** (`Literal`) |
| `app/services/simulation_ipc.py` | env-status `str`, missing `-> None` | **Fixed** (`Literal`) |
| `app/models/task.py` | bare `Dict`, `-> list`, missing `-> None` | **Fixed** |
| `app/services/report_agent.py`, `graph_builder.py` | bare `Callable`, worker `-> tuple` | **Fixed** (callback shapes differ by module — verified each) |
| `app/services/wonderwall_profile_generator.py` | worker `-> tuple` | **Fixed** |
| `wonderwall/social_agent/` (round_analyzer, agents_generator) | `List[Dict]`, `Dict[int, set]`, `-> List` | **Fixed** |
| notification services (slack/discord/telegram/email/webhook) | `Dict[str, Any]` payloads | **Honest — left as-is** (heterogeneous JSON; shared TypedDict is Task 2) |
| `app/services/platform_stats.py`, `country_registry.py`, `mcp_server.py`, `bibtex_service.py` | `Dict[str, Any]` / `Any` | **Honest — left as-is** (mixed value types, defensive coercion, recursive any-shape) |
| Flask route handlers (`app/api/*.py`) | missing return annotations | **Deferred** (Flask union returns; high conflict risk in 7000-line file) |

## Applied strengthenings (file:line — old → new + evidence)

### Highest value

1. **`app/utils/llm_client.py` `LLMClient.chat`** (`-> str` → `-> Optional[str]`).
   The body **returns `None`** when `response.choices[0].message.content is
   None` (reasoning models intermittently null out a turn — see the in-code
   comment). `chat_json` already guards `if response is None`. The old `-> str`
   was simply **wrong**. Also `response_format: Optional[Dict]` →
   `Optional[Dict[str, Any]]`.

2. **`app/utils/llm_client.py` factories** `create_llm_client`,
   `create_smart_llm_client`, `create_ner_llm_client` (no return → `->
   "LLMClient | ClaudeCodeClient"`). Each returns `LLMClient` OR
   `ClaudeCodeClient` depending on `LLM_PROVIDER`/`SMART_PROVIDER`. Added a
   `TYPE_CHECKING` import of `ClaudeCodeClient` (no runtime import; no cycle —
   `claude_code_client` does not import `llm_client`). String annotation used
   because the file has no `from __future__ import annotations`.

3. **`app/services/signal_service.py`** — `Literal`s for the documented API
   contract: `_DIRECTION_LABELS` value → `Literal["Bullish","Neutral","Bearish"]`;
   new alias `_RiskTier = Literal["low-risk","medium-risk","high-risk"]` applied
   to `_RISK_TIER_BY_HEALTH`, `_DEFAULT_RISK_TIER`, and `_resolve_risk_tier`
   return; `_pick_leader` → `Literal["bullish","neutral","bearish"]`. Evidence:
   the module docstring enumerates exactly these output strings, and the
   tie-break candidate tuple uses exactly these literal keys.

### Storage layer

4. **`app/storage/graph_storage.py` + `neo4j_storage.py`** —
   `add_text_batch`/`wait_for_processing` `progress_callback: Optional[Callable]`
   → `Optional[Callable[[float], None]]`. Evidence: `neo4j_storage` invokes
   `progress_callback(progress)` / `progress_callback(1.0)` with a single float,
   return unused.
5. **`search(...)`** abstract + concrete: missing return → `-> Dict[str, Any]`.
   Evidence: body builds `{"edges": [...], "nodes": [...], "query": str}` (mixed
   value types ⇒ `Any` is the correct value type).
6. **`app/storage/community_builder.py`** — `search`/`list_all` `-> List[Dict]`
   → `List[Dict[str, Any]]`; `get_detail -> Optional[Dict]` →
   `Optional[Dict[str, Any]]`. Added `Any` to the typing import. Evidence: all
   return `[dict(rec) ...]` / `dict(row)` over neo4j Records with mixed values.

### Services

7. **`app/services/graph_builder.py`** `add_text_batches`
   `progress_callback: Optional[Callable]` → `Optional[Callable[[str, float],
   None]]`. **Note the different shape** from the storage callback: this one is
   invoked `progress_callback("Chunk x/y done", current/total)` — `(str,
   float)`. Verified separately so I didn't apply the wrong arity.
8. **`app/services/report_agent.py`** — `plan_outline` &
   `_generate_section_react` `progress_callback` →
   `Optional[Callable[[str, int, str], None]]`. Evidence: every
   `progress_callback(...)` call in the file passes `(stage:str, pct:int,
   msg:str)`, and the public `generate_report` already declares exactly that
   type. The parallel worker `_generate_one(idx, section) -> tuple` →
   `(section: ReportSection) -> tuple[int, str, str]` (returns `(idx,
   section.title, content)`; `ReportSection.title: str`, `_generate_section_react
   -> str`).
9. **`app/services/wonderwall_profile_generator.py`** `generate_single_profile`
   `-> tuple` → `tuple[int, WonderwallAgentProfile, str | None]`. Evidence:
   returns `(idx, profile, None)` / `(idx, fallback_profile, str(e))`;
   `generate_profile_from_entity -> WonderwallAgentProfile`.
10. **`app/services/simulation_ipc.py`** — `_update_env_status(status: str)` →
    `Literal["alive", "stopped"]` (only callers pass those two; `check_env_alive`
    compares against `"alive"`). Added missing `-> None` to `start`, `stop`,
    `send_response`, `send_success`, `send_error`. Added `Literal` import.
11. **`app/services/oracle_seed.py`** `_rpc`/`call_tool`
    `params/arguments: Optional[Dict]` → `Optional[Dict[str, Any]]` (JSON-RPC
    params / MCP tool args).
12. **`app/services/simulation_manager.py`** `SimulationState.config_diff:
    Optional[Dict]` → `Optional[Dict[str, Any]]` (a config diff blob).

### Models

13. **`app/models/task.py`** — bare `Dict`/`-> list` everywhere parameterized:
    `result`, `metadata`, `progress_detail` → `Dict[str, Any]` /
    `Optional[Dict[str, Any]]`; `create_task`/`update_task`/`complete_task`
    params; `list_tasks -> list` → `List[Dict[str, Any]]` (returns
    `[t.to_dict() ...]`, and `to_dict -> Dict[str, Any]`); added `-> None` to
    `update_task`/`complete_task`/`fail_task`. Added `List` to import.

### Bundled sim engine (`wonderwall/`)

14. **`agents_generator.py`** `generate_agents_100w -> List` →
    `list[SocialAgent]` (`agent_graph = []` then `.append(SocialAgent(...))`;
    file has `from __future__ import annotations`).
15. **`round_analyzer.py`** — SQLite-row helpers `List[Dict]` → `List[Dict[str,
    Any]]` (`_get_recent_posts`, `_get_viral_posts`, `_get_posts_seen_by_agent`,
    `_build_posts_seen_from_actions`); `Dict[int, set]` → `Dict[int, set[int]]`
    (`_get_follow_graph` + `_build_posts_seen_from_actions` param — followee ids
    are agent ints); `update_trust_from_actions` → `-> None`.

## NEEDS REVIEW / not applied

1. **`webhook_service.py:505,672,786`, `discord/slack/telegram/email_notify.py`,
   `bibtex_service.py`: `state: Optional[Any]`** — Looks like a `SimulationState`
   but is **actually a `SimulationRunState`** (passed from
   `simulation_runner.py`). Confirmed `build_payload` reads
   `profiles_count`/`created_at`/`parent_simulation_id` via `getattr(...,
   default)` — attrs that **do not exist** on `SimulationRunState` and fall back
   to `state.json`. The function is intentionally duck-typed across two state
   classes; `Optional[Any]` is the *honest* type. **Annotating it as a concrete
   class would be wrong.** Would need a shared `StateLike` Protocol to fix
   correctly (Task 2 territory).
2. **`graph_tools.py:402,409` (`llm`/`fast_llm` properties) and
   `community_builder.py:56` (`_llm_client`)**: declared `-> LLMClient` but the
   factory can return `ClaudeCodeClient`. The accurate type is the union (now
   exposed by the factory annotations in step 2). Left as-is to avoid rippling
   `Optional[LLMClient]` annotations across many consumer files — and because
   `ClaudeCodeClient` is structurally interface-compatible (`chat`/`chat_json`),
   the narrow `LLMClient` is a safe understatement. **Tighten alongside Task 2's
   LLM-client type consolidation.**
3. **`agents_generator.py:352,394` `-> tuple[AgentGraph, dict]`** — the `dict`
   is `{agent_index: response["user_id"]}`. Key is clearly `int`, but the value
   (`user_id` from a platform `sign_up` response) couldn't be confirmed as `int`
   vs `str` with high confidence. Would need the `action.sign_up` response type.
4. **`app/api/simulation.py:155,1604` `-> tuple`** (`_get_simulation_id_or_400`,
   `_check_simulation_prepared`) — precise type is `tuple[str | None,
   tuple[flask.Response, int] | None]` but needs new `Response`/`Optional`/`Tuple`
   imports in a 7000-line file with high merge-conflict risk against other tasks.
   Deferred.
5. **Many service-layer `Dict[str, Any]` return shapes** (`platform_stats.compute_platform_stats`,
   `signal_service.compute_signal`, `webhook_service.build_payload`,
   `surface_stats.read_surface_stats` extension, `graph_tools.get_graph_statistics`)
   have fully-documented fixed shapes that are **ideal TypedDict candidates** but
   were **deliberately not converted** — the codebase has exactly one TypedDict
   today (`scripts/counterfactual_loader.py`) and introducing a fleet of new
   TypedDicts in `app/` is precisely the consolidation Task 2 owns. Converting
   them here would near-guarantee a merge conflict.
6. **Legitimate `# type: ignore` left in place** (16 total): untyped optional
   imports (`yaml`, `duckdb`, `httpx`, `nashpy`, `huggingface_hub`), fallback
   `X = None` re-binds in `scripts/run_parallel_simulation.py`, and two
   post-validation narrowings (`embedding_service.py:137`,
   `counterfactual_loader.py:48`). None are removable without real refactors.

## Cross-cutting notes (esp. Task 2)

- **Conflict-likely files with Task 2 (type consolidation):**
  `app/utils/llm_client.py` (I added the `LLMClient | ClaudeCodeClient` factory
  return + `TYPE_CHECKING` import — Task 2 will likely centralize this union /
  introduce a Protocol; coordinate so we don't both define it). `app/models/task.py`
  and `app/services/simulation_manager.py` (shared state models). The
  notification services share an undocumented webhook-payload shape — a
  `WebhookPayload` TypedDict is the obvious Task-2 consolidation and I
  intentionally did **not** create a parallel one.
- **Pre-existing issue worth flagging (not fixed):**
  `app/services/simulation_manager.py:294` uses `storage: 'GraphStorage' = None`
  as a forward-ref string but never imports `GraphStorage` (ruff `F821`). It's a
  string annotation so it doesn't break at runtime, but it's a latent
  weak/broken type. Out of scope for a surgical edit; flagging for Task 2.
- All edits prefer **reusing existing names** (existing `Literal` style from
  `agent_graph.py`, existing dataclasses, existing `Dict[str, Any]` convention)
  over inventing new shared types.
