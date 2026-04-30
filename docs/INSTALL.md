# Install

<sup>English · [中文](INSTALL.zh-CN.md)</sup>

Pick one of the paths below.

| Path | GPU? | Best for |
|---|---|---|
| [Railway / Render](#one-click-cloud) | No | Fastest path to a live deployment |
| [`./miroshark` (OpenRouter)](#quick-start-miroshark-launcher) | Optional | Local dev, lowest friction |
| [Cloud API — OpenRouter](#option-a1-openrouter) | No | One key covers every slot + embeddings |
| [Cloud API — OpenAI](#option-a2-openai) | No | You already have an OpenAI key |
| [Cloud API — Anthropic](#option-a3-anthropic) | No | You already have an Anthropic key |
| [Docker + Ollama](#option-b-docker--local-ollama) | Yes | Fully self-hosted, one command |
| [Manual + Ollama](#option-c-manual--local-ollama) | Yes | Fully self-hosted, manual control |
| [Claude Code CLI](#option-d-claude-code-no-api-key) | No | Uses your Claude Pro/Max subscription |

## Prerequisites

- An OpenAI-compatible API key (OpenRouter, OpenAI, Anthropic…), Ollama for local inference, **or** Claude Code CLI
- Python 3.11+, Node.js 18+, Neo4j 5.15+

**Installing Neo4j** (the `./miroshark` launcher starts it for you — you only need to install the package):

- **macOS** — `brew install neo4j`
- **Linux** — `sudo apt install neo4j` *(or your distro's equivalent)*
- **Windows** — install [Neo4j Desktop](https://neo4j.com/download/) (GUI — start the DB there, then run the launcher from WSL2 or Git Bash), or run the whole stack inside [WSL2](https://learn.microsoft.com/windows/wsl/install) and follow the Linux steps
- **Zero-install** — create a free [Neo4j Aura](https://neo4j.com/cloud/aura-free/) cloud instance and set `NEO4J_URI` / `NEO4J_PASSWORD` in `.env`

> The `./miroshark` launcher is a bash script — on Windows it needs WSL2 or Git Bash.

Set the password once on macOS/Linux native installs — MiroShark's default is `miroshark` to match `.env.example`:

```bash
neo4j-admin dbms set-initial-password miroshark
```

## Hardware

**Local (Ollama):**

| | Minimum | Recommended |
|---|---|---|
| RAM | 16 GB | 32 GB |
| VRAM | 10 GB | 24 GB |
| Disk | 20 GB | 50 GB |

**Cloud mode:** no GPU needed — just Neo4j and an API key. Any 4 GB RAM machine works.

---

## One-click cloud

Deploy to the cloud in under 3 minutes — no local setup required.

**Before you deploy, create:**

1. A free [Neo4j Aura](https://neo4j.com/cloud/aura-free/) instance — grab the `NEO4J_URI` (starts with `neo4j+s://`) and password.
2. An [OpenRouter](https://openrouter.ai/) API key — used for LLM calls and embeddings.

### Railway (recommended — persistent storage, free trial)

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/new/template?template=https://github.com/aaronjmars/MiroShark)

After clicking, set these environment variables in the Railway dashboard:

| Variable | Value |
|---|---|
| `LLM_API_KEY` | Your OpenRouter key (`sk-or-v1-...`) |
| `NEO4J_URI` | Your Aura URI (`neo4j+s://...`) |
| `NEO4J_PASSWORD` | Your Aura password |
| `EMBEDDING_API_KEY` | Same OpenRouter key |
| `OPENAI_API_KEY` | Same OpenRouter key |

### Render (free tier — 750 hrs/month, spins down after 15 min idle)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/aaronjmars/MiroShark)

Render reads `render.yaml` automatically. Set the same env vars above when prompted.

> Cloud deploys use OpenRouter for all LLM calls — Ollama is not available in this mode. Both platforms expose MiroShark on a public HTTPS URL, no port forwarding needed.

---

## Quick start: `./miroshark` launcher

**The recommended path** — one [OpenRouter](https://openrouter.ai/) key and the launcher.

**Prereqs** — Python 3.11+, Node 18+, Neo4j (`brew install neo4j` / `sudo apt install neo4j`), and an OpenRouter key.

```bash
git clone https://github.com/aaronjmars/MiroShark.git && cd MiroShark
cp .env.example .env
```

`.env.example` ships with the Cloud preset (Mimo V2 Flash + Grok-4.1 Fast) as the active default. Open `.env` and paste your OpenRouter key into the five blank `*_API_KEY=` lines (`LLM_`, `SMART_`, `NER_`, `OPENAI_`, `EMBEDDING_` — same key in all of them). No model edits needed unless you want a different lineup.

Then launch:

```bash
./miroshark
```

What the launcher does:

1. Checks Python 3.11+, Node 18+, uv, Neo4j/Docker
2. Starts Neo4j if not already running (Docker or native)
3. Installs frontend + backend deps if missing
4. Kills stale processes on ports 3000/5001
5. Launches Vite dev server (`:3000`) and Flask API (`:5001`)
6. Ctrl+C to stop everything

Open `http://localhost:3000`. First simulation in ~10 min, ~$1. See [Models](MODELS.md) for the full preset breakdown.

> Prefer to run everything local? Skip to [Option B (Docker + Ollama)](#option-b-docker--local-ollama) or [Option C (manual Ollama)](#option-c-manual--local-ollama) below.

---

## Option A: Cloud API (no GPU)

Only Neo4j runs locally. LLM and embeddings use a cloud provider. Three flavours below — pick the one that matches the key you already have.

```bash
# Common prep for all three flavours
brew install neo4j       # macOS  (Linux: sudo apt install neo4j)
cp .env.example .env
```

### Option A.1: OpenRouter

One key covers every slot, including embeddings. Easiest to set up and the path benchmarked in [Models](MODELS.md).

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

### Option A.2: OpenAI

Use your OpenAI Platform key directly.

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

### Option A.3: Anthropic

Use your Anthropic Console key via the OpenAI-compatible endpoint. **Anthropic doesn't offer embeddings** — point `EMBEDDING_*` at Ollama (`nomic-embed-text`, see [Option C](#option-c-manual--local-ollama)) or at an OpenAI/OpenRouter key just for embeddings.

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

> Prompt caching (`LLM_PROMPT_CACHING_ENABLED=true`) hits its sweet spot here — the ReACT report loop reuses the same system prompt across iterations, so caching meaningfully reduces the Sonnet bill.

### Option A.4: Custom endpoint for Wonderwall

The Wonderwall slot (the per-agent simulation loop, ~850–1650 calls/run) accepts an independent endpoint override so you can route the volume hits to a self-hosted vLLM, Modal/Replicate deployment, fine-tuned model, or Ollama on a different host — while keeping graph build, reports, and NER on a hosted provider.

Add to any of the configurations above:

```bash
WONDERWALL_BASE_URL=https://your-endpoint.example.com/v1
WONDERWALL_API_KEY=not-checked            # any string for open endpoints
WONDERWALL_MODEL_NAME=your-model-id
```

Either field can be left blank. A blank `WONDERWALL_BASE_URL` reuses `LLM_BASE_URL`, a blank `WONDERWALL_API_KEY` reuses `LLM_API_KEY`. Settings → Advanced → Wonderwall in the UI exposes the same three fields and updates take effect on the next simulation start (no Flask restart). See [docs/MODELS.md#custom-endpoint-for-wonderwall](MODELS.md#custom-endpoint-for-wonderwall) for the full pattern.

---

Once `.env` is set, launch:

```bash
./miroshark
# or, manual:  npm run setup:all && npm run dev
```

Open `http://localhost:3000`. Backend API at `http://localhost:5001`.

---

## Option B: Docker — local Ollama

```bash
git clone https://github.com/aaronjmars/MiroShark.git
cd MiroShark
docker compose up -d

# Pull models into Ollama
docker exec miroshark-ollama ollama pull qwen2.5:32b
docker exec miroshark-ollama ollama pull nomic-embed-text
```

Open `http://localhost:3000`.

---

## Option C: Manual — local Ollama

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

See [Models](MODELS.md) for the Ollama context-window override (important — defaults to 4096 tokens but MiroShark needs 10–30k).

---

## Option D: Claude Code (no API key)

Use your Claude Pro/Max subscription as the LLM backend via the local `claude` CLI. No API key or GPU required — just a logged-in installation.

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

Edit `.env`:

```bash
LLM_PROVIDER=claude-code
# Optional: pick a specific model (default uses your Claude Code default)
# CLAUDE_CODE_MODEL=claude-sonnet-4-20250514
```

You still need embeddings (Claude Code doesn't support them) and a separate LLM for the CAMEL-AI simulation rounds. Use Ollama or a cloud API for both.

```bash
npm run setup:all && npm run dev
```

### What Claude Code covers

When `LLM_PROVIDER=claude-code`, MiroShark services route through Claude Code. The only exception is the CAMEL-AI simulation engine itself, which manages its own LLM connections internally.

| Component | Claude Code | Needs separate LLM |
|---|---|---|
| Graph building (ontology + NER) | Yes | — |
| Agent profile generation | Yes | — |
| Simulation config generation | Yes | — |
| Report generation | Yes | — |
| Persona chat | Yes | — |
| CAMEL-AI simulation rounds | — | Yes (Ollama or cloud) |
| Embeddings | — | Yes (Ollama or cloud) |

> **Performance note:** each LLM call spawns a `claude -p` subprocess (~2-5s overhead). Best for small simulations or hybrid mode — use Ollama/cloud for high-volume simulation rounds, Claude Code for everything else.
