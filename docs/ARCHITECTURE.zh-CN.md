<sup>[English](ARCHITECTURE.md) · 中文</sup>

# 架构

## 流水线总览

1. **图谱构建** — 把你文档中的实体和关系抽取到一个 Neo4j 知识图谱里。NER 使用少样本示例和拒绝规则来过滤垃圾实体。分块处理通过批量 Neo4j 写入(UNWIND)做了并行。

2. **智能体配置** — 基于知识图谱生成人设。每个实体获得 5 层上下文:图谱属性、关系、语义检索、相邻节点,以及 LLM 驱动的网络调研(在涉及公众人物或图谱上下文不足时自动触发)。个体 vs 机构人设通过关键词匹配自动检测。

3. **模拟** — 三个平台(Twitter、Reddit、Polymarket)通过 `asyncio.gather` 同时运行。一个由 LLM 生成、初始价格非 50/50 的预测市场驱动 Polymarket 交易。智能体能看到跨平台上下文:交易者读 Twitter/Reddit 帖子,社交媒体智能体能看到市场价格。一个滑动窗口式的轮次记忆通过后台 LLM 调用压缩旧轮次。信念状态记录每个智能体的立场、置信度和信任度,每轮都用启发式更新。

4. **报告** — 一个 ReACT 智能体使用 `simulation_feed`(真实的帖子/评论/交易)、`market_state`(价格/盈亏)、图谱搜索、信念轨迹、纳什均衡等工具来撰写分析报告。报告会引用智能体真实的发言和市场实际的走势。

5. **交互** — 通过人设对话直接和任意智能体聊天,向群组提问,或者在任意轮次给模拟分叉一个反事实事件,以并排对比"如果"情景。点击任意智能体可以查看其完整画像和模拟历史。

## 跨平台模拟引擎

每一轮三个平台同时执行。数据在它们之间流动:

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

## Polymarket 集成

模拟配置创建期间,LLM 会生成单个预测市场,围绕该模拟的核心问题量身定制。市场标题生成走 **Smart** 槽位(见 [Models](MODELS.zh-CN.md)),让措辞精准、有时间界限、可结算 — 这是定义整场模拟的提示词,值得用更强的模型。AMM 使用恒定乘积定价,初始价格依据 LLM 的概率估计而非 50/50。交易者在他们的观察提示里能看到 Twitter/Reddit 上真实的帖子,以及自己的投资组合和市场数据。

## 性能

| 优化项 | 优化前 | 优化后 |
|---|---|---|
| Neo4j 写入 | 每个实体一个事务 | 批量 UNWIND(快 10 倍) |
| 分块处理 | 顺序 | 并行 ThreadPoolExecutor(快 3 倍) |
| 配置生成 | 顺序批量 | 并行批量(快 3 倍) |
| 平台执行 | Twitter+Reddit 并行,Polymarket 顺序 | 三者全并行 |
| 记忆压缩 | 阻塞 | 后台线程 |

## Web 增强

在为公众人物(政治家、CEO、创始人)生成画像时,或当图谱上下文太薄(<150 字符)时,系统会发起一次 LLM 调研调用,用真实世界数据丰富画像。在 `.env` 中设置 `WEB_SEARCH_MODEL=perplexity/sonar-pro`,通过 OpenRouter 进行接地的网络搜索。

## 单轮帧 API

`GET /api/simulation/<id>/frame/<round>` 返回某一轮的紧凑快照 — 动作、活跃智能体计数、当轮市场价格和信念状态 — 适合大型模拟的 scrub UI。这是不必通过 `/run-status/detail` 一次性加载全部 N × M 动作的替代方案。查询参数:`platforms=twitter,reddit,polymarket`、`include_belief`、`include_market`。被 **ReplayView** 用于时间轴拖动,也被 CLI(`miroshark-cli frame <id> <round>`)使用。

## 记忆与检索流水线

除了模拟引擎,MiroShark 还自带一个研究级的图谱记忆栈,灵感来自 Hindsight、Graphiti、Letta 和 HippoRAG。每个被摄入的文档和模拟动作都流过下面的过程:

### 摄入

```
text → NER (with ontology)
     → batch embed (OpenRouter text-embedding-3-large or local Ollama)
     → Entity resolution (fuzzy + vector + LLM reflection — dedups "NeuralCoin"/"Neural Coin"/"NC")
     → MERGE entities into Neo4j with canonical UUIDs
     → Contradiction detection (LLM adjudicates same-endpoint pairs → invalidate old)
     → CREATE RELATION edges with {valid_at, invalid_at, kind, source_type, source_id}
```

### 检索(`storage.search(...)`)

```
query
  ├─ vector edge search (Neo4j HNSW)   ─┐
  ├─ BM25 edge search (Neo4j fulltext) ─┼─ temporal + kind filters → fused candidates (top 30)
  └─ BFS traversal from seed entities  ─┘
                                        ↓
                           BGE-reranker-v2-m3 cross-encoder (Apple MPS / CUDA / CPU)
                                        ↓
                         top `limit` with _sources tag ("v" / "k" / "g" / combos)
```

### 缩放层(`storage.build_communities(...)`)

- 在实体图上做 Leiden 社区检测(通过 igraph)
- 每个簇由 LLM 生成标题 + 2 句话摘要
- 持久化为带有 `MEMBER_OF` 边的 `:Community` 节点
- 通过 `browse_clusters` 智能体工具对簇摘要做语义检索

### 推理记忆

每次报告生成都会把完整的 ReACT 轨迹持久化为可遍历子图:

```
(:Report)-[:HAS_SECTION]->(:ReportSection)-[:HAS_STEP]->(:ReasoningStep)
```

步骤类别有 `thought | tool_call | observation | conclusion`。可以用 `storage.get_reasoning_trace(section_uuid)` 查询历史报告的推理过程。

### 这些能给你什么

- 多跳查询能用上(图遍历能抓到只有连接关系匹配的事实)
- 时间维度查询能用上(`as_of="2026-04-10T14:00Z"` 返回那一刻所知的世界)
- 认识论过滤(`kinds=["belief"]` 只返回智能体观点,不返回事实)
- 报告可以被反复查询("为什么这个智能体得出 X 结论?")
- 首次召回足够高,所以报告智能体那 5 次工具调用预算能用得更远

11 个特性默认全部开启,都可以通过 `.env` 开关单独关闭 — 见 [Configuration](CONFIGURATION.zh-CN.md#特性开关汇总)。
