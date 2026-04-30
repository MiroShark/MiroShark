# Features

<sup>English · [中文](FEATURES.zh-CN.md)</sup>

Deep dive on every feature. One heading per feature, ordered roughly by when you'd hit it in a typical run.

## Smart Setup (Scenario Auto-Suggest)

The Simulation Prompt field is the single blank-page barrier between uploading a document and running a simulation. Smart Setup removes it: the moment you drop in a `.md`/`.txt` file or paste a URL, MiroShark sends a short preview (~2K chars) of the extracted text to the configured LLM and returns three prediction-market-style scenario cards within ~2 seconds — one **Bull**, one **Bear**, one **Neutral** framing, each with a concrete YES/NO question, a plausible initial probability band, and a one-sentence rationale grounded in the document.

Click **Use this →** on any card to fill the Simulation Prompt field, or dismiss them and type your own. Suggestions are cached per-document (SHA-256 of the preview) so navigating away and back doesn't re-hit the LLM. If the LLM call fails or times out, the panel silently doesn't appear — your typed scenario still works exactly as before.

- **Endpoint:** `POST /api/simulation/suggest-scenarios`

## What's Trending (Auto-Discovery)

Smart Setup handles users who arrive with a document. What's Trending handles the other half — people who want to simulate *something* about AI, crypto, or geopolitics but don't have a specific article in mind. The panel sits below the URL Import box and shows the 5 most recent items across a configurable list of public RSS/Atom feeds (defaults: Reuters tech, The Verge, Hacker News, CoinDesk).

Click any card and MiroShark pre-fills the URL field, fetches the article, and immediately fires Scenario Auto-Suggest on the resulting text — blank page to three scenario cards in one click. Operators can override the feed list with the `TRENDING_FEEDS` env var (comma-separated URLs). Server-side cache holds results for 15 minutes; if every feed errors the panel disappears silently.

- **Endpoint:** `GET /api/simulation/trending`

## Just Ask (Question-Only Mode)

No document and no specific article in mind? Type a question on the Home screen ("Will the EU AI Act's biometrics clause survive the final trilogue?") and MiroShark asks the Smart model to research the topic and synthesize a 1500–3000-character briefing — neutral, structured with Context / Key Actors / Recent Events / Open Questions. The briefing becomes a `miroshark://ask/...` seed document in the URL list and pre-fills the simulation prompt, so the downstream pipeline (ontology → graph → profiles → sim) runs unchanged. Cached per-question for quick re-runs.

- **Endpoint:** `POST /api/simulation/ask`

## Counterfactual Branching

Run a simulation, pause to inspect, then ask: "what if the CEO resigns in round 24?" — click **⤷ Branch** in the simulation workspace, enter a trigger round and a breaking-news injection, and MiroShark forks the simulation with the parent's full agent population. When the runner reaches the trigger round, the injection is promoted to a director event and prepended to every agent's observation prompt as a BREAKING block. Compare the branch against the original via the existing **Compare** view.

Preset templates can declare `counterfactual_branches` (e.g. `ceo_resigns`, `class_action`, `rug_pull`, `sec_notice`) so the branch dialog offers one-click scenarios.

- **Endpoint:** `POST /api/simulation/branch-counterfactual`

## Director Mode (Live Event Injection)

Branching forks a new timeline; Director Mode edits the *current* one. While a simulation is running, inject a breaking-news event that lands on every agent's next observation prompt — no fork, no restart. Useful for stress-testing a scenario ("a competitor open-sources their model", "the SEC just opened an investigation") without spending the compute of a full branch.

Up to 10 events per simulation, each up to 500 characters. The UI control sits next to the run-status header. Events are persisted with the simulation state and replayed in the per-round frame API, so they show up in exports and embeds.

- **Endpoints:** `POST /api/simulation/<id>/director/inject`, `GET /api/simulation/<id>/director/events`

## Preset Templates

Six benchmarked scenario templates ship in `backend/app/preset_templates/` — one-click starting points that pre-fill the seed document, simulation prompt, agent mix, and (optionally) `counterfactual_branches` and `oracle_tools`:

| Template | Shape of the run |
|---|---|
| `crypto_launch` | Token / protocol launch — analysts, retail, influencers, traders react to the TGE |
| `corporate_crisis` | Enterprise incident (breach, product failure, exec scandal) with press + markets |
| `political_debate` | Policy / election topic with ideological spread and media loops |
| `product_announcement` | Keynote/feature launch — review cycle, developer reaction, consumer pickup |
| `campus_controversy` | Student/faculty/admin dynamic around a controversial event |
| `historical_whatif` | Counterfactual history — "what if event X hadn't happened?" |

