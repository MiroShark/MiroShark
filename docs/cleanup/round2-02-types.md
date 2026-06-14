# Round 2 — Task 02: Type definitions inventory & consolidation

Branch: isolated worktree off `main`. MODE = auto-apply high-confidence, surface
risky. Builds on round-1 `docs/cleanup/02-types.md` (which consolidated the
triplicated `CommandType` enum and added the `WebhookPayload` TypedDict).

## Methodology

1. Re-ran the full type census across `backend/app/`, `backend/scripts/`,
   `backend/lib/`, `backend/tests/` (excluded the vendored `backend/wonderwall/`
   except for read-only confirmation): `@dataclass`, `Enum`, `TypedDict`,
   `NamedTuple`, pydantic `BaseModel`, and module-level type aliases.
2. Verified round-1 consolidations persisted (`CommandType` now imported in all
   three `run_*_simulation.py`; `WebhookPayload` present).
3. Dispatched a broad structural-dict-shape sweep (Explore agent) over
   `app/` + `scripts/` to find fixed-shape `Dict[str, Any]` literals with
   identical key sets repeated across 2+ distinct locations.
4. Checked frontend (`frontend/src/`) for duplicated constant / enum-as-object
   shapes that belong in a shared `utils`/constants module.
5. For each candidate: grep-verified usage, checked import-cycle risk, and
   proved byte-identical output before applying.

## Census (confirms round-1, no new owned types)

- **No pydantic `BaseModel`s** of MiroShark's own. **No `NamedTuple`s.**
- Enums (`str, Enum`, all distinct state machines — NOT merged, same as round 1):
  `CommandType`/`CommandStatus` (simulation_ipc), `SimulationStatus`,
  `RunnerStatus`, `ReportStatus`, `TaskStatus`, `ProjectStatus`.
- `TypedDict`: `WebhookPayload` (webhook_service.py:129, round-1),
  `CounterfactualSpec` (scripts/counterfactual_loader.py:20). Both unique.
- ~30 owned `@dataclass`es; no two share a name across `app/`+`scripts/`
  (`grep ... | uniq -d` empty → the round-1 `CommandType` triplication is gone).

## Findings (file:line) — ranked

