# Observability & Debugging

<sup>English · [中文](OBSERVABILITY.zh-CN.md)</sup>

MiroShark includes a built-in observability system with real-time visibility into every LLM call, agent decision, graph build step, and simulation round.

## Debug panel

Press **Ctrl+Shift+D** anywhere in the UI to open the debug panel. Four tabs:

| Tab | What it shows |
|---|---|
| **Live Feed** | Real-time SSE event stream — every LLM call, agent action, round boundary, graph build step, and error. Color-coded, filterable by platform/agent/text, expandable for full detail. |
| **LLM Calls** | Table of all LLM calls with caller, model, input/output tokens, latency. Click to expand full prompt and response (when `MIROSHARK_LOG_PROMPTS=true`). Aggregate stats at top. |
| **Agent Trace** | Per-agent decision timeline — what the agent observed, what the LLM responded, what action was parsed, success/failure. |
| **Errors** | Filtered error view with stack traces. |

## Event stream

All events are written as append-only JSONL:

- `backend/logs/events.jsonl` — global (all Flask-process events)
- `uploads/simulations/{id}/events.jsonl` — per-simulation (includes subprocess events)

### SSE endpoint

```
GET /api/observability/events/stream?simulation_id=sim_xxx&event_types=llm_call,error
```

Returns `text/event-stream` with live events. The debug panel uses this automatically.

### REST endpoints

```
GET /api/observability/events?simulation_id=sim_xxx&from_line=0&limit=200
GET /api/observability/stats?simulation_id=sim_xxx
GET /api/observability/llm-calls?simulation_id=sim_xxx&caller=ner_extractor
```

## Event types

| Type | Emitted by | Data |
|---|---|---|
| `llm_call` | Every LLM call (NER, ontology, profiles, config, reports) | model, tokens, latency, caller, response preview |
| `agent_decision` | Agent `perform_action_by_llm()` during simulation | env observation, LLM response, parsed action, tool calls |
| `round_boundary` | Simulation loop (start/end of each round) | simulated hour, active agents, action count, elapsed time |
| `graph_build` | Graph builder lifecycle | phase, node/edge counts, chunk progress |
| `error` | Any caught exception with traceback | error class, message, traceback, context |

## Configuration

```bash
# .env
MIROSHARK_LOG_PROMPTS=true    # Log full LLM prompts/responses (large files, debug only)
MIROSHARK_LOG_LEVEL=info      # debug|info|warn — controls event verbosity
```

By default, only response previews (200 chars) are logged. Set `MIROSHARK_LOG_PROMPTS=true` to capture full prompts and responses for deep debugging.

## Aggregate metrics

For higher-level "is this MiroShark instance healthy?" monitoring, three platform-aggregate endpoints describe the whole deployment rather than a single simulation:

- `GET /api/stats` — every public, completed simulation rolled into a single envelope: `total_sims`, `consensus_distribution`, `avg_confidence_pct`, `total_surface_views`, `unique_projects`, `newest_sim_id`. Cached 60 s with an ETag, so a Grafana / Datadog scrape can poll once a minute cheaply.
- `GET /api/stats/badge.svg` — flat Shields.io-style pill (`MiroShark | N simulations`) for any README, Substack header, or status page that needs a live activity indicator.
- `GET /api/project/<project_id>/stats` — same envelope shape as `/api/stats` but filtered to a single `project_id`, plus a `quality_distribution` of `excellent / good / fair / poor` buckets. The operator-side surface for monitoring one workspace across many published sims — pull the same numbers Aeon's daily push-recap derives client-side. Unknown `project_id` returns an all-zero envelope (not 404); malformed `project_id` returns 400.
