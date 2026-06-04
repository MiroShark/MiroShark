# HTTP API Reference

<sup>English · [中文](API.zh-CN.md)</sup>

Base URL is `http://localhost:5001` in dev. Every endpoint returns JSON unless otherwise noted.

> **Interactive docs:** the running backend serves Swagger UI at `/api/docs` and the OpenAPI 3.1 spec at `/api/openapi.yaml` (or `/api/openapi.json`). Point [`openapi-generator`](https://openapi-generator.tech/) at the spec to produce a Python / TypeScript / Go SDK in one command.

## Localization

Every endpoint resolves an active locale per request. Order of precedence:

1. `?lang=` query parameter (use on share-surface URLs that need to be locale-pinned in their canonical form — `/share/<id>`, `cite.bib`, `badge.svg`, `chart.svg`)
2. `X-MiroShark-Locale` request header (what the bundled SPA sends on every API call)
3. `Accept-Language` request header (standard fallback for off-the-shelf HTTP clients)
4. `en` (default)

Supported locales: `en`, `zh-CN`. Unknown tags fall back to `en` silently — `?lang=fr` on the current build returns the English payload, not a 400.

What gets localized: API error messages (`{"success": false, "error": "..."}`), preset template `name` / `description` metadata, RSS / Atom feed copy, and the report agent's narration. Raw simulation data (posts, trades, agent stances) is never translated.

```bash
# SPA-style: header-driven
curl -s -H "X-MiroShark-Locale: zh-CN" "https://your-host/api/templates/list"

# Share-surface-style: query-pinned for stable canonical URLs
curl -s "https://your-host/share/<id>?lang=zh-CN"
```

## Setup & Discovery

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/simulation/suggest-scenarios` | Scenario auto-suggest (Bull / Bear / Neutral) from a document preview |
| `GET` | `/api/simulation/trending` | Pull RSS/Atom items for the "What's Trending" panel |
| `POST` | `/api/simulation/ask` | Just Ask — synthesize a seed briefing from a question |
| `POST` | `/api/graph/fetch-url` | Fetch + extract text from a URL |
| `GET` | `/api/templates/list` | Preset templates |
| `GET` | `/api/templates/<id>?enrich=true` | Template + live FeedOracle enrichment |

## Graph Build (Step 1)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/graph/ontology/generate` | NER + ontology extraction |
| `POST` | `/api/graph/build` | Build Neo4j graph from ontology |
| `GET` | `/api/graph/task/<task_id>` | Poll async task status |
| `GET` | `/api/graph/data/<graph_id>` | Paginated graph nodes + edges |
| `GET` | `/api/simulation/entities/<graph_id>` | Browse entities |
| `GET` | `/api/simulation/entities/<graph_id>/<uuid>` | Single entity + neighborhood |

## Simulation Lifecycle

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/simulation/create` | Create simulation from seed + prompt |
| `POST` | `/api/simulation/prepare` | Kick off profile generation (Step 2) |
| `POST` | `/api/simulation/prepare/status` | Poll Step 2 |
| `POST` | `/api/simulation/start` | Launch Wonderwall subprocess (Step 3) |
| `POST` | `/api/simulation/stop` | Terminate |
| `POST` | `/api/simulation/branch-counterfactual` | Fork with counterfactual injection |
| `POST` | `/api/simulation/fork` | Duplicate config |
| `POST` | `/api/simulation/<id>/director/inject` | Director mode — live event injection |
| `GET` | `/api/simulation/<id>/director/events` | List director events |

## Live State & Data

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/simulation/<id>/run-status` | Current round / totals |
| `GET` | `/api/simulation/<id>/run-status/detail` | Per-platform progress |
| `GET` | `/api/simulation/<id>/frame/<round>` | Compact per-round snapshot |
| `GET` | `/api/simulation/<id>/timeline` | Round-by-round summary |
| `GET` | `/api/simulation/<id>/actions` | Raw agent action log |
| `GET` | `/api/simulation/<id>/posts` | Paginated posts (Twitter + Reddit) |
| `GET` | `/api/simulation/<id>/profiles` | Agent personas |
| `GET` | `/api/simulation/<id>/profiles/realtime` | Live belief updates |
| `GET` | `/api/simulation/<id>/polymarket/markets` | Markets + current prices |
| `GET` | `/api/simulation/<id>/polymarket/market/<mid>/prices` | Price history |

## Analytics

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/simulation/<id>/belief-drift` | Stance drift per topic per round |
| `GET` | `/api/simulation/<id>/counterfactual` | Original vs branch comparison |
| `GET` | `/api/simulation/<id>/agent-stats` | Per-agent engagement + posting |
| `GET` | `/api/simulation/<id>/influence` | Influence leaderboard |
| `GET` | `/api/simulation/<id>/interaction-network` | Agent-to-agent graph |
| `GET` | `/api/simulation/<id>/demographics` | Archetype distribution |
| `GET` | `/api/simulation/<id>/quality` | Run health diagnostics |
| `GET` | `/api/simulation/<id>/peak-round` | Machine-readable belief inflection points — the round each stance (`bullish` / `neutral` / `bearish`) peaked (`{round, pct}`), the `most_volatile_round` (largest summed round-over-round swing), `max_swing_pct`, and `total_rounds`. Pure O(n) derivation from the same ±0.2 stance split `trajectory.csv` uses; peak ties resolve to the earliest round. Publish-gated; `404` until trajectory data exists. Cached 5 minutes. `curl -s "https://your-host/api/simulation/<id>/peak-round"` |
| `GET` | `/api/simulation/<id>/volatility` | Belief-volatility analytics — the distribution of round-over-round belief swings: `mean_delta_pct`, `std_dev_delta_pct`, `max_delta_pct`, `max_delta_round`, plus a normalized `volatility_index` on `[0, 100]` (`min(std_dev × 5, 100)`) and a `trend` label (`stable` / `converging` / `contested`). Same `|Δbullish| + |Δneutral| + |Δbearish|` swing definition `peak-round` uses, so `max_delta_round` here equals `most_volatile_round` there. Tells a high-volatility Bullish result (agents swung repeatedly before aligning) from a low-volatility one. Publish-gated; `404` when the sim has fewer than two rounds. Cached 5 minutes. `curl -s "https://your-host/api/simulation/<id>/volatility"` |
| `GET` | `/api/simulation/<id>/agents/sparklines` | Per-agent belief sparklines — for each agent, a `{round, position}` series the frontend draws as a compact SVG line, plus `final_stance` / `final_position` / `color`. The agent-level layer under `chart.svg`'s aggregate curve. Same `_avg_position` mean + ±0.2 threshold every surface uses; agent names from `reddit_profiles.json`. Agents ordered most-bullish-first; `has_per_agent_data` is `false` for single-round sims. Publish-gated; `404` until per-agent data exists. Cached 5 minutes. `curl -s "https://your-host/api/simulation/<id>/agents/sparklines"` |
| `POST` | `/api/simulation/compare` | Side-by-side belief comparison |

## Interaction

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/simulation/interview` | Chat with one agent |
| `POST` | `/api/simulation/interview/batch` | Ask a group in parallel |
| `POST` | `/api/simulation/<id>/agents/<name>/trace-interview` | Chat with full reasoning trace |
| `GET` | `/api/simulation/<id>/interviews/<name>` | Past transcripts with an agent |

## Publish / Embed / Export

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/simulation/<id>/publish` | Toggle `is_public` |
| `POST` | `/api/simulation/<id>/share-link` | Mint a private share-link token (admin-gated; body `{expires_in_days?}`, default 30, clamped `[1, 365]`). Returns `{token, preview_url, share_url, expires_at_iso, expires_in_days}`. The `preview_url` (`/preview/<token>`) bypasses the `is_public` gate for the preview page only — it does **not** publish the sim, list it on the gallery, or unlock the per-sim REST surfaces. `noindex,nofollow` + no Open Graph tags on the resolved page, so a leaked URL doesn't auto-unfurl in Discord/Slack/Twitter. Use for stakeholder previews, pre-publication review, and selective handoff to a co-author |
| `GET`  | `/api/simulation/<id>/share-links` | List active (non-revoked, non-expired) share-link tokens for a sim, newest-first by `created_at_epoch`. Admin-gated. Each entry carries `token`, `preview_url`, `share_url`, `created_at_iso`, `expires_at_iso`, `expires_in_days_remaining`, `expires_in_seconds_remaining` |
| `DELETE` | `/api/simulation/<id>/share-link/<token>` | Revoke one share-link token. Idempotent — returns `204` whether the token existed or had already been revoked. Admin-gated. The associated `/preview/<token>` URL stops resolving immediately (no proxy caching) |
| `GET`  | `/preview/<token>` | Private-preview landing page resolved from a share-link token. Returns the same SPA redirect as `/share/<id>` but with `<meta name="robots" content="noindex,nofollow">`, `X-Robots-Tag: noindex,nofollow`, `Referrer-Policy: no-referrer`, and **no** Open Graph / Twitter / Farcaster Frame / oEmbed tags — so the preview can be shared with one person without being indexed or auto-unfurled. Unknown / revoked / expired tokens all return the same `404` body ("This preview link is no longer valid.") so a probe can't distinguish the cases. `Cache-Control: no-store` |
| `GET` | `/api/simulation/<id>/embed-summary` | Embed payload (public sims only) |
| `GET` | `/api/simulation/<id>/share-card.png` | 1200×630 OG image (auto-unfurls) |
| `GET` | `/api/simulation/<id>/replay.gif` | Animated belief-bar replay |
| `GET` | `/api/simulation/<id>/transcript.md` | Markdown transcript (Notion / Obsidian / Substack) |
| `GET` | `/api/simulation/<id>/transcript.json` | Structured JSON transcript (SDKs / LLM-as-judge) |
| `GET` | `/api/simulation/<id>/trajectory.csv` | Per-round belief CSV (`pandas.read_csv()` / Excel / Tableau / R) |
| `GET` | `/api/simulation/<id>/trajectory.jsonl` | Per-round belief JSONL (DuckDB / pipelines) |
| `GET` | `/api/simulation/<id>/chart.svg` | Per-round belief chart as a stdlib-rendered SVG — embed as `<img>` in Notion / Substack / Ghost / GitHub READMEs / LaTeX. Same ±0.2 stance threshold; vector scales to any size with no JavaScript |
| `GET` | `/api/simulation/<id>/badge.svg` | Flat Shields.io-compatible 20-pixel status badge — `MiroShark` left half, `{direction} {confidence}%` right half coloured by stance (`#22c55e` Bullish / `#6b7280` Neutral / `#ef4444` Bearish). Embed in any GitHub README, Notion page, Substack post, or personal site as a one-line Markdown image; the live signal updates as the sim runs |
| `GET` | `/api/simulation/<id>/frame-metadata` | Farcaster Frame v2 metadata — `frame_version`, `image_url` (chart SVG, falling back to share card), `image_aspect_ratio`, `share_url`, `buttons`, `has_trajectory`. The matching `fc:frame:*` meta tags are emitted by the share page so a Farcaster cast containing the share URL renders as an interactive Frame card |
| `GET` | `/api/simulation/<id>/thread.txt` | Auto-formatted X / Twitter tweet thread (one tweet per belief inflection point, ≤280 chars each) |
| `GET` | `/api/simulation/<id>/thread.json` | Same tweet thread as `thread.txt` but as `{tweets, total, inflections_recorded, truncated}` for programmatic consumers |
| `GET` | `/api/simulation/<id>/polymarket.json` | Polymarket-shaped binary-market prediction — `yes_probability` / `no_probability` (sum to 1.0), `confidence_tier` (four-bucket discrete scale on top of signal.json's continuous `confidence_pct`), the underlying belief percentages, and a `suggested_market_title` shaped as `"Will …?"`. Stricter publish gate than `signal.json`: only completed sims emit a payload (a Polymarket bot acting on a mid-run signal would chase numbers that can still flip). Cached 5 minutes |
| `GET` | `/api/simulation/<id>/clone.json` | Clone payload — the first surface that returns the sim's *inputs* rather than its outputs. `clone_payload` is wire-compatible with `POST /api/simulation/create` (same field set, same defaults): a caller with the same `project_id` re-runs the sim with one curl; an AntFleet benchmark fork swaps `polymarket_market_count` from 1 to 5 and POSTs. `simulation_requirement` is echoed alongside for context (it lives at the project level rather than the create body). Cached 1 hour — these inputs don't shift round-to-round |
| `GET` | `/api/simulation/<id>/agents.json` | Agent roster export — the *participants* surface. Each agent's `name`, `username`, `bio`, `persona_preview` (truncated to 280 chars), demographics (`age` / `gender` / `mbti` / `country` / `profession` / `interested_topics`), `karma`, plus `final_stance` / `final_position` / `rounds_participated` derived from the same `trajectory.json` the sparklines read. Same ±0.2 stance threshold every other surface uses, so an agent tagged `bullish` here is `bullish` in the transcript and sparkline. Agents ordered most-bullish-first by final position; profile-only agents (no belief data) appear at the bottom with `final_stance=neutral`, `final_position=null`, `rounds_participated=0`. The companion to `agents/sparklines` (which shows belief *trajectories*): this surface answers *who was in the debate*. Publish-gated; `404` until profile data exists. Cached 1 hour — the roster is structural |
| `GET` | `/api/simulation/<id>/surface-stats` | Per-share-surface request counters — share card / replay GIF / transcript / trajectory / chart.svg / thread / watch page / Atom / RSS / reproduce.json / lineage / notebook.ipynb, plus a synthetic `total` |
| `GET` | `/api/simulation/<id>/reproduce.json` | Citation primitive — v1-schema reproducibility config blob carrying scenario, agent count, total rounds, platform toggles, time-config knobs, director events, and fork / counterfactual lineage. Identical exports of a finished sim are bytewise-identical (citation-hash friendly) |
| `GET` | `/api/simulation/<id>/cite.bib` | Drop-in BibTeX `@misc{…}` academic citation entry. Imports cleanly into Zotero / Mendeley via "Import from URL"; the `note` field carries the reproduce.json SHA-256 (verifiable via `sha256sum --check`); the `annote` field carries the OriginTrail DKG UAL when the sim has been anchored on-chain. `text/plain; charset=utf-8` |
| `GET` | `/api/simulation/<id>/notebook.ipynb` | Pre-populated Jupyter notebook — trajectory CSV embedded directly + belief-evolution / final-consensus / quality-summary cells scaffolded. Runs air-gapped (no network call back required). nbformat 4 JSON. Same bytewise-stable property as the reproduce.json blob |
| `GET` | `/api/simulation/<id>/lineage` | Lineage graph slice — parent the sim was forked / branched from + every public child whose `parent_simulation_id` points back at it. Closes the navigation gap the reproduction config left open |
| `GET` | `/api/simulation/<id>/webhook-log` | Recent outbound-webhook delivery attempts (last 10 + total count). Admin-token gated |
| `POST` | `/api/simulation/<id>/webhook-retry` | Re-fire the completion webhook for a finished sim. Admin-token gated |
| `GET` | `/share/<id>` | Public OG-tag landing page (auto-redirects to SPA). Also emits `application/json+oembed` + `text/xml+oembed` discovery `<link>` tags for published sims |
| `GET` | `/oembed?url=<share-url>&format=<json\|xml>` | oEmbed 1.0 provider — auto-unfurls a pasted `/share/<id>` link into a `type: "rich"` card (share-card thumbnail + `/embed/<id>` iframe) on Notion, Ghost, Substack, WordPress, and other oEmbed consumers. `format` defaults to `json`; unsupported format → `501`. Foreign-domain / unpublished / missing URL → `404`. Honors `X-Forwarded-*` |
| `GET` | `/watch/<id>` | Live spectator-watch page — minimal full-viewport broadcast view, polls every 15 s, OG / Twitter-card unfurl |
| `GET` | `/sitemap.xml` | Auto-generated sitemap (sitemaps.org 0.9) listing every public sim's `/share/<id>` + `/watch/<id>` URLs. `404` when `ENABLE_SITEMAP=false`. Cached 1 h |
| `GET` | `/robots.txt` | Crawler directives — `Disallow: /api/`, `Allow: /share/` etc., advertises `Sitemap:` when enabled. Cached 1 h |
| `GET` | `/api/config/sitemap` | Public flag `{enabled, sitemap_url}` exposed to the SPA so EmbedDialog renders the right indexing hint |
| `GET` | `/api/stats` | Platform-level aggregate stats — `total_sims` (public + completed), `consensus_distribution` (bullish/neutral/bearish counts + pcts via the same plurality rules `signal.json` uses), `avg_confidence_pct`, `total_surface_views` (sum across every sim's `surface-stats.json`), `unique_projects`, `newest_sim_id` + `newest_sim_created_at`. ETag derived from `total_sims` + `newest_sim_id` so `If-None-Match` short-circuits to `304`. Cached 60 s |
| `GET` | `/api/stats/badge.svg` | Flat Shields.io-compatible platform badge — `MiroShark` left half (`#555555`), `N simulations` right half (platform-blue `#0ea5e9`). Sibling of the per-sim `badge.svg` — embed in any community README, Substack, or operator portfolio to advertise live platform activity. Always returns `200` (a zero-sim deployment renders `MiroShark | 0 simulations`). Cached 60 s |
| `GET` | `/api/surfaces.json` | Machine-readable catalog of every share / platform surface this deployment exposes. Each entry carries `key`, `endpoint` (with `<simulation_id>` placeholder where relevant), `method`, `type` (one of `analytics` / `visualization` / `export` / `embed` / `integration` / `platform` / `discovery`), `description` (≤120 chars), `added_in_pr`, and a copy-pasteable `example_curl`. `ETag` short-circuits to `304` until a new surface ships. Always returns `200` or `304`. Cached 1 h |
| `GET` | `/api/ecosystem.json` | Machine-readable counterpart of `ECOSYSTEM.md` — every external project, agent, and product publicly identified as built on MiroShark. Each entry carries `name`, `url`, `description` (≤160 chars), `category` (one of `product` / `tool` / `integration` / `agent` / `benchmark`), `x_handle` (without leading `@`, nullable), and `repo` (`https://github.com/…` URL, nullable). Alphabetised by `name` to match ECOSYSTEM.md ordering. `ETag` short-circuits to `304` until a new integrator ships. Always returns `200` or `304`. Cached 1 h |
| `GET` | `/api/project/<project_id>/stats` | Per-project aggregate stats — `total_sims` (public + completed for this project), `published_sims` (alias), `consensus_distribution` (same plurality rules as `signal.json`), `avg_confidence_pct`, `quality_distribution` (`excellent` / `good` / `fair` / `poor` buckets — new in this surface), `total_surface_views`, `newest_sim_id` + `newest_sim_created_at`. Per-project sibling of `/api/stats`. `project_id` must match `[A-Za-z0-9_.-]{1,120}` (400 otherwise); unknown `project_id` returns an all-zero envelope, not 404. ETag `"project-<total>-<newest_id_prefix>"` short-circuits to `304`. Cached 60 s |
| `POST` | `/api/simulation/<id>/article` | Generate a Substack-style write-up |
| `GET` | `/api/simulation/<id>/export` | Full JSON export |
| `GET` | `/api/simulation/list` | List simulations |
| `GET` | `/api/simulation/history` | Simulation history / diffs |
| `GET` | `/api/simulation/public` | Filterable, paginated public gallery feed |

### Gallery search & filtering

`GET /api/simulation/public` supports keyword + dominant-stance + quality-tier + outcome-label + sort filters so an analyst can pull "every excellent-quality bearish call about Aave" as one URL:

```text
GET /api/simulation/public?q=aave&consensus=bearish&quality=excellent&sort=rounds&page=1
```

| Query param | Values | Notes |
|---|---|---|
| `q` | free text, ≤200 chars | Case-insensitive substring match against the scenario. |
| `consensus` | `bullish` / `neutral` / `bearish` | Dominant final-round stance using the same ±0.2 threshold the share card / replay GIF / transcript / webhook / feed all use. |
| `quality` | `excellent` / `good` / `fair` / `poor` | Compared case-insensitively against the first word of `quality_health`. |
| `outcome` | `correct` / `incorrect` / `partial` | Implies `verified=1` (verified-only). |
| `sort` | `date` / `rounds` / `agents` / `trending` | `date` (default — newest first), `rounds` (highest current_round first), `agents` (largest population first), or `trending` (highest cumulative share-surface serve count first — sums every counter the `surface-stats` endpoint exposes). |
| `verified` | truthy (`1`/`true`/`yes`) | Restrict to simulations with a recorded outcome annotation — the `/verified` hall. |
| `limit` / `offset` | `[1, 100]` / `≥0` | Pagination knobs. `total` reflects the **filtered** count. |
| `page` | `≥1` | 1-based alternative to `offset`. Wins over `offset` when both are supplied. |

Filters compose with logical AND. Empty / unknown values are no-ops, so `?consensus=` returns the unfiltered listing and `?sort=popularity` falls back to `sort=date` rather than 400-ing.

### Analyst quickstart

Pull a simulation's per-round belief trajectory straight into Pandas:

```python
import pandas as pd
df = pd.read_csv("https://your-host/api/simulation/<id>/trajectory.csv")
print(df.describe())
df[["round", "bullish_pct", "bearish_pct"]].plot(x="round")
```

Or via DuckDB / JSONL for streaming pipelines:

```python
import duckdb
duckdb.sql("""
  SELECT round, bullish_pct
  FROM read_json_auto('https://your-host/api/simulation/<id>/trajectory.jsonl')
""").df()
```

The CSV column order is locked: `round, round_timestamp, bullish_pct, neutral_pct, bearish_pct, participating_agents, total_posts, total_engagements, quality_health, participation_rate`. The bullish / neutral / bearish percentages use the same ±0.2 stance threshold as the gallery, share card, transcript, webhook, and feed surfaces, so the numbers in the DataFrame match what every other surface reports for the same round.

Or skip the boilerplate entirely and download the pre-populated notebook — trajectory data embedded, belief-evolution + final-consensus charts scaffolded, ready to run:

```bash
curl -fsSL "https://your-host/api/simulation/<id>/notebook.ipynb" \
  -o simulation.ipynb
jupyter lab simulation.ipynb     # or: code simulation.ipynb, or upload to Colab
```

The notebook is self-contained — the trajectory CSV is embedded as a Python string literal so the cells run in an air-gapped kernel. Identical exports of a finished simulation produce bytewise-identical notebooks (citation-hash friendly), same property the `reproduce.json` blob has. nbformat 4 spec: <https://nbformat.readthedocs.io/>.

### Polymarket trading-bot quickstart

A Polymarket bot can go from "simulation result" to "actionable YES / NO signal" in a single curl call — the `polymarket.json` endpoint is the adapter:

```bash
curl -s "https://your-host/api/simulation/<id>/polymarket.json" \
  | jq '{yes: .yes_probability, no: .no_probability, tier: .confidence_tier}'
```

```python
import requests
sig = requests.get(f"https://your-host/api/simulation/{sim_id}/polymarket.json", timeout=10).json()
if sig["confidence_tier"] in ("confident", "high-conviction") and sig["risk_tier"] != "high-risk":
    place_order(market_id, side="YES" if sig["yes_probability"] > 0.5 else "NO",
                size=POSITION_SIZE_BY_TIER[sig["confidence_tier"]])
```

Stricter publish gate than `signal.json`: only sims with `status == "completed"` emit a payload. A 404 means the simulation is still running or has no recorded rounds — a bot should treat it as "not ready" and skip, not retry. The `confidence_tier` field is the four-bucket discrete scale (`speculative` / `moderate` / `confident` / `high-conviction`) bots use for position-sizing logic; the underlying `confidence_pct` is also returned for callers that want the continuous value. `yes_probability + no_probability == 1.0` within float tolerance — the invariant a Polymarket order-book consumer expects.

### oEmbed auto-unfurl

Most oEmbed consumers (Notion, Ghost, Substack, WordPress) discover the endpoint automatically from the `<link rel="alternate" type="application/json+oembed">` tag on the `/share/<id>` page — paste the share link and the rich card appears with no further setup. To query the provider directly:

```bash
curl -s "https://your-host/oembed?url=https://your-host/share/<id>" \
  | jq '{type, title, thumbnail_url, html}'
```

```bash
# XML representation (some consumers, Notion among them, probe the text/xml+oembed link)
curl -s "https://your-host/oembed?url=https://your-host/share/<id>&format=xml"
```

Returns a `type: "rich"` payload — `thumbnail_url` is the 1200×630 share-card PNG and `html` is an 800×500 iframe over `/embed/<id>`. The `url` must be a share link on this deployment's own host; a foreign domain, an unpublished sim, or a missing sim all return `404`. An unsupported `format` returns `501` per the oEmbed spec.

### Search Engine Discoverability

Two infrastructure-tier endpoints make the public-simulation gallery discoverable to web search:

- `GET /sitemap.xml` — auto-generated sitemap (sitemaps.org 0.9 schema). One `<url>` per published sim's `/share/<id>` page (priority `0.8`) plus one per `/watch/<id>` page (priority `0.7`). `<lastmod>` in W3C `YYYY-MM-DD` form. `<changefreq>always</changefreq>` for in-progress sims, `weekly` / `daily` for completed ones. Sorted by `simulation_id` so two consecutive renders against the same corpus are byte-identical. Returns `404` when `ENABLE_SITEMAP=false`. Cached `public, max-age=3600`.
- `GET /robots.txt` — crawler directives. Always served. `Disallow: /api/` keeps the JSON namespace out of the index; `Allow:` lines for `/share/`, `/watch/`, `/explore`, `/verified`, `/embed/` invite crawlers into the public-discovery surfaces. When the sitemap is enabled, advertises it via the standard `Sitemap: <PUBLIC_BASE_URL>/sitemap.xml` directive.

**Submission flow:** in Google Search Console (or Bing Webmaster Tools / Yandex Webmaster / etc.), add the site once and submit `https://<your-deployment>/sitemap.xml`. Every newly published simulation lands in the next crawl — no per-sim manual step.

**Opt-out:** set `ENABLE_SITEMAP=false` in the deployment environment to make `/sitemap.xml` return 404 and drop the `Sitemap:` advertisement from `robots.txt`. Useful for private MiroShark instances or operator-only deployments where simulations should not surface in public search results.

The Embed dialog has a "🔍 Discoverable in web search" callout that confirms the simulation is in the sitemap (or explains how to enable it when disabled). The flag is exposed via `GET /api/config/sitemap` — public, no secret config leaked.

## Report Agent

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/report/generate` | Launch ReACT report agent |
| `POST` | `/api/report/generate/status` | Poll generation |
| `GET` | `/api/report/<id>` | Full report |
| `GET` | `/api/report/by-simulation/<sim_id>` | Report for a simulation |
| `GET` | `/api/report/<id>/download` | PDF export |
| `POST` | `/api/report/chat` | Chat with report agent (re-queries graph) |
| `GET` | `/api/report/<id>/agent-log` | Full ReACT trace |
| `GET` | `/api/report/<id>/agent-log/stream` | SSE stream |
| `GET` | `/api/report/<id>/console-log` | Raw LLM call logs |

## Observability

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/observability/events/stream` | SSE feed |
| `GET` | `/api/observability/events` | Event log (paginated) |
| `GET` | `/api/observability/stats` | Aggregate stats |
| `GET` | `/api/observability/llm-calls` | LLM call history |

## Settings & Push

| Method | Path | Purpose |
|---|---|---|
| `GET` / `POST` | `/api/settings` | Runtime settings (masked keys) |
| `POST` | `/api/settings/test-llm` | Ping configured LLM |
| `GET` | `/api/simulation/push/vapid-public-key` | VAPID key for web push |
| `POST` | `/api/simulation/push/subscribe` | Register a browser subscription |
| `POST` | `/api/simulation/push/test` | Fire a test notification |

## Interactive Documentation

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/docs` | Swagger UI rendered against this spec — try-it-out enabled |
| `GET` | `/api/openapi.yaml` | OpenAPI 3.1 spec, YAML form (canonical) |
| `GET` | `/api/openapi.json` | Same spec, JSON form (handy for `openapi-generator`) |

The spec is committed to the repo at `backend/openapi.yaml`. A unit test
(`backend/tests/test_unit_openapi.py`) walks every Flask route on every
push and fails CI if the spec drifts away from the implementation.
