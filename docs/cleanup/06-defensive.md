# Task 6 — Defensive code / try-except cleanup

Mode: **auto-apply high-confidence, surface risky.** Highest-risk task; bar for
"high confidence" set deliberately very high. When in doubt → NEEDS REVIEW.

## Summary

This is a **deliberately defensive codebase**. Of ~898 `except` handlers in
`backend/` (AST count over `.py`, excluding `.venv`/`__pycache__`), the vast
majority guard genuinely fallible operations: file/PDF/JSON I/O, LLM/openai
responses, neo4j/network calls, subprocess, encoding detection, parsing of
external or stored data, and intentional best-effort observability that "must
never break the agent." The frontend's empty `catch` blocks all guard
`localStorage`, `document.execCommand`, or network calls.

After examining every category of swallow/continue/re-raise handler and a wide
sample of individual sites across 15+ files, **only one** handler met the
high-confidence bar for removal: a redundant `except Exception: raise` inside a
neo4j retry loop that does nothing the handler's absence wouldn't do.

- **Applied removals: 1**
- **Deferred (NEEDS REVIEW / intentionally kept): the rest** — 173 swallow/continue
  handlers (132 `pass`, 41 `continue`) plus ~41 log-and-continue, all of which
  guard real I/O / external data / documented graceful degradation.

## Taxonomy of try/except blocks (backend, AST-derived)

| Category | Count | Disposition |
|---|---|---|
| `except …: pass` (body is only `pass`) | 132 | KEEP — all guard I/O, JSON decode, OSError, optional imports, or best-effort observability |
| `except …: continue` (body is only `continue`) | 41 | KEEP — all guard parse/convert of stored/external data inside loops |
| `except …: raise` (bare re-raise, redundant) | 1 → 0 | **REMOVED** (the one applied change) |
| log-and-continue / log-and-return-None | ~41 | KEEP — best-effort with diagnostics; not bug-hiding |
| other (catch + handle: fallback, retry, error response, finally cleanup, etc.) | ~684 | KEEP — out of scope or genuine handling |
| **Total handlers** | **~898** | |

Frontend (`frontend/src/`): 6 empty `catch (_) {}` sites — all guard
`localStorage` (private-browsing throws), `document.execCommand('copy')`, or an
`await listSimulations()` network call. All KEEP.

## Applied removals

### 1. `backend/app/storage/neo4j_storage.py:100-101` — redundant bare re-raise

`_call_with_retry()` retries on transient neo4j errors. It had a second handler
that caught everything else only to re-raise it unchanged:

```python
# before
for attempt in range(self.MAX_RETRIES):
    try:
        return func(*args, **kwargs)
    except (TransientError, ServiceUnavailable, SessionExpired) as e:
        last_error = e
        wait = self.RETRY_DELAY_BASE * (2 ** attempt)
        logger.warning(...)
        time.sleep(wait)
    except Exception:
        raise          # <-- redundant
raise last_error  # type: ignore
```

```python
# after
for attempt in range(self.MAX_RETRIES):
    try:
        return func(*args, **kwargs)
    except (TransientError, ServiceUnavailable, SessionExpired) as e:
        last_error = e
        wait = self.RETRY_DELAY_BASE * (2 ** attempt)
        logger.warning(...)
        time.sleep(wait)
raise last_error  # type: ignore
```

**Why safe:** the only handler that *does* anything is the transient-error
retry. `except Exception: raise` re-raises a non-transient exception unchanged
— exactly what happens if no handler exists. Behavior is identical: transient →
retry, anything else → propagate immediately out of the loop. No error hiding
introduced (the exception still propagates). No tests reference
`_call_with_retry`/`TransientError`/retry behavior (grepped `backend/tests/`).
`py_compile` + `ruff check` clean (the 2 ruff warnings ruff reports on this file
— f-string-without-placeholder at L247, ambiguous `l` at L885 — are pre-existing
and unrelated; verified present at HEAD).

## NEEDS REVIEW / not applied (the bulk)

