<sup>[English](INSTALL.md) · 中文</sup>

# 安装

从下面的几条路径中任选其一。

| 路径 | 需要 GPU? | 适用场景 |
|---|---|---|
| [Railway / Render](#一键云部署) | 否 | 最快上线的部署路径 |
| [`./miroshark`(OpenRouter)](#快速开始-miroshark-启动器) | 可选 | 本地开发,阻力最小 |
| [云端 API — OpenRouter](#方案-a1openrouter) | 否 | 一把密钥覆盖所有槽位与嵌入 |
| [云端 API — OpenAI](#方案-a2openai) | 否 | 已有 OpenAI 密钥 |
| [云端 API — Anthropic](#方案-a3anthropic) | 否 | 已有 Anthropic 密钥 |
| [Docker + Ollama](#方案-bdocker--本地-ollama) | 是 | 完全自部署,一行命令 |
| [手动 + Ollama](#方案-c手动--本地-ollama) | 是 | 完全自部署,手动控制 |
| [Claude Code CLI](#方案-dclaude-code无需-api-密钥) | 否 | 使用你的 Claude Pro/Max 订阅 |

## 前置依赖

- 一把 OpenAI 兼容 API 密钥(OpenRouter、OpenAI、Anthropic 等),用于本地推理的 Ollama,**或者** Claude Code CLI
- Python 3.11+、Node.js 18+、Neo4j 5.15+

**安装 Neo4j**(`./miroshark` 启动器会替你启动它 — 你只需要装好这个软件包):

- **macOS** — `brew install neo4j`
- **Linux** — `sudo apt install neo4j` *(或对应发行版的等价命令)*
- **Windows** — 安装 [Neo4j Desktop](https://neo4j.com/download/)(图形界面 — 在那里启动数据库,然后从 WSL2 或 Git Bash 运行启动器),或者把整套技术栈跑在 [WSL2](https://learn.microsoft.com/windows/wsl/install) 里并按 Linux 步骤操作
- **零安装** — 创建一个免费 [Neo4j Aura](https://neo4j.com/cloud/aura-free/) 云实例,把 `NEO4J_URI` / `NEO4J_PASSWORD` 设到 `.env`

> `./miroshark` 启动器是一个 bash 脚本 — 在 Windows 上需要 WSL2 或 Git Bash。

在 macOS/Linux 原生安装上设置一次密码 — MiroShark 默认使用 `miroshark`,与 `.env.example` 保持一致:

```bash
neo4j-admin dbms set-initial-password miroshark
```

## 硬件

**本地(Ollama):**

| | 最低 | 推荐 |
|---|---|---|
| 内存 | 16 GB | 32 GB |
| 显存 | 10 GB | 24 GB |
| 磁盘 | 20 GB | 50 GB |

**云端模式:** 不需要 GPU — 只要 Neo4j 和一把 API 密钥。任意 4 GB 内存的机器都能跑。

---

## 一键云部署

3 分钟内部署到云端 — 无需任何本地搭建。

**部署前先创建:**

1. 一个免费 [Neo4j Aura](https://neo4j.com/cloud/aura-free/) 实例 — 拿到 `NEO4J_URI`(以 `neo4j+s://` 开头)和密码。
2. 一把 [OpenRouter](https://openrouter.ai/) API 密钥 — 用于 LLM 调用与嵌入。

### Railway(推荐 — 持久化存储,免费试用)

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/new/template?template=https://github.com/aaronjmars/MiroShark)

点击之后,在 Railway 控制台中设置以下环境变量:

| 变量 | 值 |
|---|---|
| `LLM_API_KEY` | 你的 OpenRouter 密钥(`sk-or-v1-...`) |
| `NEO4J_URI` | 你的 Aura URI(`neo4j+s://...`) |
| `NEO4J_PASSWORD` | 你的 Aura 密码 |
| `EMBEDDING_API_KEY` | 同一把 OpenRouter 密钥 |
| `OPENAI_API_KEY` | 同一把 OpenRouter 密钥 |

### Render(免费套餐 — 750 小时/月,闲置 15 分钟后会自动停机)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/aaronjmars/MiroShark)

Render 会自动读取 `render.yaml`。提示时设置上面相同的环境变量即可。

> 云端部署使用 OpenRouter 处理所有 LLM 调用 — 此模式下不可用 Ollama。两个平台都会以一个公开 HTTPS URL 暴露 MiroShark,无需端口转发。

---

## 快速开始: `./miroshark` 启动器

**推荐路径** — 一把 [OpenRouter](https://openrouter.ai/) 密钥加上启动器。

**前置依赖** — Python 3.11+、Node 18+、Neo4j(`brew install neo4j` / `sudo apt install neo4j`),以及一把 OpenRouter 密钥。

```bash
git clone https://github.com/aaronjmars/MiroShark.git && cd MiroShark
cp .env.example .env
```

`.env.example` 出厂自带云端预设(Mimo V2 Flash + Grok-4.1 Fast)作为默认配置。打开 `.env`,把你的 OpenRouter 密钥粘贴进五行空白的 `*_API_KEY=`(`LLM_`、`SMART_`、`NER_`、`OPENAI_`、`EMBEDDING_` — 五行用同一把密钥)。除非你想换一套不同的模型组合,否则不需要修改任何模型字段。

然后启动:

```bash
./miroshark
```

启动器会做这些事:

1. 检查 Python 3.11+、Node 18+、uv、Neo4j/Docker
2. 如果 Neo4j 未运行就启动它(Docker 或原生)
3. 缺失则安装前后端依赖
4. 杀掉占用 3000/5001 端口的僵尸进程
5. 启动 Vite 开发服务器(`:3000`)和 Flask API(`:5001`)
6. Ctrl+C 全部停止

打开 `http://localhost:3000`。第一次模拟约 10 分钟、约 1 美元。完整预设说明见 [Models](MODELS.zh-CN.md)。

> 想完全本地运行?跳到下面的 [方案 B(Docker + Ollama)](#方案-bdocker--本地-ollama) 或 [方案 C(手动 Ollama)](#方案-c手动--本地-ollama)。

---

## 方案 A: 云端 API(无需 GPU)

只有 Neo4j 跑在本地。LLM 与嵌入都走云端提供商。下面三个口味 — 选一个匹配你已有密钥的。

```bash
# 三个口味通用的准备步骤
brew install neo4j       # macOS  (Linux: sudo apt install neo4j)
cp .env.example .env
```

### 方案 A.1:OpenRouter

一把密钥覆盖所有槽位,包括嵌入。配置最简单,也是 [Models](MODELS.zh-CN.md) 中跑过基准的那条路径。

```bash
LLM_API_KEY=sk-or-v1-YOUR_KEY
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_NAME=xiaomi/mimo-v2-flash

SMART_PROVIDER=openai
SMART_API_KEY=sk-or-v1-YOUR_KEY
SMART_BASE_URL=https://openrouter.ai/api/v1
SMART_MODEL_NAME=x-ai/grok-4.1-fast

NER_MODEL_NAME=x-ai/grok-4.1-fast
NER_BASE_URL=https://openrouter.ai/api/v1
NER_API_KEY=sk-or-v1-YOUR_KEY

WONDERWALL_MODEL_NAME=xiaomi/mimo-v2-flash
WEB_SEARCH_MODEL=x-ai/grok-4.1-fast:online

OPENAI_API_KEY=sk-or-v1-YOUR_KEY
OPENAI_API_BASE_URL=https://openrouter.ai/api/v1

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=openai/text-embedding-3-large
EMBEDDING_BASE_URL=https://openrouter.ai/api
EMBEDDING_API_KEY=sk-or-v1-YOUR_KEY
EMBEDDING_DIMENSIONS=768
```

### 方案 A.2:OpenAI

直接使用你的 OpenAI Platform 密钥。

```bash
LLM_API_KEY=sk-proj-YOUR_KEY
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

SMART_PROVIDER=openai
SMART_API_KEY=sk-proj-YOUR_KEY
SMART_BASE_URL=https://api.openai.com/v1
SMART_MODEL_NAME=gpt-4o                   # or gpt-4.1 for stronger reports

NER_MODEL_NAME=gpt-4o-mini
NER_BASE_URL=https://api.openai.com/v1
NER_API_KEY=sk-proj-YOUR_KEY

WONDERWALL_MODEL_NAME=gpt-4o-mini

OPENAI_API_KEY=sk-proj-YOUR_KEY
OPENAI_API_BASE_URL=https://api.openai.com/v1

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-proj-YOUR_KEY
EMBEDDING_DIMENSIONS=768                  # OpenAI truncates to this via the dimensions param
```

### 方案 A.3:Anthropic

通过 OpenAI 兼容端点使用你的 Anthropic Console 密钥。**Anthropic 不提供嵌入** — 把 `EMBEDDING_*` 指向 Ollama(`nomic-embed-text`,见 [方案 C](#方案-c手动--本地-ollama)),或者只用一把 OpenAI/OpenRouter 密钥来做嵌入。

```bash
LLM_API_KEY=sk-ant-YOUR_KEY
LLM_BASE_URL=https://api.anthropic.com/v1/
LLM_MODEL_NAME=claude-haiku-4-5

SMART_PROVIDER=openai
SMART_API_KEY=sk-ant-YOUR_KEY
SMART_BASE_URL=https://api.anthropic.com/v1/
SMART_MODEL_NAME=claude-sonnet-4-6

NER_MODEL_NAME=claude-haiku-4-5
NER_BASE_URL=https://api.anthropic.com/v1/
NER_API_KEY=sk-ant-YOUR_KEY

WONDERWALL_MODEL_NAME=claude-haiku-4-5

OPENAI_API_KEY=sk-ant-YOUR_KEY
OPENAI_API_BASE_URL=https://api.anthropic.com/v1/

# Embeddings: Anthropic doesn't provide any — use local Ollama
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434
EMBEDDING_DIMENSIONS=768
```

> 提示词缓存(`LLM_PROMPT_CACHING_ENABLED=true`)在这条路径上收益最大 — ReACT 报告循环会在多轮迭代之间复用同一个系统提示词,所以缓存能显著降低 Sonnet 账单。

### 方案 A.4:为 Wonderwall 配置自定义端点

Wonderwall 槽位(每个智能体的模拟循环,每次运行约 850–1650 次调用)允许独立的端点覆盖,这样你可以把高频调用路由到自部署的 vLLM、Modal/Replicate 部署、微调模型,或另一台主机上的 Ollama —— 同时把图谱构建、报告和 NER 留在托管提供商上。

把这几行加到上面任何一种配置里:

```bash
WONDERWALL_BASE_URL=https://your-endpoint.example.com/v1
WONDERWALL_API_KEY=not-checked            # any string for open endpoints
WONDERWALL_MODEL_NAME=your-model-id
```

任意一个字段都可以留空。`WONDERWALL_BASE_URL` 留空则复用 `LLM_BASE_URL`,`WONDERWALL_API_KEY` 留空则复用 `LLM_API_KEY`。UI 中的 设置 → 高级 → Wonderwall 暴露相同的三个字段,改动会在下次开始模拟时生效(无需重启 Flask)。完整模式见 [docs/MODELS.md#custom-endpoint-for-wonderwall](MODELS.zh-CN.md#为-wonderwall-配置自定义端点)。

---

`.env` 配置完后,启动:

```bash
./miroshark
# 或手动: npm run setup:all && npm run dev
```

打开 `http://localhost:3000`。后端 API 在 `http://localhost:5001`。

---

## 方案 B: Docker — 本地 Ollama

```bash
git clone https://github.com/aaronjmars/MiroShark.git
cd MiroShark
docker compose up -d

# Pull models into Ollama
docker exec miroshark-ollama ollama pull qwen2.5:32b
docker exec miroshark-ollama ollama pull nomic-embed-text
```

打开 `http://localhost:3000`。

---

## 方案 C: 手动 — 本地 Ollama

```bash
# 1. Start Neo4j (macOS; for Linux: sudo apt install neo4j)
brew install neo4j && brew services start neo4j

# 2. Start Ollama & pull models
ollama serve &
ollama pull qwen2.5:32b
ollama pull nomic-embed-text

# 3. Configure & run
cp .env.example .env
npm run setup:all
npm run dev
```

Ollama 上下文窗口的覆盖配置(很重要 — 默认只有 4096 tokens,而 MiroShark 需要 10–30k)请见 [Models](MODELS.zh-CN.md)。

---

## 方案 D: Claude Code(无需 API 密钥)

通过本地 `claude` CLI 把你的 Claude Pro/Max 订阅当作 LLM 后端。无需 API 密钥或 GPU — 只要本地有一份已登录的安装。

```bash
# 1. Install Claude Code (if not already)
npm install -g @anthropic-ai/claude-code

# 2. Log in (opens browser)
claude

# 3. Start Neo4j (macOS; for Linux: sudo apt install neo4j)
brew install neo4j && brew services start neo4j

# 4. Configure
cp .env.example .env
```

编辑 `.env`:

```bash
LLM_PROVIDER=claude-code
# Optional: pick a specific model (default uses your Claude Code default)
# CLAUDE_CODE_MODEL=claude-sonnet-4-20250514
```

你仍然需要嵌入(Claude Code 不支持嵌入)以及一个独立的 LLM 给 CAMEL-AI 模拟轮次用。两者都可以选择 Ollama 或一个云端 API。

```bash
npm run setup:all && npm run dev
```

### Claude Code 覆盖哪些组件

当 `LLM_PROVIDER=claude-code` 时,MiroShark 的服务会通过 Claude Code 路由。唯一例外是 CAMEL-AI 模拟引擎本身,它在内部管理自己的 LLM 连接。

| 组件 | Claude Code | 需要独立 LLM |
|---|---|---|
| 图谱构建(本体 + NER) | 是 | — |
| 智能体画像生成 | 是 | — |
| 模拟配置生成 | 是 | — |
| 报告生成 | 是 | — |
| 人设对话 | 是 | — |
| CAMEL-AI 模拟轮次 | — | 是(Ollama 或云端) |
| 嵌入 | — | 是(Ollama 或云端) |

> **性能提示:** 每次 LLM 调用都会派生一个 `claude -p` 子进程(开销约 2–5 秒)。最适合小模拟或混合模式 — 高频模拟轮次用 Ollama/云端,其他都交给 Claude Code。
