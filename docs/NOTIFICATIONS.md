# Channel Notifications

MiroShark fires a notification the moment a simulation reaches a terminal
state (`simulation.completed` or `simulation.failed`). Three independent
channels run in parallel — each opt-in via its own env var:

| Channel  | Env var               | Format             | Use case                                                      |
| -------- | --------------------- | ------------------ | ------------------------------------------------------------- |
| Webhook  | `WEBHOOK_URL`         | Raw JSON `POST`    | Zapier / Make / n8n / IFTTT / custom listeners                |
| Discord  | `DISCORD_WEBHOOK_URL` | Discord rich embed | Discord channels — coloured cards with belief % fields        |
| Slack    | `SLACK_WEBHOOK_URL`   | Slack Block Kit    | Slack channels — header + block-bar fields + action button    |

Channels are independent. Set one, two, or all three — each fires
separately. Unset env vars are silently skipped, so existing deployments
that only use the generic webhook are unaffected by this feature.

The SPA exposes a public probe at `GET /api/config/notifications`
returning `{webhook_configured, discord_configured, slack_configured}` so
the operator can confirm channel status without opening the backend
config.

## Generic webhook (existing, PR #46)

Already documented in [WEBHOOKS.md](./WEBHOOKS.md). Posts a JSON blob
matching the payload shape in
[`backend/app/services/webhook_service.py`](../backend/app/services/webhook_service.py).

## Discord rich embed

Set `DISCORD_WEBHOOK_URL` to a Discord incoming webhook URL:

```bash
# Discord → Server Settings → Integrations → Webhooks → New Webhook
# Copy the webhook URL ("https://discord.com/api/webhooks/000/xxx").
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/000/xxx
```

On every terminal-state transition, MiroShark POSTs a single embed:

* **Title** — scenario, truncated to 100 chars.
* **Description** — one-line status verb ("Simulation reached its
  terminal round." or "Simulation ended in a failure state.").
* **Color** — green / grey / red / amber depending on the dominant
  consensus stance (failed runs always amber).
* **Fields** — Bullish %, Neutral %, Bearish %, Quality, Rounds,
  Agents, Resolution (when set).
* **Thumbnail** — share card PNG (only when `PUBLIC_BASE_URL` is set
  so the embed can render an absolute URL).
* **URL** — share page link (`/share/<sim_id>`), absolute when
  `PUBLIC_BASE_URL` is set.
* **Footer / timestamp** — "MiroShark" + the dispatch timestamp.

Failed runs append an additional `Error` field with the truncated
exit-code message.

Discord deduplicates per `(sim_id, status)` pair in the dispatching
process — the simulation runner's two terminal code paths (exit-code
monitor + the `simulation_end` event in the action log) both call
into the notifier but Discord only sees one card per terminal state.

The endpoint is fire-and-forget: a slow Discord endpoint never delays
the simulation runner, and a 4xx logs a warning without raising.

## Slack Block Kit

Set `SLACK_WEBHOOK_URL` to a Slack Incoming Webhook URL:

```bash
# api.slack.com/apps → your app → Incoming Webhooks → Add New Webhook to Workspace
# Copy the webhook URL ("https://hooks.slack.com/services/T0/B0/abc").
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T0/B0/abc
```

On every terminal-state transition, MiroShark POSTs a Block Kit
message with four blocks:

* **Header** — scenario, truncated to 120 chars.
* **Context** — bold status verb + monospaced sim id.
* **Section** — `mrkdwn` fields:
  * Bullish / Neutral / Bearish with Unicode block-bars
    (`█████░░░░░ 52.0%`).
  * Quality health.
  * Scale (`N agents · N rounds`).
  * Resolution (when set).
* **Actions** — a single "View simulation" button linking to
  `/share/<sim_id>`. Only emitted when `PUBLIC_BASE_URL` is set
  (Slack rejects buttons whose URL isn't absolute).

Failed runs append an `Error` section with a fenced code block
containing the truncated exit-code message.

Same dedup posture and fire-and-forget guarantees as Discord.

## Picking the right channel

* **Discord** — community-facing. Use when the audience wants the
  result *visually*: belief percentages, the share-card thumbnail,
  a tap-through to the simulation. Best for distribution channels
  ("here's what just simulated for you").
* **Slack** — ops-facing. Use when the audience wants the result
  *operationally*: a quick read of the bars, an explicit action
  button, the sim id in monospaced font. Best for engineering /
  research channels.
* **Generic webhook** — automation-facing. Use when the result
  needs to land in a workflow tool (Zapier / Make / n8n) that
  unpacks the JSON itself.

## Sandbox note

Pure stdlib (`urllib.request` + `json` + `os` + `hmac`). No new
dependencies. The HMAC signing scheme on the generic webhook
(`X-MiroShark-Signature`, PR #79) applies only to that channel —
Discord and Slack incoming webhooks use the platforms' own
URL-as-secret authentication and ignore signature headers.
