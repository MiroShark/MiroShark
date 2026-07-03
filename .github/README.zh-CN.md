<p align="center">
  <img src="../docs/images/miroshark-logo.jpg" alt="MiroShark" width="120" />
</p>

<h1 align="center">MiroShark</h1>

<p align="center">
  <a href="https://github.com/aaronjmars/MiroShark/stargazers"><img src="https://img.shields.io/github/stars/aaronjmars/MiroShark?style=flat-square&logo=github" alt="GitHub stars"></a>
  <a href="https://github.com/aaronjmars/MiroShark/network/members"><img src="https://img.shields.io/github/forks/aaronjmars/MiroShark?style=flat-square&logo=github" alt="GitHub forks"></a>
  <a href="https://x.com/miroshark_"><img src="https://img.shields.io/badge/Follow-%40miroshark__-black?style=flat-square&logo=x&labelColor=000000" alt="Follow on X"></a>
  <a href="https://bankr.bot/discover/0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3"><img src="https://img.shields.io/badge/MiroShark%20on-Bankr-orange?style=flat-square&labelColor=1a1a2e" alt="MiroShark on Bankr"></a>
</p>

<p align="center">
  <a href="README.md">English</a> · <b>中文</b> · <a href="README.ja.md">日本語</a> · <a href="README.fr.md">Français</a>
</p>

<p align="center">
  <img src="../docs/images/miroshark-demo.gif" alt="MiroShark 演示" />
</p>

---

> **一切皆可模拟,只需 $1、不到 10 分钟。**
> 投入任何素材 — 新闻稿、头条、政策草案、一个无解的问题、一段历史假设 — MiroShark 都会派出数百个智能体,每小时一轮地做出反应:发帖、辩论、交易、改变想法。

<p align="center">
  <img src="../docs/images/simulate-anything-hero-v2.jpg" alt="一切皆可模拟 — 每次模拟 $1、10 分钟出首份结果、100 个智能体:输入 → 构建世界 → 群体 → 报告" width="100%" />
</p>

## 它做什么

- 你提供一个情景,MiroShark 围绕它构建世界。
- 数百个有据可依的智能体在 Twitter、Reddit 与预测市场上每小时一轮地做出反应。
- 与任意智能体对话。在运行中投入突发新闻。派生出反事实分支。
- 生成一份引用真实发帖与交易的复盘报告。

<p align="center">
  <img src="../docs/images/simulation-phases-v2.jpg" alt="MiroShark 流水线:阶段 1 本体生成 → 阶段 2 图谱构建 → 阶段 3 智能体配置 → 阶段 4 模拟执行 → 阶段 5 报告与交互" width="100%" />
</p>

## 快速开始

