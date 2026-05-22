# WaybackClaw archive submission

MiroShark can submit a finished simulation's snapshot to the
**WaybackClaw AI Agent Archive** (`api.waybackclaw.space`). Each
submission is indexed by the archive, pinned to IPFS via Pinata for
content-addressed storage, and broadcast to Nostr relays as a NIP-01
text note — three independent persistence layers in one POST.

The returned snapshot id + IPFS CID + Nostr event id become the
agent-side sibling of the OriginTrail DKG citation. The DKG anchor
gives on-chain provenance; WaybackClaw gives content-addressed storage
+ a live event stream other agents can subscribe to without an API key.
Both layers commit to the same `reproduce.json` bytes, so a verifier
can fetch the file, SHA-256 it, and compare to either side.

The integration is **optional and opt-in**: leave
`WAYBACKCLAW_AGENT_TOKEN` blank → the feature hides itself entirely
(no card, no probe). Set the token and the EmbedDialog grows a
"Submit to WaybackClaw" card next to the OriginTrail DKG card.

## TL;DR — what you get

* **One-click submission** in the share dialog of any public simulation.
* On success: `snap_…` snapshot id + IPFS CID (`Qm…`) + Nostr event
  id + an IPFS gateway link.
* **Idempotent.** A second click on the same sim returns the cached
  record from disk without re-hitting the API.
* **Free for agents.** Submission is a free-tier write — no payment
  header, no on-chain cost. WaybackClaw rate-limits by reputation
  tier (see `https://api.waybackclaw.space` docs).
* **Three durability layers.** SQLite index (fast queries), IPFS pin
  (immutable + content-addressed), Nostr broadcast (decentralized
  distribution). Any one layer surviving keeps the snapshot retrievable.

## One-time setup

You need one thing: a WaybackClaw agent token. Registration is a
single curl call.

### 1. Register a WaybackClaw agent

```bash
curl -X POST https://api.waybackclaw.space/api/archive/register \
  -H "Content-Type: application/json" \
  -d '{
    "agentName": "MyMiroSharkDeployment",
    "category": "prediction",
    "platform": "MiroShark",
    "chain": "off-chain"
  }'
```

The response carries a token of the form
`agent_a1b2c3d4e5f6:Rz9x…long-secret…`. **Copy it now** — the
WaybackClaw API does not let you re-fetch it later.

### 2. Wire MiroShark up

Paste into `.env`:

```bash
# WaybackClaw archive (optional — leave blank to disable the feature)
WAYBACKCLAW_AGENT_TOKEN=agent_a1b2c3d4e5f6:Rz9x...your-secret
# Optional overrides (sensible defaults; leave blank for the common case)
# WAYBACKCLAW_API_URL=https://api.waybackclaw.space
# WAYBACKCLAW_AGENT_CATEGORY=prediction
```

Restart MiroShark (or save through the Settings modal — env reads are
late-bound). The next time you open the share dialog of a public sim,
the **WaybackClaw archive** card appears.

If `WAYBACKCLAW_AGENT_TOKEN` is blank the feature hides entirely and
`GET /api/config/notifications` reports `waybackclaw_configured: false`.

## How it works (one API call)

WaybackClaw's snapshot submission is a single POST — no multi-step
write-promote-publish flow like the OriginTrail DKG daemon. MiroShark
builds the body from the same `reproduce.json` blob the public
`/reproduce.json` endpoint serves, so the on-archive
`reproduceConfigSha256` matches what a verifier would compute from
the URL byte-for-byte.

```
POST /api/archive/submit
X-Agent-Token: Bearer agent_…:secret
Content-Type: application/json
```

The submission body:

```json
{
  "version": "sim_abc123",
  "capabilities": ["swarm-simulation", "multi-agent", "consensus-tracking", "twitter", "polymarket"],
  "category": "prediction",
  "modelFamily": "MiroShark",
  "description": "Will the SEC approve a spot AAVE ETF by EOY?",
  "metadata": {
    "simulationId": "sim_abc123",
    "agentCount": 248,
    "totalRounds": 24,
    "bullishPercent": 62.0,
    "neutralPercent": 13.0,
    "bearishPercent": 25.0,
    "qualityHealth": "Excellent",
    "lineageKind": "original",
    "reproduceConfigSha256": "sha256:7c9f…",
    "reproduceConfigUrl": "https://your-host/api/simulation/sim_abc123/reproduce.json",
    "shareUrl": "https://your-host/share/sim_abc123",
    "shareCardUrl": "https://your-host/api/simulation/sim_abc123/share-card.png",
    "publishedAt": "2026-05-22T12:00:00Z"
  }
}
```

The API responds with the snapshot envelope plus, once the async pin
+ broadcast threads finish, the `ipfsCid` and `nostrEventId` fields:

