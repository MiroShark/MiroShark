# OriginTrail DKG citation surface

MiroShark can anchor a finished simulation's citation surface on the
**OriginTrail Decentralized Knowledge Graph (DKG)** as a cryptographically
verifiable Knowledge Asset. The returned UAL (Universal Asset Locator),
Merkle root, and transaction hash become a permanent, blockchain-anchored
citation key — the same provenance property Stripe gives a charge or a
DOI gives a paper, but for a MiroShark simulation result.

This is the **citation primitive** the share-surface stack always wanted:
`reproduce.json` makes a sim reproducible, the share card makes it
shareable, and the DKG anchor makes it **un-rewritable**. A researcher
quoting your Aave risk sim can point at the UAL and anyone can verify
the underlying claims have not been edited since publication.

The integration is **optional and opt-in**: empty env vars → the feature
hides itself entirely (no button, no probe). Set the four `DKG_*` vars
and the EmbedDialog grows a "Publish to DKG" button.

## TL;DR — what you get

* **One-click anchor** in the share dialog of any public simulation.
* On success: `urn:dkg:context-graph:…` UAL + `0x…` Merkle root + `0x…`
  transaction hash + block number + a link to the DKG explorer.
* **Idempotent.** A second click on the same sim returns the existing
  citation from disk without re-hitting the daemon (no double-spend of
  TRAC or gas).
* **Citation verification.** The on-chain Merkle root commits to a
  Turtle RDF document that includes the SHA-256 of the sim's
  `reproduce.json` bytes. A verifier fetches the URL, re-hashes the
  bytes, and compares — match = the sim has not been altered since
  anchoring.

## One-time setup

You need three things: a running DKG daemon, a funded wallet on the
target chain (testnet or mainnet), and a Context Graph to publish into.

### 1. Install + run the DKG daemon

```bash
# OriginTrail's TypeScript daemon — Node 22+ required
npm install -g @origintrail-official/dkg

# Initialize: creates ~/.dkg/config.yaml, auto-funds a wallet on the
# testnet faucet. Use ``--no-fund`` to bring your own wallet.
dkg init

# Start the daemon — runs on http://127.0.0.1:9200
dkg start
```

The daemon picks up your chain config from `~/.dkg/config.yaml`. The
default points at Base Sepolia (testnet); switch to Base mainnet
manually if you want real durability. MiroShark doesn't pick the chain
— it just labels the citation with whichever chain the daemon is
configured against (this is what `DKG_NETWORK` controls below; it's
metadata for the explorer URL, nothing more).

### 2. Create a Context Graph for MiroShark sims

A Context Graph is a scoped, topic-bounded subgraph within the DKG.
One MiroShark instance publishes all its sims into one Context Graph.

```bash
dkg context-graph create miroshark
# → prints the new Context Graph ID; copy it.
```

### 3. Grab the auth token

```bash
dkg auth show
# → prints the Bearer token the daemon expects on every API call.
```

### 4. Wire MiroShark up

Paste into `.env`:

```bash
# OriginTrail DKG (optional — leave blank to disable the feature)
DKG_API_URL=http://127.0.0.1:9200
DKG_AUTH_TOKEN=<the token from `dkg auth show`>
DKG_CONTEXT_GRAPH_ID=<the id from `dkg context-graph create`>
DKG_NETWORK=testnet            # or "mainnet" — explorer label only
```

Restart MiroShark (or save through the Settings modal — env reads are
late-bound). The next time you open the share dialog of a public sim,
the **OriginTrail DKG citation** card appears.

If any of the three required vars is blank the feature hides entirely
and `GET /api/config/notifications` reports `dkg_configured: false`.
`DKG_NETWORK` defaults to `testnet` and is never required.

## How it works (one publish, four daemon calls)

The OriginTrail DKG v9/v10 daemon uses a three-tier memory model that
maps onto the publish flow:

```
1. POST /api/assertion/create            # Working Memory (private draft)
2. POST /api/assertion/{name}/write      # append Turtle RDF
3. POST /api/assertion/{name}/promote    # WM → Shared Working Memory
4. POST /api/shared-memory/publish       # SWM → Verified Memory (on-chain)
```

Step 4 returns:

```json
{
  "ual": "urn:dkg:context-graph:…",
  "merkleRoot": "0x…",
  "transactionHash": "0x…",
  "blockNumber": 12345,
  "finalized": true
}
```

MiroShark persists these as `<sim_dir>/dkg-citation.json` so a re-click
on the button returns the cached citation directly. The four-step
pipeline is implemented in
[`backend/app/services/dkg_publisher.py`](../backend/app/services/dkg_publisher.py).

### What goes in the Knowledge Asset

The Turtle RDF document committed on-chain is a minimal but complete
representation of the simulation:

