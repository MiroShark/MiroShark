<sup>[English](CONFIGURATION.md) · 中文</sup>

# 配置

所有设置都在 `.env`(从 `.env.example` 拷贝)。下面这份完整参考按关注点分组。模型选择(哪个槽位用哪个模型、基准、Ollama 上下文覆盖)请见 [Models](MODELS.zh-CN.md)。

## 最低必填项

```bash
# LLM
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://openrouter.ai/api/v1     # or http://localhost:11434/v1 for Ollama
LLM_MODEL_NAME=xiaomi/mimo-v2-flash

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

## 模型槽位

MiroShark 把不同的工作流路由到不同的模型。共有四个相互独立的槽位:

| 槽位 | 环境变量 | 作用 | 调用量 |
|---|---|---|---|
| **Default** | `LLM_MODEL_NAME` | 画像、模拟配置、记忆压缩 | ~75–126 次调用 |
| **Smart** | `SMART_MODEL_NAME` | 报告、本体、图谱推理 | ~19 次调用 |
| **NER** | `NER_MODEL_NAME` | 实体抽取(结构化 JSON) | ~85–250 次调用 |
| **Wonderwall** | `WONDERWALL_MODEL_NAME` | 模拟循环中的智能体决策 | ~850–1650 次调用 |

未设置的槽位会回退到 Default 模型。如果只设置了 `SMART_MODEL_NAME`(没有设 `SMART_PROVIDER`/`SMART_BASE_URL`/`SMART_API_KEY`),smart 模型会继承 default 的提供商设置。`WONDERWALL_MODEL_NAME` 也是同样的逻辑 — 设置 `WONDERWALL_BASE_URL` 和/或 `WONDERWALL_API_KEY` 就能把 Wonderwall 指向另一个 OpenAI 兼容端点(例如自部署的 vLLM/Modal 部署),而不影响其他槽位。

每个槽位经过基准测试的推荐配置见 [Models](MODELS.zh-CN.md)。

## 完整 `.env` 参考

```bash
# ─── LLM (default — profiles, sim config, memory compaction) ───
LLM_PROVIDER=openai                # "openai" (default) or "claude-code"
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen2.5:32b

# ─── Smart model (reports, ontology, graph reasoning — #1 quality lever) ───
# SMART_PROVIDER=openai
# SMART_MODEL_NAME=x-ai/grok-4.1-fast          # Cloud preset

# ─── Wonderwall (agent sim loop — #1 cost driver, use cheapest viable) ───
# WONDERWALL_MODEL_NAME=xiaomi/mimo-v2-flash
# Optional: route Wonderwall to a custom OpenAI-compatible endpoint
# (self-hosted vLLM, Modal, custom fine-tune…). Both fields are
# optional — leaving either blank inherits LLM_BASE_URL / LLM_API_KEY.
# WONDERWALL_BASE_URL=https://your-endpoint.example.com/v1
# WONDERWALL_API_KEY=not-checked

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

## 管理员认证(写操作端点)

有三个端点会写入某个模拟的本地状态,它们都受同一把运维者密钥保护:

- `POST /api/simulation/<id>/publish` — 切换 `is_public`
- `POST /api/simulation/<id>/resolve` — 记录真实结果
- `POST /api/simulation/<id>/outcome` — 已验证预测的注解

请把密钥以 `Authorization: Bearer $MIROSHARK_ADMIN_TOKEN` 的形式发送。服务端使用 `hmac.compare_digest` 进行恒定时间比较。读端点(包括 `GET /outcome`、公开画廊、嵌入小部件)依然不需要鉴权。

**默认拒绝。** 如果 `MIROSHARK_ADMIN_TOKEN` 在后端进程环境中未设置或为空,这些受控端点会返回 `503 — admin auth not configured`,而不是悄悄放行写入。这里没有"无需鉴权"的隐式回退。否则,一个忘记设置密钥的运维者会在毫无警告的情况下上线一个开放的写入接口 — 这个 503 把配置错误变得显眼。

用 `openssl rand -hex 32`(或者任意足够长的随机字符串)生成 token,把它写入 `.env`,然后重启后端。token 在请求时读取,所以轮换之后只需要重启进程即可 — 无需重新加载代码。

## 特性开关汇总

所有检索与记忆特性默认开启。可以分别关闭:

| 开关 | 默认值 | 关闭意味着什么 |
|---|---|---|
| `RERANKER_ENABLED` | `true` | 没有 cross-encoder 重排;top-N 直接来自混合融合 |
| `GRAPH_SEARCH_ENABLED` | `true` | 不再从种子实体做 BFS 遍历 — 仅向量 + BM25 |
| `ENTITY_RESOLUTION_ENABLED` | `true` | "NeuralCoin" / "Neural Coin" / "NC" 这类重复项会保持独立 |
| `ENTITY_RESOLUTION_USE_LLM` | `true` | 仅模糊匹配 + 向量;没有 LLM 反思步骤 |
| `CONTRADICTION_DETECTION_ENABLED` | `true` | 互相冲突的边都保持有效 |
| `REASONING_TRACE_ENABLED` | `true` | 报告推理过程不会持久化到图谱 |
| `WEB_ENRICHMENT_ENABLED` | `true` | 画像只基于文档本身 |
| `LLM_PROMPT_CACHING_ENABLED` | `true` | 系统消息上不再启用 Anthropic 提示词缓存 |
| `LLM_DISABLE_REASONING` | `true` | OpenRouter 推理模型会输出 CoT(在 Qwen3/Grok 上延迟约高 3 倍) |
| `ORACLE_SEED_ENABLED` | `false` | 模板会忽略 `oracle_tools` |
| `MCP_AGENT_TOOLS_ENABLED` | `false` | 标记了 `tools_enabled` 的人设无法调用 MCP |

## 可观测性

调试面板(Ctrl+Shift+D)与事件流细节请见 [Observability](OBSERVABILITY.zh-CN.md)。
