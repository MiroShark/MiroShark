<sup>[English](OBSERVABILITY.md) · 中文</sup>

# 可观测性与调试

MiroShark 内置了一套可观测性系统,可实时观察每一次 LLM 调用、智能体决策、图谱构建步骤和模拟轮次。

## 调试面板

在 UI 任意位置按 **Ctrl+Shift+D** 打开调试面板。共四个标签:

| 标签 | 显示什么 |
|---|---|
| **Live Feed** | 实时 SSE 事件流 — 每次 LLM 调用、智能体动作、轮次边界、图谱构建步骤和错误。带颜色编码,可按平台/智能体/文本过滤,可展开查看完整细节。 |
| **LLM Calls** | 所有 LLM 调用的列表,显示调用方、模型、输入/输出 tokens、延迟。点击可展开完整提示词和响应(当 `MIROSHARK_LOG_PROMPTS=true` 时)。顶部有聚合统计。 |
| **Agent Trace** | 单智能体的决策时间线 — 智能体看到了什么、LLM 回复了什么、解析出了什么动作、成功/失败。 |
| **Errors** | 过滤后的错误视图,带堆栈跟踪。 |

## 事件流

所有事件都以追加模式的 JSONL 写入:

- `backend/logs/events.jsonl` — 全局(所有 Flask 进程的事件)
- `uploads/simulations/{id}/events.jsonl` — 每个模拟一份(包含子进程事件)

### SSE 端点

```
GET /api/observability/events/stream?simulation_id=sim_xxx&event_types=llm_call,error
```

返回 `text/event-stream` 格式的实时事件。调试面板自动使用这个端点。

### REST 端点

```
GET /api/observability/events?simulation_id=sim_xxx&from_line=0&limit=200
GET /api/observability/stats?simulation_id=sim_xxx
GET /api/observability/llm-calls?simulation_id=sim_xxx&caller=ner_extractor
```

## 事件类型

| 类型 | 由谁发出 | 数据 |
|---|---|---|
| `llm_call` | 每一次 LLM 调用(NER、本体、画像、配置、报告) | model、tokens、latency、caller、响应预览 |
| `agent_decision` | 模拟期间的 agent `perform_action_by_llm()` | 环境观察、LLM 响应、解析后的动作、工具调用 |
| `round_boundary` | 模拟循环(每轮开始/结束) | 模拟时刻、活跃智能体、动作数量、耗时 |
| `graph_build` | 图谱构建器生命周期 | phase、节点/边数量、分块进度 |
| `error` | 任意被捕获的异常并带 traceback | 错误类、消息、traceback、上下文 |

## 配置

```bash
# .env
MIROSHARK_LOG_PROMPTS=true    # Log full LLM prompts/responses (large files, debug only)
MIROSHARK_LOG_LEVEL=info      # debug|info|warn — controls event verbosity
```

默认只记录响应预览(200 字符)。把 `MIROSHARK_LOG_PROMPTS=true` 打开,即可在深度调试时捕获完整提示词与响应。
