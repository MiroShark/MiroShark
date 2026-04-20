<p align="center">
  <img src="./docs/images/miroshark.jpg" alt="MiroShark" width="120" />
</p>

<h1 align="center">MiroShark</h1>

<p align="center">
  <strong>Universal Swarm Intelligence Engine — Run Locally or with Any Cloud API</strong><br>
  Multi-agent simulation engine: upload any document (press release, policy draft, financial report), and it generates hundreds of AI agents with unique personalities that simulate public reaction on social media — posts, arguments, opinion shifts — hour by hour.
</p>

<p align="center">
  <img src="./docs/images/miroshark.gif" alt="MiroShark Demo" />
</p>

<p align="center">
  <img src="./docs/images/miroshark-overview.jpg" alt="MiroShark Overview" />
</p>

<p align="center">
  <img src="./docs/images/diagram1.jpg" alt="Diagram 1" />
</p>

<p align="center">
  <img src="./docs/images/diagram2.jpg" alt="Diagram 2" />
</p>

---

## How It Works

1. **Graph Build** — Extracts entities and relationships from your document into a Neo4j knowledge graph. NER uses few-shot examples and rejection rules to filter garbage entities. Chunk processing is parallelized with batched Neo4j writes (UNWIND).
2. **Agent Setup** — Generates personas grounded in the knowledge graph. Each entity gets 5 layers of context: graph attributes, relationships, semantic search, related nodes, and LLM-powered web research (auto-triggers for public figures or when graph context is thin). Individual vs. institutional personas are detected automatically via keyword matching.
3. **Simulation** — All three platforms (Twitter, Reddit, Polymarket) run simultaneously via `asyncio.gather`. A single LLM-generated prediction market with non-50/50 starting price drives Polymarket trading. Agents see cross-platform context: traders read Twitter/Reddit posts, social media agents see market prices. A sliding-window round memory compacts old rounds via background LLM calls. Belief states track stance, confidence, and trust per agent with heuristic updates each round.
4. **Report** — A ReACT agent writes analytical reports using `simulation_feed` (actual posts/comments/trades), `market_state` (prices/P&L), graph search, and belief trajectory tools. Reports cite what agents actually said and how markets moved.
5. **Interaction** — Chat directly with any agent via persona chat, or send questions to groups. Click any agent to view their full profile and simulation history.

### Smart Setup (Scenario Auto-Suggest)

The Simulation Prompt field is the single blank-page barrier between uploading a document and running a simulation. Smart Setup removes it: the moment you drop in a `.md`/`.txt` file or paste a URL, MiroShark sends a short preview (~2K chars) of the extracted text to the configured LLM and returns three prediction-market-style scenario cards within ~2 seconds — one **Bull**, one **Bear**, one **Neutral** framing, each with a concrete YES/NO question, a plausible initial probability band, and a one-sentence rationale grounded in the document.

Click **Use this →** on any card to fill the Simulation Prompt field, or dismiss them and type your own. Suggestions are cached per-document (SHA-256 of the preview) so navigating away and back doesn't re-hit the LLM. If the LLM call fails or times out, the panel silently doesn't appear — your typed scenario still works exactly as before. The endpoint is `POST /api/simulation/suggest-scenarios`.

## Screenshots

<div align="center">
<table>
<tr>
<td><img src="./docs/images/1.jpg" width="100%"/></td>
<td><img src="./docs/images/2.jpg" width="100%"/></td>
</tr>
<tr>
<td><img src="./docs/images/3.jpg" width="100%"/></td>
<td><img src="./docs/images/4.jpg" width="100%"/></td>
</tr>
<tr>
<td><img src="./docs/images/5.jpg" width="100%"/></td>
<td><img src="./docs/images/6.jpg" width="100%"/></td>
</tr>
</table>
</div>

## Architecture

### Cross-Platform Simulation Engine

All three platforms execute simultaneously each round. Data flows between them:

```
                    ┌─────────────────────────────────────────┐
                    │         Round Memory (sliding window)    │
                    │  Old rounds: LLM-compacted summaries     │
                    │  Previous round: full action detail       │
                    │  Current round: live (partial)            │
                    └──────┬──────────┬──────────┬────────────┘
                           │          │          │
                    ┌──────▼───┐ ┌────▼─────┐ ┌─▼────────────┐
                    │ Twitter  │ │  Reddit  │ │  Polymarket   │
                    │          │ │          │ │               │
                    │ Posts    │ │ Comments │ │ Trades (AMM)  │
                    │ Likes    │ │ Upvotes  │ │ Single market │
                    │ Reposts  │ │ Threads  │ │ Buy/Sell/Wait │
                    └──────┬───┘ └────┬─────┘ └─┬────────────┘
                           │          │          │
                    ┌──────▼──────────▼──────────▼────────────┐
                    │         Market-Media Bridge              │
                    │  Social sentiment → trader prompts       │
                    │  Market prices → social media prompts    │
                    │  Social posts → trader observation       │
                    └──────┬──────────┬──────────┬────────────┘
                           │          │          │
                    ┌──────▼──────────▼──────────▼────────────┐
                    │         Belief State (per agent)         │
                    │  Positions: topic → stance (-1 to +1)    │
                    │  Confidence: topic → certainty (0 to 1)  │
                    │  Trust: agent → trust level (0 to 1)     │
                    └─────────────────────────────────────────┘
```

### Polymarket Integration

A single prediction market is generated by the LLM during config creation, tailored to the simulation's core question. The AMM uses constant-product pricing with non-50/50 initial prices based on the LLM's probability estimate. Traders see actual Twitter/Reddit posts in their observation prompt alongside portfolio and market data.

### Performance

| Optimization | Before | After |
|---|---|---|
| Neo4j writes | 1 transaction per entity | Batched UNWIND (10x faster) |
| Chunk processing | Sequential | Parallel ThreadPoolExecutor (3x faster) |
| Config generation | Sequential batches | Parallel batches (3x faster) |
| Platform execution | Twitter+Reddit parallel, Polymarket sequential | All 3 parallel |
| Memory compaction | Blocking | Background thread |

### Web Enrichment

When generating personas for public figures (politicians, CEOs, founders) or when graph context is thin (<150 chars), the system makes an LLM research call to enrich the profile with real-world data. Set `WEB_SEARCH_MODEL=perplexity/sonar-pro` in `.env` for grounded web search via OpenRouter.

## Quick Start

### One-Click Cloud Deploy

Deploy MiroShark to the cloud in under 3 minutes — no local setup required.