```turtle
@prefix mir: <https://miroshark.io/ns/sim#> .
@prefix schema: <https://schema.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<urn:miroshark:sim:sim_abc123> a mir:Simulation ;
  schema:identifier "sim_abc123" ;
  schema:name """Will the SEC approve a spot AAVE ETF by EOY?""" ;
  mir:agentCount 248 ;
  mir:totalRounds 24 ;
  mir:twitterEnabled true ;
  mir:redditEnabled true ;
  mir:polymarketEnabled true ;
  mir:bullishPercent "62.0"^^xsd:decimal ;
  mir:neutralPercent "13.0"^^xsd:decimal ;
  mir:bearishPercent "25.0"^^xsd:decimal ;
  mir:qualityHealth "Excellent" ;
  mir:lineageKind "original" ;
  mir:reproduceConfigSha256 "sha256:7c9f…" ;
  mir:reproduceConfigUrl <https://your-host/api/simulation/sim_abc123/reproduce.json> ;
  mir:shareUrl <https://your-host/share/sim_abc123> ;
  mir:publishedAt "2026-05-15T12:00:00Z"^^xsd:dateTime .
```

The `mir:reproduceConfigSha256` literal is the actual citation key. The
Merkle root the DKG returns is a cryptographic commitment over the
entire Turtle document — so anchoring the Turtle on-chain
transitively anchors the reproduce.json hash. The reproduce.json blob
is already byte-stable (see [`backend/app/services/repro_export.py`](../backend/app/services/repro_export.py)),
so two exports of the same finished sim produce the same hash.

## HTTP endpoints

| Method | Path                                            | Auth        | Returns                                                |
| ------ | ----------------------------------------------- | ----------- | ------------------------------------------------------ |
| GET    | `/api/simulation/<id>/dkg-citation`             | Public      | Persisted citation; 404 if not yet anchored            |
| POST   | `/api/simulation/<id>/publish-dkg`              | Admin token | Triggers WM→SWM→VM publish; returns the citation       |
| GET    | `/api/config/notifications`                     | Public      | `{dkg_configured, dkg_network, …}` presence booleans   |

The publish endpoint requires `Authorization: Bearer $MIROSHARK_ADMIN_TOKEN`
because anchoring on-chain costs TRAC + gas — the same admin gate the
`webhook-retry` endpoint uses for the same reason.

Response codes:

* `200` — publish succeeded (or cached citation returned)
* `403` — simulation not published (call `POST /publish` first)
* `404` — simulation not found
* `422` — sim hasn't reached the prepared state (nothing to anchor)
* `502` — DKG daemon returned an error (chain failure, insufficient
  TRAC, name collision, etc.)
* `503` — `DKG_*` env vars not configured on this deployment
* `504` — DKG daemon unreachable / publish timed out

## Verifying a citation

Once a sim is anchored, anyone with the UAL can verify:

```bash
# 1. Read the assertion from any DKG node
curl -s "https://your-host/api/simulation/sim_abc123/dkg-citation" \
  | jq .data

# 2. Fetch the reproduce.json bytes
curl -s "https://your-host/api/simulation/sim_abc123/reproduce.json" > repro.json

# 3. SHA-256 the bytes
shasum -a 256 repro.json
# → 7c9f6e… repro.json

# 4. Compare to the on-chain literal
# Open the DKG explorer URL from the citation and confirm the
# mir:reproduceConfigSha256 value matches.
```

A mismatch means the simulation parameters have been altered since
anchoring — by design, the on-chain Merkle root cannot be silently
rewritten.

## Cost model

* **Testnet** (Base Sepolia, default): TRAC + gas are auto-funded from
  the faucet. Free for development.
* **Mainnet** (Base): real TRAC token + ETH gas per publish. A typical
  Knowledge Asset publish currently costs single-digit cents in gas
  plus a small TRAC stake. Costs vary with network conditions — see
  [OriginTrail's pricing docs](https://docs.origintrail.io/) for
  current numbers.

MiroShark's idempotent on-disk citation file means re-clicking the
button on the same sim **does not** spend gas again. To force a
re-anchor (e.g. after a sim was corrected), pass `force: true` in the
POST body — the v1 UI doesn't expose this; it's an escape hatch for
operators who know what they're asking for.

## Disabling

Comment out (or remove) `DKG_API_URL` / `DKG_AUTH_TOKEN` /
`DKG_CONTEXT_GRAPH_ID` in `.env` and restart. The card disappears, the
public probe reports `dkg_configured: false`, and existing
`dkg-citation.json` files stay on disk (still served by
`GET /dkg-citation` if the operator re-enables the feature later).

## See also

* [OriginTrail/dkg-v9 — official daemon repo](https://github.com/OriginTrail/dkg-v9)
* [OriginTrail DKG documentation](https://docs.origintrail.io/)
* [`backend/app/services/dkg_publisher.py`](../backend/app/services/dkg_publisher.py)
* [`backend/app/services/repro_export.py`](../backend/app/services/repro_export.py) — the reproduce.json builder whose bytes get hashed
* [Notifications](NOTIFICATIONS.md) — sibling channels (Webhook, Discord, Slack)
