# Configuration

All settings live in `.env` (copy from `.env.example`). The full reference below is organized by concern. For model selection (which model for which slot, benchmarks, Ollama context overrides) see [Models](MODELS.md).

## Minimum required

```bash
# LLM
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://openrouter.ai/api/v1     # or http://localhost:11434/v1 for Ollama
LLM_MODEL_NAME=qwen/qwen3.5-flash-02-23

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=miroshark

# Embeddings
EMBEDDING_PROVIDER=openai                     # or "ollama"
EMBEDDING_MODEL=openai/text-embedding-3-large
EMBEDDING_API_KEY=your-api-key
EMBEDDING_DIMENSIONS=768
```

## Model slots

MiroShark routes different workflows to different models. Four independent slots:

| Slot | Env var | What it does | Volume |
|---|---|---|---|
| **Default** | `LLM_MODEL_NAME` | Profiles, sim config, memory compaction | ~75–126 calls |
| **Smart** | `SMART_MODEL_NAME` | Reports, ontology, graph reasoning | ~19 calls |
| **NER** | `NER_MODEL_NAME` | Entity extraction (structured JSON) | ~85–250 calls |
| **Wonderwall** | `WONDERWALL_MODEL_NAME` | Agent decisions in simulation loop | ~850–1650 calls |

When a slot is not set it falls back to the Default model. If only `SMART_MODEL_NAME` is set (without `SMART_PROVIDER`/`SMART_BASE_URL`/`SMART_API_KEY`), the smart model inherits the default provider settings.

See [Models](MODELS.md) for benchmarked recommendations per slot.

## Full `.env` reference

```bash
# ─── LLM (default — profiles, sim config, memory compaction) ───
LLM_PROVIDER=openai                # "openai" (default) or "claude-code"
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen2.5:32b

# ─── Smart model (reports, ontology, graph reasoning — #1 quality lever) ───
# SMART_PROVIDER=openai
# SMART_MODEL_NAME=deepseek/deepseek-v3.2      # Cheap preset
# SMART_MODEL_NAME=anthropic/claude-sonnet-4.6 # Best preset (far stronger reports)

# ─── Wonderwall (agent sim loop — #1 cost driver, use cheapest viable) ───
# WONDERWALL_MODEL_NAME=qwen/qwen3.5-flash-02-23

# ─── NER (entity extraction — needs reliable JSON, no hidden CoT) ───
# NER_MODEL_NAME=x-ai/grok-4.1-fast

# ─── Disable chain-of-thought on reasoning-capable OpenRouter models ───
# ~3x lower latency on Qwen3-Flash / Grok-4.1-Fast. Flip to false
# per-deployment if a slot needs CoT.
LLM_DISABLE_REASONING=true

# ─── Claude Code mode (only when LLM_PROVIDER=claude-code) ───
# CLAUDE_CODE_MODEL=claude-sonnet-4-20250514

# ─── Neo4j ───
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=miroshark

# ─── Embeddings ───
EMBEDDING_PROVIDER=ollama          # "ollama" or "openai"
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434
EMBEDDING_DIMENSIONS=768

# ─── Reranker (BGE cross-encoder, ~1GB one-time download) ───
RERANKER_ENABLED=true
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_CANDIDATES=30             # pool size before rerank

# ─── Graph-traversal retrieval (Zep/Graphiti-style BFS from seed entities) ───
GRAPH_SEARCH_ENABLED=true
GRAPH_SEARCH_HOPS=1                # 1 or 2
GRAPH_SEARCH_SEEDS=5               # seed entities per query

# ─── Entity resolution (fuzzy + vector + optional LLM reflection) ───
ENTITY_RESOLUTION_ENABLED=true
ENTITY_RESOLUTION_USE_LLM=true

# ─── Automatic contradiction detection ───
CONTRADICTION_DETECTION_ENABLED=true

# ─── Community clustering (Leiden + LLM summaries) ───
COMMUNITY_MIN_SIZE=3
COMMUNITY_MAX_COUNT=30

# ─── Reasoning trace persistence (:Report subgraph with full ReACT decisions) ───
REASONING_TRACE_ENABLED=true

# ─── Web Enrichment (auto-researches public figures during persona gen) ───
# Also powers the /api/graph/fetch-url URL importer — models without native
# browsing must use an ":online" variant.
WEB_ENRICHMENT_ENABLED=true
# WEB_SEARCH_MODEL=x-ai/grok-4.1-fast:online

# ─── Embedding batching ───
# How many texts per HTTP request. Higher is faster on graph builds;
# drop to 32 if your provider returns 413.
EMBEDDING_BATCH_SIZE=128

# ─── Anthropic prompt caching ───
# Attaches cache_control to the system message when the active model is
# Claude-family. ~10% cost on cache reads; big win on the ReACT report loop.
# Silent no-op for non-Anthropic models.
LLM_PROMPT_CACHING_ENABLED=true

# ─── Live oracle seeds (FeedOracle MCP) ───
# Opt-in grounded data for templates that declare `oracle_tools`.
ORACLE_SEED_ENABLED=false
# FEEDORACLE_MCP_URL=https://mcp.feedoracle.io/mcp
# FEEDORACLE_API_KEY=

# ─── Per-agent MCP tools ───
# Lets personas with `tools_enabled: true` invoke MCP servers during sim.
# Configure servers in config/mcp_servers.yaml.
MCP_AGENT_TOOLS_ENABLED=false
# MCP_SERVERS_CONFIG=./config/mcp_servers.yaml
# MCP_MAX_CALLS_PER_TURN=2
# MCP_CALL_TIMEOUT_SEC=30

# ─── What's Trending (RSS/Atom feeds) ───
# Override the default Reuters/Verge/HN/CoinDesk list.
# TRENDING_FEEDS=https://techcrunch.com/feed/,https://www.theverge.com/rss/index.xml,https://hnrss.org/frontpage,https://www.coindesk.com/arc/outboundfeeds/rss/

# ─── Wonderwall / CAMEL-AI ───
# The simulation engine reads these directly. When LLM_PROVIDER=openai
# they usually match LLM_*. Leave as-is for Ollama.
OPENAI_API_KEY=ollama
OPENAI_API_BASE_URL=http://localhost:11434/v1

# ─── Observability ───
# Full prompt/response logging for debugging.
# (large JSONL files — disable in production)
# MIROSHARK_LOG_PROMPTS=true
# MIROSHARK_LOG_LEVEL=info          # debug|info|warn

# ─── Admin auth (mutation endpoints) ───
# Shared operator secret guarding POST /publish, /resolve, /outcome.
# Send as `Authorization: Bearer <token>`. Compared in constant time.
# UNSET ⇒ those endpoints return 503 (fail-closed). See "Admin auth"
# below for the full story.
# MIROSHARK_ADMIN_TOKEN=
```

