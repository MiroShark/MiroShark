<sup>[English](API.md) · 中文</sup>

# HTTP API 参考

开发环境的 base URL 是 `http://localhost:5001`。除非另有说明,每个端点都返回 JSON。

> **交互式文档:** 运行中的后端会在 `/api/docs` 暴露 Swagger UI,在 `/api/openapi.yaml`(或 `/api/openapi.json`)暴露 OpenAPI 3.1 规范。把 [`openapi-generator`](https://openapi-generator.tech/) 指向这份规范,一行命令就能生成 Python / TypeScript / Go SDK。

## 配置与发现

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/simulation/suggest-scenarios` | 从文档预览生成情景自动建议(看涨 / 看跌 / 中立) |
| `GET` | `/api/simulation/trending` | 拉取 RSS/Atom 条目,用于"热门"面板 |
| `POST` | `/api/simulation/ask` | 直接提问 — 从一个问题合成种子简报 |
| `POST` | `/api/graph/fetch-url` | 从 URL 抓取并抽取文本 |
| `GET` | `/api/templates/list` | 预设模板 |
| `GET` | `/api/templates/<id>?enrich=true` | 模板 + FeedOracle 实时增强 |

## 图谱构建(步骤 1)

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/graph/ontology/generate` | NER + 本体抽取 |
| `POST` | `/api/graph/build` | 根据本体构建 Neo4j 图谱 |
| `GET` | `/api/graph/task/<task_id>` | 轮询异步任务状态 |
| `GET` | `/api/graph/data/<graph_id>` | 分页的图节点 + 边 |
| `GET` | `/api/simulation/entities/<graph_id>` | 浏览实体 |
| `GET` | `/api/simulation/entities/<graph_id>/<uuid>` | 单个实体 + 邻域 |

## 模拟生命周期

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/simulation/create` | 根据种子 + 提示词创建模拟 |
| `POST` | `/api/simulation/prepare` | 启动画像生成(步骤 2) |
| `POST` | `/api/simulation/prepare/status` | 轮询步骤 2 |
| `POST` | `/api/simulation/start` | 启动 Wonderwall 子进程(步骤 3) |
| `POST` | `/api/simulation/stop` | 终止 |
| `POST` | `/api/simulation/branch-counterfactual` | 注入反事实并分叉 |
| `POST` | `/api/simulation/fork` | 复制配置 |
| `POST` | `/api/simulation/<id>/director/inject` | 导演模式 — 实时事件注入 |
| `GET` | `/api/simulation/<id>/director/events` | 列出导演事件 |

## 实时状态与数据

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/simulation/<id>/run-status` | 当前轮次 / 总数 |
| `GET` | `/api/simulation/<id>/run-status/detail` | 各平台进度 |
| `GET` | `/api/simulation/<id>/frame/<round>` | 单轮的紧凑快照 |
| `GET` | `/api/simulation/<id>/timeline` | 逐轮总结 |
| `GET` | `/api/simulation/<id>/actions` | 原始智能体动作日志 |
| `GET` | `/api/simulation/<id>/posts` | 分页帖子(Twitter + Reddit) |
| `GET` | `/api/simulation/<id>/profiles` | 智能体人设 |
| `GET` | `/api/simulation/<id>/profiles/realtime` | 实时信念更新 |
| `GET` | `/api/simulation/<id>/polymarket/markets` | 市场 + 当前价格 |
| `GET` | `/api/simulation/<id>/polymarket/market/<mid>/prices` | 价格历史 |

## 分析

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/simulation/<id>/belief-drift` | 每个话题每轮的立场漂移 |
| `GET` | `/api/simulation/<id>/counterfactual` | 原始 vs 分支对比 |
| `GET` | `/api/simulation/<id>/agent-stats` | 单智能体的参与度 + 发帖 |
| `GET` | `/api/simulation/<id>/influence` | 影响力排行榜 |
| `GET` | `/api/simulation/<id>/interaction-network` | 智能体之间的交互图 |
| `GET` | `/api/simulation/<id>/demographics` | 原型分布 |
| `GET` | `/api/simulation/<id>/quality` | 运行健康诊断 |
| `POST` | `/api/simulation/compare` | 信念并排对比 |

## 交互

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/simulation/interview` | 与单个智能体对话 |
| `POST` | `/api/simulation/interview/batch` | 并行向一组智能体提问 |
| `POST` | `/api/simulation/<id>/agents/<name>/trace-interview` | 带完整推理链的对话 |
| `GET` | `/api/simulation/<id>/interviews/<name>` | 与某个智能体的历史对话 |

## 发布 / 嵌入 / 导出

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/simulation/<id>/publish` | 切换 `is_public` |
| `GET` | `/api/simulation/<id>/embed-summary` | 嵌入载荷(仅公开模拟) |
| `POST` | `/api/simulation/<id>/article` | 生成 Substack 风格的报道 |
| `GET` | `/api/simulation/<id>/export` | 完整 JSON 导出 |
| `GET` | `/api/simulation/list` | 列出模拟 |
| `GET` | `/api/simulation/history` | 模拟历史 / 差异 |
| `GET` | `/api/simulation/public` | 可筛选、分页的公开图库列表 |

### 图库搜索与筛选

`GET /api/simulation/public` 支持关键词 + 主导立场 + 质量等级 + 结果标签 + 排序筛选,可让分析师通过单个 URL 拉取「关于 Aave 的每一次优秀质量看跌预言」:

```text
GET /api/simulation/public?q=aave&consensus=bearish&quality=excellent&sort=rounds&page=1
```

| 查询参数 | 取值 | 说明 |
|---|---|---|
| `q` | 自由文本,≤200 字符 | 不区分大小写的情景文本子串匹配。 |
| `consensus` | `bullish` / `neutral` / `bearish` | 使用与分享卡片 / 回放 GIF / 转录 / Webhook / 订阅源相同的 ±0.2 阈值计算的最终轮主导立场。 |
| `quality` | `excellent` / `good` / `fair` / `poor` | 与 `quality_health` 首词进行不区分大小写比较。 |
| `outcome` | `correct` / `incorrect` / `partial` | 隐含 `verified=1`(仅已验证)。 |
| `sort` | `date` / `rounds` / `agents` | `date`(默认 — 最新优先)、`rounds`(当前轮次最多优先)或 `agents`(种群最大优先)。 |
| `verified` | 真值(`1`/`true`/`yes`) | 限制为已记录结果注释的模拟 — 即 `/verified` 展厅。 |
| `limit` / `offset` | `[1, 100]` / `≥0` | 分页参数。`total` 反映**已筛选**的计数。 |
| `page` | `≥1` | `offset` 的 1 起编号替代值。两者同时出现时 `page` 优先。 |

筛选条件以逻辑与组合。空值 / 未知值均为无操作:`?consensus=` 返回未筛选列表;`?sort=popularity` 回退至 `sort=date` 而非 400 报错。

## 报告智能体

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/report/generate` | 启动 ReACT 报告智能体 |
| `POST` | `/api/report/generate/status` | 轮询生成进度 |
| `GET` | `/api/report/<id>` | 完整报告 |
| `GET` | `/api/report/by-simulation/<sim_id>` | 某次模拟对应的报告 |
| `GET` | `/api/report/<id>/download` | PDF 导出 |
| `POST` | `/api/report/chat` | 与报告智能体对话(会重新查询图谱) |
| `GET` | `/api/report/<id>/agent-log` | 完整 ReACT 轨迹 |
| `GET` | `/api/report/<id>/agent-log/stream` | SSE 流 |
| `GET` | `/api/report/<id>/console-log` | 原始 LLM 调用日志 |

## 可观测性

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/observability/events/stream` | SSE 推送 |
| `GET` | `/api/observability/events` | 事件日志(分页) |
| `GET` | `/api/observability/stats` | 聚合统计 |
| `GET` | `/api/observability/llm-calls` | LLM 调用历史 |

## 设置与推送

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` / `POST` | `/api/settings` | 运行时设置(密钥已脱敏) |
| `POST` | `/api/settings/test-llm` | Ping 已配置的 LLM |
| `GET` | `/api/simulation/push/vapid-public-key` | Web Push 用的 VAPID key |
| `POST` | `/api/simulation/push/subscribe` | 注册一个浏览器订阅 |
| `POST` | `/api/simulation/push/test` | 触发一条测试通知 |

## 交互式文档

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/docs` | 基于本规范渲染的 Swagger UI — 启用 try-it-out |
| `GET` | `/api/openapi.yaml` | OpenAPI 3.1 规范,YAML 格式(基准) |
| `GET` | `/api/openapi.json` | 同一份规范,JSON 格式(便于 `openapi-generator`) |

规范本身已提交到仓库的 `backend/openapi.yaml`。一个单元测试(`backend/tests/test_unit_openapi.py`)会在每次 push 时遍历所有 Flask 路由,如果规范和实现出现漂移就让 CI 失败。
