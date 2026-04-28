# Seed Chat — Design Spec

**Date:** 2026-04-28
**Status:** Approved (awaiting plan)

## Goal

Replace MiroShark's Home page with a Q&A chat that uses Claude (via the Max-plan `claude -p` CLI) to slot-fill a structured "seed", then launch the existing research → swarm simulation → Decision Lab → report pipeline with that seed as input.

## Why

Today the front door pushes users toward uploading reports/URLs. For policy and "battle-of-information" use cases (e.g. analysing pros/cons of Australia's 25% resources tax), there is no seed document — the user has a question and rough intent, but extracting a high-quality simulation seed requires interrogation. A Claude-driven Q&A is a better front door than a file upload.

## User Journey

1. User lands on `/` and sees a chat interface (left, ~70%) plus a live "seed slots" sidebar (right, ~30%).
2. User types initial idea ("pros/cons brief on Australia's 25% resources tax, focused on the media debate").
3. Claude asks targeted questions to fill empty slots ("Which stakeholders should be modeled? Suggested: Minerals Council, ACTU, Treasury, BCA, regional WA/QLD towns — add/remove?").
4. As slots fill, the sidebar ticks them off and highlights what changed.
5. When required slots are filled, Claude says *"I think we have what we need — review and launch, or keep refining?"* and the **Launch** button enables.
6. User can keep refining, or click **Launch** at any time after readiness.
7. Launch POSTs the seed to the existing pipeline and redirects to the Process / Simulation views.

## Seed Schema

```json
{
  "topic":   "string — the issue/question being investigated",
  "intent":  "string — what the user wants out of this",
  "stakeholders": [
    { "name": "string", "role": "string", "stance": "supporting | opposing | neutral | unknown" }
  ],
  "decision_branches": [
    { "label": "string", "description": "string" }
  ],
  "contested_claims": [ "string" ],
  "output_format": "pros_cons | decision_memo | executive_summary | full_report"
}
```

**Required to launch:** `topic`, `intent`, `stakeholders` (≥2), `output_format`.
**Optional but nudged:** `decision_branches`, `contested_claims`.

Worked example (Australia 25% resources tax):

```json
{
  "topic": "Australia's proposed 25% mineral resources tax",
  "intent": "Pros/cons brief for personal use, focused on contested claims in the media",
  "stakeholders": [
    {"name":"Minerals Council of Australia","role":"Industry lobby","stance":"opposing"},
    {"name":"ACTU","role":"Union peak body","stance":"supporting"},
    {"name":"Federal Treasury","role":"Policy author","stance":"supporting"},
    {"name":"BCA","role":"Big-business lobby","stance":"opposing"},
    {"name":"WA/QLD regional towns","role":"Affected communities","stance":"unknown"}
  ],
  "decision_branches": [
    {"label":"25% flat", "description":"As proposed"},
    {"label":"25% with regional carve-out", "description":"Exemption for towns reliant on mining payroll"},
    {"label":"Status quo", "description":"No new tax"}
  ],
  "contested_claims": [
    "Will trigger ~50k job losses",
    "Will reduce foreign investment by $X bn",
    "Big four miners already pay headline 30% corporate rate"
  ],
  "output_format": "pros_cons"
}
```

## Architecture

### Backend (Python / Flask)

**New: `backend/app/api/seed_chat.py`** — Flask blueprint
- `POST /api/seed-chat/turn`
  - Body: `{ messages: [{role, content}, ...], seed_state: {...} }`
  - Response: `{ assistant_message, updated_seed_state, ready_to_launch: bool }`
- `POST /api/seed-chat/launch`
  - Body: `{ seed: {...} }`
  - Maps seed → existing pipeline calls (research, simulation, Decision Lab). The exact downstream endpoint(s) and field mapping are resolved during the implementation plan after reading the current `api/graph.py`, `api/simulation.py`, and `api/decision_lab.py` route handlers.
  - Response: `{ project_id }` (redirect target)

**New: `backend/app/services/seed_extractor.py`**
- Single function `process_turn(messages, current_state) -> (assistant_msg, updated_state, ready_to_launch)`
- Owns the system prompt and slot logic
- Uses `create_llm_client()` so transport stays config-driven (works with `ClaudeCodeClient` when `LLM_PROVIDER=claude-code`)
- Each turn re-evaluates all slots from the full conversation (idempotent — refresh-safe, no hidden state)
- Readiness = required slots present **and** Claude's own `ready: true` signal in the JSON envelope

**Touched: `backend/app/__init__.py`** — register the new blueprint.

**Touched: `.env`** — switch `LLM_PROVIDER=openai` → `LLM_PROVIDER=claude-code`.

### Frontend (Vue 3)

**New: `frontend/src/views/SeedChat.vue`** — the new front door
- Two-pane layout: chat (left, ~70%) + slot sidebar (right, ~30%)
- Bottom: "Launch" button — visible always, disabled until backend signals `ready_to_launch`
- Optimistic message append; loading indicator during Claude turn

**New: `frontend/src/components/SeedSlotsPanel.vue`**
- Renders the seed state with checkmarks for filled slots, empty bullets for missing ones
- Highlights what just changed on each turn
- Read-only in v1 (inline editing → v2)

**New: `frontend/src/api/seedChat.js`** — axios wrappers for the two endpoints

**Touched: `frontend/src/router/index.js`** — `path: '/'` now points to `SeedChat`. Old `Home.vue` renamed to `HomeLegacy.vue` and routed at `/legacy` so the upload flow stays reachable.

**Touched: `frontend/src/views/Home.vue`** → renamed to `HomeLegacy.vue`.

### LLM Transport

- Reuse existing `ClaudeCodeClient.chat(messages=...)` — no client changes.
- Each turn the backend builds the full message list, including a system prompt that contains the schema and current slot state. No conversation state stored on Claude's side.

### Data Flow Per Turn

```
User types → POST /api/seed-chat/turn (messages + seed_state)
  → seed_extractor builds prompt with schema, history, current slots
  → ClaudeCodeClient.chat_json() returns {reply, updated_slots, ready}
  → response returned to frontend
  → frontend appends reply, updates sidebar, conditionally enables Launch
```

### Files Affected

| File | Change |
|------|--------|
| `backend/app/api/seed_chat.py` | NEW |
| `backend/app/services/seed_extractor.py` | NEW |
| `backend/app/__init__.py` | register blueprint |
| `frontend/src/views/SeedChat.vue` | NEW |
| `frontend/src/components/SeedSlotsPanel.vue` | NEW |
| `frontend/src/api/seedChat.js` | NEW |
| `frontend/src/router/index.js` | swap `/` route, add `/legacy` |
| `frontend/src/views/Home.vue` | rename to `HomeLegacy.vue` |
| `.env` | switch `LLM_PROVIDER` |

5 new files + 4 touched.

## Error Handling

| Boundary | Failure mode | Behavior |
|----------|--------------|----------|
| Claude CLI not installed | `claude --version` non-zero | Backend 503 `{error: "claude_cli_unavailable"}`; frontend banner: "Claude CLI not reachable — check `claude --version`" |
| Claude returns malformed JSON | Parse fails | Keep prior `seed_state`, append assistant text reply, log warning. Conversation continues. |
| Claude timeout (>300s) | subprocess timeout | 504; frontend "Claude is slow — retry?" with retry button |
| Pipeline launch fails | downstream endpoint error | Toast error; conversation stays open; user can retry or edit seed |
| Empty user message | client-side guard | Disable send button when input empty |

## Tests

**Backend**
- `backend/tests/test_seed_extractor.py`
  - Fixture conversations → assert correct slot state
  - Required slots not yet filled → `ready_to_launch == false`
  - All required filled + readiness signal → `ready_to_launch == true`
  - Malformed LLM JSON → graceful degradation (state preserved)
- `backend/tests/test_seed_chat_api.py`
  - `POST /api/seed-chat/turn` happy path (mocked LLM)
  - `POST /api/seed-chat/launch` triggers correct downstream call
  - 503 when LLM client init fails

**Frontend**
- `SeedSlotsPanel.spec.js` — given seed state, renders correct ✓/○ icons; highlights diff
- `SeedChat.spec.js` — message appends, loading state, Launch button enable/disable

**Manual smoke test**
- Open `/`, type "pros/cons of Australia's 25% resources tax — media battle"
- Verify Claude asks at least one targeted clarifying question
- Verify slots fill as conversation progresses
- Hit Launch when ready, confirm pipeline kicks off

## Risks

- **Subprocess overhead per turn** (~2-5s). Acceptable for chat. If sluggish, switch to streaming or move to Claude SDK over HTTP later.
- **JSON reliability.** Claude returning a structured envelope every turn is not guaranteed. Mitigation: explicit system prompt with example, lenient parser (regex-extract first `{...}` block), graceful degradation.
- **Schema rigidity.** If a topic legitimately has no `decision_branches`, Claude might invent fake ones to satisfy the schema. Mitigation: those fields are optional; explicit prompt instruction "leave empty if not applicable, do not invent."
- **Front door swap.** Bookmarks of `/` for upload flow break. Mitigation: `/legacy` route preserves access; nav link added.

## Out of Scope (v1)

- Streaming token-by-token responses
- Conversation persistence across page refresh
- Editing past messages
- Inline slot editing in the sidebar
- Multi-user / auth / saved sessions

## Decisions Log

- **Front-door scope:** Replace Home (option A from brainstorm).
- **Downstream:** Full pipeline (option B).
- **Stopping criterion:** Hybrid — Claude proposes ready, user can override (option C).
- **Slot filling:** Schema-driven (option A) with live sidebar.
- **Slot extraction strategy:** One LLM call per turn returns both the assistant reply and the updated slot JSON, not a separate extraction pass — fewer subprocesses, fewer roundtrips, accept JSON-fragility risk.
- **Old Home page:** Preserved at `/legacy` rather than deleted.