## Admin auth (mutation endpoints)

Three endpoints write to a simulation's on-disk state and are gated on
a shared operator secret:

- `POST /api/simulation/<id>/publish` — toggles `is_public`
- `POST /api/simulation/<id>/resolve` — records the actual outcome
- `POST /api/simulation/<id>/outcome` — verified-prediction annotation

Send the secret as `Authorization: Bearer $MIROSHARK_ADMIN_TOKEN`. The
server compares it with `hmac.compare_digest` so the comparison is
constant-time. Read endpoints (including `GET /outcome`, the public
gallery, and the embed widget) stay unauthenticated.

**Fail-closed.** If `MIROSHARK_ADMIN_TOKEN` is unset or empty in the
backend's process environment, the gated endpoints return
`503 — admin auth not configured` rather than silently allowing the
mutation. There is no implicit "no auth required" fallback. An operator
who forgot to set the secret would otherwise ship an open mutation
surface with no warning — the 503 makes the misconfig loud.

Generate a token with `openssl rand -hex 32` (or any sufficiently long
random string), set it in `.env`, and restart the backend. The token is
read at request time so a process restart after rotation is enough — no
code reload required.

## Feature flags summary

All retrieval and memory features are on by default. Disable individually:

| Flag | Default | What flipping off means |
|---|---|---|
| `RERANKER_ENABLED` | `true` | No cross-encoder rerank; top-N comes straight from hybrid fusion |
| `GRAPH_SEARCH_ENABLED` | `true` | No BFS traversal from seed entities — vector + BM25 only |
| `ENTITY_RESOLUTION_ENABLED` | `true` | Duplicates like "NeuralCoin" / "Neural Coin" / "NC" stay separate |
| `ENTITY_RESOLUTION_USE_LLM` | `true` | Fuzzy + vector only; no LLM reflection step |
| `CONTRADICTION_DETECTION_ENABLED` | `true` | Conflicting edges both remain valid |
| `REASONING_TRACE_ENABLED` | `true` | Report reasoning isn't persisted to the graph |
| `WEB_ENRICHMENT_ENABLED` | `true` | Personas grounded only in the document |
| `LLM_PROMPT_CACHING_ENABLED` | `true` | No Anthropic prompt caching on system messages |
| `LLM_DISABLE_REASONING` | `true` | OpenRouter reasoning models emit CoT (~3× higher latency on Qwen3/Grok) |
| `ORACLE_SEED_ENABLED` | `false` | Templates ignore `oracle_tools` |
| `MCP_AGENT_TOOLS_ENABLED` | `false` | `tools_enabled` personas can't invoke MCP |

## Observability

See [Observability](OBSERVABILITY.md) for the debug panel (Ctrl+Shift+D) and event stream details.
