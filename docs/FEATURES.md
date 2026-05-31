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

## Shareable Scenario Links

Every other share surface (`/share/<id>`, `/watch/<id>`, replay GIF, transcript, RSS, trajectory CSV, gallery search) points readers at a *finished* simulation. Shareable Scenario Links cover the other half — the *un-run* scenario. Drop a URL into a tweet, blog post, or Discord message and the reader lands on the New Sim form with the scenario already pre-filled, one click away from launching their own run with the exact same setup.

The URL accepts four optional query parameters, each independently:

| Param | Effect | Cap |
|---|---|---|
| `scenario` | Pre-fills the Simulation Prompt textarea | 500 chars |
| `url` | Auto-fetches into the URL Import list (must be `http://` or `https://`) | 2000 chars |
| `ask` | Pre-fills the Just Ask question field — does *not* auto-run (avoids surprise LLM cost) | 300 chars |
| `template` | Auto-launches the named preset template (skips the home page entirely) | slug only |

Any combination works. `?scenario=Simulate%20a%20stablecoin%20depeg&url=https://example.com/incident-report` pre-fills the prompt *and* fetches the article in the same flow. `?template=corporate_crisis` skips straight to the template launch path. When pre-fill happens, a dismissible orange-edged banner sits above the console so the operator knows the form was populated by a shared link before they hit Launch.

Inputs are sanitised on read — HTML / `javascript:` URIs / control characters are stripped, length caps prevent megabyte payloads, and `url=` is rejected unless it starts with `http://` or `https://`. Once the form is populated, the URL params are stripped via `router.replace` so a refresh doesn't replay the pre-fill and a copy-paste of the address bar reflects the user's edited state, not the original shared link.

The reverse direction lives in two places. On the home page, a discreet **🔗 Share as link** button beneath the Simulation Prompt textarea constructs a `?scenario=...&url=...&ask=...` URL from the current form state and copies it to the clipboard — the un-run-scenario counterpart to the **Fork this scenario** button on the live watch / share-card pages. On every preset template card a small **🔗** icon next to the Launch button copies a `?template=<slug>` URL — Aaron's "try this sim" tweets gain a one-click CTA that drops the reader directly into the named template's launch flow.

Pure frontend; no backend changes. Sanitization lives in `frontend/src/utils/urlParams.js` (DOMPurify-backed) and is reused by both the read path on `/` and the write path on the home page + template gallery.

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

## Demographic Grounding (Nemotron-Anchored Personas)

Graph-grounded personas give every agent a real-world *narrative* anchor — the journalist character traces back to a journalist entity in the document. Demographic Grounding adds a *demographic* anchor on top: when `DEMOGRAPHICS_COUNTRY` is set to a registered country code (`sg`, `us`, …), the persona generator pulls one row per agent from the corresponding NVIDIA **Nemotron-Personas** parquet dataset and feeds it to the LLM as a `DEMOGRAPHIC ANCHOR` block alongside the graph context.

The result is an agent that's still authored by the LLM and still grounded in the document's relationships, but whose age, sex, geography, occupation, education, and industry come from a census-like row rather than the model's defaults. For organizational entities the same row is reframed as an `AUDIENCE ANCHOR` so the institutional voice stays intact while the tone localizes to the target demographic.

Country packs are JSON files under `backend/app/countries/` (Singapore and US ship by default). Each pack declares the HuggingFace repo id, geography field (`planning_area`, `state`), valid values, and named geography groups (`north-east`, `west`, …). To add a new country, drop a new JSON file in the directory — no code changes.

The feature is purely additive: empty env var → behavior unchanged. Missing `duckdb`/`huggingface_hub` deps → silent skip. Partial sample coverage → first N agents get seeds, the rest use graph-only generation.

- **Endpoint:** `GET /api/countries`, `GET /api/countries/<code>`
- **Details:** [DEMOGRAPHICS.md](DEMOGRAPHICS.md)

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

## Belief Trajectory Export (CSV / JSONL)

The fifth surface alongside the share card (preview), replay GIF (motion), transcript Markdown (prose), and transcript JSON (SDKs). The previous four cover the *qualitative* read of a simulation; trajectory CSV / JSONL covers the *quantitative* one — the row-per-round table a quant researcher pastes into a notebook to compute variance, autocorrelation, or compare across replicates.

Two endpoints, same row schema, different serialization:

- `GET /api/simulation/<id>/trajectory.csv` — RFC 4180 CSV, one row per recorded round. Locked column order: `round, round_timestamp, bullish_pct, neutral_pct, bearish_pct, participating_agents, total_posts, total_engagements, quality_health, participation_rate`. `pandas.read_csv("…/trajectory.csv")`, Excel "Get Data → From Web", Tableau Web Data Connector, R `read.csv()`, and Observable `d3.csv()` consume it natively. The CSV header row is emitted even for empty trajectories so downstream consumers don't have to special-case zero-row files.
- `GET /api/simulation/<id>/trajectory.jsonl` — JSON Lines (newline-delimited JSON), one object per line with the same field shape as the CSV row. The format `pandas.read_json(lines=True)`, DuckDB `read_json_auto`, and stream-processing pipelines (Kafka, Beam, Materialize) consume natively without a CSV-to-DataFrame conversion. Empty input yields zero bytes — well-formed JSONL has no header concept.

Same publish gate as the share card and transcript (`is_public=true`). The bullish / neutral / bearish percentages use the same ±0.2 stance threshold as every other surface, so a number in the CSV matches what the gallery, share card, replay GIF, transcript, webhook, and feed report for the same round. The Embed dialog exposes a "Download .csv" + "Download .jsonl" pair beneath the transcript row, plus a copyable CSV URL and a `pd.read_csv("<url>")` quickstart snippet.

## Farcaster Frame v2

The on-chain audience surface. `$MIROSHARK` lives on Base; the Base-native social layer is Farcaster / Warpcast. When a token holder, researcher, or operator pasted a `/share/<id>` URL into a Farcaster cast before this feature, the cast rendered as a blank link card — every other paste context (Twitter/X, Discord, Slack, LinkedIn, iMessage, Notion, Ghost, Substack) gets a rich unfurl from the existing Open Graph block, but Farcaster saw nothing because the spec uses its own `fc:frame:*` meta-tag schema.

The share-page `<head>` now emits a Frame v2 block alongside the existing Open Graph / Twitter tags. The `fc:frame:image` points at the per-round belief trajectory chart SVG (the same one the share dialog exposes under `📈 Trajectory chart (SVG)`), so a cast preview shows the actual bullish / neutral / bearish curve at 2:1 aspect ratio — readable inside the Warpcast feed without expanding. A single `View Simulation →` link button takes the reader to the SPA share landing in one tap. Sims that haven't recorded any rounds yet fall back to the share-card PNG at 1.91:1 so a freshly published sim still gets a Farcaster-ready unfurl while the trajectory accumulates.

Pure stdlib on the backend (`xml.etree.ElementTree` already drives the chart SVG; the Frame logic itself is just dict assembly + meta-tag templating in `app/services/frame_metadata.py`). Zero new dependencies — same posture as PR #82 (sitemap), PR #80 (notebook), PR #79 (HMAC), PR #85 (chart SVG). Private sims suppress Frame tag injection entirely, so scenario titles never leak into a cast for a sim the operator hasn't explicitly published.

The EmbedDialog surfaces a `🟣 Farcaster Frame` section: a lazy-loaded preview of the Frame image, a Warpcast composer link pre-filled with the share URL (so the operator can preview the Frame card before casting), and a copyable share URL ready to paste into any Farcaster client (Warpcast, Supercast, the in-wallet Frame in Coinbase Wallet). The `frame-metadata` JSON endpoint exists so the dialog can build the Warpcast compose link without hardcoding the host, and so future Frame-action buttons (post actions, mint flows) can be added via backend config rather than HTML redeployment.

- **Frame meta tags:** `fc:frame`, `fc:frame:image`, `fc:frame:image:aspect_ratio`, `fc:frame:button:1`, `fc:frame:button:1:action`, `fc:frame:button:1:target` — emitted by `GET /share/<id>` for published sims, silently absent for private sims.
- **Endpoint:** `GET /api/simulation/<id>/frame-metadata` → `{frame_version, image_url, image_aspect_ratio, share_url, buttons, has_trajectory, sim_title}`. Same publish gate as the chart SVG — 403 on unpublished sims, 200 with the share-card fallback for sims with no trajectory yet.

## oEmbed Auto-Unfurl (Notion / Ghost / Substack / WordPress)

The writing-platform distribution surface. Open Graph and Twitter tags cover the social platforms; Farcaster Frame v2 covers Warpcast. But the platforms where researchers and analysts actually *publish* — Notion, Ghost, Substack, WordPress — don't render from Open Graph alone; they implement the [oEmbed 1.0 spec](https://oembed.com) and look for a discovery `<link>` tag, then call back to the provider for a structured embed payload. Without it, a MiroShark link pasted into a Notion page or a Substack draft renders as a bare URL.

`GET /oembed?url=<share-url>` is that provider. The share-page `<head>` now emits two discovery tags for published sims — `<link rel="alternate" type="application/json+oembed">` and the `text/xml+oembed` variant (some consumers, Notion among them, probe for the XML link) — both pointing at the root-mounted `/oembed` endpoint. A consumer that finds the tag calls back with the share URL and receives a `type: "rich"` payload: the 1200×630 share-card PNG as `thumbnail_url` and an 800×500 iframe over the existing `/embed/<id>` SPA route as `html`. Every organic citation becomes a rich preview card with no user action.

oEmbed adds a *protocol*, not a renderer — the thumbnail and iframe both point at surfaces that already ship. Pure stdlib on the backend (`re` + `urllib.parse` + `xml.etree.ElementTree` in `app/services/oembed_service.py`), zero new dependencies. The endpoint never dereferences the inbound URL; it only extracts a sim id from a path on a host this deployment owns, so a foreign-domain `url` returns `404` and the surface can't be aimed at another site. Private and missing sims also return `404` (indistinguishable from each other), so the endpoint never confirms a private sim exists — the same gating posture as the OG / Frame tags.

- **Endpoint:** `GET /oembed?url=<share-url>&format=<json|xml>` → oEmbed `rich` payload. `format` defaults to `json`; an unsupported format returns `501` per the spec. Mounted at the root (no `/api` prefix). Honors `X-Forwarded-Proto` / `X-Forwarded-Host`.
- **Discovery tags:** `GET /share/<id>` emits `application/json+oembed` + `text/xml+oembed` `<link>` tags for published sims, silently absent for private sims.
- **Counter:** the `oembed` key joins the surface-stats schema so an operator can see how many third-party unfurls the endpoint drove.

## Trajectory Chart SVG

The scalable-vector companion to the trajectory CSV / JSONL data export. Where the CSV gives Pandas / Excel / Tableau / R the raw numbers, `GET /api/simulation/<id>/chart.svg` gives every other platform a ready-made image of the belief journey — bullish (`#22c55e`), neutral (`#6b7280`), bearish (`#ef4444`) polylines plotted against round number on a fixed `viewBox="0 0 800 400"`, with a 5-line y-axis grid, round-number x-axis labels, a three-swatch legend, and the scenario title.