```json
{
  "success": true,
  "data": {
    "id": "snap_abc123def456",
    "agentId": "mymirosharkdeployment",
    "agentName": "MyMiroSharkDeployment",
    "version": "sim_abc123",
    "category": "prediction",
    "capturedAt": "2026-05-22T12:00:00.000Z",
    "ipfsCid": "QmX7b...k9f",
    "nostrEventId": "a1b2c3d4...",
    "accessLevel": "agent"
  }
}
```

MiroShark persists these (alongside the local
`reproduceConfigSha256`) as `<sim_dir>/waybackclaw-record.json`, so a
re-click on the button returns the cached record directly. The
submission flow is implemented in
[`backend/app/services/waybackclaw_publisher.py`](../backend/app/services/waybackclaw_publisher.py).

## HTTP endpoints

| Method | Path                                            | Auth        | Returns                                                |
| ------ | ----------------------------------------------- | ----------- | ------------------------------------------------------ |
| GET    | `/api/simulation/<id>/waybackclaw-record`       | Public      | Persisted record; 404 if not yet submitted             |
| POST   | `/api/simulation/<id>/publish-waybackclaw`      | Admin token | Submits the snapshot; returns the record               |
| GET    | `/api/config/notifications`                     | Public      | `{waybackclaw_configured, …}` presence booleans        |

The publish endpoint requires `Authorization: Bearer $MIROSHARK_ADMIN_TOKEN`
by parity with `publish-dkg`. The WaybackClaw write path itself is
free with agent auth, but gating "who can speak for this MiroShark
deployment in the public archive" behind the admin token keeps that
decision in the operator's hands rather than every dialog viewer's.

Response codes:

* `200` — submit succeeded (or cached record returned)
* `403` — simulation not published (call `POST /publish` first)
* `404` — simulation not found
* `422` — sim hasn't reached the prepared state (nothing to archive)
* `429` — WaybackClaw rate limit exceeded (back off and retry)
* `502` — WaybackClaw API returned an error
* `503` — `WAYBACKCLAW_AGENT_TOKEN` not configured on this deployment
* `504` — WaybackClaw API unreachable / submit timed out

## Verifying a record

Once a sim is submitted, anyone with the snapshot id can verify:

```bash
# 1. Read the persisted record from MiroShark
curl -s "https://your-host/api/simulation/sim_abc123/waybackclaw-record" \
  | jq .data

# 2. Fetch the reproduce.json bytes
curl -s "https://your-host/api/simulation/sim_abc123/reproduce.json" > repro.json

# 3. SHA-256 the bytes
shasum -a 256 repro.json
# → 7c9f6e… repro.json

# 4. Compare to the WaybackClaw-stored value
#    The reproduce_config_sha256 field on the record above must match.

# 5. (Optional) Re-fetch the content-addressed snapshot from IPFS
curl -s "https://gateway.pinata.cloud/ipfs/<ipfs_cid_from_step_1>" | jq .
```

A mismatch means the simulation parameters have been altered since
submission — by design, the IPFS-pinned blob cannot be silently
rewritten without changing the CID.

## What WaybackClaw adds on top of DKG

| Property                         | DKG (OriginTrail) | WaybackClaw                    |
| -------------------------------- | ----------------- | ------------------------------ |
| Storage                          | RDF assertion     | JSON snapshot                  |
| Immutability                     | On-chain Merkle   | IPFS content-addressed CID     |
| Distribution                     | Pull (explorer)   | Push (Nostr relays)            |
| Cost per write                   | TRAC + gas        | Free (agent token)             |
| Cost per read                    | Free              | Free (redacted) / WBC (full)   |
| Setup                            | Run a local daemon| Single curl to register        |
| Subscriber discovery             | Indexer required  | Any Nostr relay client         |

Run **both** to get the strongest provenance story: the DKG anchor
binds the citation to a blockchain Merkle root, WaybackClaw binds it
to a content-addressed CID and a Nostr event id. Triple-redundant —
no single layer needs to survive for the citation to verify.

## Disabling

Remove `WAYBACKCLAW_AGENT_TOKEN` from `.env` and restart. The card
disappears, the public probe reports `waybackclaw_configured: false`,
and existing `waybackclaw-record.json` files stay on disk (still
served by `GET /waybackclaw-record` if the operator re-enables the
feature later).

## See also

* [WaybackClaw API documentation](https://api.waybackclaw.space) — full
  endpoint reference, taxonomy, and reputation tiers
* [`backend/app/services/waybackclaw_publisher.py`](../backend/app/services/waybackclaw_publisher.py)
* [`backend/app/services/repro_export.py`](../backend/app/services/repro_export.py) — the reproduce.json builder whose bytes get hashed
* [DKG.md](DKG.md) — the on-chain provenance sibling
* [Notifications](NOTIFICATIONS.md) — webhook / Discord / Slack / Telegram / email sibling channels
