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
- **Selection:** mirrors `GET /api/simulation/public` exactly — newest 20 published runs, sorted by `created_at` descending, publish-gated.
- **Auto-discovery:** the SPA's `index.html` declares `<link rel="alternate" type="application/atom+xml">` (and the RSS variant) so browsers expose the feed via the address-bar globe icon.
- **Caching:** `Cache-Control: public, max-age=300` — five minutes is short enough for newly published sims to appear in the next aggregator poll, long enough to absorb aggressive polling without taxing the gallery query.
- **Implementation:** pure stdlib (`xml.etree.ElementTree` + `html`). Zero new dependencies; same ±0.2 stance threshold as every other surface so a "62% bullish" string matches the gallery card byte-for-byte.

The Embed dialog has a "Follow the gallery via RSS" callout with one-click subscribe links for the Atom feed, the RSS 2.0 feed, and the verified-only Atom feed. The /explore header has a "📡 Subscribe via RSS" chip that mirrors the active filter (verified-only when the filter is on).

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