**Before you deploy, create:**
1. A free [Neo4j Aura](https://neo4j.com/cloud/aura-free/) instance — grab the `NEO4J_URI` (starts with `neo4j+s://`) and password from the dashboard.
2. An [OpenRouter](https://openrouter.ai/) API key — used for LLM calls and embeddings. Free credits available on signup.

**Railway** (recommended — includes persistent storage and a free trial):

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/new/template?template=https://github.com/aaronjmars/MiroShark)

After clicking deploy, set these environment variables in the Railway dashboard:

| Variable | Value |
|---|---|
| `LLM_API_KEY` | Your OpenRouter key (`sk-or-v1-...`) |
| `NEO4J_URI` | Your Aura URI (`neo4j+s://...`) |
| `NEO4J_PASSWORD` | Your Aura password |
| `EMBEDDING_API_KEY` | Same OpenRouter key |
| `OPENAI_API_KEY` | Same OpenRouter key |

**Render** (free tier available — 750 hrs/month, spins down after 15 min idle):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/aaronjmars/MiroShark)

Render reads `render.yaml` automatically. Set the same environment variables above when prompted.

> **Note:** Cloud deploys use OpenRouter for all LLM calls. Ollama is not available in this mode. Both platforms expose MiroShark on a public HTTPS URL — no port forwarding needed.

---

### Prerequisites

- An OpenAI-compatible API key *(including OpenRouter, OpenAI, Anthropic, etc.)*, Ollama for local inference, **or** Claude Code CLI
- Python 3.11+, Node.js 18+, Neo4j 5.15+ **or** Docker & Docker Compose

---

### Quick Start: `./miroshark`

The launcher script handles everything — dependency checks, Neo4j startup, package installation, and launching both frontend and backend:

```bash
cp .env.example .env   # configure your LLM + Neo4j settings
./miroshark
```

What it does:
1. Checks Python 3.11+, Node 18+, uv, Neo4j/Docker
2. Starts Neo4j if not already running (Docker or native)
3. Installs frontend + backend dependencies if missing
4. Kills stale processes on ports 3000/5001
5. Launches Vite dev server (`:3000`) and Flask API (`:5001`)
6. Ctrl+C to stop everything

---

### Option A: Cloud API (no GPU needed)

Only Neo4j runs locally. LLM and embeddings use a cloud provider.

```bash
# 1. Start Neo4j (or: brew install neo4j && brew services start neo4j)
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/miroshark \
  neo4j:5.15-community

# 2. Configure
cp .env.example .env
```

Edit `.env` (example using OpenRouter):

```bash
LLM_API_KEY=sk-or-v1-your-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_NAME=qwen/qwen3-235b-a22b-2507

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_BASE_URL=https://openrouter.ai/api
EMBEDDING_API_KEY=sk-or-v1-your-key
EMBEDDING_DIMENSIONS=768
```

```bash
npm run setup:all && npm run dev
```

Open `http://localhost:3000` — backend API at `http://localhost:5001`.

---

### Option B: Docker — Local Ollama

```bash
git clone https://github.com/aaronjmars/MiroShark.git
cd MiroShark
docker compose up -d

# Pull models into Ollama
docker exec miroshark-ollama ollama pull qwen3.5:27b
docker exec miroshark-ollama ollama pull nomic-embed-text
```

Open `http://localhost:3000`.

---

### Option C: Manual — Local Ollama

```bash
# 1. Start Neo4j
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/miroshark \
  neo4j:5.15-community

# 2. Start Ollama & pull models
ollama serve &
ollama pull qwen3.5:27b
ollama pull nomic-embed-text

# 3. Configure & run
cp .env.example .env
npm run setup:all
npm run dev
```

---

### Option D: Claude Code (no API key needed)

Use your Claude Pro/Max subscription as the LLM backend via the local Claude Code CLI. No API key or GPU required — just a logged-in `claude` installation.

```bash
# 1. Install Claude Code (if not already)
npm install -g @anthropic-ai/claude-code

# 2. Log in (opens browser)
claude

# 3. Start Neo4j
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/miroshark \
  neo4j:5.15-community

# 4. Configure
cp .env.example .env
```

Edit `.env`:

```bash
LLM_PROVIDER=claude-code
# Optional: pick a specific model (default uses your Claude Code default)
# CLAUDE_CODE_MODEL=claude-sonnet-4-20250514
```

You still need embeddings — use a cloud provider or local Ollama for those (Claude Code doesn't support embeddings). You also still need Ollama or a cloud API for the CAMEL-AI simulation rounds (see coverage table below).

```bash
npm run setup:all && npm run dev
```

> **What's covered:** When `LLM_PROVIDER=claude-code`, all MiroShark services route through Claude Code — graph building (ontology, NER), agent profile generation, simulation config, report generation, and persona chat. The only exception is the CAMEL-AI simulation engine itself, which requires an OpenAI-compatible API (Ollama or cloud) since it manages its own LLM connections internally.

| Component | Claude Code | Needs separate LLM |
|---|---|---|
| Graph building (ontology + NER) | Yes | — |
| Agent profile generation | Yes | — |
| Simulation config generation | Yes | — |
| Report generation | Yes | — |
| Persona chat | Yes | — |
| CAMEL-AI simulation rounds | — | Yes (Ollama or cloud) |
| Embeddings | — | Yes (Ollama or cloud) |

> **Performance note:** Each LLM call spawns a `claude -p` subprocess (~2-5s overhead). Best for small simulations or hybrid mode — use Ollama/cloud for the high-volume simulation rounds, Claude Code for everything else.

---

## Configuration

### Cloud Presets (OpenRouter)

Two benchmarked presets are available in `.env.example`. Copy one and set your API key.

Each model slot controls a different quality axis — benchmarked across 10+ model combos (see `models.md`):

| Slot | Controls | Key finding |
|---|---|---|
| **Default** | Persona richness, sim density | Haiku produces distinct 348-char voices; Gemini Flash produces generic 173-char copy |
| **Smart** | Report quality (#1 lever) | Claude Sonnet 9/10, Gemini 2.5 Flash 5/10, DeepSeek 2/10 |
| **NER** | Extraction reliability | gemini-2.0-flash reliable; flash-lite causes 3x retry bloat |
| **OASIS** | Cost (biggest consumer) | 850+ calls, 7M+ tokens. Verbosity matters more than $/M |

#### Cheap Mode — ~$1.20/run, ~13 min

All Gemini. Fast and reliable, but thin reports and generic personas.

| Slot | Model | $/M | Why |
|---|---|---|---|
| Default | `google/gemini-2.0-flash-001` | $0.10 | Fast, reliable JSON |
| Smart | `google/gemini-2.5-flash` | $0.30 | Adequate reports |
| NER | `google/gemini-2.0-flash-001` | $0.10 | No retry bloat |
| OASIS | `google/gemini-2.0-flash-lite-001` | $0.075 | Cheapest, least verbose |

#### Best Mode — ~$3.50/run, ~25 min

Claude reports, Haiku personas, cheap OASIS. Best report quality at reasonable cost.

| Slot | Model | $/M | Why |
|---|---|---|---|
| Default | `anthropic/claude-haiku-4.5` | $0.80/$4.00 | Rich personas, dense sim configs |
| Smart | `anthropic/claude-sonnet-4.6` | $3.00/$15.00 | 9/10 report quality, only ~19 calls |
| NER | `google/gemini-2.0-flash-001` | $0.10 | Proven reliable, no retries |
| OASIS | `google/gemini-2.0-flash-lite-001` | $0.075 | OASIS doesn't drive quality — Smart does |

> Both presets use `openai/text-embedding-3-small` for embeddings and `google/gemini-2.0-flash-001:online` for web research.

### Local Mode (Ollama)

> **Context override required.** Ollama defaults to 4096 tokens, but MiroShark prompts need 10-30k. Create a custom Modelfile:
>
> ```bash
> printf 'FROM qwen3:14b\nPARAMETER num_ctx 32768' > Modelfile
> ollama create mirosharkai -f Modelfile
> ```

| Model | VRAM | Speed | Notes |
|---|---|---|---|
| `qwen3.5:27b` | 20GB+ | ~40 t/s | Best quality |
| `qwen3.5:35b-a3b` *(MoE)* | 16GB | ~112 t/s | Fastest — MoE activates only 3B params |
| `qwen3:14b` | 12GB | ~60 t/s | Solid balance |
| `qwen3:8b` | 8GB | ~42 t/s | Minimum viable; 40K context limit |

**Hardware quick-pick:**

| Setup | Model |
|---|---|
| RTX 3090/4090 or M2 Pro 32GB+ | `qwen3.5:27b` |
| RTX 4080 / M2 Pro 16GB | `qwen3.5:35b-a3b` |
| RTX 4070 / M1 Pro | `qwen3:14b` |
| 8GB VRAM / laptop | `qwen3:8b` |

**Embeddings locally:** `ollama pull nomic-embed-text` — 768 dimensions, matches Neo4j default.

**Hybrid tip:** Run local for simulation rounds (high-volume), route to Claude for reports. Most users land here naturally:

```bash
LLM_MODEL_NAME=qwen3.5:27b
SMART_PROVIDER=claude-code
SMART_MODEL_NAME=claude-sonnet-4-20250514
```

### Model Routing

MiroShark routes different workflows to different models. Four independent slots:

| Slot | Env var | What it does | Volume |
|---|---|---|---|
| **Default** | `LLM_MODEL_NAME` | Profiles, sim config, memory compaction | ~75-126 calls |
| **Smart** | `SMART_MODEL_NAME` | Reports, ontology, graph reasoning | ~19 calls |
| **NER** | `NER_MODEL_NAME` | Entity extraction (structured JSON) | ~85-250 calls |
| **OASIS** | `OASIS_MODEL_NAME` | Agent decisions in simulation loop | ~850-1650 calls |

When a slot is not set, it falls back to the Default model. If only `SMART_MODEL_NAME` is set (without `SMART_PROVIDER`/`SMART_BASE_URL`/`SMART_API_KEY`), the smart model inherits the default provider settings.

### Environment Variables

All settings live in `.env` (copy from `.env.example`):

```bash
# LLM (default — profiles, sim config, memory compaction)
LLM_PROVIDER=openai                # "openai" (default) or "claude-code"
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen3.5:27b

# Smart model (reports, ontology, graph reasoning — #1 quality lever)
# SMART_PROVIDER=claude-code
# SMART_MODEL_NAME=claude-sonnet-4-20250514

# OASIS model (agent sim loop — #1 cost driver, use cheapest viable model)
# OASIS_MODEL_NAME=google/gemini-2.0-flash-lite-001

# NER model (entity extraction — needs reliable JSON, avoid flash-lite)
# NER_MODEL_NAME=google/gemini-2.0-flash-001

# Claude Code mode (only when LLM_PROVIDER=claude-code)
# CLAUDE_CODE_MODEL=claude-sonnet-4-20250514

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=miroshark

# Embeddings
EMBEDDING_PROVIDER=ollama          # "ollama" or "openai"
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434
EMBEDDING_DIMENSIONS=768

# Web Enrichment (auto-researches public figures during persona generation)
WEB_ENRICHMENT_ENABLED=true
# WEB_SEARCH_MODEL=google/gemini-2.0-flash-001:online
```


---

## Observability & Debugging

MiroShark includes a built-in observability system that gives real-time visibility into every LLM call, agent decision, graph build step, and simulation round.

### Debug Panel

Press **Ctrl+Shift+D** anywhere in the UI to open the debug panel. Four tabs:

| Tab | What it shows |
|-----|--------------|
| **Live Feed** | Real-time SSE event stream — every LLM call, agent action, round boundary, graph build step, and error. Color-coded, filterable by platform/agent/text, expandable for full detail. |
| **LLM Calls** | Table of all LLM calls with caller, model, input/output tokens, latency. Click to expand full prompt and response (when `MIROSHARK_LOG_PROMPTS=true`). Aggregate stats at top. |
| **Agent Trace** | Per-agent decision timeline — what the agent observed, what the LLM responded, what action was parsed, success/failure. |
| **Errors** | Filtered error view with stack traces. |

### Event Stream

All events are written as append-only JSONL:
- `backend/logs/events.jsonl` — global (all Flask-process events)
- `uploads/simulations/{id}/events.jsonl` — per-simulation (includes subprocess events)

#### SSE Endpoint

```
GET /api/observability/events/stream?simulation_id=sim_xxx&event_types=llm_call,error
```

Returns `text/event-stream` with live events. The debug panel uses this automatically.

#### REST Endpoints

```
GET /api/observability/events?simulation_id=sim_xxx&from_line=0&limit=200
GET /api/observability/stats?simulation_id=sim_xxx
GET /api/observability/llm-calls?simulation_id=sim_xxx&caller=ner_extractor
```

### Event Types

| Type | Emitted by | Data |
|------|-----------|------|
| `llm_call` | Every LLM call (NER, ontology, profiles, config, reports) | model, tokens, latency, caller, response preview |
| `agent_decision` | Agent `perform_action_by_llm()` during simulation | env observation, LLM response, parsed action, tool calls |
| `round_boundary` | Simulation loop (start/end of each round) | simulated hour, active agents, action count, elapsed time |
| `graph_build` | Graph builder lifecycle | phase, node/edge counts, chunk progress |
| `error` | Any caught exception with traceback | error class, message, traceback, context |

### Configuration

```bash
# .env
MIROSHARK_LOG_PROMPTS=true    # Log full LLM prompts/responses (large files, debug only)
MIROSHARK_LOG_LEVEL=info      # debug|info|warn — controls event verbosity
```

By default, only response previews (200 chars) are logged. Set `MIROSHARK_LOG_PROMPTS=true` to capture full prompts and responses for deep debugging.

---

## Hardware Requirements

**Local (Ollama):**

| | Minimum | Recommended |
|---|---|---|
| RAM | 16 GB | 32 GB |
| VRAM | 10 GB | 24 GB |
| Disk | 20 GB | 50 GB |

**Cloud mode:** No GPU needed — just Neo4j and an API key. Any 4 GB RAM machine works.

## Use Cases

- **PR crisis testing** — simulate public reaction to a press release before publishing
- **Trading signals** — feed financial news and observe simulated market sentiment
- **Policy analysis** — test draft regulations against a simulated public
- **Creative experiments** — feed a novel with a lost ending; agents write a narratively consistent conclusion

Support the project : 0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3
AGPL-3.0. See [LICENSE](./LICENSE).

## Credits

Built on [MiroFish](https://github.com/666ghj/MiroFish) by [666ghj](https://github.com/666ghj) (Shanda Group). Neo4j + Ollama storage layer adapted from [MiroFish-Offline](https://github.com/nikmcfly/MiroFish-Offline) by [nikmcfly](https://github.com/nikmcfly). Simulation engine powered by [OASIS](https://github.com/camel-ai/oasis) (CAMEL-AI).
