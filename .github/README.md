<p align="center">
  <img src="../docs/images/simulate-anything-hero-v2.jpg" alt="MiroShark — Simulate anything for $1 in under 10 minutes. Drop in a document, headline, policy draft, or a what-if question and MiroShark spawns 100+ grounded AI agents that post, argue, and trade across Twitter, Reddit, and a prediction market hour by hour, then writes a report citing the actual posts and trades. Pipeline: input, build world, swarm, report. Keywords: multi-agent simulation, social simulation, swarm intelligence, agent-based modeling, LLM agents, prediction market, scenario testing." width="100%" />
</p>

<h1 align="center">Simulate <em>anything.</em></h1>

<p align="center">
  <strong>Star us&nbsp;❤️&nbsp;→</strong>&nbsp;
  <a href="https://github.com/MiroShark/MiroShark/stargazers"><img src="https://img.shields.io/github/stars/MiroShark/MiroShark?style=flat-square&logo=github&label=star&color=8B5CF6&labelColor=1a1a2e" alt="Star MiroShark on GitHub"></a> &nbsp;·&nbsp;
  <a href="https://www.miroshark.xyz/docs"><img src="https://img.shields.io/badge/Docs-miroshark.xyz-8B5CF6?style=flat-square&logo=gitbook&logoColor=white&labelColor=1a1a2e" alt="Documentation"></a> &nbsp;·&nbsp;
  <a href="https://x.com/miroshark_"><img src="https://img.shields.io/badge/%40miroshark__-black?style=flat-square&logo=x&labelColor=000000" alt="@miroshark_ on X"></a> &nbsp;·&nbsp;
  <a href="https://bankr.bot/discover/0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3"><img src="https://img.shields.io/badge/%24miroshark-Bankr-F97316?style=flat-square&labelColor=1a1a2e" alt="$miroshark on Bankr"></a>
</p>

<p align="center">
  <b>$1</b> · per simulation &nbsp;·&nbsp; <b>10 min</b> · first result &nbsp;·&nbsp; <b>100+</b> · grounded agents
</p>

<div align="center">

