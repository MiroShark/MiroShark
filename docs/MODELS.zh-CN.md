<sup>[English](MODELS.md) · 中文</sup>

# 模型

四个相互独立的模型槽位(对应的环境变量见 [Configuration](CONFIGURATION.zh-CN.md#模型槽位))。本篇讲哪些模型应该填到哪个槽位。

## 云端预设(OpenRouter)

`.env.example` 出厂自带一套经过基准测试的预设。复制一份,填上你的 API 密钥即可。

每个槽位控制不同的质量轴:

| 槽位 | 控制的内容 | 关键发现 |
|---|---|---|
| **Default** | 人设丰富度、模拟密度 | Mimo V2 Flash 在 flash 价位上能给出辨识度高的人物声音 |
| **Smart** | 报告质量(头号杠杆) | Grok-4.1 Fast 在关闭 reasoning 的 ReACT 报告循环中表现稳定 |
| **NER** | 抽取可靠性 | 需要确定性的 JSON — 选一个不会暗中输出 CoT 的模型 |
| **Wonderwall** | 成本(最大消费方) | 850+ 次调用、7M+ tokens。冗长程度比 $/M 更重要 |

### 云端模式 — 约 1 美元/次,约 10 分钟

Mimo V2 Flash 做人设 + Grok-4.1 Fast 做 smart/NER。每个槽位都关闭了 reasoning(`LLM_DISABLE_REASONING=true` 会在 `extra_body` 里发送 `reasoning: {enabled: false}`),这就是一次场景建议从约 45 秒变成约 3 秒的差别。

| 槽位 | 模型 | 备注 |
|---|---|---|
| Default | `xiaomi/mimo-v2-flash` | 画像生成、模拟配置、记忆压缩 |
| Smart | `x-ai/grok-4.1-fast` | 报告 ReACT 循环 — 每次运行只有约 19 次调用 |
| NER | `x-ai/grok-4.1-fast` | 关闭 reasoning 后输出稳定 JSON |
| Wonderwall | `xiaomi/mimo-v2-flash` | 每次运行 850+ 次智能体动作调用;保持低冗长度 |

嵌入用 `openai/text-embedding-3-large`(通过 Matryoshka 截断到 768 维)。Web 增强用 `x-ai/grok-4.1-fast:online`。

> **延迟提示** — 每次 OpenRouter 调用都会经过 `LLMClient`,默认会在 `extra_body` 中注入 `reasoning: {enabled: false}`。仅当某个具体槽位从思维链中收益时才用 `LLM_DISABLE_REASONING=false` 关掉这个默认行为(对 MiroShark 的结构化提示词来说很罕见)。

### 为 Wonderwall 配置自定义端点

Wonderwall 槽位接受按槽位的端点覆盖,可以让你在 OpenRouter 支撑的 Default/Smart/NER 槽位旁边运行一个自部署或微调过的模型:

```bash
WONDERWALL_BASE_URL=https://your-endpoint.example.com/v1
WONDERWALL_API_KEY=not-checked          # any string for open endpoints
WONDERWALL_MODEL_NAME=your-model-id
```

任意一个字段都可以省略 — `WONDERWALL_BASE_URL` 留空则复用 `LLM_BASE_URL`,`WONDERWALL_API_KEY` 留空则复用 `LLM_API_KEY`。适合把每次运行 850+ 次智能体动作调用路由到 vLLM / Modal / 服务器上的 Ollama 部署,同时把报告和图谱构建槽位留在托管提供商上。

## 本地模式(Ollama)

> **必须覆盖上下文长度。** Ollama 默认是 4096 tokens,但 MiroShark 的提示词需要 10–30k。创建一个自定义 Modelfile:
>
> ```bash
> printf 'FROM qwen3:14b\nPARAMETER num_ctx 32768' > Modelfile
> ollama create mirosharkai -f Modelfile
> ```

| 模型 | 显存 | 速度 | 备注 |
|---|---|---|---|
| `qwen2.5:32b` | 20GB+ | ~40 t/s | `.env.example` 中的默认 — 全能型 |
| `qwen3:30b-a3b` *(MoE)* | 18GB | ~110 t/s | 最快 — MoE 每个 token 只激活 3B 参数 |
| `qwen3:14b` | 12GB | ~60 t/s | 中端 GPU 的均衡选择 |
| `qwen3:8b` | 8GB | ~42 t/s | 最低可用;上下文紧时减少 Wonderwall 轮次 |

### 硬件快速选型

| 配置 | 模型 |
|---|---|
| RTX 3090/4090 或 M2 Pro 32GB+ | `qwen2.5:32b` |
| RTX 4080 / M2 Pro 16GB | `qwen3:30b-a3b` |
| RTX 4070 / M1 Pro | `qwen3:14b` |
| 8GB 显存 / 笔记本 | `qwen3:8b` |

**本地嵌入:** `ollama pull nomic-embed-text` — 768 维,与 Neo4j 默认一致。

## 混合模式

大多数用户自然落到这里:本地跑高频模拟轮次,把报告路由到 Claude。

```bash
LLM_MODEL_NAME=qwen2.5:32b
SMART_PROVIDER=claude-code
SMART_MODEL_NAME=claude-sonnet-4-20250514
```