推荐路径:**一个 [OpenRouter](https://openrouter.ai/) 密钥 + `./miroshark` 启动器**。首次模拟约 10 分钟、约 $1。

**前置条件** — Python 3.11+、Node 18+、Neo4j,以及一个 [OpenRouter 密钥](https://openrouter.ai/)。

安装 Neo4j — 启动器会替你启动它:

- **macOS** — `brew install neo4j`
- **Linux** — `sudo apt install neo4j` *(或所在发行版对应的命令)*
- **Windows** — 安装 [Neo4j Desktop](https://neo4j.com/download/) *(原生 GUI — 先在其中启动数据库,然后通过 WSL2 或 Git Bash 运行启动器)*,或在 [WSL2](https://learn.microsoft.com/windows/wsl/install) 内运行整套环境并按 Linux 步骤操作
- **零安装** — 创建一个免费 [Neo4j Aura](https://neo4j.com/cloud/aura-free/) 云实例,在 `.env` 中将 `NEO4J_URI` / `NEO4J_PASSWORD` 指向它

然后:

```bash
git clone https://github.com/aaronjmars/MiroShark.git && cd MiroShark
cp .env.example .env
# 将你的 OpenRouter 密钥粘贴到 LLM_API_KEY / SMART_API_KEY /
# NER_API_KEY / OPENAI_API_KEY / EMBEDDING_API_KEY 五个字段
# (同一个密钥,粘 5 处)。默认组合是 Mimo V2.5 + Gemini 3 Flash。
./miroshark
```

启动器会检查依赖、启动 Neo4j、安装前后端,并在 `:3000` + `:5001` 提供服务。Ctrl+C 停止一切。打开 `http://localhost:3000` 并投入一份文档即可。

**其他路径** — [一键 Railway / Render 部署](../docs/INSTALL.zh-CN.md#一键云部署)、[Docker + Ollama](../docs/INSTALL.zh-CN.md#方案-b-docker--本地-ollama)、[手动 Ollama](../docs/INSTALL.zh-CN.md#方案-c-手动--本地-ollama)、[Claude Code CLI](../docs/INSTALL.zh-CN.md#方案-d-claude-code无需-api-密钥) — 全部见 **[docs/INSTALL.zh-CN.md](../docs/INSTALL.zh-CN.md)**。

<p align="center">
  <img src="../docs/images/miroshark-overview-cn-v2.jpg" alt="MiroShark 总览" />
</p>

## 界面语言

启动后,在导航栏右上角点击 **中 / EN** 切换按钮即可在中英文之间切换。语言选择保存在浏览器中,公开图库卡片的标题与描述也会随当前语言切换。

## 应用场景

- **公关危机演练** — 在新闻稿发布前模拟舆论反应
- **市场反应** — 喂入财经新闻,观察模拟交易者与投资者情绪
- **广告测试** — 在投放前用模拟受众检验文案、标题或卖点
- **政策分析** — 用模拟公众检验法规草案
- **人生抉择** — 把个人决定(换工作、搬家、上线时机)作为情景,看多元人设辩论
- **历史假设** — 改写一段历史事件,看一群人设如何重新叙述其后续
- **创意实验** — 喂入失去结尾的小说,智能体续写出叙事自洽的结局

<p align="center">
  <img src="../docs/images/agent-grounding-v2.jpg" alt="每个智能体的五层接地:人口学种子、网络补全、语义检索、关系、图谱属性" width="100%" />
</p>

## 主要功能

精选亮点:

| 功能 | 说明 |
|---|---|
| **智能配置** | 投入文档 → 约 2 秒生成三套自动情景(看涨 / 看跌 / 中立) |
| **直接提问** | 不用文档,直接打字提问 — MiroShark 自行调研并撰写种子简报 |
| **反事实分支** | 在运行中的模拟里派生分支并注入事件(「如果 24 轮时 CEO 辞职会怎样?」) |
| **导演模式** | 在当前时间线中投入突发新闻,无需派生分支 |
| **每个智能体的 MCP 工具** | 人设在模拟过程中调用真实 MCP 工具(网页搜索、API 等) |
| **文章生成** | Substack 风格的复盘文章,基于真实发帖与交易数据 |
| **公开图库与已验证预言** | 在 `/explore` 浏览并派生所有公开模拟;在 `/verified` 追踪命中的预言 |
| **全渠道分享** | 社交卡片、回放动图、推文串、RSS / Atom、嵌入,以及 Slack / Discord / Telegram / Webhook 通知 |

……以及 **40+ 项更多功能** — 分享表面、导出、集成、可观测性与链上引用。详见 **[完整功能列表与深入解析:docs/FEATURES.zh-CN.md](../docs/FEATURES.zh-CN.md)**。

<p align="center">
  <img src="../docs/images/graph-memory-pipeline-v2.jpg" alt="图谱记忆流水线:摄入(NER、嵌入、实体消歧、矛盾检测、时间边)与检索(向量 + BM25 + BFS 融合 + 重排)" width="100%" />
</p>

## 文档

| | |
|---|---|
| [安装](../docs/INSTALL.zh-CN.md) | 全部部署路径:云端、Docker、Ollama、Claude Code |
| [配置](../docs/CONFIGURATION.zh-CN.md) | 环境变量、模型路由、特性开关 |
| [模型](../docs/MODELS.zh-CN.md) | 云端预设、本地 Ollama 模型、基准发现 |
| [架构](../docs/ARCHITECTURE.zh-CN.md) | 模拟引擎、记忆管线、图谱检索 |
| [功能](../docs/FEATURES.zh-CN.md) | 上述功能表中每一项的深入解析 |
| [HTTP API](../docs/API.zh-CN.md) | 按关注点分组的全部端点 — 含 `/api/docs` 交互式 Swagger UI 与 `/api/openapi.yaml` 规范 |
| [CLI](../docs/CLI.zh-CN.md) | `miroshark-cli` 参考 |
| [MCP](../docs/MCP.zh-CN.md) | Claude Desktop / Cursor / Windsurf / Continue 集成 + 报告智能体工具(可在「设置 → AI 集成」中获取自动生成的片段) |
| [Webhook](../docs/WEBHOOKS.zh-CN.md) | 完成 Webhook 载荷、头部、投递语义、Slack / Discord / Zapier / n8n 食谱 |
| [DKG 引用](../docs/DKG.md) | OriginTrail DKG 锚定 — 任何已完成模拟的 UAL + Merkle 根 + 链上引用键 |
| [WaybackClaw 归档](../docs/WAYBACKCLAW.md) | WaybackClaw 提交 — 任何已完成模拟的快照 id + IPFS CID + Nostr 事件 id |
| [可观测性](../docs/OBSERVABILITY.zh-CN.md) | 调试面板、事件流、日志 |
| [生态](../ECOSYSTEM.md) | 基于 MiroShark 构建的项目、智能体与产品 |
| [贡献](CONTRIBUTING.zh-CN.md) | 测试与开发 |

---

## 许可证

AGPL-3.0,详见 [LICENSE](LICENSE)。

支持本项目:`0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3`

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=aaronjmars/miroshark&type=Date)](https://www.star-history.com/#aaronjmars/miroshark&Date)