[![stars](https://img.shields.io/github/stars/MiroShark/MiroShark?style=flat-square&label=stars&color=8B5CF6)](https://github.com/MiroShark/MiroShark/stargazers)
[![forks](https://img.shields.io/github/forks/MiroShark/MiroShark?style=flat-square&label=forks&color=F97316)](https://github.com/MiroShark/MiroShark/network/members)
[![license](https://img.shields.io/badge/license-AGPL--3.0-8B5CF6?style=flat-square)](../LICENSE)
[![python](https://img.shields.io/badge/python-3.11+-3572A5?style=flat-square)](https://www.python.org/)
[![node](https://img.shields.io/badge/node-18+-16A534?style=flat-square)](https://nodejs.org/)

</div>

<p align="center">
  <b>English</b> · <a href="README.zh-CN.md">中文</a> · <a href="README.ja.md">日本語</a> · <a href="README.fr.md">Français</a>
</p>

<br/>

<p align="center">
  <img src="../docs/images/miroshark-demo.gif" alt="MiroShark live demo — a user drops in a document, MiroShark builds the world graph, spawns 100+ agents, and they post, argue, and trade in real time while a report is written." />
</p>

<br/><br/>

<h2 align="center">What it does</h2>

<!-- NEW IMAGE: what-it-does.jpg -->
<p align="center">
  <img src="../docs/images/what-it-does.jpg" alt="What MiroShark does, in four steps: (1) You bring a scenario — MiroShark builds the world around it. (2) Hundreds of grounded agents across Twitter, Reddit, and a prediction market, hour by hour. (3) Chat with any agent, drop breaking news mid-run, fork the timeline. (4) Get a report on what happened, citing actual posts and trades." width="100%" />
</p>

<br/>

<h3 align="center">Get started</h3>

```bash
git clone https://github.com/aaronjmars/MiroShark.git && cd MiroShark
cp .env.example .env    # paste one OpenRouter key
./miroshark             # deps + Neo4j + servers → http://localhost:3000
```

<p align="center">
  <a href="../docs/INSTALL.md"><img src="https://img.shields.io/badge/%F0%9F%93%96%20Full%20install-cloud%20·%20Docker%20·%20Ollama%20·%20Claude%20Code-8B5CF6?style=for-the-badge&labelColor=1a1a2e" alt="Full install guide"></a>
</p>

<br/><br/>

<h2 align="center">How it <em>works</em></h2>

<p align="center">
  <img src="../docs/images/miroshark-overview-diagram-v2.jpg" alt="MiroShark overview — information propagates through X (Twitter), herd effects form in Reddit and Polymarket, 100+ agent personas across 3 platforms drive cross-platform dynamics, and a ReAct report agent writes the recap. Five workflow steps." width="100%" />
</p>

<p align="center">
  <img src="../docs/images/simulation-phases-v2.jpg" alt="MiroShark five-phase pipeline: Phase 1 Ontology Generation, Phase 2 Graph Building, Phase 3 Agent Setup, Phase 4 Simulation Execution, Phase 5 Report and Interaction." width="100%" />
</p>

<br/><br/>

<h2 align="center">Grounded agents</h2>

<p align="center">Not roleplay. Every agent is grounded in five layers of real context.</p>

<p align="center">
  <img src="../docs/images/agent-grounding-v2.jpg" alt="Five layers of grounding per MiroShark agent: demographic seed, web enrichment, semantic search, relationships, and graph attributes." width="100%" />
</p>

<br/><br/>

<h2 align="center">Graph memory</h2>

<p align="center">
  <img src="../docs/images/graph-memory-pipeline-v2.jpg" alt="MiroShark graph-memory pipeline. Ingestion: NER, embed, entity resolution, contradiction check, temporal edges. Retrieval: vector plus BM25 plus BFS, fused and reranked." width="100%" />
</p>

<br/><br/>

<h2 align="center">What can you <em>simulate?</em></h2>

<!-- NEW IMAGE CARDS: one per use case, clickable → docs/FEATURES.md -->
<p align="center">
  <a href="../docs/FEATURES.md" title="PR crisis testing — simulate public reaction to a press release before you publish"><img src="../docs/images/usecase-pr-crisis.jpg" alt="PR crisis testing — simulate public reaction to a press release before publishing." width="70%"/></a>
</p>
<p align="center">
  <a href="../docs/FEATURES.md" title="Market reaction — feed financial news, watch simulated trader and investor sentiment move a prediction market"><img src="../docs/images/usecase-market.jpg" alt="Market reaction — feed financial news and observe simulated trader and investor sentiment on a live prediction market." width="70%"/></a>
</p>
<p align="center">
  <a href="../docs/FEATURES.md" title="Advertising — test a campaign, headline, or pitch against a simulated audience before you spend"><img src="../docs/images/usecase-ads.jpg" alt="Advertising — test a campaign, headline, or pitch against a simulated audience before spending." width="70%"/></a>
</p>
<p align="center">
  <a href="../docs/FEATURES.md" title="Policy analysis — test draft regulations against a simulated public"><img src="../docs/images/usecase-policy.jpg" alt="Policy analysis — test draft regulations against a simulated public." width="70%"/></a>
</p>
<p align="center">
  <a href="../docs/FEATURES.md" title="What-if history — rewrite a historical event and watch a population of personas re-narrate the aftermath"><img src="../docs/images/usecase-history.jpg" alt="What-if history — rewrite a historical event and see how a population of personas re-narrates the aftermath." width="70%"/></a>
</p>
<p align="center">
  <a href="../docs/FEATURES.md" title="Creative experiments — feed a novel with a lost ending and agents write a narratively consistent conclusion"><img src="../docs/images/usecase-creative.jpg" alt="Creative experiments — feed a novel with a lost ending; agents write a narratively consistent conclusion." width="70%"/></a>
</p>

<br/><br/>

<h2 align="center">Features</h2>

<!-- NEW IMAGE: feature-wall.jpg — the 8 marquee features as one glass-tile grid -->
<p align="center">
  <a href="../docs/FEATURES.md" title="See the full feature list and deep dives"><img src="../docs/images/feature-wall.jpg" alt="MiroShark marquee features: Smart Setup (doc → 3 Bull/Bear/Neutral scenarios in 2s), Just Ask (question with no doc → researched seed briefing), Counterfactual Branching (fork a running sim with an injected event), Director Mode (inject breaking news into the current timeline), Per-Agent MCP Tools (agents call real web search and APIs), Article Generation (Substack-style grounded write-up), Public Gallery and Verified Predictions, Share Everywhere (cards, replay GIFs, tweet threads, RSS, embeds, Slack/Discord/Telegram/webhooks)." width="100%"/></a>
</p>

<p align="center"><a href="../docs/FEATURES.md"><b>40+ features · full list and deep dives →</b></a></p>

<br/><br/>

<h2 align="center">Docs</h2>

<p align="center">
  <a href="../docs/INSTALL.md"><img src="https://img.shields.io/badge/Install-8B5CF6?style=flat-square&labelColor=1a1a2e" alt="Install"></a>
  <a href="../docs/CONFIGURATION.md"><img src="https://img.shields.io/badge/Configuration-8B5CF6?style=flat-square&labelColor=1a1a2e" alt="Configuration"></a>
  <a href="../docs/MODELS.md"><img src="https://img.shields.io/badge/Models-8B5CF6?style=flat-square&labelColor=1a1a2e" alt="Models"></a>
  <a href="../docs/ARCHITECTURE.md"><img src="https://img.shields.io/badge/Architecture-8B5CF6?style=flat-square&labelColor=1a1a2e" alt="Architecture"></a>
  <a href="../docs/API.md"><img src="https://img.shields.io/badge/HTTP%20API-8B5CF6?style=flat-square&labelColor=1a1a2e" alt="HTTP API"></a>
  <a href="../docs/CLI.md"><img src="https://img.shields.io/badge/CLI-8B5CF6?style=flat-square&labelColor=1a1a2e" alt="CLI"></a>
  <a href="../docs/MCP.md"><img src="https://img.shields.io/badge/MCP-8B5CF6?style=flat-square&labelColor=1a1a2e" alt="MCP"></a>
  <a href="../docs/WEBHOOKS.md"><img src="https://img.shields.io/badge/Webhooks-8B5CF6?style=flat-square&labelColor=1a1a2e" alt="Webhooks"></a>
  <a href="../docs/DKG.md"><img src="https://img.shields.io/badge/DKG%20citation-F97316?style=flat-square&labelColor=1a1a2e" alt="DKG citation"></a>
  <a href="../docs/WAYBACKCLAW.md"><img src="https://img.shields.io/badge/WaybackClaw-F97316?style=flat-square&labelColor=1a1a2e" alt="WaybackClaw archive"></a>
  <a href="../ECOSYSTEM.md"><img src="https://img.shields.io/badge/Ecosystem-16A534?style=flat-square&labelColor=1a1a2e" alt="Ecosystem"></a>
</p>

<br/><br/>

<h2 align="center">Community</h2>

<table width="100%" border="0" cellspacing="0" role="presentation">
  <tr>
    <td align="center" valign="middle" width="33%">
      <a href="https://x.com/miroshark_" title="Follow @miroshark_ on X"><img src="../docs/images/comm-x.jpg" alt="Follow @miroshark_ on X for launches, demos, and updates." width="100%"/></a>
    </td>
    <td align="center" valign="middle" width="33%">
      <a href="https://www.miroshark.xyz/docs" title="Read the MiroShark docs"><img src="../docs/images/comm-docs.jpg" alt="Read the MiroShark documentation." width="100%"/></a>
    </td>
    <td align="center" valign="middle" width="33%">
      <a href="https://bankr.bot/discover/0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3" title="$miroshark on Bankr"><img src="../docs/images/comm-bankr.jpg" alt="$miroshark token on Bankr." width="100%"/></a>
    </td>
  </tr>
</table>

<br/><br/>

<p align="center"><sub>AGPL-3.0 · Support the project: <code>0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3</code> 🦈</sub></p>
