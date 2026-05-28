# Webhooks

<sup>English · [中文](WEBHOOKS.zh-CN.md)</sup>

MiroShark fires an outbound HTTP **POST** to a URL of your choosing the moment a simulation reaches a terminal state — `completed` or `failed`. The payload includes the scenario, final consensus, quality assessment, and a public share-card URL so consumers like Slack and Discord auto-unfurl with a rich preview.

> **Tip:** open MiroShark → **Settings → Integrations · Webhook** to paste your URL and fire a test event without leaving the app. The same URL is read by the runner for live runs.

---

## Why a webhook

The completion webhook is the integration surface for everything that lives outside MiroShark itself:

- **Slack / Discord / Teams** — paste an Incoming Webhook URL; chat channels light up the moment a long simulation finishes, with the share-card image inline.
- **Zapier / Make / n8n / IFTTT** — point the Zap/Scenario/Workflow at MiroShark and fan out from there: email digests, Notion rows, Airtable records, Google Sheet updates, custom dashboards.
- **Custom apps** — your own Cloud Run / Lambda / Express endpoint receives the JSON; do whatever you like with it (kick off downstream analysis, append to a queue, write to BigQuery, …).

No bot, no OAuth, no hosted infrastructure. One URL field.

---

## Configuration

Either set environment variables before launching MiroShark:

```bash
WEBHOOK_URL=https://hooks.slack.com/services/T0XXX/B0YYY/abcSECRETxyz
PUBLIC_BASE_URL=https://miroshark.app           # optional, see below
WEBHOOK_SECRET=                                  # optional, see "Verifying webhook signatures" below
WEBHOOK_EVENTS=                                  # optional, see "Filtering events" below
```

…or open **Settings → Integrations · Webhook** and paste the URL there. Settings changes apply at runtime — no restart.

`PUBLIC_BASE_URL` is the publicly-reachable base of your MiroShark deployment (e.g. `https://miroshark.app`). When set, the payload contains absolute `share_url` and `share_card_url` fields so Slack / Discord auto-unfurl with the simulation card. Leave it blank if you only need relative paths and your consumer can build absolute URLs itself.

