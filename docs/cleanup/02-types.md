# Task 2 — Type definitions: inventory & consolidation

Branch: `cleanup/code-quality-2026-05` (isolated worktree). MODE = auto-apply
high-confidence, surface risky.

## Summary

- The repo uses **no Pydantic `BaseModel`s** of its own (the only `BaseModel`
  references are the vendored CAMEL `BaseModelBackend`). Real types are
  `@dataclass` (≈30 in MiroShark-owned code) and `str`-valued `Enum`s.
- Surveyed all dataclasses, enums, `TypedDict`s, and type aliases across
  `backend/app/`, `backend/scripts/`, `backend/tests/`, and the vendored
  `backend/wonderwall/`.
- **One genuine type duplication was found and consolidated**: a bare-constants
  `CommandType` class redefined in 3 run scripts, duplicating the canonical
  `CommandType(str, Enum)` in `app/services/simulation_ipc.py`.
- Several near-namesakes were examined and deliberately **left separate**
  because they model different concepts (status enums, `*Snapshot`/`*Record`
  round types, `EntityNode` vs `NodeInfo`). Rationale below.

## Type inventory + duplication findings (file:line)

### Enums (all `str, Enum` unless noted; all MiroShark-owned distinct lifecycles)
- `app/models/task.py:14` `TaskStatus`
- `app/models/project.py:26` `ProjectStatus`
- `app/services/simulation_manager.py:25` `SimulationStatus`
- `app/services/simulation_runner.py:34` `RunnerStatus`
- `app/services/report_agent.py:411` `ReportStatus`
- `app/services/simulation_ipc.py:25` `CommandType`, `:31` `CommandStatus`
- Vendored (do NOT touch): `wonderwall/social_platform/typing.py:17,81,88`
  `ActionType`, `RecsysType`, `DefaultPlatformType` (plain `Enum`).

These status enums share overlapping *values* (`running/completed/failed/...`)
but represent **independent state machines** (project vs task vs simulation vs
runner vs report vs IPC command). They are NOT the same concept — not merged.

### Dataclasses (MiroShark-owned)
- `app/services/simulation_runner.py:47,74,100` `AgentAction`, `RoundSummary`,
  `SimulationRunState`
- `app/services/graph_memory_updater.py:17` `AgentActivity`
- `app/services/simulation_config_generator.py:52,84,114,133,167`
  `AgentActivityConfig`, `TimeSimulationConfig`, `EventConfig`, `PlatformConfig`,
  `SimulationParameters`
- `app/services/graph_tools.py:24,54,78,135,207,269,320` `SearchResult`,
  `NodeInfo`, `EdgeInfo`, `InsightForgeResult`, `PanoramaResult`,
  `AgentInterview`, `InterviewResult`
- `app/services/entity_reader.py:13,42` `EntityNode`, `FilteredEntities`
- `app/services/graph_builder.py:21` `GraphInfo`
- `app/services/agent_mcp_tools.py:48` `MCPServerSpec`
- `app/services/report_agent.py:421,441,464` `ReportSection`, `ReportOutline`,
  `Report`
- `app/services/wonderwall_profile_generator.py:30` `WonderwallAgentProfile`
- `app/services/simulation_ipc.py:39,64` `IPCCommand`, `IPCResponse`
- `app/services/simulation_manager.py:46` `SimulationState`
- `app/models/project.py:36` `Project`, `app/models/task.py:23` `Task`
- `app/storage/reasoning_trace.py:34` `_StepRecord`
- `scripts/round_memory.py:134` `RoundRecord`
- `scripts/market_media_bridge.py:23,68` `MarketSnapshot`, `SentimentSnapshot`
- `scripts/mcp_agent_bridge.py:57,64` `MCPCallRequest`, `MCPCallResult`
- Vendored (do NOT touch): `wonderwall/.../base.py:362` `SimulationConfig`,
  `wonderwall/.../polymarket/amm.py:32` `TradeResult`,
  `wonderwall/.../round_analyzer.py:28` `RoundSnapshot`,
  `wonderwall/.../belief_state.py:25` `BeliefState`,
  `wonderwall/.../config/user.py:23` `UserInfo`,
  `wonderwall/.../config/neo4j.py:18` `Neo4jConfig`,
  `wonderwall/.../env_action.py:21,39` `ManualAction`, `LLMAction`.

### TypedDict / type aliases
- `scripts/counterfactual_loader.py:20` `CounterfactualSpec(TypedDict)` — unique.
- Module-level aliases are all `PROMPTS: dict[str, str]` locale tables plus
  small `tuple[str, ...]` column lists (`trajectory_export.py:45`,
  `notebook_export.py:83`, `archive_service.py:506`) and a `dict[str,str]`
  color map (`agent_sparklines_service.py:62`). None duplicated.

### Duplication found
- **`CommandType` redefined as a bare-constants class** in:
  - `scripts/run_twitter_simulation.py:149`
  - `scripts/run_reddit_simulation.py:159`
  - `scripts/run_parallel_simulation.py:285`

  All three were byte-identical (`INTERVIEW/BATCH_INTERVIEW/CLOSE_ENV` →
  `"interview"/"batch_interview"/"close_env"`) and duplicate the canonical
  `CommandType(str, Enum)` at `app/services/simulation_ipc.py:25`.

## Applied consolidations

### Removed 3 duplicate `CommandType` definitions → import canonical enum
- **What**: Deleted the local `class CommandType` constants block in
  `run_twitter_simulation.py`, `run_reddit_simulation.py`,
  `run_parallel_simulation.py` and replaced each with
  `from app.services.simulation_ipc import CommandType`.