None of the following were applied. They are listed by why they are *kept* (not
because they're necessarily ideal, but because removing them would hide an error
or change observable behavior — outside this task's high-confidence bar).

### KEEP — guard file / JSON / encoding I/O (largest group)
Reading/writing sim artifacts and decoding stored or uploaded data. Removing
these would crash request handlers / runners on a corrupt or missing file.
Representative sites:
- `app/api/simulation.py:7334, 7376, 9437, 10078, 10529` — `open(...) + json.load/dump` of `quality.json`, `resolution.json`, interview transcripts, graph cache.
- `app/api/simulation.py:3724, 9225, 9868` (continue) — `json.loads` per-line of `events.jsonl`.
- `app/api/observability.py:203, 269, 328` (continue) — `json.JSONDecodeError` per JSONL line.
- `app/utils/file_parser.py:29 (UnicodeDecodeError), 46`, `app/utils/event_logger.py:77, 162, 180, 196, 203, 216, 233, 315` — encoding detection + JSONL event log read/write.
- `app/utils/url_fetcher.py:47 (socket.gaierror), 75, 82 (JSONDecodeError)` — network fetch + decode of external responses.
- `app/utils/run_summary.py:124`, `app/services/simulation_config_generator.py:567`, `report_agent.py:1983, 2008, 3125`, `simulation_runner.py:1384, 1401` — `json.JSONDecodeError` on stored/LLM data.
- `app/services/{share_card,dkg_publisher,replay_gif,waybackclaw_publisher,sitemap,simulation_ipc}.py` (`OSError` sites) — filesystem writes/reads, IPC pipes.
- `app/services/sitemap.py:129` — `datetime.strptime` on `state.json` timestamps (`ValueError`).
- All `scripts/run_*_simulation.py`, `scripts/belief_integration.py`, `scripts/*` — JSONL/JSON file I/O and run orchestration.

### KEEP — guard parse/convert of stored/external/LLM data (arithmetic & casts)
`int()` / `float()` / division over values pulled from parsed JSON or LLM
tool-call args. These raise `ValueError`/`TypeError`/`ZeroDivisionError` on
malformed data and are the intended guard:
- `app/api/simulation.py:412` — `int(yes_range[...])` from parsed market JSON.
- `wonderwall/social_agent/round_analyzer.py:589` — `int(target_id)` from LLM tool-call args.
- `app/services/platform_stats.py:162, 409`, `chart_svg.py:137, 406`, `transcript.py:119, 186, 199`, `thread_formatter.py:164`, `peak_round.py:106`, `repro_export.py:189`, `trajectory_export.py:154`, `agent_sparklines_service.py:103, 183, 191`, `settings.py:212`, `bibtex_service.py:175` — numeric/format conversions over snapshot/record data.

### KEEP — `list.remove(...)` idiom (`except ValueError: pass`)
- `app/api/simulation.py:281, 292` — `order.remove(key)` in an LRU cache; `ValueError` means "not present". Idiomatic remove-if-present; removing the guard would crash on a cache miss. (Pure/local, but the swallow IS the intended semantics, so not removable without behavior change.)

### KEEP — optional-import / hardware-capability guards
- `app/storage/reranker_service.py:56` — `import torch; torch.cuda.is_available()`; the comment documents that torch can hang/fail probing devices, falls back to CPU.
- `wonderwall/environment/env.py:113` — `ImportError` optional-import guard.

### KEEP — documented best-effort observability ("never breaks the agent")
Event emission to `events.jsonl` and decision/LLM-call telemetry; explicitly
designed to degrade silently so the sim keeps running:
- `wonderwall/social_agent/agent.py:236, 249 (finally), 286, 295`, `agent_graph.py:207`, `round_analyzer.py:359, 383, 405, 466, 485, 592`, `belief_state.py:454`.
- `app/services/{simulation_runner,webhook_service,oracle_seed,graph_memory_updater,surface_stats,platform_stats,...}.py` best-effort sites.
- `scripts/action_logger.py:237`, `scripts/director_events.py:36, 113, 120`, `scripts/mcp_agent_bridge.py:209`.

### KEEP — process / signal / async lifecycle
- `app/services/simulation_runner.py:1153` — `ProcessLookupError` (process already gone on kill).
- `scripts/run_*_simulation.py` — `asyncio.TimeoutError`, `SystemExit` around the simulation main loop (intentional control-flow + shutdown handling).

### KEEP — frontend browser-API / network guards
- `frontend/src/i18n.js:12, 32, 38, 56` — `localStorage` access (throws when storage is disabled/private mode).
- `frontend/src/components/EmbedDialog.vue:3691` — `document.execCommand('copy')`.
- `frontend/src/views/ComparisonView.vue:287` — `await listSimulations()` HTTP call.

### Riskiest items deliberately deferred
The broad `except Exception: pass` sites in `simulation.py` and
`simulation_runner.py` that wrap multi-line bodies (e.g. `7334`, `10078`,
`simulation_runner.py:375, 723, 1683`) are the most tempting to tighten — but
each wraps real file/JSON I/O and several are on the hot request path. A future
narrowing pass could replace `except Exception` with the specific
`(OSError, json.JSONDecodeError)` and add a `logger.debug`, but that is a
behavior-adjacent change beyond this task's high-confidence bar and was left for
human review.

## Cross-cutting notes

- **Files likely to conflict with other cleanup tasks:** `backend/app/api/simulation.py`
  (touched here only by analysis, not edited, but it's the giant hot file every
  task crosses) and `backend/app/storage/neo4j_storage.py` (the one edited file —
  any task touching neo4j storage or that file's pre-existing ruff warnings at
  L247/L885 will overlap).
- **Pre-existing lint not touched:** `neo4j_storage.py` L247 (f-string without
  placeholder) and L885 (ambiguous variable name `l`) — left as-is per the
  "don't touch unrelated code" rule.
- **No error-hiding introduced.** The single removal makes a non-transient
  exception propagate exactly as before.
