# Round 2 — Task 05: Strengthen weak/escape-hatch types

Agent 05 of the round-2 from-scratch cleanup. Own isolated worktree.
Python-only pass focused on `backend/app/` (+ a wrong-type sweep across
`backend/wonderwall/`). No venv: verified with `ruff check` (global) and
hand-traced producer/consumer code. No mypy config exists in the repo, so every
new annotation was checked against how the value is actually produced and
consumed.

## Methodology

1. Inventoried every escape-hatch marker: `Any`, `Dict[str, Any]`, `List[Any]`,
   `Optional[Any]`, bare `object`, `# type: ignore`, `cast(...)`,
   untyped public signatures, `**kwargs: Any`, bare `Callable`.
2. Ran two AST sweeps for **genuinely-wrong** types:
   - functions with a non-`Optional` concrete return annotation that contain a
     `return None` / bare `return` (excluding generators);
   - functions whose body can **fall off the end** (no `return`/`raise` on all
     paths) yet are annotated to return a concrete type. A precise
     control-flow `terminates()` walker (handles `if/else`, `try/except/else/
     finally`, `with`, `while True`, `match`) eliminated the false positives
     from try/except-tailed functions.
3. For each surviving candidate, read the function + every call site to confirm
   the real type before changing anything.
4. Re-ran `ruff check` per changed file and diffed against `HEAD` to prove zero
   new lint errors.

## Inventory (counts, `backend/app`)

| Marker | Count | Disposition |
|---|---|---|
| `Dict[str, Any]` / `dict[str, Any]` | 483 | Mostly **honest** JSON/duck-typed boundaries — left (see below) |
| `List[Any]` / `list[Any]` | 1 | Left (genuine heterogeneous demographic row) |
| `Optional[Any]` | 6 | **Deferred** — all the `_safe_load_json` family (see below) |
| `# type: ignore` | 9 → 8 | 1 removed via generics; 7 are optional-dep imports; 1 legitimate |
| `cast(...)` | 0 | none in app |
| bare `Callable` | 0 | all already parameterized |
| untyped public signatures | several | strengthened the high-value ones |

### Why most `Dict[str, Any]` stay

Consistent with the round-1 finding: this codebase uses `Dict[str, Any]`
deliberately at real JSON / neo4j-property-bag / webhook-payload / IPC /
LLM-`response_format` boundaries, and already uses concrete generics where
shapes are uniform. The 483 count massively overstates *fixable* sites. The real
round-2 wins were a **wrong** return type, a removable `# type: ignore` via
generics, and untyped observability/trace plumbing.

## Findings

### Genuinely WRONG type (high value) — FIXED

- **`app/api/simulation.py:2200` `_get_report_id_for_simulation`** was annotated
  `-> str` but returns `None` on three paths (no reports dir → `None`; no
  matching reports → `None`; the trailing `except` → `None`) **and** returns
  `matching_reports[0].get("report_id")` which is itself `Optional[str]`. The
  docstring even says *"Returns: report_id or None"*. The single call site
  (`simulation.py:2347`) assigns the result straight into a dict, so
  `str | None` is fully compatible. → changed to `-> str | None`. (Round 1
  missed this one; the multi-line dir-walk body hid the `None` returns.)

### `# type: ignore` removed via generics — FIXED

- **`app/storage/neo4j_storage.py:83` `_call_with_retry`** was fully untyped
  (`func`, `*args`, `**kwargs`, no return) and ended in
  `raise last_error  # type: ignore` (the ignore masked `last_error: Optional`).
  Retyped generic: `Callable[..., _T], *args: Any, **kwargs: Any) -> _T`, and
  declared `last_error: Exception` (annotation-only). The loop runs
  `MAX_RETRIES = 3 > 0` times, so `last_error` is always bound before the
  post-loop `raise` — the `# type: ignore` is now unnecessary and was removed.
  Behavior-preserving (the raise path is reachable only after the `except`
  branch executed, which binds `last_error`). Return type `_T` is exactly the
  result of `func(*args, **kwargs)`, which is what all ~25 call sites rely on.

## APPLIED