Pure-stdlib `xml.etree.ElementTree` renderer — no Cairo, no matplotlib, no Pillow, zero new dependencies. Same approach as the sitemap (PR #82) and the Jupyter notebook (PR #80). The output is bytewise-deterministic so the byte hash works as a cache key the same way the reproduce.json hash works as a citation key.

Embeddable anywhere `<img>` renders — Notion, Substack, Ghost, GitHub READMEs, LinkedIn posts, Discord embeds with image attachments, and LaTeX papers via `\includesvg{}`. Vector means a reader on a 5K display sees crisp lines, and a reader on a phone sees the same chart sized down without losing axis labels. `<img>` means no JavaScript at the embed site — the chart loads with the page like any other static asset.

Same publish gate as the trajectory CSV. Returns `404` when the simulation hasn't recorded any rounds yet (the embed site can render its own placeholder rather than a blank SVG that looks like a styling bug). The Embed dialog exposes a `📈 Trajectory chart (SVG)` section beneath the trajectory CSV row: a lazy-loaded preview, a "Download .svg" anchor, a copyable URL, and a paste-ready `<img>` embed snippet. The chart-svg counter joins the surface-stats schema so an operator can see how many embeds the chart drove independently of the share card and replay GIF.

## Trading Signal JSON

The action primitive sitting on top of the data-export stack. The previous surfaces (trajectory CSV, trajectory JSONL, chart SVG, transcript, notebook, reproduce.json) describe *what happened*; `GET /api/simulation/<id>/signal.json` collapses the same final-state numbers into a single line a quant tool, alert pipeline, or Zapier / Make / n8n workflow can consume directly.

Returns a stable v1-schema JSON document:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "direction": "Bullish",
  "confidence_pct": 43.4,
  "risk_tier": "low-risk",
  "bullish_pct": 62.3,
  "neutral_pct": 17.7,
  "bearish_pct": 20.0,
  "quality_health": "excellent",
  "signal_generated_at": "2026-05-19T12:34:56Z"
}
```

- **`direction`** — `Bullish` / `Neutral` / `Bearish`, the plurality stance from the final-round belief distribution. Tie-break order is documented and stable: `bullish > bearish > neutral` so a consumer can predict the output even on rare even-split rounds.
- **`confidence_pct`** — how far the leading stance is from the three-way noise floor. `(leading_pct - 33.333) / 66.667 * 100` clamped to `[0, 100]` and rounded to one decimal place. A 33.3% leading stance is 0 (pure split); a 100% leading stance is 100 (unanimous); a 66.7% leading stance is ~50 (the midpoint).
- **`risk_tier`** — `low-risk` / `medium-risk` / `high-risk`, mapped from `quality_health`: `excellent` → `low-risk`, `good` → `medium-risk`, anything else (`fair`, `poor`, missing, `"N/A"`) → `high-risk`. The default-to-high posture is deliberate — an unknown-quality signal is treated cautiously by downstream consumers.
- **`bullish_pct` / `neutral_pct` / `bearish_pct`** — the underlying breakdown, same ±0.2 stance threshold as every other surface. A "Bullish 62%" signal here matches what the gallery card, share card, replay GIF, and trajectory CSV report for the same simulation.
- **`signal_generated_at`** — ISO-8601 UTC timestamp tracking when the signal was *computed*, not when the underlying simulation completed. Re-derived on every request (bytewise determinism is not a property of this surface — unlike `reproduce.json` / `notebook.ipynb` whose bytes need to be citation-hashable).

Pure derivation. No new computation. The underlying numbers are the same ones the embed-summary endpoint already builds, the gallery card already displays, and the share card PNG already renders. Stdlib-only (`datetime` for the timestamp); the `signal_service.py` module is ~200 LoC with no new dependencies.

Same publish gate as every other share surface (`is_public=true`). Returns `404` when the simulation hasn't recorded any rounds yet (no `belief.final` block on the embed summary) so an embedding tool can render a "not ready" placeholder rather than a half-baked signal an alert pipeline might act on. Cached for 5 minutes — a live sim's final stance can flip round-to-round, so a short cache lets alert pipelines see fresh signals while crawlers don't hammer the embed-summary build.

The Embed dialog exposes a `📡 Trading signal (JSON)` section beneath the trajectory chart row: a live preview of the signal payload, a "Download .json" anchor, a copyable URL, and a paste-ready `curl` snippet. The `signal_json` counter joins the surface-stats schema so an operator can see how many alert pipelines the signal drove independently of the visual surfaces.

Closes the gap between *"a sim produces data"* and *"a sim produces a signal"* — the last mile a quant audience needed before MiroShark output could land directly in an automation rather than a notebook.

## Peak-Round Analytics

`trajectory.csv` hands an analyst the raw per-round belief split; `chart.svg` draws the same numbers as a line. Neither answers the two questions a quant operator asks first — *"which round did bullish peak?"* and *"which round had the biggest swing?"* — without parsing every row. `GET /api/simulation/<id>/peak-round` collapses the whole trajectory into a single O(n) summary of inflection points.

Returns a stable v1-schema JSON document:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "bullish": { "round": 4, "pct": 71.4 },
  "neutral": { "round": 1, "pct": 55.0 },
  "bearish": { "round": 9, "pct": 48.2 },
  "most_volatile_round": 4,
  "max_swing_pct": 38.6,
  "total_rounds": 12
}
```

- **`bullish` / `neutral` / `bearish`** — `{round, pct}` for the round each stance reached its maximum share. Ties resolve to the *earliest* round (strict `>` comparison), so the output is deterministic on a flat-topped trajectory — it answers "when did bullish *first* peak."
- **`most_volatile_round`** — the round carrying the largest summed absolute round-over-round belief swing (`|Δbullish| + |Δneutral| + |Δbearish|`). The first round has no predecessor so its swing is zero; ties resolve to the earliest round.
- **`max_swing_pct`** — the swing value at `most_volatile_round`, rounded to two decimal places. `0.0` for a single-round or fully flat trajectory.
- **`total_rounds`** — number of usable rounds in the trajectory.

Pure derivation. The per-round percentages come from the same `trajectory_export.compute_stance_split` (±0.2 threshold) that `trajectory.csv` uses, so "bullish peaked at 71.4% on round 4" here matches row 4 of the CSV. The only new information is the *shape*: a machine-readable inflection summary, not a re-computation. Stdlib-only (`json` + `os`); `peak_round.py` is ~190 LoC with no new dependencies.

Same publish gate as every other share surface (`is_public=true`). Returns `404` when the simulation has no trajectory data yet so a consumer can tell a "not ready" sim (404) apart from a "private" sim (403). Cached for 5 minutes — matches the `chart.svg` / `trajectory` / `signal.json` cadence.

The Embed dialog exposes a `📊 Peak beliefs (JSON)` section beneath the trading-signal row: a live preview (bullish / bearish peaks, the most-volatile round, total rounds), a copyable URL, and a paste-ready `curl` snippet. The `peak_round` counter joins the surface-stats schema so an operator can see how often the analytical summary is pulled independently of the raw CSV.

Completes the analytical quadrant alongside `trajectory.csv` (raw data), `chart.svg` (visual), and `signal.json` (final-state action primitive) — the inflection-point view those three left implicit.

## Belief Volatility Score

`signal.json` answers *where the swarm landed* (direction + confidence). `peak-round` picks the single most-volatile round. Neither answers the question a quant operator asks third — *"how contested was the path to consensus?"* A high-volatility Bullish result (agents swung repeatedly before aligning) is a different input than a low-volatility one where consensus formed in round three and held; for a position-sizing model the same final direction can mean very different things. `GET /api/simulation/<id>/volatility` describes the distribution of round-over-round swings so the turbulence dimension is finally readable next to the direction and the inflection.

Returns a stable v1-schema JSON document:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "mean_delta_pct": 12.45,
  "std_dev_delta_pct": 8.16,
  "max_delta_pct": 38.6,
  "max_delta_round": 4,
  "volatility_index": 40.8,
  "trend": "converging",
  "total_rounds": 12,
  "delta_count": 11
}
```

- **`mean_delta_pct` / `std_dev_delta_pct` / `max_delta_pct`** — the mean, population standard deviation, and maximum of the round-over-round summed-absolute belief swings, all rounded to two decimal places. The swing for each round is `|Δbullish| + |Δneutral| + |Δbearish|` — the exact definition `peak-round` already uses to pick its single `most_volatile_round`.
- **`max_delta_round`** — the round carrying `max_delta_pct`. Equals `most_volatile_round` from `peak-round` on the same input by construction; ties resolve to the earliest round.
- **`volatility_index`** — a normalized 0–100 turbulence score: `min(std_dev_delta_pct × 5, 100)`. A std dev of 20 pp maps to 100, a fully flat trajectory lands at 0. The 5× multiplier is a calibration knob — the formula is in the schema so an integrator can rescale to a different range without reverse-engineering.
- **`trend`** — `"stable"` when `std_dev_delta_pct < 3` (very tight cluster), `"converging"` when the second half of the trajectory's deltas has strictly lower std dev than the first half (the swarm calmed down), `"contested"` otherwise. Trajectories with fewer than four deltas fall back to the std-dev-only buckets, since there's no honest half-vs-half comparison.
- **`total_rounds` / `delta_count`** — the number of usable rounds and the number of round-over-round deltas (`total_rounds - 1`).

Pure derivation, transposed: instead of picking the single maximum (the inflection view) it summarises the distribution of *every* swing. Stdlib-only (`json` + `os` + `math` for std dev); `volatility_service.py` has no new dependencies.

Same publish gate as every other share surface (`is_public=true`). Returns `404` when the simulation has fewer than two rounds (no deltas to compute) so a consumer can tell a "not ready" sim (404) apart from a "private" sim (403). Cached for 5 minutes — matches the `chart.svg` / `trajectory` / `peak-round` / `signal.json` cadence.

The Embed dialog exposes a `📈 Belief volatility (JSON)` section beneath the peak-round row: a live preview (volatility index with a gradient bar, max swing, mean swing, std dev, trend chip), a copyable URL, and a paste-ready `curl` snippet. The `volatility` counter joins the surface-stats schema so an operator can see how often the turbulence view is pulled independently of the raw CSV.

Closes the three-factor analytical view — `signal.json` for *direction*, `peak-round` for *when*, `volatility` for *how contested* — that downstream quant tooling needs alongside the raw trajectory.

## Per-Agent Belief Sparklines

`chart.svg` and the embed-summary draw the *aggregate* belief curve — what the swarm concluded, round by round. `peak-round` collapses that aggregate into inflection points. Neither exposes the layer underneath: *each individual agent's* belief path. A researcher studying swarm convergence — *"which agent anchored the consensus? did the financial-analyst cohort align before the retail traders?"* — had no surface for it short of parsing `transcript.md` by hand. `GET /api/simulation/<id>/agents/sparklines` is the agent-level companion: one belief trajectory per agent.

Returns a stable v1-schema JSON document:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "agent_count": 24,
  "round_count": 12,
  "has_per_agent_data": true,
  "agents": [
    {
      "agent_id": 7,
      "name": "Skeptical Quant",
      "final_stance": "bullish",
      "final_position": 0.612,
      "color": "#22c55e",
      "trajectory": [
        { "round": 1, "position": 0.05 },
        { "round": 2, "position": 0.31 },
        { "round": 3, "position": 0.612 }
      ]
    }
  ]
}
```

