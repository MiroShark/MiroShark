# Webhooks

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
```

…or open **Settings → Integrations · Webhook** and paste the URL there. Settings changes apply at runtime — no restart.

`PUBLIC_BASE_URL` is the publicly-reachable base of your MiroShark deployment (e.g. `https://miroshark.app`). When set, the payload contains absolute `share_url` and `share_card_url` fields so Slack / Discord auto-unfurl with the simulation card. Leave it blank if you only need relative paths and your consumer can build absolute URLs itself.

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

---

## Delivery semantics

- **Fire-and-forget** — the POST runs on a daemon thread, so a slow endpoint never delays the simulation runner.
- **Best-effort, no retries** — a single attempt with a 5-second timeout. Consumers that need durability should accept the webhook into a queue and acknowledge with HTTP 2xx as fast as possible.
- **Deduped per process** — the runner can detect completion via two paths (process exit code + per-platform `simulation_end` events). Both call into the webhook service; only the first fire per `(sim_id, status)` actually sends.
- **`completed` and `failed` only** — pause / resume / running events are *not* delivered.
- **2xx = success** — anything else is logged as a delivery failure but never raised.

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