| File | Change | Why |
|---|---|---|
| `app/api/simulation.py` | `_get_report_id_for_simulation -> str` ⇒ `-> str \| None` | WRONG type; returns None on 3 paths + `.get()` |
| `app/storage/neo4j_storage.py` | `_call_with_retry` → generic `Callable[..., _T] -> _T`; drop `# type: ignore`; `last_error: Exception` | untyped + removable ignore |
| `app/utils/trace_context.py` | `set(**kwargs: object) -> None`, `get(key: str, default: object=None) -> object`, `get_all() -> dict[str, object]`, `new_trace() -> str`, `clear() -> None`, `wrap_fn(fn: Callable[..., _R]) -> Callable[..., _R]` | untyped public statics; stored values are heterogeneous (`object`, not `Any`) |
| `app/utils/event_logger.py` | `emit -> None`, `unsubscribe -> None`, `close -> None`; `_push(event: Dict[str,Any]) -> None`; `get_recent/poll/read_new_events -> List[Dict[str,Any]]`; `write_simulation_event -> None` | untyped returns + bare `Dict`/`List[Dict]` tightened to `Dict[str, Any]` |
| `app/utils/logger.py` | `_ensure_utf8_stdout -> None`; `debug/info/warning/error/critical(msg: object, *args: object, **kwargs: Any) -> None` | match stdlib `logging.Logger` signature exactly |
| `app/utils/claude_code_client.py` | `_verify_claude_installed -> None`; `_emit_event(messages: List[Dict[str,str]], content: Optional[str], t0: float, *, error: Optional[BaseException]=None) -> None` | untyped private signature; params traced to call sites |
| `app/utils/llm_client.py` | `_emit_llm_event(... response: "Optional[ChatCompletion]"=None, error: Optional[BaseException]=None, temperature: float=0.7) -> None`; add `ChatCompletion` under `TYPE_CHECKING` | untyped; `response` is the openai SDK `ChatCompletion` (no runtime import — `TYPE_CHECKING` + quoted annotation) |
| `app/models/task.py` | `cleanup_old_tasks(...) -> None` | missing return annotation |

### Notes on the new types
- `**kwargs: Any` in `logger.py` is **not** a weakening — it mirrors the exact
  stdlib `logging.Logger.debug/info/...` signature (`exc_info`, `stack_info`,
  `extra`, `stacklevel`). `object` is used for the genuinely-heterogeneous
  `msg`/`*args`/`TraceContext` values, which is the *strong* "must-narrow" type,
  never `Any`.
- `TraceContext.get -> object`: stored values are heterogeneous (`round_num`/
  `agent_id` are `int`, the rest `str`). `object` is the honest strong type. All
  6 call sites combine the result with `or ''` / pass it through, which is valid
  on `object` — no runtime change, no narrowing breakage.
- `ChatCompletion` annotation is a quoted forward-ref because the module has no
  `from __future__ import annotations`; the `TYPE_CHECKING` import means zero
  runtime import cost and no new import cycle.

## DEFERRED

- **`_safe_load_json` family** (`Optional[Any]` × 6: `batch_status.py:116`,
  `platform_stats.py:96`, `outcome_distribution.py:112`, `platform_status.py:89`,
  `activity_feed.py:115`, `project_stats.py:110`). These wrap `json.load(fh)`,
  which legitimately returns any JSON value (dict / list / scalar / null);
  callers narrow with `isinstance(..., dict)` **or** rely on `or {}` / `.get()`.
  The honest strong type is `object`, but changing to `object` would require the
  non-narrowing `or {}` / `.get()` call sites to add narrowing — a real risk of
  introducing type friction with no runtime benefit. `Optional[Any]` here is an
  intentional "best-effort, caller narrows" boundary. **Left as-is.**
- **`embedding_service.py:137` `return results  # type: ignore`**: `results` is
  `List[Optional[List[float]]]` but the contract fills every slot before return;
  the function is `-> List[List[float]]`. Removing the ignore cleanly would
  require either a runtime assertion or restructuring that could change behavior
  if a provider returns a short vector batch. **Left** (legitimate escape hatch).
- **`neo4j_storage.py:101`-style** import `# type: ignore` and the 6 optional-dep
  import ignores (`duckdb`, `huggingface_hub`, `nashpy`, `numpy`, `httpx`,
  `yaml`) — these silence missing stubs for optional deps. Low value, left.
- **`backend/wonderwall/`**: ran the wrong-type fall-off-the-end sweep; **no**
  genuinely-wrong types surfaced. Per the vendored-fork rule (high-confidence
  only), made **no** changes there.
- **`task.py` `result`/`progress_detail: Dict[str, Any]`**: genuinely
  heterogeneous task-result payloads keyed by task type. A `TypedDict` would need
  coordination with the type-consolidation agent and per-task-type shapes.
  Left for that agent.

## CONFLICT_RISK

Low. Touches 8 files, all small surgical annotation edits (no logic changes, no
import-graph changes beyond two `typing`/`TYPE_CHECKING` additions). The only
file another agent is likely to also touch is `neo4j_storage.py` (largest
`Dict[str, Any]` count) — my change is confined to the `_call_with_retry`
signature + one import line, so a 3-way merge should be clean.

## VERIFICATION

- `ruff check` on every changed file: **0 new errors**. The 2 pre-existing
  `F541`/`E741` warnings in `neo4j_storage.py` (lines 251, 889) are untouched and
  predate this branch (confirmed by `git stash` baseline diff).
- Each new annotation traced to producers + all call sites (counts above).
- All new runtime-evaluated annotations are valid on Python 3.11
  (`str | None`, `dict[str, object]`, `Callable[..., _T]`); the one openai-SDK
  annotation is quoted + `TYPE_CHECKING`-guarded, so it never evaluates at
  runtime.
- No pydantic model field annotations were changed → no runtime validation
  behavior change.