| # | Finding | Locations | Sev | Disposition |
|---|---------|-----------|-----|-------------|
| 1 | **Test-event sample payload (13-key `WebhookPayload` shape) duplicated byte-for-byte across the 4 notify channels** | slack_notify.py:418, discord_notify.py:427, telegram_notify.py:542, email_notify.py:770 | High | **APPLIED** — extracted `build_test_payload()` factory |
| 2 | `IPCHandler` / `UnicodeFormatter` / `MaxTokensWarningFilter` duplicated class names across the 3 `run_*_simulation.py` scripts | run_twitter/reddit/parallel | Med | DEFERRED → Task 1 (behavioral handlers, bodies diverge; not pure types) |
| 3 | `NodeInfo` (graph_tools.py:54) vs `EntityNode` (entity_reader.py:13) share 5 fields | two files | Med | DEFERRED (disjoint subsystems, cycle risk) |
| 4 | `AgentAction` (simulation_runner.py:47) vs `AgentActivity` (graph_memory_updater.py:17) same shape, different purpose | two files | Low | DEFERRED (different purpose) |
| 5 | `{"success", "data"/"error"}` Flask envelope (~157 sites) / `{"ok", "message"}` notify return (12 sites) | api/*.py, *_notify.py | Med | DEFERRED → weak-types/Task 5 (cross-module behavior change) |
| 6 | Frontend inline color hex / `Object.freeze` maps | several .vue | Low | DEFERRED (round-1 documented lockstep CSS constants) |

## APPLIED — consolidate the 4 notify test payloads onto `WebhookPayload`

**What.** Added `build_test_payload(scenario: str) -> WebhookPayload` (and a
`TEST_PAYLOAD_SIM_ID` constant) to `webhook_service.py` — the canonical home of
the `WebhookPayload` TypedDict. Replaced the four byte-identical inline
`sample_payload = {...}` dicts in `slack_notify.send_test_notification`,
`discord_notify.send_test_notification`, `telegram_notify.send_test_notification`,
and `email_notify.send_test_notification` with a lazy
`from . import webhook_service` + `webhook_service.build_test_payload(<scenario>)`.

The four payloads were identical **except the one `scenario` string** (which
names the channel: "your Slack/Discord/Telegram/SMTP … is configured"), now the
sole factory argument.

**Why it's the right consolidation (and not over-merge).**
- The shape *is* the canonical `WebhookPayload` (test variant) — exactly the type
  round 1 already centralised. This is genuine same-concept duplication, not a
  near-namesake.
- It does NOT touch the notify-channel **rendering** helpers (`build_slack_message`
  / `build_discord_embed` / `build_telegram_message` / `build_email_message`,
  `_truncate`, `belief_bar`, …) that round-1 DRY explicitly preserved as
  "documented decoupling". Only the shared *input data shape* is centralised; each
  channel still formats independently.

**Why safe (behavior-preserving).**
- **Byte-identical output:** standalone repro confirmed the factory dict `==` the
  old inline dict (same keys, same order, `share_path == "/share/sim_test_event"`,
  `share_card_path == "/api/simulation/sim_test_event/share-card.png"`).
- **No new import cycle:** all four notify modules *already* import
  `webhook_service` lazily inside their `notify_*` functions and call
  `webhook_service.build_payload(...)`; `webhook_service` imports **no** notify
  module. The new `from . import webhook_service` in each `send_test_notification`
  follows that exact established pattern.
- **Tests unaffected:** the `send_test_notification` unit tests
  (`test_unit_{slack,discord,telegram,email}_notify.py`) mock `_post_json` and
  assert on the *rendered* body (`"blocks"`/`"embeds"` present) and on
  `{ok, message}` — all derived from the same payload fields. No test asserts the
  raw inline dict's key set.
- `ruff check` on all 5 changed files: **All checks passed.**

## DEFERRED (with rationale)

- **`webhook_service.send_test_webhook` payload (webhook_service.py:1171)** — a
  *fifth* near-identical test payload, deliberately **NOT** merged into
  `build_test_payload`. It is a distinct variant: it sets real `created_at` /
  `completed_at` / `fired_at` timestamps, `parent_simulation_id`, **and an extra
  `"test": True` flag that `test_unit_webhook.py:432` explicitly asserts on**. It
  targets a raw HTTP endpoint and intentionally mirrors the *full* fired payload,
  unlike the 4 channels' minimal builder input. Forcing one factory would either
  break that test or pollute the notify payloads — correct "don't over-merge".
- **Status enums** (`SimulationStatus`/`RunnerStatus`/`ReportStatus`/`TaskStatus`/
  `ProjectStatus`/`CommandStatus`) — independent state machines with overlapping
  but non-identical value sets. Same call as round 1: keep separate.
- **`NodeInfo` vs `EntityNode`** — verified `graph_tools` never imports
  `entity_reader` and vice-versa; `EntityNode` is consumed by `simulation_config_
  generator` + `wonderwall_profile_generator`, `NodeInfo` only inside
  `graph_tools`. Merging couples two disjoint subsystems / risks a cycle for a 5
  shared fields — not high-confidence. Left separate.
- **`{"success"/"data"/"error"}` and `{"ok","message"}` envelopes** — pervasive
  (~157 + 12 sites) but a single shared TypedDict here is a cross-module,
  behavior-surface change. Belongs to the weak-types lane; flagged, not applied.
- **`IPCHandler`/`UnicodeFormatter`/`MaxTokensWarningFilter`** — duplicated
  *classes* but behavioral (logic dedup), bodies diverge by platform → Task 1.
- **Frontend** — inline hex colors / small `Object.freeze` maps in `.vue` files
  are round-1's documented lockstep CSS constants; no high-confidence shared-type
  extraction.

## Verification

- `python3 -m py_compile` on all 5 changed files → OK.
- Standalone repro: factory output `==` each old inline payload (byte-identical
  keys + values).
- `ruff check` (changed files) → All checks passed (no new errors).
- Name-collision grep: `build_test_payload` / `TEST_PAYLOAD_SIM_ID` did not exist
  before this change.

## Files changed

- `backend/app/services/webhook_service.py` (added factory + constant)
- `backend/app/services/slack_notify.py`
- `backend/app/services/discord_notify.py`
- `backend/app/services/telegram_notify.py`
- `backend/app/services/email_notify.py`

## Conflict risk for the integrator

- **Low.** The factory body lives in `webhook_service.py` between `build_payload`
  and `_post_json`. The four edits are inside each channel's
  `send_test_notification` only. If Task 1 (DRY) touches the same notify files it
  is most likely in the *rendering* helpers, not these test functions — but flag a
  possible textual overlap in `send_test_notification` regions.