Browse them in the UI via the **Templates** gallery on the setup screen, or hit `GET /api/templates/list`. Fetch a single template with `GET /api/templates/<id>`; append `?enrich=true` to resolve any declared `oracle_tools` live against FeedOracle before returning.

## Live Oracle Data (FeedOracle MCP)

Opt in to grounded seed data from the [FeedOracle MCP server](https://mcp.feedoracle.io/mcp) (484 tools across MiCA compliance, DORA assessments, macro/FRED data, DEX liquidity, sanctions, carbon markets, and more). Templates declare the tools they want:

```json
"oracle_tools": [
  {"server": "feedoracle_core", "tool": "peg_deviation", "args": {"token_symbol": "USDT"}},
  {"server": "feedoracle_core", "tool": "macro_risk",    "args": {}}
]
```

Flip `ORACLE_SEED_ENABLED=true` in `.env`, check **Use live oracle data** on any template card, and MiroShark dispatches the calls and appends the results as a markdown "Oracle Evidence" block to the seed document before ingest. Silent no-op when disabled or any call fails — the static seed still works.

## Per-Agent MCP Tools

Opt-in, OpenMiro-style: selected personas (journalists, analysts, traders) can invoke real MCP tools during the simulation. Mark a persona with `"tools_enabled": true` in its profile JSON, configure the servers in `config/mcp_servers.yaml`, and set `MCP_AGENT_TOOLS_ENABLED=true`.

Each round the runner:

1. **Injects** the tool catalogue into the agent's system message (marker-delimited so it refreshes each round).
2. **Parses** the agent's post for self-closing tags like `<mcp_call server="web_search" tool="search" args='{"q":"..."}' />` (up to 2 calls/turn).
3. **Dispatches** them through a pooled stdio subprocess per server (one process per sim, reused).
4. **Injects the results** back into the agent's system message for the next round.

Failed calls become `{"_error": "..."}` payloads rather than exceptions — agent prompts stay well-formed. The bridge has a 30-second per-call timeout (`MCP_CALL_TIMEOUT_SEC`) and tears down subprocesses on simulation end (or `atexit` on abnormal exit).

## Custom Wonderwall Endpoint

The simulation loop is the heaviest model consumer in MiroShark — 850–1650 calls per run, 7M+ tokens, all going through CAMEL-AI's per-agent action loop. The Wonderwall slot has its own `WONDERWALL_BASE_URL` + `WONDERWALL_API_KEY` env vars (and matching inputs in **Settings → Advanced → Wonderwall**) so you can route those volume hits to any OpenAI-compatible endpoint without touching the Default/Smart/NER slots — keep graph build, reports, and entity extraction on OpenRouter/Anthropic while the agents talk to a self-hosted vLLM, a Modal/Replicate deployment, an Ollama instance on a separate GPU, or a custom fine-tune of your own.

Both fields are independently optional. A blank `WONDERWALL_BASE_URL` inherits `LLM_BASE_URL`; a blank `WONDERWALL_API_KEY` inherits `LLM_API_KEY`. Open endpoints (no auth) work by passing any non-empty placeholder like `not-checked`.

```bash
WONDERWALL_BASE_URL=https://your-endpoint.example.com/v1
WONDERWALL_API_KEY=not-checked
WONDERWALL_MODEL_NAME=your-model-id
```

Wiring lives in three places. (1) `backend/scripts/run_parallel_simulation.py` (and the twitter / reddit variants) prefer `WONDERWALL_*` over `LLM_*` when reading env at subprocess start. (2) `backend/app/services/simulation_runner.py` forwards `Config.WONDERWALL_*` into the subprocess `env` at spawn time, so Settings UI updates apply on the next run without a Flask restart. (3) The Settings API (`POST /api/settings`) and the corresponding section of `SettingsPanel.vue` accept all three fields.

Useful when:
- The Wonderwall character/persona prompts work better with a fine-tune you've trained yourself.
- You want to bound cost to a fixed-rate self-hosted GPU rather than per-token billing.
- You want to compare a custom small model's belief drift / coherence against a hosted baseline by running matched simulations with everything but the Wonderwall slot held constant.

## Publishing for Embed

`EmbedDialog` has a `Public / Private` toggle backed by `is_public` on the simulation state. Embed URLs return `403` on unpublished simulations — flip the toggle (or `POST /api/simulation/<id>/publish`) to make them publicly embeddable. Defaults to private so existing sims are unaffected.

## Predictive Accuracy Ledger (Verified Predictions)

Every public simulation can be annotated with the real-world outcome it called. From the Embed dialog, choose **Called it / Partial / Called wrong**, paste the article/tweet/dashboard URL that confirmed the outcome, add a one-sentence summary (≤280 chars), and submit. The annotation lands on `<sim_dir>/outcome.json` and immediately surfaces:

- A **📍 Verified** / **⚠ Called wrong** / **◑ Partial** pill on the gallery card (the pill links straight to the outcome URL when one is provided).
- A coloured left-edge accent on the card so the verified hall reads at a glance when scrolling fast.
- A **Verified only** filter chip on `/explore` that flips the listing to the curated set.
- A dedicated **`/verified`** URL — same component as `/explore` but pre-filtered to the hall of accurate calls. Drop this link into a thread when you want a single page that proves the simulations work.

The annotation is open-ended on purpose — distinct from the binary `/resolve` endpoint, which is YES/NO and tied to Polymarket consensus. A simulation can have both: the binary resolution drives the existing accuracy_score, the outcome annotation drives the gallery credibility surface.

- **Endpoints:** `POST /api/simulation/<id>/outcome` (publish-gated), `GET /api/simulation/<id>/outcome` (read-only, no gate), `GET /api/simulation/public?verified=1` (filtered gallery).
- **UI:** "Mark outcome" panel inside the Embed dialog; **Verified only** filter chip + 📍 pills on `/explore`; dedicated `/verified` route.

## Social Share Card

When a simulation is published, the Embed dialog also exposes a **social card** that can be auto-unfurled by Twitter/X, Discord, Slack, LinkedIn, and any other Open-Graph-aware client. Two endpoints back it:

- `GET /api/simulation/<id>/share-card.png` — a 1200×630 PNG rendered server-side (Pillow). Shows the scenario headline, status pill, optional quality badge + resolution, agent / round metrics, and the final bullish/neutral/bearish split as a stacked bar. Same `is_public` gate as the embed widget. Cached on disk by content hash so repeat unfurler hits don't re-render.
- `GET /share/<id>` — a public landing page carrying the right `og:image` / `twitter:image` meta tags. Bots scrape the tags and render the card; real browsers redirect to the SPA simulation view (JS-first, with `<meta http-equiv="refresh">` fallback).

Paste the `/share/<id>` URL anywhere — the post unfurls with a polished card instead of a generic preview.

## Animated Belief Replay (GIF)

Same canvas as the share card (1200×630), but one frame per round — bullish / neutral / bearish bars sliding to each round's distribution with a round counter and a progress bar. Discord and Slack auto-play GIFs from a direct file URL, so dropping the link in a channel renders the animation inline.

- `GET /api/simulation/<id>/replay.gif` — server-rendered animated GIF (Pillow, no FFmpeg). Each frame holds for 600 ms with the final round held 3× longer so the resting consensus reads as the punch-line. Trajectories longer than 60 rounds are subsampled evenly across the run with the final round always preserved. Same `is_public` gate as the share card. Cached on disk by content hash.

The Embed dialog renders a paused thumbnail with a tap-to-play affordance (so opening the dialog doesn't pull the GIF for every viewer) and exposes a copyable URL plus a Download GIF button beneath the share-card row.

## Simulation Transcript Export

The text companion to the share card (preview) and replay GIF (motion) — the same simulation as a citable per-round agent transcript so research papers, Substack posts, and Discord threads can quote what agents actually said without screenshotting.

Two endpoints, same payload, different encoding:

- `GET /api/simulation/<id>/transcript.md` — Markdown with a YAML front-matter block (`sim_id`, `scenario`, `agent_count`, `total_rounds`, `consensus_label`, `quality_health`, `outcome_label`). Notion, Obsidian, Bear, and Substack pick it up as page metadata; the body is one `## Round N` section per recorded round with each agent post as a block quote tagged with the agent's stance. Trajectories longer than ~80 rounds elide the middle rounds in the rendered Markdown view (with a note pointing to the JSON form for the full series) so the document stays readable.
- `GET /api/simulation/<id>/transcript.json` — same payload as a structured JSON document, pretty-printed (`indent=2`) so a `curl` to a file is immediately readable. Intended for SDK consumers and downstream pipelines (LLM-as-judge eval frameworks, Python client SDK, etc.).

Both endpoints share the share-card publish gate (`is_public=true`). Per-agent stance labels use the same ±0.2 threshold as every other surface — a "bullish" agent on the gallery is the same agent's tag in the transcript. The Embed dialog exposes a "Download .md" + "Download .json" pair beneath the replay-GIF row.

## Public Gallery Feeds (RSS / Atom)

The same cards `/explore` renders, served as a syndication feed so researchers and tooling already on Feedly / Readwise / Inoreader / NetNewsWire / Obsidian RSS subscribe in their existing toolchain — no login, no MiroShark account. Every newly published simulation lands in their reader the same way an AI newsletter or Substack post does.

Two endpoints, same payload, different XML format:

- `GET /api/feed.atom` — Atom 1.0 (preferred — modern readers + the default browser auto-discovery target).
- `GET /api/feed.rss` — RSS 2.0 (kept for older self-hosted aggregators and academic RSS pipelines).

Each entry carries the scenario as the title (truncated with an ellipsis past 100 chars), the bullish / neutral / bearish consensus split as the summary line, the share-card PNG as `<media:thumbnail>` + `<media:content>` (so River-view aggregators surface a preview image), and the animated replay GIF as a second `<media:content>` (so Feedly's magazine layout shows motion). Outcome and quality are exposed as `<category>` elements so subscribers can filter on them in their reader.

- **Verified-only feed:** append `?verified=1` for the curated stream of simulations whose operators marked a real-world outcome — the syndication mirror of `/verified`.
- **Selection:** mirrors `GET /api/simulation/public` exactly — newest 20 published runs, sorted by `created_at` descending, publish-gated.
- **Auto-discovery:** the SPA's `index.html` declares `<link rel="alternate" type="application/atom+xml">` (and the RSS variant) so browsers expose the feed via the address-bar globe icon.
- **Caching:** `Cache-Control: public, max-age=300` — five minutes is short enough for newly published sims to appear in the next aggregator poll, long enough to absorb aggressive polling without taxing the gallery query.
- **Implementation:** pure stdlib (`xml.etree.ElementTree` + `html`). Zero new dependencies; same ±0.2 stance threshold as every other surface so a "62% bullish" string matches the gallery card byte-for-byte.

The Embed dialog has a "Follow the gallery via RSS" callout with one-click subscribe links for the Atom feed, the RSS 2.0 feed, and the verified-only Atom feed. The /explore header has a "📡 Subscribe via RSS" chip that mirrors the active filter (verified-only when the filter is on).

## Article Generation

After a simulation finishes, click **Write Article** and MiroShark asks the Smart model to produce a 400–600-word Substack-style write-up grounded in what actually happened — key findings, market dynamics, belief shifts, and implications. The article is cached at `generated_article.json` so it doesn't re-spend tokens on reopen; pass `force_regenerate=true` to refresh.

- **Endpoint:** `POST /api/simulation/<id>/article`

## Interaction Network & Demographics

Two post-simulation analytics that don't need LLM calls:

- **Interaction Network** (`GET /api/simulation/<id>/interaction-network`) — builds an agent-to-agent graph from likes/reposts/replies/mentions, with degree centrality, bridge scores, and echo-chamber metrics. Cached in `network.json`. Rendered as a force-directed graph in the **InteractionNetwork** panel.
- **Demographic Breakdown** (`GET /api/simulation/<id>/demographics`) — clusters agents into archetypes (analyst, influencer, retail, observer, …) and reports distribution + engagement per bucket. Useful for spotting which archetype is driving a narrative.

## Simulation Quality Diagnostics

Every run gets a health score at `GET /api/simulation/<id>/quality` — engagement density, belief coherence, agent diversity, action variance. Surfaces whether a run went the distance or collapsed into noise/silence. If coherence is low, the report is probably thin.

## History Database

The **HistoryDatabase** panel (accessible from any view via the database icon) is a full-featured browser for every simulation on disk — search by prompt/document/tag, filter by status, clone an existing run with its agent population, export to JSON, or delete. Backed by `GET /api/simulation/list`, `GET /api/simulation/history`, `GET /api/simulation/<id>/export`, and `POST /api/simulation/fork`.

## Trace Interview (Debug)

Regular persona chat shows the agent's reply. Trace Interview shows the full chain — observation prompt, LLM thoughts, parsed action, tool calls if any — for a single agent at a point in time. Invaluable for explaining *why* an agent said what they said when an interview answer looks off.

- **Endpoints:** `POST /api/simulation/<id>/agents/<agent_name>/trace-interview`, `GET /api/simulation/<id>/interviews/<agent_name>`

## Push Notifications (PWA)

The frontend registers a Service Worker and can fire web-push alerts when long-running work finishes — graph build done, simulation finished, report ready. Enable it by granting notifications permission when prompted; the backend serves a VAPID key at `GET /api/simulation/push/vapid-public-key` and accepts subscriptions at `POST /api/simulation/push/subscribe`. Test with `POST /api/simulation/push/test`. Safe to ignore if you don't need it — silent no-op without an opt-in.