- **`agents`** — one entry per agent that holds a usable belief position, ordered most-bullish-first by `final_position` (ties broken by `agent_id`), so the list reads top-to-bottom from the strongest bull to the strongest bear.
- **`trajectory`** — the agent's scalar belief position per round, sorted ascending by round. Each `position` is the mean of that agent's per-topic `belief_positions` (roughly `[-1, 1]`), rounded to three decimals — the exact `_avg_position` every other surface averages before bucketing.
- **`final_stance` / `color`** — the stance of the agent's last-round position under the same ±0.2 threshold, plus the matching hex color (`#22c55e` bullish, `#6b7280` neutral, `#ef4444` bearish) so a sparkline is the same green as a bullish `chart.svg` line.
- **`name`** — display name from `reddit_profiles.json` (then `polymarket_profiles.json`); `"Agent <id>"` when no profile row exists, so a sparkline is never anonymous.
- **`has_per_agent_data`** — `true` only when at least one agent has a 2-point trajectory (enough to draw a line). A single-round simulation returns the agents as single dots with this flag `false`, so a consumer can show a "needs ≥2 rounds" note instead of a row of meaningless dots.

Pure derivation, transposed: instead of bucketing all agents into one per-round percentage (the aggregate view), it tracks one scalar per agent per round. Stdlib-only (`json` + `os`); `agent_sparklines_service.py` has no new dependencies.

Same publish gate as every other share surface (`is_public=true`). Returns `404` when no agent holds a usable belief position yet — a "not ready" sim (404) apart from a "private" sim (403). Cached for 5 minutes — matches the `chart.svg` / `trajectory` / `peak-round` cadence.

The Embed dialog exposes a `🤖 Agent trajectories (JSON)` section beneath the peak-round row: a scrollable list of agents, each a name chip + an inline SVG sparkline (belief position over rounds, stroked in the agent's stance color) + the final-stance label, plus a copyable URL and a paste-ready `curl` snippet. The `agent_sparklines` counter joins the surface-stats schema so an operator can see how often the agent-level view is pulled.

## Polymarket-Ready Prediction JSON

The first share surface adapted for a specific external integrator. `signal.json` emits a generic action primitive (`direction` + `confidence_pct` + `risk_tier`); `GET /api/simulation/<id>/polymarket.json` re-shapes that primitive into the binary YES / NO probability envelope a Polymarket trading bot expects between *"simulation result"* and *"actionable market signal"*.

Returns a stable v1-schema JSON document:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "direction": "Bullish",
  "yes_probability": 0.62,
  "no_probability": 0.38,
  "confidence_pct": 43.4,
  "confidence_tier": "moderate",
  "risk_tier": "low-risk",
  "bullish_pct": 62.0,
  "neutral_pct": 18.0,
  "bearish_pct": 20.0,
  "quality_health": "excellent",
  "suggested_market_title": "Will Aave pass the safety-module change?",
  "source_sim_id": "<sim_id>",
  "polymarket_generated_at": "2026-05-23T14:22:01Z"
}
```

- **`yes_probability` / `no_probability`** — direction-aware. A Bullish swarm emits a high `yes_probability` (`bullish_pct / 100`); a Bearish swarm emits a low one (`1 - bearish_pct / 100`); a Neutral swarm lands exactly at `0.5` (the coin-flip prior). `yes + no == 1.0` within float tolerance — the invariant a Polymarket order-book consumer expects. Both rounded to four decimal places, matching Polymarket's display rail precision.
- **`confidence_tier`** — four-bucket discrete scale on top of `signal.json`'s continuous `confidence_pct`. `<25` → `speculative`, `25-50` → `moderate`, `50-75` → `confident`, `≥75` → `high-conviction`. Upper bounds are exclusive (`25.0` is `moderate`, not `speculative`). Bots typically gate position size on this tier — different sizing for "speculative" vs. "high-conviction" — rather than the raw continuous value.
- **`suggested_market_title`** — synthesised as `"Will {scenario}?"` for Polymarket's display rail. A scenario that already starts with `"Will "` is not double-prefixed; trailing punctuation is stripped before truncation at 120 characters (with `"…?"` when truncated). Missing / empty scenarios fall back to `"Will resolve YES?"`. A *suggested* title — the bot author is expected to massage the string.
- **`source_sim_id`** — echoes the simulation id under the field name a Polymarket bot expects when writing back to its own audit log. The canonical `simulation_id` key (every other share surface) carries the same value, so consumers can read either.

Pure derivation, layered on `signal_service`. The `polymarket_service.py` module is ~230 LoC of stdlib Python — `compute_polymarket` calls `signal_service.compute_signal` and reshapes its output. Every property the signal payload guarantees (tie-break order, one-decimal rounding, ISO-8601 timestamp format) carries through. A "Bullish 62%" simulation emits identical underlying numbers across the gallery card, the share card, `signal.json`, `badge.svg`, and `polymarket.json` — only the *envelope* changes.

Stricter publish gate than `signal.json`: only sims with `status == "completed"` emit a payload. A Polymarket bot sizing positions against a mid-run signal would chase numbers that can still flip; the completed-only posture prevents that footgun. Mid-run sims and freshly-published sims that haven't recorded any rounds yet both return `404`. Cached for 5 minutes — matches the `signal.json` cadence so a bot polling both surfaces sees consistent values.

The Embed dialog exposes a `🎯 Polymarket prediction (JSON)` section beneath the trading-signal row: a live preview of the YES / NO probabilities, the confidence and risk tiers, the suggested market title, a "Download .json" anchor, a copyable URL, and a paste-ready `curl | jq` snippet. The `polymarket_json` counter joins the surface-stats schema so an operator can see how many Polymarket bots the prediction surface drove independently of the visual surfaces.

Zero new dependencies (streak: 31 PRs). The first surface naming a specific external integrator — pairing with PR #83 ("Discord/Slack notifications" — first feature naming `@revaultdrops`) and continuing the explicit-audience pattern that drives external integrator adoption.

## Simulation Clone JSON

Every other share surface returns *outputs* — direction, chart, badge, trajectories, volatility score, agent sparklines, Polymarket envelope. `GET /api/simulation/<id>/clone.json` is the first surface that returns *inputs*: the exact configuration a sim was built with, in the shape `POST /api/simulation/create` accepts.

Returns a stable v1-schema JSON envelope:

```json
{
  "schema_version": "1",
  "simulation_id": "sim_abc123",
  "project_id": "proj_xyz789",
  "graph_id": "miroshark_def456",
  "simulation_requirement": "Will Aave's reserve factor doubling reduce TVL?",
  "scenario_preview": "Will Aave's reserve factor doubling reduce TVL?",
  "clone_payload": {
    "project_id": "proj_xyz789",
    "graph_id": "miroshark_def456",
    "enable_twitter": true,
    "enable_reddit": true,
    "enable_polymarket": false,
    "polymarket_market_count": 1,
    "country": null,
    "demographic_filters": null
  },
  "example_curl": "curl -fsSL -X POST 'https://your-host/api/simulation/create' -H 'Content-Type: application/json' -d '{…}'"
}
```

- **Wire-compatible with `/api/simulation/create`** — `clone_payload` is the literal request body that endpoint accepts. A caller with the same `project_id` re-runs the sim with one `curl -X POST`; a benchmark workflow forking the sim swaps a knob and POSTs the modified body. No reshaping required, no manual re-entry of toggles or filters.
- **`simulation_requirement` is informational** — the scenario text lives at the project level (a project may host multiple simulations across the same graph + scenario). `/api/simulation/create` doesn't accept `simulation_requirement` as a body field — the project's value is reused. A fork that needs a *different* scenario updates the project before POSTing the clone payload. The field is echoed in the envelope so the caller knows what the cloned sim debates.
- **`country` + `demographic_filters` carry through** — when the original sim was anchored in a Nemotron demographic pack, the clone payload preserves the country code (lowercased + stripped, matching `manager.create_simulation`'s normalisation) and the filter dict (empty filter dicts coerce to `null` since they are semantically equivalent to "no filtering"). A caller forking into a different demographic just swaps the field and POSTs.
- **`example_curl` carries the literal `https://your-host` placeholder** — same posture as the surfaces catalog. A copy-paste of the example never accidentally hits an internal URL; the operator substitutes their deployment host before running it.
- **`polymarket_market_count` is clamped to `[1, 5]`** — matches `manager.create_simulation`'s clamp so a hand-edited state.json can't produce a clone payload that the create handler would reject.

Pure derivation. The `clone_service.py` module is ~250 LoC of stdlib Python — `build_clone_payload` reads `state.json` (the structural fields `/create` accepts) and `simulation_config.json` (the scenario text). No new dependencies, no LLM calls, no graph traversal — pure file I/O over two on-disk artifacts every published sim already has.

Same publish gate as every other share surface (`is_public=true`). Returns `404` when no `state.json` exists on disk (mid-prepare or pruned) so a consumer can tell a "not ready" sim (404) apart from a "private" sim (403). Cached for one hour — the clone payload is structural (project_id / graph_id / toggles / country / demographic_filters). Unlike the analytical surfaces (peak-round / volatility / signal), these inputs don't shift round-to-round; an hour is the right cadence for a "structural snapshot of how this sim was configured" surface.

The `clone_json` counter joins the surface-stats schema. Pairs with the existing `/api/simulation/compare` endpoint: clone the inputs, run the sim, then diff the outputs against the original. Closes the API half of the still-unbuilt Scenario Clone Button workflow.

## Consensus Status Badge SVG

The cheapest visible pointer back to a simulation. The previous twelve share surfaces describe a simulation in increasing depth (chart SVG, replay GIF, trajectory CSV / JSONL, transcript, notebook, signal.json, archive.zip, ...); `GET /api/simulation/<id>/badge.svg` is the *passive distribution lever* — a flat 20-pixel-tall Shields.io-compatible SVG that fits inside any `<img>` tag, Markdown image link, or `<link rel="alternate">` reference. Every researcher's GitHub README, every Notion page, every operator's personal site can embed a live consensus badge with one line of Markdown:

```markdown
![MiroShark](https://your-host/api/simulation/<id>/badge.svg)
```

