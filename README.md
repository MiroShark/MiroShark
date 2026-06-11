<p align="center">
  <img src="./docs/images/miroshark-logo.jpg" alt="MiroShark" width="120" />
</p>

<h1 align="center">MiroShark</h1>

<p align="center">
  <a href="https://github.com/aaronjmars/MiroShark/stargazers"><img src="https://img.shields.io/github/stars/aaronjmars/MiroShark?style=flat-square&logo=github" alt="GitHub stars"></a>
  <a href="https://github.com/aaronjmars/MiroShark/network/members"><img src="https://img.shields.io/github/forks/aaronjmars/MiroShark?style=flat-square&logo=github" alt="GitHub forks"></a>
  <a href="https://x.com/miroshark_"><img src="https://img.shields.io/badge/Follow-%40miroshark__-black?style=flat-square&logo=x&labelColor=000000" alt="Follow on X"></a>
  <a href="https://bankr.bot/discover/0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3"><img src="https://img.shields.io/badge/MiroShark%20on-Bankr-orange?style=flat-square&labelColor=1a1a2e" alt="MiroShark on Bankr"></a>
</p>

<p align="center">
  <b>English</b> · <a href="./README.zh-CN.md">中文</a> · <a href="./README.ja.md">日本語</a>
</p>

<p align="center">
  <img src="./docs/images/miroshark-demo.gif" alt="MiroShark Demo" />
</p>

---

> **Simulate anything, for $1 & less than 10 min — Universal Swarm Intelligence Engine**
> Drop in anything — a press release, a news headline, a policy draft, a question you can't answer, a historical what-if — and MiroShark spawns hundreds of agents that react to it hour by hour. Posting, arguing, trading, changing their minds.

<p align="center">
  <img src="./docs/images/simulate-anything-hero-v2.jpg" alt="Simulate anything — $1 per simulation, 10 min first result, 100 agents: input → build world → swarm → report" width="100%" />
</p>

## What it does

- You bring a scenario. MiroShark builds the world around it.
- Hundreds of grounded agents. Twitter, Reddit, and a prediction market. Hour by hour.
- Chat with any of them. Drop breaking news mid-run. Fork the timeline.
- Get a report on what happened, citing actual posts and trades.

<p align="center">
  <img src="./docs/images/simulation-phases-v2.jpg" alt="MiroShark pipeline: Phase 1 Ontology Generation → Phase 2 Graph Building → Phase 3 Agent Setup → Phase 4 Simulation Execution → Phase 5 Report & Interaction" width="100%" />
</p>

## Quick start