`WEBHOOK_SECRET` is the shared secret used to HMAC-sign every dispatched payload — see [Verifying webhook signatures](#verifying-webhook-signatures) below. Leave it blank to skip signing (existing integrations continue working unchanged). Generate a fresh value with `python -c 'import secrets; print(secrets.token_hex(32))'` and paste it into both the MiroShark `.env` and your consumer's environment.

`WEBHOOK_EVENTS` is an optional allow-list — comma-separated tokens like `bullish,high_confidence` that filter dispatch to the slice of events you care about. See [Filtering events](#filtering-events) below for the token reference and AND/OR semantics. Blank fires on every completion (existing behavior, backward-compatible).

---

## Payload schema

```json
{
  "event": "simulation.completed",
  "sim_id": "sim_abc123def456",
  "scenario": "Will the SEC approve a spot Solana ETF before Q3 2026?",
  "status": "completed",
  "current_round": 20,
  "total_rounds": 20,
  "agent_count": 248,
  "quality_health": "Excellent",
  "final_consensus": {
    "bullish": 62.0,
    "neutral": 13.0,
    "bearish": 25.0
  },
  "resolution_outcome": "YES",
  "share_path": "/share/sim_abc123def456",
  "share_card_path": "/api/simulation/sim_abc123def456/share-card.png",
  "share_url": "https://miroshark.app/share/sim_abc123def456",
  "share_card_url": "https://miroshark.app/api/simulation/sim_abc123def456/share-card.png",
  "created_at": "2026-04-26T10:12:34",
  "completed_at": "2026-04-26T10:35:11",
  "parent_simulation_id": null,
  "fired_at": "2026-04-26T10:35:11.842113+00:00"
}
```

| Field | Type | Notes |
|---|---|---|
| `event` | string | `simulation.completed`, `simulation.failed`, or `simulation.test` |
| `sim_id` | string | Stable identifier — also in the `X-MiroShark-Sim-Id` header |
| `scenario` | string | Truncated to 280 characters with a Unicode ellipsis |
| `status` | string | `completed`, `failed`, or `test` |
| `current_round` | int | Last completed round at completion time |
| `total_rounds` | int | Configured total — `0` if not yet known |
| `agent_count` | int | Number of agent profiles |
| `quality_health` | string \| null | `Excellent` / `Good` / `Fair` / `Poor`, or `null` if assessment skipped |
| `final_consensus` | object \| null | Bullish / neutral / bearish percentages from the last belief snapshot |
| `resolution_outcome` | string \| null | Set when the run had a polymarket resolution (`YES` / `NO`) |
| `share_path` | string | Always relative; safe to log |
| `share_card_path` | string | Always relative |
| `share_url` | string \| absent | Only present when `PUBLIC_BASE_URL` is set |
| `share_card_url` | string \| absent | Only present when `PUBLIC_BASE_URL` is set |
| `created_at` | string \| null | ISO 8601, simulation creation time |
| `completed_at` | string \| null | ISO 8601, terminal-state time |
| `parent_simulation_id` | string \| null | Set when this run was forked from another |
| `fired_at` | string | ISO 8601 with timezone, when the webhook left MiroShark |
| `error` | string \| absent | Only on `simulation.failed` — truncated to 1000 chars |
| `test` | bool \| absent | `true` only on the `simulation.test` event |

### HTTP headers

| Header | Value |
|---|---|
| `Content-Type` | `application/json; charset=utf-8` |
| `User-Agent` | `MiroShark-Webhook/1.0` |
| `X-MiroShark-Event` | The same value as `event` |
| `X-MiroShark-Sim-Id` | The same value as `sim_id` |
| `X-MiroShark-Signature` | `sha256=<hex>` HMAC of the raw body. Present only when `WEBHOOK_SECRET` is set. See [Verifying webhook signatures](#verifying-webhook-signatures). |

---

## Delivery semantics

- **Fire-and-forget** — the POST runs on a daemon thread, so a slow endpoint never delays the simulation runner.
- **Best-effort, no retries** — a single attempt with a 5-second timeout. Consumers that need durability should accept the webhook into a queue and acknowledge with HTTP 2xx as fast as possible.
- **Deduped per process** — the runner can detect completion via two paths (process exit code + per-platform `simulation_end` events). Both call into the webhook service; only the first fire per `(sim_id, status)` actually sends.
- **`completed` and `failed` only** — pause / resume / running events are *not* delivered.
- **2xx = success** — anything else is logged as a delivery failure but never raised.
- **Delivery log** — every dispatch attempt (auto-fired *or* manually replayed) appends one JSON line to `<sim_dir>/webhook-log.jsonl` with timestamp, masked URL, HTTP status code, latency, and trigger label. Bounded to 50 rows on disk; `GET /api/simulation/<id>/webhook-log` (admin-token gated) returns the last 10 entries newest-first plus the all-time `total_attempts` counter.
- **Manual retry** — `POST /api/simulation/<id>/webhook-retry` (admin-token gated) re-fires the completion webhook for a sim already in a terminal state. Useful when the original delivery hit a transient 5xx, the URL was misconfigured at the time, or the consuming integration was down. The retry payload carries an extra top-level `retry: true` so downstream consumers can dedupe replays. The replay bypasses the per-process `(sim_id, status)` dedup gate that auto-fires honour (that gate exists only to prevent the runner's two terminal code paths from double-firing automatically; an explicit retry should always go through). Returns 400 when no webhook URL is configured, 409 when the simulation has not reached a terminal state.

---

## Filtering events

`WEBHOOK_EVENTS` is an optional comma-separated allow-list that filters dispatch at the source. The default — unset or blank — fires on every `simulation.completed` and `simulation.failed`, matching the original behavior. When set, MiroShark evaluates the rules against each payload before sending; failed evaluations are logged and skipped.

Useful when an integrator only cares about a slice of the stream — a Polymarket bot that only wants directional, high-confidence signals; a research pipeline that only wants excellent-quality runs; an alert channel that only wants Bearish flips.

### Tokens

| Category | Tokens | Meaning |
|---|---|---|
| Direction | `bullish`, `neutral`, `bearish` | The dominant stance in the final consensus, using the same `>=` plurality rule the share card / Discord embed colour uses |
| Confidence | `high_confidence` | Leading-stance percentage `>=` 75% |
| Confidence | `medium_confidence` | Leading-stance percentage in `[50%, 75%)` |
| Quality | `excellent_quality` | `quality_health == "excellent"` |
| Quality | `good_quality` | `quality_health` is `"excellent"` or `"good"` |

### Logic

- **OR within a category** — `bullish,bearish` means "any directional consensus" (skip neutral).
- **AND across categories** — `bullish,high_confidence` means "directional AND high confidence". A payload must satisfy every category that has at least one token set.
- **Failed sims always fire** — `simulation.failed` bypasses the filter so the alert an operator most needs to see never gets swallowed.
- **Unknown tokens are ignored** — a typo like `WEBHOOK_EVENTS=bulish` does not silently disable the webhook; the filter falls through to "no recognized rules" and dispatches normally.

### Examples

```bash
# Skip neutral consensus — only fire on directional outcomes:
WEBHOOK_EVENTS=bullish,bearish

# Polymarket bot — only fire on high-confidence directional signals:
WEBHOOK_EVENTS=bullish,bearish,high_confidence

# Research pipeline — only fire on excellent-quality runs:
WEBHOOK_EVENTS=excellent_quality

# Strict — directional, high-confidence, excellent quality, all three:
WEBHOOK_EVENTS=bullish,bearish,high_confidence,excellent_quality
```

Suppressed deliveries are logged at `info` level with the parsed token set, the payload's derived direction / confidence / quality, and the category that failed — so an operator can see exactly why a webhook didn't fire. They are **not** written to the per-sim `webhook-log.jsonl` (only attempted deliveries are).

---

## Verifying webhook signatures

When `WEBHOOK_SECRET` is configured on your MiroShark instance, every outbound payload is signed with HMAC-SHA256 and the signature is shipped as the `X-MiroShark-Signature` header. The signature lets your consumer prove the payload actually came from your MiroShark instance and wasn't spoofed en route — the same scheme [Stripe](https://stripe.com/docs/webhooks/signatures) and [GitHub](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries) use.

The signature is computed over the **raw request body** (not the parsed JSON) so a recipient must verify *before* parsing — re-serializing JSON can re-order keys or change whitespace and break the digest.

**Backward compatible.** When `WEBHOOK_SECRET` is unset or empty on the MiroShark side, the signature header is omitted entirely and existing integrations keep working without changes. Recipients should treat "no signature header" as "no signature configured" and decide locally whether to accept unsigned deliveries.

Generate a strong secret once and set the **same value** on both sides:

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
# → 64 hex chars; paste into WEBHOOK_SECRET on both ends
```

### Python (Flask / FastAPI / plain WSGI)

```python
import hashlib, hmac, os

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"].encode()

def verify(raw_body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(WEBHOOK_SECRET, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")
```

`hmac.compare_digest` is constant-time so a network attacker can't time-trial the comparison.

### Node.js (Express)

```javascript
const crypto = require('crypto');
const SECRET = process.env.WEBHOOK_SECRET;

function verify(rawBody, header) {
  const expected = 'sha256=' + crypto.createHmac('sha256', SECRET).update(rawBody).digest('hex');
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(header || ''));
}
```

In Express, attach `express.raw({ type: 'application/json' })` to the route so `req.body` arrives as a `Buffer` — verify before `JSON.parse`.

### Bash / curl + openssl

Manual one-shot check from the terminal — useful when triaging "did the webhook fire from the right MiroShark?" from inside a Slack incident channel:

```bash
SIGNATURE=$(curl -fsSL -X POST https://your-app.example.com/miroshark-webhook \
  -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  -D - -o /dev/null | grep -i '^x-miroshark-signature:' | cut -d' ' -f2 | tr -d '\r')

EXPECTED=sha256=$(openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -hex payload.json | awk '{print $2}')

[ "$SIGNATURE" = "$EXPECTED" ] && echo OK || echo TAMPERED
```

---

## Examples

### Slack

```bash
WEBHOOK_URL=https://hooks.slack.com/services/T0XXX/B0YYY/abcSECRETxyz
PUBLIC_BASE_URL=https://miroshark.example.com
```

The Slack message will unfurl `share_url` automatically into the OG card produced by `GET /api/simulation/<id>/share-card.png` (1200×630 PNG with scenario, consensus split, and quality badge). No additional formatting needed.

### Discord

```bash
WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abcSECRETxyz
PUBLIC_BASE_URL=https://miroshark.example.com
```

Discord channel webhooks accept the same JSON body. The `share_url` unfurls in the channel.

### Zapier / Make / n8n

Create a "Webhook by Zapier" / "Webhooks · Custom webhook" / "Webhook" trigger node and copy its URL into `WEBHOOK_URL`. Every simulation completion becomes a fresh trigger event with the full payload above — fan out to email, Notion, Sheets, or any of the 5,000+ integrations they offer.

### Custom listener (Python)

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/miroshark-webhook")
async def receive(req: Request):
    payload = await req.json()
    if payload["event"] == "simulation.completed":
        print(f"{payload['sim_id']}: {payload['scenario']!r} → {payload['final_consensus']}")
    return {"ok": True}
```

---

## Testing your endpoint

The fastest path is the **Send test event** button in **Settings → Integrations · Webhook** — it POSTs the same shape with `event: "simulation.test"` and `test: true`, and shows the response status / latency inline.

The same call is exposed as `POST /api/settings/test-webhook` for scripting:

```bash
curl -s -X POST http://localhost:5000/api/settings/test-webhook \
     -H 'Content-Type: application/json' \
     -d '{"url": "https://example.com/hook"}'
```

Response:

```json
{
  "success": true,
  "message": "HTTP 200",
  "latency_ms": 142,
  "url_masked": "https://example.com/***"
}
```

Omit the body to test the currently saved `WEBHOOK_URL`.

---

## Security notes

- The full webhook URL is treated as a secret — `GET /api/settings` only returns the masked form (`https://hooks.slack.com/***`). The path is never echoed back.
- Webhook calls go straight from your MiroShark instance to your endpoint — no Anthropic or third-party hop.
- Validation rejects any URL that doesn't start with `http://` or `https://`. JavaScript / file / FTP URLs are blocked at the API layer.
- `WEBHOOK_SECRET` is **transport-only** — it's used to sign each dispatch but never persisted to the per-sim delivery log (`webhook-log.jsonl` records the masked URL, never the secret) and never echoed by any API endpoint. Rotate it any time by setting a new value on both sides; in-flight retries continue using whatever secret is set at retry time.