The badge has the canonical Shields.io flat layout: left half "MiroShark" on the standard `#555555` grey, right half `{direction} {confidence_pct}%` on the stance colour — `#22c55e` (Bullish), `#6b7280` (Neutral), `#ef4444` (Bearish). The colour vocabulary matches every other belief surface (chart SVG, share card, replay GIF, watch page, email belief percentages), so a reader who saw the chart in the same README recognises the badge instantly. Direction + confidence derive from the same `compute_signal` pipeline `signal.json` uses — a "Bullish 72%" badge here matches the signal payload, the gallery card, and the share card byte-for-byte.

Pure stdlib `xml.etree.ElementTree` renderer (~330 LoC in `app/services/badge_service.py`); zero new dependencies — same posture as `chart_svg`, `frame_metadata`, `share_card`, and every other renderer module. The rendered SVG is bytewise-deterministic across calls with the same inputs, so a future ETag layer / on-disk cache gets stable cache keys.

- **`viewBox="0 0 W 20"`** — Shields.io flat-style canonical height. The badge sits flush next to a GitHub-Actions / npm / PyPI badge in the same README without an obvious height mismatch. The width scales with the right-label length (`Bullish 5%` is narrower than `Bearish 100%`).
- **Pill ends** — Rounded corners via a `<clipPath>` with `rx="3"` so the badge renders correctly across every `<img>` consumer including older Notion / Substack / GitHub Markdown previewers. No `<linearGradient>` or `<defs>` — the flat preset is bytewise smaller and renders identically in screen-reader text-only mode.
- **Accessibility** — `role="img"` + `aria-label="MiroShark: Bullish 72%"` + a `<title>` element. Screen readers announce the status; SEO crawlers pick up the same text.
- **Defensive on input** — Unknown / missing direction renders with the neutral grey + an explicit `Unknown` label rather than raising. Confidence outside `[0, 100]` clamps; non-numeric becomes `0`. The route handler treats "no rounds yet" as a 404 upstream so an embedded `<img>` renders a broken-image placeholder rather than a misleading `Unknown 0%` badge.

Same publish gate as every other share surface (`is_public=true`). `Cache-Control: public, max-age=60` — a live sim's stance flip propagates through to every embedded badge within one polling cycle (matches the watch-page poll cadence), so a researcher embedding the badge in a README and refreshing the page sees the latest consensus. Short enough that mid-run stance shifts get to readers quickly; long enough that a popular README doesn't hammer the embed-summary build with one fetch per page view.

The Embed dialog exposes a `🏷️ Status badge (SVG)` section: a live in-place preview, a copyable badge URL, a `![MiroShark Belief Badge](...)` Markdown snippet, and an `<img height="20">` HTML snippet. The `badge_svg` counter joins the surface-stats schema so an operator can see how many README / blog / Notion embeds drive views back to the share page.

Turns every distributed share URL into a *pull point* for new visitors who see the badge in a researcher's README — the first share surface that brings the simulation *to* the reader, instead of waiting for the reader to navigate to the share page.

## Platform Aggregate Statistics

The first endpoint that describes the platform itself rather than one simulation. `GET /api/stats` collapses every simulation on disk that satisfies `is_public == true` AND `status == "completed"` into a single envelope: a total sim count, a consensus distribution (bullish / neutral / bearish counts + percentages), an average `confidence_pct` across the corpus, a sum of every `surface-stats.json` counter on disk, the count of unique `project_id`s the simulations span, and the newest-sim identifier + created-at timestamp. One read powers press kits ("MiroShark has run N simulations"), external dashboards, LLM-agent health checks (*"is this MiroShark instance active?"*), and the platform Shields.io badge below.

```json
{
  "success": true,
  "data": {
    "schema_version": "1",
    "total_sims": 1247,
    "consensus_distribution": {
      "bullish": 612, "neutral": 308, "bearish": 327,
      "bullish_pct": 49.1, "neutral_pct": 24.7, "bearish_pct": 26.2
    },
    "avg_confidence_pct": 58.4,
    "total_surface_views": 41682,
    "unique_projects": 89,
    "newest_sim_id": "sim_e7c1b2f3a9d4",
    "newest_sim_created_at": "2026-05-24T15:42:11.103928"
  }
}
```

- **Stance counts inherit the per-sim derivation.** The same plurality + tie-break rules (`bullish > bearish > neutral`) that turn a sim's final belief split into a `direction` on the per-sim `signal.json` produce the platform-level counts here. A simulation labelled Bullish on its `signal.json` is counted in the `bullish` bucket on this aggregate — two surfaces, one source of truth.
- **`unique_projects`, not `unique_operators`.** `SimulationState` carries no operator / created-by field — `project_id` is the closest stable identifier. Each project is conventionally a single research / operator workspace, so the project count is a reasonable proxy for the operator count, but the field name doesn't promise data the model can't back. A future model migration can add a dedicated `operator` field and a sibling `unique_operators` aggregate without breaking this surface.
- **One-scan, 60-second cache.** A module-level cache keyed on the simulation root absorbs bursty press unfurls — every call after the first inside the 60-second window is a dict copy, not a disk scan. The route additionally emits a short `ETag` derived from `total_sims` + `newest_sim_id`; an `If-None-Match` conditional GET short-circuits to `304 Not Modified` without re-serialising the body, so a README badge polling every minute pays roughly the cost of one HEAD request per window.
- **Empty deployments degrade cleanly.** A fresh install with zero published simulations returns a fully-zeroed envelope, not a 404. A consumer rendering "*N simulations run*" doesn't need to special-case the first day of deployment.

Pure stdlib (`os` + `json` + `time` + `threading`, ~340 LoC in `app/services/platform_stats.py`); zero new dependencies — same posture as `signal_service`, `badge_service`, and every other aggregate module. The scan walks `WONDERWALL_SIMULATION_DATA_DIR` directly; no Neo4j, no LLM, no outbound network.

## Platform Stats Badge SVG

The platform-level sibling of the per-sim `/badge.svg`. `GET /api/stats/badge.svg` returns a flat 20-pixel Shields.io-compatible pill — `MiroShark` on the standard Shields.io grey (`#555555`), `N simulations` on platform-blue (`#0ea5e9`). One line of Markdown turns any community README, Substack header, or operator portfolio into a live platform-activity indicator:

```markdown
![MiroShark](https://your-host/api/stats/badge.svg)
```

The count is the same `total_sims` value `/api/stats` reports — the two surfaces share the same scan and the same 60-second cache. Platform-blue is visually distinct from the three per-sim stance colours (`#22c55e` / `#6b7280` / `#ef4444`) so a reader never mistakes the platform badge for a per-sim consensus badge — sim badges sit on the right edge of "this specific run was bullish"; platform badges sit on the left edge of "this whole project is active".

A zero-sim deployment renders a valid `MiroShark | 0 simulations` pill rather than a 404 — an embedded `<img>` on a freshly-installed instance never broken-image-glyphs. Same flat layout, accessibility attributes (`role="img"`, `aria-label="MiroShark: N simulations"`, `<title>` element), and rounded `<clipPath>` pill ends as the per-sim badge; the only differences are the right-half label and fill colour. Bytewise-deterministic across calls with the same input count — a future ETag layer can hash the response bytes directly.

