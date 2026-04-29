# Models

Four independent model slots (see [Configuration](CONFIGURATION.md#model-slots) for the env vars). This doc covers which models to put in which slot.

## Cloud preset (OpenRouter)

One benchmarked preset ships in `.env.example`. Copy it and set your API key.

Each slot controls a different quality axis:

| Slot | Controls | Key finding |
|---|---|---|
| **Default** | Persona richness, sim density | Mimo V2 Flash gives distinct voices at flash-tier price |
| **Smart** | Report quality (#1 lever) | Grok-4.1 Fast holds up on ReACT report loops with reasoning disabled |
| **NER** | Extraction reliability | Needs deterministic JSON — pick a model that doesn't silently emit CoT |
| **Wonderwall** | Cost (biggest consumer) | 850+ calls, 7M+ tokens. Verbosity matters more than $/M |

### Cloud mode — ~$1/run, ~10 min

Mimo V2 Flash personas + Grok-4.1 Fast smart/NER. Reasoning is disabled on every slot (`LLM_DISABLE_REASONING=true` sends `reasoning: {enabled: false}` in `extra_body`), which is the difference between a ~45s scenario-suggest call and a ~3s one.

| Slot | Model | Notes |
|---|---|---|
| Default | `xiaomi/mimo-v2-flash` | Persona generation, sim config, memory compaction |
| Smart | `x-ai/grok-4.1-fast` | Report ReACT loop — only ~19 calls/run |
| NER | `x-ai/grok-4.1-fast` | Stable JSON with reasoning off |
| Wonderwall | `xiaomi/mimo-v2-flash` | 850+ agent-action calls/run; keep verbosity low |

Embeddings use `openai/text-embedding-3-large` (truncated to 768 dims via Matryoshka). Web enrichment uses `x-ai/grok-4.1-fast:online`.

> **Latency note** — every OpenRouter call goes through `LLMClient`, which injects `reasoning: {enabled: false}` into `extra_body` by default. Turn it off with `LLM_DISABLE_REASONING=false` only if a specific slot benefits from chain-of-thought (rare for MiroShark's structured prompts).

### Custom endpoint for Wonderwall

The Wonderwall slot accepts a per-slot endpoint override so you can run a self-hosted or fine-tuned model alongside the OpenRouter-backed Default/Smart/NER slots:

```bash
WONDERWALL_BASE_URL=https://your-endpoint.example.com/v1
WONDERWALL_API_KEY=not-checked          # any string for open endpoints
WONDERWALL_MODEL_NAME=your-model-id
```

Either field can be omitted — a blank `WONDERWALL_BASE_URL` reuses `LLM_BASE_URL`, a blank `WONDERWALL_API_KEY` reuses `LLM_API_KEY`. Useful for routing the 850+ agent-action calls per run to a vLLM / Modal / Ollama-on-a-server deployment while keeping the report and graph-build slots on a hosted provider.

## Local mode (Ollama)

> **Context override required.** Ollama defaults to 4096 tokens, but MiroShark prompts need 10–30k. Create a custom Modelfile:
>
> ```bash
> printf 'FROM qwen3:14b\nPARAMETER num_ctx 32768' > Modelfile
> ollama create mirosharkai -f Modelfile
> ```

| Model | VRAM | Speed | Notes |
|---|---|---|---|
| `qwen2.5:32b` | 20GB+ | ~40 t/s | Default in `.env.example` — solid all-rounder |
| `qwen3:30b-a3b` *(MoE)* | 18GB | ~110 t/s | Fastest — MoE activates only 3B params per token |
| `qwen3:14b` | 12GB | ~60 t/s | Good balance for mid-range GPUs |
| `qwen3:8b` | 8GB | ~42 t/s | Minimum viable; drop Wonderwall rounds if context is tight |

### Hardware quick-pick

| Setup | Model |
|---|---|
| RTX 3090/4090 or M2 Pro 32GB+ | `qwen2.5:32b` |
| RTX 4080 / M2 Pro 16GB | `qwen3:30b-a3b` |
| RTX 4070 / M1 Pro | `qwen3:14b` |
| 8GB VRAM / laptop | `qwen3:8b` |

**Embeddings locally:** `ollama pull nomic-embed-text` — 768 dimensions, matches the Neo4j default.

## Hybrid mode

Most users land here naturally: run local for the high-volume simulation rounds, route to Claude for reports.

```bash
LLM_MODEL_NAME=qwen2.5:32b
SMART_PROVIDER=claude-code
SMART_MODEL_NAME=claude-sonnet-4-20250514
```