- **Canonical location**: `app/services/simulation_ipc.py` (`CommandType`,
  already the producer side used by `IPCCommand`/`SimulationIPCClient`).
- **Why safe**:
  - The canonical enum is `str, Enum`, so `CommandType.INTERVIEW == "interview"`
    is `True`. All usages are `command_type == CommandType.X` where
    `command_type = command.get("command_type")` (a plain JSON string), so
    comparison semantics are byte-for-byte preserved. Verified at runtime:
    `'interview' == CommandType.INTERVIEW` → `True` (and the other two members).
  - The scripts already import other `app.services.*` / `app.utils.*` modules
    via the same `sys.path.insert(_backend_dir)` setup, so the import path is
    an established pattern, not new.
  - `simulation_ipc.py` imports only stdlib + `app.utils.logger` (no heavy
    deps), so importing it from a standalone script is cheap and cannot fail at
    import time on a machine that can already run the scripts.
- **Verification**: `python3 -m py_compile` passes for all 3 scripts +
  `simulation_ipc.py`; `ruff check` introduces no new rule classes (see note
  below); repo grep confirms no remaining script-local `CommandType` class.

## NEEDS REVIEW / not-applied (file:line + rationale)

1. **Status-string literals scattered across notify/render services**
   (`app/services/watch_renderer.py:726-734`, `discord_notify.py:247,281-283`,
   `slack_notify.py:156-158,253`, `email_notify.py:314-316,383,497`,
   `telegram_notify.py:216-218,307-313`, `api/simulation.py:2625`,
   `services/platform_stats.py:30`). These compare bare strings like
   `"completed"/"failed"/"running"` against status payloads that originate from
   **several different enums** (SimulationStatus / RunnerStatus / ReportStatus)
   and from serialized JSON. Replacing them with a single shared enum is a
   behavior-touching, cross-module change with import-cycle risk (notify
   services would need to import service-layer enums) — out of scope for a
   surgical type pass. Flag to Task 5 (weak-types).

2. **`IPCHandler` / `UnicodeFormatter` / `MaxTokensWarningFilter` duplicated
   across run scripts** (`run_twitter_simulation.py:63,80,156`,
   `run_reddit_simulation.py:73,90,166`, `run_parallel_simulation.py:119` +
   `ParallelIPCHandler:291`). These are duplicated *classes*, but they are
   behavioral handlers/loggers (not pure type/data definitions) and the
   `IPCHandler` bodies diverge by platform (twitter vs reddit vs parallel). This
   is logic dedup, not type consolidation → defer to **Task 1 (dedup)**. Note:
   the IPC dir constants (`IPC_COMMANDS_DIR`/`IPC_RESPONSES_DIR`/
   `ENV_STATUS_FILE`) sitting next to the removed `CommandType` are likewise
   triplicated and belong to Task 1.

3. **`EntityNode` (`entity_reader.py:13`) vs `NodeInfo` (`graph_tools.py:54`)**
   share 5 fields (`uuid/name/labels/summary/attributes`) but differ: `EntityNode`
   carries `related_edges`/`related_nodes` + `get_entity_type()` and is the
   graph-read domain object (used by profile-gen & config-gen); `NodeInfo` is a
   lightweight tool-facing view with `to_text()`. They live in disjoint
   subsystems and never interconvert. Merging is plausible but would couple two
   subsystems and risk a cycle — not "clearly the same concept". Left separate.

4. **`AgentAction` (`simulation_runner.py:47`) vs `AgentActivity`
   (`graph_memory_updater.py:17`)** both describe a platform action
   (`platform/agent_id/agent_name/action_type/action_args/round_num/timestamp`).
   `AgentAction` adds `result`/`success` + `to_dict`; `AgentActivity` adds
   `to_episode_text()` (NER-oriented natural-language rendering). Same *shape*,
   different *purpose* (run-state record vs graph-memory episode source). A
   shared base could be justified but is a judgement call with behavior surface
   — surfaced, not applied.

## Cross-cutting notes for other tasks

- **Task 1 (dedup)**: The three `run_*_simulation.py` scripts share large
  duplicated blocks — `IPCHandler`/`ParallelIPCHandler`, `UnicodeFormatter`,
  `MaxTokensWarningFilter`, and the `IPC_*`/`ENV_STATUS_FILE` constants. I only
  removed the `CommandType` type dup; the rest is logic/constant dedup in your
  lane. **Likely merge conflict**: all three scripts now have a new
  `from app.services.simulation_ipc import CommandType` line where the old class
  block was — coordinate if you refactor that region.
- **Task 4 (cycles)**: My change makes `scripts/run_*` import
  `app.services.simulation_ipc`. Scripts are leaf entry points (nothing imports
  them) and `simulation_ipc` is a low-level module, so this introduces **no new
  cycle**. If you extract a shared IPC helper, keep `CommandType` in
  `simulation_ipc` (or a sibling) to avoid a scripts→services→scripts loop.
- **Task 5 (weak-types)**: Best targets are the bare status-string comparisons
  (NEEDS REVIEW #1) and the `action_type: str` fields on `AgentAction`/
  `AgentActivity`/`ManualAction` that mirror the vendored
  `wonderwall.ActionType` enum but stay stringly-typed at the MiroShark
  boundary.

## Files changed
- `backend/scripts/run_twitter_simulation.py`
- `backend/scripts/run_reddit_simulation.py`
- `backend/scripts/run_parallel_simulation.py`