A second-order distribution amplifier: per-sim badges (PR #94) are pull points for *specific simulations*; the platform badge is a pull point for *MiroShark itself*. Every operator running an Aeon framework instance, every researcher with a personal site, every Substack post about swarm simulations becomes a live signal that the platform is active and growing.

## BibTeX Academic Citation

Closes the academic citation arc. `reproduce.json` (PR #79) carries every parameter a second operator needs to re-run the simulation; the OriginTrail DKG citation (PR #84) anchors those bytes on-chain as cryptographic provenance; the `notebook.ipynb` (PR #80) drops the trajectory into a researcher's IDE. `GET /api/simulation/<id>/cite.bib` adds the missing layer — a one-call BibTeX `@misc{…}` entry that drops straight into a LaTeX paper source, imports cleanly into Zotero / Mendeley via "Import from URL" (both readers consume `text/plain` BibTeX at an HTTP URL directly), and carries the reproduce.json SHA-256 in the `note` field so a reviewer can verify the citation points to the same simulation parameters years later via `sha256sum --check`.

```bibtex
@misc{miroshark-sim_abc123def4,
  title        = {What if Aave's reserve factor doubled overnight?},
  author       = {MiroShark},
  year         = {2026},
  month        = may,
  url          = {https://miroshark.example.com/share/sim_abc123def456},
  howpublished = {\url{https://miroshark.example.com/api/simulation/sim_abc123def456/reproduce.json}},
  note         = {Reproducibility SHA-256: 5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8},
  annote       = {OriginTrail DKG UAL: did:dkg:base:8453/0xabc/12345},
}
```

- **Stable citation key.** `miroshark-{sim_id[:16]}` with non-`[A-Za-z0-9_-]` characters stripped — the BibTeX grammar allows only those in a citation key. Same input → same key across re-renders, so an author who pinned the key once never sees their `\cite{}` references silently rewire.
- **Escapes the seven BibTeX specials.** `&`, `%`, `$`, `#`, `_` get the canonical backslash escape; `{` and `}` get the backslash-bracket escape; backslashes themselves get `\textbackslash{}`; carets and tildes get `\^{}` / `\~{}`. A scenario containing "100% APY & a flash_loan exploit" parses cleanly in LaTeX without a manual sanitisation step.
- **SHA-256 sourced from the on-chain anchor when available.** The DKG citation (`<sim_dir>/dkg-citation.json`) stores the reproduce.json hash as `sha256:<hex>` — the BibTeX builder strips the prefix and lands the bare hex digest in the `note` field. When no DKG citation exists, the builder freshly hashes the canonical reproduce.json bytes (via the same `repro_export.render_json_bytes` the standalone `/reproduce.json` route uses), so the `note` value matches what `curl reproduce.json | sha256sum` would produce.
- **`annote` records the DKG UAL when present.** A reviewer reading the citation can follow the UAL to the on-chain assertion, fetch the Knowledge Asset, and verify the recorded reproduce.json hash matches the local hash — DOI-grade provenance without a publishing-house intermediary.
- **Zotero / Mendeley import URL is the endpoint URL.** Paste `https://miroshark.example.com/api/simulation/<id>/cite.bib` into Zotero → "File → Import from URL" or Mendeley → "Web Importer" and the entry lands in the library with metadata pre-populated. No manual BibTeX export step.
- **Defensive on input.** Missing scenario → "Untitled MiroShark simulation". Missing / unparseable `created_at` → current UTC year + month. Missing `simulation_id` → `miroshark-unknown` (the route handler still returns 404 in that case — the fallback exists for the unit tests that exercise the renderer in isolation). The route handler never raises on this surface — citation must be available even when ancillary files are missing.

Pure stdlib `hashlib` + `datetime` + `re` (~310 LoC in `app/services/bibtex_service.py`); zero new dependencies — same posture as `signal_service`, `badge_service`, and `repro_export`. The rendered bytes are bytewise-deterministic across calls with identical inputs (the only timestamp-driven content is the optional generation comment, which the route handler omits), so a citation chain anchored against the entry's bytes (a future ETag layer / hash-based cache) is stable across requests.

Same publish gate as every other share surface (`is_public=true`). `Content-Type: text/plain; charset=utf-8` so Zotero's URL importer picks the right parser, with `Content-Disposition: inline; filename="miroshark-<id12>.bib"` so `curl -OJ` saves it ready to drop into a `\bibliography{}` block. Cached for 5 minutes — matches the `reproduce.json` + notebook cadence; the entry stabilises once the sim reaches a terminal state.

The Embed dialog exposes a `📖 BibTeX citation (.bib)` section beneath the reproducibility config panel: a copyable `cite.bib` URL, a `curl -fsSL '<url>' -o miroshark-<id>.bib` snippet, a paste-ready `\cite{miroshark-...}` LaTeX reference snippet (the citation key is deterministic from the sim id, so the in-paper reference syntax is correct before the `.bib` file is even fetched), and a "Download .bib" anchor for the save-as flow. The `cite_bib` counter joins the surface-stats schema so an operator can see how many academic citations the simulation is driving independently of the other surfaces — a spike here indicates the sim is being cited in a paper draft.

Turns "MiroShark is a research tool" from a positioning claim into a citation chain a peer reviewer can actually follow.

## Simulation Archive Bundle

The take-offline composite — one ZIP, every published share surface inside. Until now a researcher finishing a simulation had to chain up to nine separate `curl` calls to take the artifact set offline (`share-card.png`, `chart.svg`, `trajectory.csv`, `trajectory.jsonl`, `transcript.md`, `thread.txt`, `reproduce.json`, `notebook.ipynb`, `signal.json`). `GET /api/simulation/<id>/archive.zip` collapses every successfully-rendered surface into one timestamped ZIP plus a `manifest.json` that pairs each contained file with its SHA-256, byte size, MIME type, and canonical source URL.

```json
{
  "schema_version": "1",
  "simulation_id": "sim_abc123…",
  "archive_generated_at": "2026-05-20T12:34:56Z",
  "base_url": "https://miroshark.example.com",
  "file_count": 8,
  "files": [
    {
      "filename": "share-card.png",
      "sha256": "<hex>",
      "size_bytes": 12345,
      "source_url": "https://miroshark.example.com/api/simulation/sim_abc.../share-card.png",
      "mime_type": "image/png"
    },
    {
      "filename": "chart.svg",
      "sha256": "<hex>",
      "size_bytes": 8192,
      "source_url": "https://miroshark.example.com/api/simulation/sim_abc.../chart.svg",
      "mime_type": "image/svg+xml"
    }
  ]
}
```

**Compositional, not duplicative.** Every bundled file comes from the same renderer the standalone surface route already serves — `share_card.render_share_card`, `chart_svg.render_chart_svg_bytes`, `trajectory_export.render_csv` / `render_jsonl`, `repro_export.render_json_bytes`, `notebook_export.render_notebook_bytes`, `signal_service.compute_signal`, `transcript.render_markdown_bytes`, `thread_formatter.render_thread_txt`. A file inside `archive.zip` is byte-for-byte identical to the same file fetched from its standalone URL, so the SHA-256 in the manifest matches what a hash-of-the-canonical-URL workflow would compute. Citation chains anchored against `reproduce.json`'s OriginTrail DKG hash (PR #84) line up across both distribution paths.

**Best-effort assembly.** Every surface builder is wrapped in a `try/except` and a missing-or-corrupt artifact yields an omitted entry rather than a `500`. The `file_count` + `files` array in the manifest enumerate exactly what landed in the ZIP — a consumer who needs a specific file can tell whether it was excluded because the underlying artifact wasn't ready vs. because the run had `n=0` rounds.

**Deterministic file timestamps.** Every `ZipInfo` entry carries the same fixed `date_time` (`1980-01-01T00:00:00`) so the per-file portion of the archive bytes is reproducible across two builds of the same input set. The `manifest.json` carries `archive_generated_at` which is the only drift across requests — consumers who need bit-stable archives can hash the contained files individually (each is bytewise-deterministic) and ignore the manifest timestamp.

Pure stdlib (`zipfile` + `hashlib` + `io` + `json` + `datetime`). Zero new dependencies — same posture as every other surface module. `archive_service.py` is ~430 LoC.

Same publish gate as every other share surface (`is_public=true`). Returns `404` when no exportable surfaces are available yet (a freshly published sim that hasn't recorded any rounds — even `signal.json` and `reproduce.json` need a final belief block to compose). Cached for 5 minutes — matches the notebook + reproduce.json cadence so a live run's growing trajectory propagates through within a polling cycle.

The Embed dialog exposes a `📦 Archive bundle (.zip)` section beneath the trading-signal row: a live file-count badge (read off the `X-MiroShark-Archive-Files` response header so the dialog doesn't have to download the full ZIP just to render a preview), a summary grid (file count + compression format + citation guarantee), a "Download archive.zip" anchor, a copyable URL, and a paste-ready `curl -OJ` snippet that uses the server-supplied filename. The `archive_zip` counter joins the surface-stats schema so an operator can see how many take-offline workflows the archive drove independently of the individual surfaces.

Closes the *"how does a researcher take a sim home"* gap that nine independent endpoints couldn't close on their own.

## Gallery Search & Filtering

`/explore` is the public research surface — every published MiroShark simulation, browsable as a card grid. Once the corpus grew past a few dozen entries the reverse-chronological scroll stopped being a tool, so the gallery now indexes itself: a keyword search box, a consensus filter chip group, a quality filter chip group, and a sort dropdown sit above the cards. The active filter set lives in URL params (`?q=…&consensus=bearish&quality=excellent&sort=rounds`), so any filtered view is bookmarkable and shareable — "every excellent-quality bearish call about Aave" is a URL you can tweet.

- **`q`** — case-insensitive substring match against the scenario text. Trimmed; capped at 200 chars.
- **`consensus`** — `bullish` / `neutral` / `bearish`. Filters by the dominant final-round stance using the same ±0.2 threshold the share card, replay GIF, transcript, webhook, and feed renderers all use, so a "bullish" filter here matches what those surfaces report for the same simulation.
- **`quality`** — `excellent` / `good` / `fair` / `poor`. Compared case-insensitively against the first word of `quality_health`.
- **`outcome`** — `correct` / `incorrect` / `partial`. Implies `verified=1` (verified-only).
- **`sort`** — `date` (default — newest first), `rounds` (highest current_round first), `agents` (largest population first), or `trending` (highest cumulative share-surface serve count first — sums every counter the `surface-stats` endpoint exposes; ties break on date so the most-served-and-most-recent floats above the most-served-and-stale). `trending` is the first feedback loop from distribution analytics into discovery ranking — sims that get shared get found more easily.
- **`page`** — 1-based page number; alternative to `offset`. `page=1` is offset 0. The two compose the same way: `total` reflects the **filtered** count (not the corpus size), so the load-more "X remaining" hint and `has_more` flag stay accurate inside the active filter set.

The `/verified` route preserves the `verifiedOnly: true` mode and stays compatible with every filter — `/verified?q=aave&consensus=bullish` works. Toggling Verified ↔ Explore via the header chip carries the active query string across the route swap so the user doesn't lose their search.

- **Endpoint:** `GET /api/simulation/public?q=…&consensus=bullish&quality=excellent&sort=rounds&page=2`
- **Compose with verified:** `GET /api/simulation/public?verified=1&consensus=bearish` returns every bearish call that has a recorded outcome.
- **Implementation:** pure stdlib in-memory filter over the gallery cards already assembled by the public endpoint. Zero new dependencies. The endpoint stays cached for 30 s, so a busy gallery amortises the per-sim card build over many filtered requests.

A "📊 Reset" button appears once any filter is active; the empty state ("No simulations match your filters") points back at the same reset rather than dead-ending on a "no public sims yet" message that wouldn't apply.

## Public Gallery Feeds (RSS / Atom)

The same cards `/explore` renders, served as a syndication feed so researchers and tooling already on Feedly / Readwise / Inoreader / NetNewsWire / Obsidian RSS subscribe in their existing toolchain — no login, no MiroShark account. Every newly published simulation lands in their reader the same way an AI newsletter or Substack post does.

Two endpoints, same payload, different XML format:

- `GET /api/feed.atom` — Atom 1.0 (preferred — modern readers + the default browser auto-discovery target).
- `GET /api/feed.rss` — RSS 2.0 (kept for older self-hosted aggregators and academic RSS pipelines).

Each entry carries the scenario as the title (truncated with an ellipsis past 100 chars), the bullish / neutral / bearish consensus split as the summary line, the share-card PNG as `<media:thumbnail>` + `<media:content>` (so River-view aggregators surface a preview image), and the animated replay GIF as a second `<media:content>` (so Feedly's magazine layout shows motion). Outcome and quality are exposed as `<category>` elements so subscribers can filter on them in their reader.

- **Verified-only feed:** append `?verified=1` for the curated stream of simulations whose operators marked a real-world outcome — the syndication mirror of `/verified`.
- **Filtered feeds:** the same filter knobs the gallery API exposes work on the feed surface — `?consensus=bullish&quality=excellent&sort=trending&q=etf&outcome=correct&limit=N` (default 20, max 50). Filters combine with logical AND, unknown values fall back to "no filter" for that knob, and active filters surface in the feed channel title + subtitle ("MiroShark · Public Simulations · Bullish · Excellent · Filtered: …"). Same ±0.2 stance dominance threshold as the gallery, so `consensus=bullish` returns the same set on both surfaces. Subscribe to "bullish-only" in Feedly, pipe "trending + excellent" into an n8n workflow, or tail "correct outcomes only" in a Slack channel via Zapier — without any new write paths or new dependencies. The Embed dialog has a filter builder that previews the URL and exposes a one-click copy button.
- **Selection:** mirrors `GET /api/simulation/public` exactly — newest 20 published runs by default, sorted by `created_at` descending, publish-gated. Filtered variants reuse the same `gallery_filters.select_filtered_cards` helper so a `consensus=bullish` set on `/explore` matches the corresponding feed slice byte-for-byte.
- **Auto-discovery:** the SPA's `index.html` declares `<link rel="alternate" type="application/atom+xml">` (and the RSS variant) so browsers expose the feed via the address-bar globe icon.
- **Caching:** `Cache-Control: public, max-age=300` — five minutes is short enough for newly published sims to appear in the next aggregator poll, long enough to absorb aggressive polling without taxing the gallery query.
- **Implementation:** pure stdlib (`xml.etree.ElementTree` + `html`). Zero new dependencies; same ±0.2 stance threshold as every other surface so a "62% bullish" string matches the gallery card byte-for-byte.

The Embed dialog has a "Follow the gallery via RSS" callout with one-click subscribe links for the Atom feed, the RSS 2.0 feed, and the verified-only Atom feed, plus a **filter builder** (consensus + quality + sort) that emits the matching `?consensus=…&quality=…&sort=…` URL with a copy button — the slice an operator picks lands directly in any reader that consumes RSS or Atom. The /explore header has a "📡 Subscribe via RSS" chip that mirrors the active filter (verified-only when the filter is on).

## Search-Engine Sitemap (`/sitemap.xml` + `/robots.txt`)

The auto-generated discovery surface for web search. Every other share surface (`/share/<id>`, `/watch/<id>`, RSS / Atom, replay GIF) makes an *individual* simulation findable to someone who already has the link. The sitemap closes the gap on the *other* half — researchers and operators who don't know the simulation exists yet but search for the scenario keywords.

`GET /sitemap.xml` walks the public-simulation corpus once per request and emits the sitemaps.org 0.9 XML document Googlebot / Bingbot / DuckDuckBot expect:

- One `<url>` block per published sim's `/share/<id>` page (priority `0.8`, the canonical citation surface).
- One `<url>` block per published sim's `/watch/<id>` page (priority `0.7`, the live broadcast surface).
- `<lastmod>` in W3C `YYYY-MM-DD` form, derived from `state.json`'s `updated_at` / `created_at` / file mtime fallback chain.
- `<changefreq>always</changefreq>` for in-progress sims (the belief bars genuinely change every round); `weekly` for completed share entries, `daily` for completed watch entries (the watch page re-renders less often once the run terminates).
- Sims sorted by `simulation_id` ascending so two consecutive renders against the same corpus produce byte-identical XML.

`GET /robots.txt` is the companion discovery file. Every deployment serves it (whether the sitemap is enabled or not) so well-behaved crawlers see the `Disallow: /api/` directive that keeps the JSON namespace out of the search index. When the sitemap is enabled, a trailing `Sitemap: <PUBLIC_BASE_URL>/sitemap.xml` line points crawlers at it for automatic discovery — submit once to Google Search Console and every newly published sim becomes searchable on the next crawl. The robots file always carries `Allow:` lines for the public-discovery surfaces (`/share/`, `/watch/`, `/explore`, `/verified`, `/embed/`) so crawlers know which routes they're invited into.

- **Opt-out:** `ENABLE_SITEMAP=false` (default `true`) makes `/sitemap.xml` return `404` and drops the `Sitemap:` line from `robots.txt`. Operators running a private MiroShark instance — or one indexing sensitive scenarios — flip the flag.
- **Bounded:** capped at 50,000 `<url>` entries (the spec ceiling per file). MiroShark's public corpus is currently three-figure small; the cap is defense-in-depth against pathological bulk-fork patterns rather than a normal truncation case.
- **Caching:** `Cache-Control: public, max-age=3600` — hourly is fast enough for a freshly published sim to surface to crawlers at the next refresh, slow enough that a noisy crawler doesn't tax the gallery query.
- **Implementation:** `app/services/sitemap.py` (~270 LoC, pure stdlib `xml.etree.ElementTree` + `os` + `datetime`) + `app/api/sitemap.py` (Flask blueprint mounted at the root, no `/api` prefix, mirroring `share_bp` / `watch_bp`). Zero new dependencies.

The Embed dialog has a "🔍 Discoverable in web search" callout — distinct from the RSS subscribe block above — with a "View sitemap.xml ↗" link. The flag comes from a public `GET /api/config/sitemap` endpoint so the dialog renders the right hint when an operator has opted out.

## Live Watch Page (Spectator Broadcast)

The seventh thin renderer over the same on-disk `sim_dir/` folder. The previous six (gallery card, share card, replay GIF, transcript, RSS / Atom feed, trajectory CSV / JSONL) all surface a *finished* simulation; the watch page surfaces a *live* one — the format MiroShark was missing for "tweet a sim mid-run" sharing.

`GET /watch/<simulation_id>` returns a self-contained server-rendered HTML page built for live spectating: a minimal full-viewport view with a belief bar, round counter, agent count, quality health, progress bar, and a vanilla-JS poller that updates the DOM in place every 15 s by hitting the existing `/api/simulation/<id>/embed-summary` and `/api/simulation/<id>/run-status` REST endpoints. Once the runner reaches a terminal state (`completed` / `failed` / `stopped`) polling stops and the "View full simulation →" + "Fork this scenario →" CTAs are revealed.

- **OG / Twitter unfurl:** the body carries `og:type`, `og:title`, `og:description`, `og:image` (1200×630 share-card PNG), `twitter:card=summary_large_image`, etc. — same auto-unfurl behaviour as `/share/<id>`. The `og:description` becomes "Round N/M · Bullish X% · Neutral Y% · Bearish Z% — watch live." for in-flight runs, falls back to the bare scenario for idle runs, and to a generic string when nothing is published yet.
- **Self-contained:** no SPA build dependency. The poller is vanilla JS, the styles are inline. Works on a stripped-down deployment, behind a restrictive CSP that allows only `img-src 'self'`, and even with JS disabled (the SSR HTML still shows a meaningful frame).
- **Publish gate:** the underlying live endpoints honour `is_public`, so a private simulation only renders the bare broadcast frame (no scenario, no live numbers). The fact a private sim *exists* with that id never leaks through the page chrome.
- **Stance threshold parity:** the bootstrap blob exposes the ±0.2 threshold the page uses for the bullish / neutral / bearish split — same threshold as every other surface, so a spectator who sees the share card on Twitter and clicks through to `/watch/<id>` doesn't see the numbers shift mid-flow.
- **Caching:** `Cache-Control: public, max-age=60` — short enough to keep the unfurl reasonably fresh after a newly-published run, long enough to absorb crawler load.
- **Implementation:** `app/services/watch_renderer.py` (pure stdlib `html` + `json`) + `app/api/watch.py` (Flask blueprint mounted at the root, no `/api` prefix, mirroring `share_bp`). Zero new dependencies.

The Embed dialog has a "Watch live (broadcast page)" callout — distinct from the share-card section above — with an "Open watch page ↗" button and a copyable URL. The callout is publish-gated to make the affordance match the underlying behaviour.

## Tweet Thread Export (X / Twitter)

The sixth share format alongside the share card (visual), replay GIF (motion), transcript (prose), trajectory CSV/JSONL (data), and watch page (live). The previous five surfaces handle long-form, structured, or live formats; this one is the **short-form text channel** that X / Twitter speaks natively — the format Aaron's primary distribution channel uses.

Two endpoints, same payload, different serialization:

- `GET /api/simulation/<id>/thread.txt` — plain-text tweet thread, one tweet per block separated by `---` on its own line. Each tweet ≤280 characters. Paste-and-go for the X compose box, or upload to a thread scheduler (Typefully, Hypefury, Tweet Hunter, Twittascope) that splits on `---`.
- `GET /api/simulation/<id>/thread.json` — same payload as `{tweets: [string], total: int, inflections_recorded: int, truncated: bool}`. Programmatic consumers iterate `tweets` directly without splitting on the separator.

Thread structure:

1. **Intro tweet** — scenario summary (truncated past ~200 chars with an ellipsis) + scale (`N rounds · M agents`) + final consensus label (`Consensus: Bullish` / `Neutral` / `Bearish` / `split`) + thread numbering `1/`.
2. **Body** — one tweet per **belief inflection point** (rounds where the dominant stance crossed the ±0.2 threshold *and* led the runner-up by ≥0.2pp; flat / no-dominant rounds are skipped as noise). Format: `"Round N: stance shifted to <label>"` + a stance-line `"↑ Bullish X% · → Neutral Y% · ↓ Bearish Z%"`.
3. **Close tweet** — `Final: <label> consensus` + the same stance line + `Quality: <health>` + `Watch the replay: <watch_url>` + `Run this scenario: <share_url>`.

Threads with more than `MAX_THREAD_TWEETS - 2 = 13` body tweets are truncated to the first 3 + last 3 inflections with a single bridge line (`… N more flips between here and the close …`); the JSON form's `truncated: true` flag signals when this happened. Same publish gate as the share card (`is_public=true`); same ±0.2 stance threshold as every other surface; honours `X-Forwarded-Proto` / `X-Forwarded-Host` for the watch + share URLs in the close tweet.

The Embed dialog has a "🧵 Tweet thread" section beneath the trajectory row: a "Copy full thread" button (joins the per-tweet array with `\n---\n` so a single paste produces a valid X thread), download links for both the `.txt` and `.json` forms, and an inline list of tweets with per-tweet copy buttons + character counters so an operator can pick individual tweets to post.

Implementation: `app/services/thread_formatter.py` (pure stdlib `json` + `os`, ~430 LoC) + `_serve_thread()` shared body in `app/api/simulation.py` mirroring the `_serve_transcript` / `_serve_trajectory` pattern. Zero new dependencies.

## Surface Usage Analytics

The first **inbound** observability surface, paired with the outbound webhook delivery log. Every successful share-surface response increments a counter on disk (`<sim_dir>/surface-stats.json`); `GET /api/simulation/<id>/surface-stats` returns the per-surface counts so an operator running MiroShark for a DeFi fund or research group can see which surfaces their audience actually uses.

Counters tracked (one per share surface):

- `share_card` — `share-card.png` serves
- `replay_gif` — `replay.gif` serves
- `transcript_md` / `transcript_json` — `transcript.md` / `transcript.json` serves
- `trajectory_csv` / `trajectory_jsonl` — `trajectory.csv` / `trajectory.jsonl` serves
- `thread_txt` / `thread_json` — `thread.txt` / `thread.json` serves
- `watch_page` — `/watch/<id>` serves (public sims only)
- `feed_atom` / `feed_rss` — number of times this simulation was syndicated to an Atom or RSS feed render
- `reproduce_json` — `reproduce.json` serves (citation primitive — every fetch is an attempted reproduction)
- `lineage` — `/lineage` serves (graph navigation — every fetch is an operator walking the fork tree)
- `notebook_ipynb` — `notebook.ipynb` serves (every fetch is an analyst opening the run in Jupyter / VS Code / Colab)

Plus a synthetic `total` summing all counters. Every key is always present (zero-defaulted), so a frontend renders the table without special-casing missing fields.

Implementation:

- **Atomic writes.** Each increment is a read-modify-write through a tempfile + `os.replace`, so two concurrent requests can't truncate the JSON to `{` and lose every prior count. Same pattern the webhook delivery log uses.
- **Bounded.** A single small JSON object — only the keys in `SURFACE_KEYS` are persisted; an unknown key from a rogue caller is silently dropped, never written.
- **Fire-and-forget.** Increment never raises; a corrupt counter file is silently reset to zeros. The serve path always succeeds, even when the analytics layer is broken (read-only mount, full disk, antivirus lock on the staging file).
- **Stdlib only.** `json` + `os` + `tempfile`. Zero new dependencies.

The Embed dialog has a "📊 Distribution" panel (collapsed by default, click the chevron to expand) — a sorted two-column table (surface · count, ranked by count desc), a `Total serves: N` row, and a `↻ Refresh` button. The panel is publish-gated; private sims see "Publish the simulation to see distribution stats." instead. Same publish gate as every other share surface (`is_public=true`).

## Reproducibility Config Export

The **citation primitive** behind every other share surface. Six of the ten share surfaces (transcript, trajectory, thread, watch, GIF, share card) make a finished simulation citable — but until this endpoint shipped, none of them carried the parameters needed to reproduce the run. PR #71's shareable scenario URLs carry the scenario text and template slug; this blob carries everything else, in a single pretty-printed file suitable for a paper appendix or a thread screenshot.

`GET /api/simulation/<id>/reproduce.json` returns a v1-schema JSON document with:

- **`schema_version`** — literal `"1"`. Bumped on breaking changes; v1-aware parsers should reject other values.
- **`exported_at`** — UTC ISO-8601 timestamp of the export.
- **`simulation_id`** — echoed sim id.
- **`scenario`** — the simulation requirement / scenario text. Falls back to the state-level `simulation_requirement` field for older sims that wrote it onto state rather than into the generated config.
- **`agent_count`** — number of agent profiles generated for the run (maps to `state.profiles_count`).
- **`total_rounds`** — total rounds the simulation ran (or is configured to run). Prefers the runner's recorded total; falls back to `time_config.total_simulation_hours * 60 / time_config.minutes_per_round` when the runner hasn't populated the field.
- **`platforms`** — the four boolean / integer parameters that decide which channels the agents post to: `twitter`, `reddit`, `polymarket`, `polymarket_market_count`.
- **`time_config`** — the four cadence knobs that drive the simulation's temporal envelope: `minutes_per_round`, `total_simulation_hours`, `peak_hours`, `off_peak_hours`. Field set is intentionally narrow: the full LLM-generated config includes per-agent posting frequency + event schedules + platform tuning, but those are derived from the entity graph rather than parameters a researcher reproduces by hand.
- **`director_events`** — operator-injected scenario events (e.g. "Liquidity Crisis" at round 15) that shaped the belief curve. `null` when no events were injected — the common case. Each event carries its `round`, `label`, and optional `description`.
- **`lineage`** — describes how this simulation was created. `kind` is one of `original` (created via the standard prepare flow), `fork` (created via `POST /api/simulation/fork`, same agent population, new sim id), or `counterfactual` (created via `POST /api/simulation/branch-counterfactual`, a fork plus an injection event scheduled at a specific round). Carries `parent_simulation_id` plus, for counterfactual branches, a `counterfactual` sub-object with `trigger_round` / `label` / 140-char `preview` so the badge can render the headline without a second fetch.
- **`config_reasoning`** — LLM-generated rationale for the chosen knobs, captured at prepare time. Empty string for older sims that didn't persist a rationale.

Implementation:

- **Pure stdlib.** `json` + `os`. No new dependencies; helpers in `app/services/repro_export.py`.
- **Read-only.** The service composes the blob from on-disk artifacts (`state.json`, `simulation_config.json`, `counterfactual_injection.json`, optional director events) — it never writes.
- **Schema-locked.** `SCHEMA_VERSION` constant + `REQUIRED_KEYS` frozenset so a downstream consumer can validate cheaply via `validate_blob(blob)`.
- **Defense-in-depth.** Corrupt artifacts degrade to `null` rather than 500ing the export — the citation surface must be available even when ancillary files are missing.
- **Bytewise-stable.** Pretty-printed (indent=2, sort_keys=True) so identical exports of the same finished simulation are byte-for-byte identical. The file hash is therefore a stable citation key.

Cached for 5 minutes; the blob does not change once the sim has reached a terminal state. Same publish gate as every other share surface — requires the simulation to be public (`is_public=true`).

The Embed dialog has a "🔬 Reproducibility config" panel (collapsed by default) — a summary grid (Schema version · Agents · Rounds · Platforms · Director events · Lineage), a "Reproduce via curl" snippet ready to copy, a `Download reproduce.json` button, and (when the sim was forked or branched) a small inline lineage badge — `🪐 Forked` or `🔀 Counterfactual` — beside the title. The badge tooltip shows the canonical parent sim id so the operator can grab it for `/share/<id>` or `/watch/<id>` without reading the JSON.

## Jupyter Notebook Export

The **analysis-ready** companion to the reproducibility config — the second institution-targeted export. The trajectory CSV told analysts *"here is the data"*; the notebook tells them *"here is the analysis, ready to run."* Institutional observers (the Lorimer-Ventures tier) who land on a published simulation download a single `.ipynb` file and open it in JupyterLab / VS Code / Google Colab — no boilerplate `pd.read_csv()` + `import matplotlib.pyplot as plt` + axis-config to write.

`GET /api/simulation/<id>/notebook.ipynb` returns an nbformat 4 JSON document with a locked seven-cell sequence:

1. **Markdown header.** Sim id, scenario as blockquote, run metadata table (agents · rounds · platforms · lineage · quality health · generated_at), reproducibility URL link.
2. **Code: imports.** A commented `%pip install --quiet pandas matplotlib` line for the kernel that doesn't have them yet, plus `import io / pandas as pd / matplotlib.pyplot as plt`.
3. **Code: trajectory load.** The full `trajectory.csv` content is embedded directly inside the notebook as a Python string literal (via `repr()`, so any byte sequence — including arbitrary numbers of consecutive quotes, backslashes, embedded newlines — round-trips correctly), then read via `pd.read_csv(io.StringIO(TRAJECTORY_CSV))`. Anyone running the cell gets the same bytes the `trajectory.csv` endpoint serves. The cell finishes with `df.head()` to preview the DataFrame.
4. **Code: belief-evolution chart.** Three-line plot (bullish / neutral / bearish percentages over rounds) using the same `#22c55e` / `#6b7280` / `#ef4444` palette every other surface uses, so a screenshot of this chart is paste-compatible with the share card.
5. **Code: final-round consensus.** Bar chart of the final stance distribution with per-bar percentage annotations.
6. **Code: quality + participation summary.** A small `pd.DataFrame` summarising row count, first/last round, unique `quality_health` values, and the last non-null `participation_rate`. Surfaces the run health at a glance without scanning the whole DataFrame.
7. **Markdown footer.** Reproducibility metadata (notebook schema version, simulation id, trajectory SHA-256 hash, full reproduce.json link). The SHA-256 lets a reviewer verify the embedded data wasn't tampered with after the file was downloaded.

Implementation:

- **Standalone-runnable.** The trajectory data lives inside the notebook itself — no network call back to the MiroShark host is required to hit Run All. This matters for paper-appendix attachments and academic archive environments where reviewer kernels are sandboxed (and for institutional analysts whose corporate firewalls block outbound HTTP).
- **Pure stdlib.** `json` + `os` + `hashlib`, plus `trajectory_export.build_rows` reused for CSV row assembly so the embedded data matches what `trajectory.csv` serves byte-for-byte. The chart code cells are strings — Matplotlib is referenced inside the cells the user runs, never imported at generation time. Zero new dependencies. Helpers in `app/services/notebook_export.py`.
- **Bytewise-stable.** Same `sort_keys=True + indent=2 + trailing newline` pattern the reproducibility config uses, so two exports of the same finished simulation produce bytewise-identical notebooks. The file hash is therefore a stable citation key, same property the `reproduce.json` blob has.
- **Schema-locked.** `SCHEMA_VERSION = "1"` plus a `CELL_ORDER` constant pinning the cell-type sequence. Downstream tools that pin "the chart cell is at index 4" stay correct across minor refactors.
- **Defense-in-depth.** Missing artifacts (sim still running, corrupt trajectory, no quality file) degrade gracefully — the notebook still renders, the embedded CSV may just have fewer rows.

Cached for 5 minutes; same publish gate as every other share surface — requires `is_public=true`. The Embed dialog has a "📓 Jupyter notebook" panel beneath the reproducibility config — a "Download via curl" snippet ready to copy, a `Download notebook.ipynb` button, and a `Copy URL` button. The download surface is intentionally pure — there's no inline preview because the `.ipynb` body is a 30+ KB JSON document the SPA shouldn't pull just to render a button.

## Simulation Lineage Navigator

Closes the navigation gap PR #75's reproducibility config export uncovered. The `parent_simulation_id` pointer is on disk for every fork or counterfactual branch, but the lineage was *one-directional* — a child knew its parent, the parent had no visibility into its children. A researcher who runs a base scenario then triggers three counterfactual branches has to remember each child sim id; there's no way to navigate from the parent to "the three branches that diverged at round 12".

`GET /api/simulation/<id>/lineage` returns the lineage graph slice rooted at the requested sim:

- **`simulation_id`** — echoed.
- **`lineage_kind`** — `"original"` / `"fork"` / `"counterfactual"`. Mirrors `lineage.kind` in the reproduce.json export.
- **`parent`** — the parent sim entry (`simulation_id`, `scenario_preview` truncated to 80 chars, `created_at`, `is_public`), or `null` for original sims. When the parent has been unpublished after the fact, the entry is echoed with `is_public=false` and an empty `scenario_preview` so the SPA can render a bare placeholder.
- **`children`** — every **public** simulation whose `parent_simulation_id` matches the requested sim. Each child carries its own `kind` (`fork` / `counterfactual`) and an optional `counterfactual` block (`trigger_round` + `label`) so the badge can render "🔀 Counterfactual at round 12 (ceo_resigns)" inline. Sorted by `created_at` ascending — oldest fork first, the natural narrative order. Capped at 50 entries.
- **`total_children`** — public-only scan total, even when the response was truncated by the cap.
- **`counterfactual`** — when the requested sim is itself a counterfactual branch, the trigger round + label travel along so the panel can render the headline without a second `reproduce.json` fetch.

Implementation:

- **Pure stdlib.** `json` + `os`. Helpers in `app/services/lineage_service.py`. No new dependencies.
- **Read-only.** The service composes the response from on-disk `state.json` files for the requested sim + the candidate child set. Never writes.
- **Public children only.** Operators forking privately for in-progress work do not leak those branches into a tweeted parent's lineage view.
- **Defense-in-depth.** A child whose `state.json` is mid-rewrite or corrupt at scan time is silently skipped — the lineage view never crashes a load. Self-pointing edge cases (a hand-edited sim whose `parent_simulation_id` is itself) do not recurse.
- **Bounded.** `MAX_CHILDREN = 50` cap is defense-in-depth against a pathologically forked sim. Sims with more children than that are an extreme outlier; `total_children` reflects the uncapped count so the UI can show "showing first N of M".

Cached for 5 minutes; the graph slice is stable once the parent and its branches reach terminal states. Same publish gate as every other share surface — requires the simulation to be public (`is_public=true`).

The Embed dialog has a "🌳 Lineage" panel that auto-shows whenever there's something to navigate to (a parent, one or more children, or both). Originals with no forks see no panel at all — the dialog stays as compact as it was before this section shipped. The panel renders the parent as a one-row card with a 60-char scenario preview + "Open parent ↗" link, and each public child as a clickable row tagged `🪐 Forked` or `🔀 Counterfactual`. Counterfactual rows surface the trigger round + label inline ("At round 12 (ceo_resigns) · scenario preview…") so the row reads as the narrative event, not a slightly different scenario. Clicking any row opens that sim's `/watch/<id>` page in a new tab.

## Webhook Delivery Log

Every dispatch attempt of the outbound completion webhook (the one configured in **Settings → Integrations → Webhook**, see [WEBHOOKS.md](WEBHOOKS.md)) appends a JSON line to `<sim_dir>/webhook-log.jsonl`. Each row records:

- **`attempt`** — monotonically increasing 1-based counter (survives the on-disk truncation at 50 rows).
- **`timestamp`** — UTC ISO-8601 of when the dispatch completed.
- **`url_masked`** — `scheme://host/***`. The path of a Slack / Discord webhook URL is the secret and is *never* persisted to disk.
- **`event`** / **`status`** — the `event` field from the dispatched payload (`simulation.completed` / `simulation.failed`) and the terminal status the run reached.
- **`status_code`** — HTTP status returned by the downstream endpoint, or `null` for network errors / timeouts (so a real 5xx is distinguishable from a TCP reset).
- **`ok`** — `true` for a 2xx response; `false` for any other outcome.
- **`latency_ms`** — wall-clock time of the HTTP call in milliseconds.
- **`error`** — human-readable upstream error string on failure (e.g. `HTTP 503`, `URL error: timeout`); `null` on success.
- **`trigger`** — `auto` for the runner-fired path, `retry` for an operator-driven replay.

Two endpoints surface the log:

- **`GET /api/simulation/<id>/webhook-log`** — admin-token gated. Returns the last 10 entries newest-first plus the all-time `total_attempts` counter and the on-disk retention bound (`max_retained: 50`). Operators use this to verify the webhook fired, see the HTTP status / latency, and decide whether to retry.
- **`POST /api/simulation/<id>/webhook-retry`** — admin-token gated. Re-fires the completion webhook for a sim already in a terminal state (useful when the original delivery hit a transient 5xx, the URL was misconfigured at the time, or the consuming integration was down). The retry payload carries `retry: true` so downstream consumers can dedupe replays. Bypasses the per-process `(sim_id, status)` dedup gate the auto-fire path uses (that gate exists only to prevent the runner's two terminal code paths from double-firing automatically; an explicit retry should always go through). Returns 400 when no webhook URL is configured, 409 when the simulation has not reached a terminal state.

The Embed dialog has a **📡 Webhook delivery history** panel beneath the outcome row (admin-token gated, collapsed by default to keep the dialog compact for users who don't have a webhook configured). Each delivery renders as a status chip (✓ green for 2xx, ✗ red for 4xx/5xx, ⏱ amber for timeouts) with the HTTP code, latency, trigger label, and timestamp. **Refresh** re-pulls the log; **Retry delivery** re-fires the webhook and refreshes after a short delay so the new attempt shows up automatically.

The dispatcher writes to disk only after the POST returns (or times out) so the dispatch path stays fire-and-forget — the log write never blocks the simulation runner. Log writes use a read-modify-rename pattern (atomic via `os.replace`) so the log can never be corrupted by a partial write. URL masking happens before serialization, so the secret in a Slack / Discord URL is gone the moment it lands on disk.

Implementation: helpers in `app/services/webhook_service.py` (`_record_delivery`, `_append_log_entry`, `read_webhook_log`, `retry_webhook_for_simulation`) + `_start_dispatch_thread` shared between auto-fire and retry paths. Zero new dependencies (pure stdlib `json` + `os` + `time` + `threading`). Bounded to 50 lines on disk; older deliveries roll off so the log never grows unbounded.

## Webhook Signature Verification

When `WEBHOOK_SECRET` is set, every outbound webhook payload is HMAC-signed and the digest is shipped as an `X-MiroShark-Signature: sha256=<hex>` header alongside the existing `X-MiroShark-Event` / `X-MiroShark-Sim-Id` headers. The signature lets a recipient prove the payload actually came from this MiroShark instance — the same scheme Stripe and GitHub use for their outbound webhooks, verifiable on the consumer side with three lines of stdlib `hmac`.

- **Signed over the raw body.** The digest is computed from the bytes that get sent on the wire, *before* any re-serialization on the recipient side. Consumers must verify before parsing JSON — re-serializing can re-order keys or change whitespace and break the digest.
- **`sha256=<64 hex chars>` format.** Same shape Stripe and GitHub use. Always lowercase hex; constant 64-char digest length.
- **Backward compatible.** When `WEBHOOK_SECRET` is unset or blank, the header is omitted entirely and existing integrations continue working without changes. Recipients that have no secret configured should treat "no signature header" as "no signature configured" and decide locally whether to accept unsigned deliveries.
- **Transport-only.** The secret is never persisted to the delivery log (`webhook-log.jsonl` records the masked URL, never the secret or the signature). Rotating the secret on both sides is a no-downtime operation — in-flight retries pick up whatever value is set at dispatch time.
- **Retries carry their own signature.** The retry endpoint adds `retry: true` to the payload, which changes the body bytes, which changes the signature. Each delivery (auto-fire or operator-driven retry) carries the signature for its own body.
- **Constant-time verification.** The published helper (`verify_signature` in `app/services/webhook_service.py`) uses `hmac.compare_digest` so a network attacker can't time-trial the comparison. The verification snippets in [WEBHOOKS.md](WEBHOOKS.md) → "Verifying webhook signatures" follow the same pattern.

Implementation: `compute_signature(payload_bytes, secret=None)` reads `WEBHOOK_SECRET` at call time (so a Settings change or env mutation takes effect immediately), returns `"sha256=" + hmac.sha256(secret, body).hexdigest()` or `None` when blank. `_post_json` injects the header only when `compute_signature` returns non-None — auto-fire, retry, and the `Send test event` button all share the same dispatch path, so all three paths sign consistently. Zero new dependencies (pure stdlib `hmac` + `hashlib`).

## Webhook Event Filtering

When `WEBHOOK_EVENTS` is set, MiroShark filters dispatch at the source — every completion payload is evaluated against the comma-separated allow-list before the daemon thread is spawned, and non-matching payloads are logged and dropped. Useful when an integrator only cares about a slice of the stream: a Polymarket bot subscribed to `bullish,bearish,high_confidence`, a research pipeline subscribed to `excellent_quality`, a Bearish-flip alerter subscribed to `bearish`. The original behavior is preserved — blank or unset `WEBHOOK_EVENTS` fires on every completion exactly as before.

- **Three categories.** Direction tokens (`bullish` / `neutral` / `bearish`) OR within themselves; confidence tokens (`high_confidence` >= 75%, `medium_confidence` 50–75%) OR within themselves; quality tokens (`excellent_quality`, `good_quality` = good OR excellent) OR within themselves. Categories combine with AND: `bullish,high_confidence,excellent_quality` means all three must hold.
- **Direction derived consistently.** The dominant-stance rule matches the share-card colour, the Discord embed border, and every other surface that reports "bullish / neutral / bearish" — `bullish` here means the same sims a viewer would call bullish.
- **Failed sims always fire.** `simulation.failed` bypasses every rule. A filter that swallows the one alert an operator added the webhook to catch would be worse than no filter at all.
- **Unknown tokens are ignored.** A typo like `WEBHOOK_EVENTS=bulish` falls through as "no recognized rules" and dispatches normally — the filter never silently disables itself.
- **Late-bound.** `WEBHOOK_EVENTS` is read on every dispatch attempt (same `os.environ` late-binding as `WEBHOOK_URL` and `WEBHOOK_SECRET`) so an operator can flip filter rules without restarting.
- **Suppressed deliveries log, don't persist.** Filtered-out fires emit one `info` line with the parsed token set, the payload's derived values, and the failing category — but no row is written to `webhook-log.jsonl` (only attempted deliveries are; an operator inspecting the log sees only what actually shipped).

Implementation: `_resolve_event_filter()` parses `WEBHOOK_EVENTS` into a lowercase token set; `payload_passes_event_filter(payload, events)` returns `(bool, trace_dict)` evaluating direction / confidence / quality rules using helpers (`_payload_direction`, `_payload_confidence_pct`, `_payload_quality_key`) that share semantics with the existing share-card / Discord-embed renderers. `fire_webhook_for_simulation` calls the filter between `_mark_fired` and `_start_dispatch_thread`; the manual retry endpoint deliberately bypasses the filter (operator-driven, like the dedup bypass). Zero new dependencies. Backward-compatible — blank `WEBHOOK_EVENTS` returns the original code path byte-for-byte.

## Channel-Native Completion Notifications (Discord + Slack + Email)

The generic webhook (`WEBHOOK_URL`) posts a raw JSON blob — perfect for Zapier / Make / n8n, but Discord renders nothing from JSON and Slack inlines it as an ugly code block. Three channel-native paths land formatted cards (or emails) in the platform's own format:

- **Discord rich embed** — set `DISCORD_WEBHOOK_URL` (Discord → Server Settings → Integrations → Webhooks). MiroShark POSTs a Discord embed with: scenario title, consensus-coloured border (`#22c55e` bullish / `#6b7280` neutral / `#ef4444` bearish / `#f59e0b` failed), Bullish / Neutral / Bearish / Quality / Rounds / Agents fields, share-card thumbnail, and a clickable share-page link. Failure runs append the truncated exit-code message as an `Error` field.
- **Slack Block Kit** — set `SLACK_WEBHOOK_URL` (api.slack.com/apps → Incoming Webhooks). MiroShark POSTs a Block Kit message with: scenario header, status-verb context line, `mrkdwn` belief bars (`█████░░░░░ 52.0%`), Quality / Scale / Resolution fields, and a "View simulation" action button. Failure runs append a fenced-code error section.
- **SMTP completion email** — set `SMTP_HOST` and `SMTP_TO` (comma-separated recipients). MiroShark sends a `multipart/alternative` message: subject `[MiroShark] Bullish: <scenario>` so inbox filters can triage by direction without parsing the body, a plain-text part with the same Unicode block bars Slack uses, and an HTML part with inline-CSS swatches matching the Discord embed colours and a consensus-coloured "View simulation →" CTA. `SMTP_USER` / `SMTP_PASSWORD` are optional so an unauthenticated relay (`localhost:25`, self-hosted Postfix) works alongside the Gmail / SendGrid / Mailgun path. The one notification channel with zero platform dependency — every operator already has a mailbox.

Channels are independent. Set one, two, three, or all four — each fires on every `simulation.completed` / `simulation.failed` event, deduped per `(sim_id, status)` so the runner's two terminal code paths never produce duplicate cards. The SPA exposes `GET /api/config/notifications` returning `{webhook_configured, discord_configured, slack_configured, email_configured}` so the EmbedDialog can render live status chips beside the share-and-embed surfaces. Pure stdlib `urllib.request` + `smtplib` — zero new dependencies. Full setup walkthrough in [NOTIFICATIONS.md](NOTIFICATIONS.md).

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