The recommended path: **one [OpenRouter](https://openrouter.ai/) key + the `./miroshark` launcher.** First simulation in ~10 min, ~$1.

**Prereqs** — Python 3.11+, Node 18+, Neo4j, and an [OpenRouter key](https://openrouter.ai/).

Install Neo4j — the launcher starts it for you:

- **macOS** — `brew install neo4j`
- **Linux** — `sudo apt install neo4j` *(or your distro's equivalent)*
- **Windows** — install [Neo4j Desktop](https://neo4j.com/download/) *(native, GUI — start the DB there, then run the launcher from WSL2 or Git Bash)*, or run the whole stack inside [WSL2](https://learn.microsoft.com/windows/wsl/install) and follow the Linux steps
- **Zero-install** — create a free [Neo4j Aura](https://neo4j.com/cloud/aura-free/) cloud instance and point `NEO4J_URI` / `NEO4J_PASSWORD` at it in `.env`

Then:

```bash
git clone https://github.com/aaronjmars/MiroShark.git && cd MiroShark
cp .env.example .env
# Paste your OpenRouter key into the LLM_API_KEY / SMART_API_KEY /
# NER_API_KEY / OPENAI_API_KEY / EMBEDDING_API_KEY slots (same key,
# 5 places). Default lineup is Mimo V2 Flash + Gemini 3 Flash.
./miroshark
```

The launcher checks dependencies, starts Neo4j, installs frontend + backend, and serves `:3000` + `:5001`. Ctrl+C stops everything. Open `http://localhost:3000` and drop in a document.

**Other paths** — [one-click Railway / Render deploy](docs/INSTALL.md#one-click-cloud), [Docker + Ollama](docs/INSTALL.md#option-b-docker--local-ollama), [manual Ollama](docs/INSTALL.md#option-c-manual--local-ollama), [Claude Code CLI](docs/INSTALL.md#option-d-claude-code-no-api-key) — all in **[docs/INSTALL.md](docs/INSTALL.md)**.

<p align="center">
  <img src="./docs/images/miroshark-overview-diagram-v2.jpg" alt="MiroShark Overview" />
</p>

## Interface language

After launching, click the **中 / EN** toggle in the top-right of the navbar to switch between English and Chinese. Your choice is persisted in the browser, and the public gallery card titles + descriptions follow the active locale.

## Use cases

- **PR crisis testing** — simulate public reaction to a press release before publishing
- **Market reaction** — feed financial news and observe simulated trader + investor sentiment
- **Advertisement** — test a campaign, headline, or pitch against a simulated audience before spending
- **Policy analysis** — test draft regulations against a simulated public
- **Life decision** — frame a personal decision (job move, relocation, launch timing) as a scenario and watch diverse personas argue it out
- **What-if history** — rewrite a historical event and see how a population of personas re-narrates the aftermath
- **Creative experiments** — feed a novel with a lost ending; agents write a narratively consistent conclusion

<p align="center">
  <img src="./docs/images/agent-grounding-v2.jpg" alt="Five layers of grounding per agent: demographic seed, web enrichment, semantic search, relationships, graph attributes" width="100%" />
</p>

## Features

A few of the highlights:

| Feature | What it does |
|---|---|
| **Smart Setup** | Drop in a doc → three auto-generated Bull / Bear / Neutral scenarios in ~2s |
| **Just Ask** | Type a question with no document — MiroShark researches and writes the seed briefing |
| **Counterfactual Branching** | Fork a running simulation with an injected event ("CEO resigns in round 24?") |
| **Director Mode** | Inject breaking news into the *current* timeline without forking |
| **Per-Agent MCP Tools** | Personas invoke real MCP tools (web search, APIs) during simulation |
| **Article Generation** | Substack-style write-up of what happened, grounded in actual posts and trades |
| **Public Gallery & Verified Predictions** | Browse and fork every published sim at `/explore`; track the calls that landed at `/verified` |
| **Share everywhere** | Social cards, replay GIFs, tweet threads, RSS / Atom, embeds, and Slack / Discord / Telegram / webhook notifications |

…and **40+ more** — share surfaces, exports, integrations, observability, and on-chain citation. See the **[full feature list and deep dives in docs/FEATURES.md](docs/FEATURES.md)**.

<p align="center">
  <img src="./docs/images/graph-memory-pipeline-v2.jpg" alt="Graph memory pipeline: ingestion (NER, embed, entity resolution, contradiction check, temporal edges) and retrieval (vector + BM25 + BFS, fused, reranked)" width="100%" />
</p>

## Documentation

| | |
|---|---|
| [Install](docs/INSTALL.md) | Every deployment path: cloud, Docker, Ollama, Claude Code |
| [Configuration](docs/CONFIGURATION.md) | Env vars, model routing, feature flags |
| [Models](docs/MODELS.md) | Cloud preset, local Ollama models, benchmark findings |
| [Architecture](docs/ARCHITECTURE.md) | Simulation engine, memory pipeline, graph retrieval |
| [Features](docs/FEATURES.md) | Deep dive on every feature in the table above |
| [HTTP API](docs/API.md) | Every endpoint, grouped by concern — plus interactive Swagger UI at `/api/docs` and a spec at `/api/openapi.yaml` |
| [CLI](docs/CLI.md) | `miroshark-cli` reference |
| [MCP](docs/MCP.md) | Claude Desktop / Cursor / Windsurf / Continue integration + report agent tools (auto-generated snippets in Settings → AI Integration) |
| [Webhooks](docs/WEBHOOKS.md) | Completion webhook payload, headers, delivery semantics, Slack/Discord/Zapier/n8n recipes |
| [DKG citation](docs/DKG.md) | OriginTrail DKG anchoring — UAL + Merkle root + on-chain citation key for any finished sim |
| [WaybackClaw archive](docs/WAYBACKCLAW.md) | WaybackClaw submission — snapshot id + IPFS CID + Nostr event id for any finished sim |
| [Observability](docs/OBSERVABILITY.md) | Debug panel, event stream, logging |
| [Ecosystem](ECOSYSTEM.md) | Projects, agents, and products built on top of MiroShark |
| [Contributing](CONTRIBUTING.md) | Tests and development |

---

## License

AGPL-3.0. See [LICENSE](./LICENSE).

Support the project: `0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3`

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=aaronjmars/miroshark&type=Date)](https://www.star-history.com/#aaronjmars/miroshark&Date)
