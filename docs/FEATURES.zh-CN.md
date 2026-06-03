<sup>[English](FEATURES.md) · 中文</sup>

# 特性

每个特性的深入介绍。一个特性一个标题,大致按你在一次典型运行中遇到它们的顺序排列。

## 功能速览

<sub>完整功能清单 — 每项功能在下方都有独立章节详述。</sub>

| 功能 | 说明 |
|---|---|
| **智能配置** | 投入文档 → 约 2 秒生成三套自动情景(看涨/看跌/中立) |
| **热门追踪** | 从 RSS 中挑选实时新闻,一键预填情景 |
| **直接提问** | 不用文档,直接打字提问 — MiroShark 自行调研并撰写种子简报 |
| **可分享情景链接** | 在推文或博客文章中放入 `?scenario=...&url=...` 链接 — 读者一打开就会看到已预填的「新建模拟」表单。`?template=<slug>` 可自动启动任一预设模板。这是 `/watch` 与 `/share` 上「派生此情景」的「未运行情景」对应版本 |
| **反事实分支** | 在运行中的模拟里派生分支并注入事件(「如果 24 轮时 CEO 辞职会怎样?」) |
| **导演模式** | 在当前时间线中投入突发新闻,无需派生分支 |
| **预设模板** | 6 套基准情景:加密代币发布、企业危机、政治辩论、产品发布、校园风波、历史假设 |
| **现实预言机** | 可选地从 [FeedOracle](https://mcp.feedoracle.io/mcp) MCP 中拉取实时数据(484 个工具) |
| **每个智能体的 MCP 工具** | 人设可在模拟过程中调用真实 MCP 工具(网页搜索、API 等) |
| **自定义 Wonderwall 端点** | 将模拟主循环指向任意 OpenAI 兼容端点(自部署 vLLM、Modal、微调模型……),不影响 Default/Smart/NER。设置 `WONDERWALL_BASE_URL` + `WONDERWALL_API_KEY` |
| **嵌入与发布** | 公开/私有切换 + 嵌入 URL,便于分享已完成的运行 |
| **社交分享卡片** | 1200×630 PNG,自动展开情景、状态、质量与信念分布,适配 Twitter/X、Discord、Slack、LinkedIn |
| **信念回放动图** | 1200×630 GIF,每轮一帧,信念条动态滑向各轮分布。Discord 与 Slack 在直接 URL 上自动播放 |
| **转录导出** | 每轮智能体发帖与立场标签,导出为 Markdown(YAML 头,适配 Notion / Obsidian / Substack)或结构化 JSON(适配 SDK 与 LLM 评审管线) |
| **轨迹导出** | 每轮一行,导出为 RFC 4180 CSV 或 JSONL — Pandas / Excel / Tableau / R / Observable 即取即用 |
| **轨迹图 SVG** | `chart.svg` 可缩放的信念图,供 Notion / Substack / Ghost / README 中 `<img>` 嵌入;纯标准库 |
| **交易信号 JSON** | `signal.json` 机器可读的 `direction` + `confidence_pct` + `risk_tier`,面向量化 / Zapier / 告警流水线 |
| **归档打包** | `archive.zip` 打包每一个分享面外加一份 SHA-256 `manifest.json`;纯标准库 |
| **Farcaster Frame** | 分享页发出 Frame v2 元标签,使 `/share/<id>` 在 Warpcast 中渲染为可交互的信念卡片 |
| **推文串导出** | `GET /api/simulation/<id>/thread.txt` — 自动生成 X / Twitter 推文串:介绍推文 + 每个信念转折点(主导立场翻转的轮次)一条推文 + 末尾推文(附观看与分享 URL)。每条推文 ≤280 字符,可单条复制或整串复制。与分享卡片 / 回放 GIF / 转录 / 轨迹 / 实时观看页一同构成第六种分享形式 |
| **实时观看页** | `/watch/<sim_id>` 全视口直播页,每 15 秒轮询信念 / 轮次 / 进度 |
| **公开图库** | `/explore` 以卡片网格浏览所有公开模拟 — 预览分享卡、共识分布与质量指标;一键打开或派生 |
| **图库搜索与筛选** | 在 `/explore` 与 `/verified` 上提供关键词搜索 + 看涨/中立/看跌 + 优秀/良好/一般/较差 + 按日期/轮次/智能体/热门排序。`trending` 按累计分享面服务次数排序,让被分发最广的模拟浮于顶部。URL 编码后 `?q=aave&consensus=bearish` 可作为书签分享。与其他所有表面共享同一 ±0.2 立场阈值 |
| **已验证预言** | 为公开模拟标注真实结果(命中 / 部分 / 失误 + 链接)。`/verified` 是命中预言专属展厅 |
| **RSS / Atom 订阅源** | `/api/feed.atom` + `/api/feed.rss` — 每个新发布的模拟无需任何整理就会进入 Feedly / Readwise / Inoreader / NetNewsWire / Obsidian RSS。`?verified=1` 只看已验证内容 |
| **搜索引擎站点地图** | 自动生成的 `/sitemap.xml`(sitemaps.org 0.9)列出每个公开模拟的 `/share/<id>` + `/watch/<id>` URL;配套的 `/robots.txt` 通过标准 `Sitemap:` 指令通告。在 Google Search Console 提交一次 — 每个新发布的模拟都将变得可被搜索。纯 stdlib `xml.etree.ElementTree`,可通过 `ENABLE_SITEMAP=false` 退出 |
| **文章生成** | Substack 风格的复盘文章,基于真实发帖与交易数据 |
| **互动网络** | 力导向智能体关系图,带回声室指标 |
| **人口分布** | 原型聚类(分析师 / 影响者 / 散户 / 旁观者……) |
| **质量诊断** | 单次运行的健康评分 — 参与度、连贯性、多样性、方差 |
| **历史数据库** | 搜索、克隆、导出或删除任一过往模拟 |
| **轨迹访谈** | 查看智能体回复背后的完整推理链,而不止是回复本身 |
| **推送通知** | 长耗时图谱 / 模拟 / 报告任务完成时的浏览器推送提醒 |
| **完成 Webhook** | 模拟一结束即 POST 一份 JSON 摘要 — 一个 URL 字段即可连通 Slack、Discord、Zapier、Make、n8n 或任意自定义端点 |
| **Discord 富嵌入** | 设置 `DISCORD_WEBHOOK_URL`,MiroShark 会在通用 Webhook 之外另行推送一份 Discord 原生 embed:按共识着色的边框、情景标题、信念百分比字段、分享卡缩略图、链接。运营者无需再为 Discord 写格式化代码 — 纯 stdlib,按需启用,fire-and-forget。详见 [NOTIFICATIONS.zh-CN.md](NOTIFICATIONS.zh-CN.md) |
| **Slack Block Kit** | 设置 `SLACK_WEBHOOK_URL`,MiroShark 会推送 Slack 原生 Block Kit 消息:情景标题块、Unicode 块字符信念百分比、质量 / 规模 / 结局字段、「打开模拟」操作按钮。频道里的不是 JSON 代码块,而是真正的频道卡片 — 纯 stdlib,按需启用,fire-and-forget |
| **SMTP 完成邮件通知** | 设置 `SMTP_HOST` 与 `SMTP_TO`(逗号分隔的收件人列表),每次模拟达到终止状态都会以 `multipart/alternative` 发出一封邮件 — 纯文本部分带 Unicode 块字符信念条,HTML 部分配合 Discord 同色系内联色块和按共识着色的「View simulation →」CTA。主题为 `[MiroShark] Bullish: <情景>`,邮箱过滤规则只看主题就能按方向分流。`SMTP_USER`/`SMTP_PASSWORD` 可选(支持无认证 LAN 中继),587 端口尝试 STARTTLS,STARTTLS 失败时若设置了凭据会拒绝明文发送。这是唯一一个不需要任何平台账户的通知通道 — 每位运营者都已经有邮箱。详见 [NOTIFICATIONS.zh-CN.md](NOTIFICATIONS.zh-CN.md) |
| **Telegram Bot 通知** | 设置 `TELEGRAM_BOT_TOKEN`(向 `@BotFather` 申请)和 `TELEGRAM_CHAT_ID`,每次模拟达到终止状态都会调用 Bot API `sendMessage`,以 HTML parse mode 渲染:加粗的情景标题、Unicode 块字符信念百分比、质量 / 规模 / 结局字段,以及一颗「View simulation」内联键盘按钮。覆盖 MiroShark 大量加密 / 政治辩论受众日常所在的即时通讯阵地。纯 stdlib,按需启用,fire-and-forget。详见 [NOTIFICATIONS.zh-CN.md](NOTIFICATIONS.zh-CN.md) |
| **Webhook 签名验证** | 可选的 `WEBHOOK_SECRET` 会用 HMAC 对每次投递的载荷签名,并通过 `X-MiroShark-Signature: sha256=<hex>` 头部送出。消费方用三行 stdlib `hmac` 即可校验 — Stripe 和 GitHub 用的就是这一套。留空即无签名头部,完全向后兼容 |
| **Webhook 投递日志** | 每个模拟在 `webhook-log.jsonl` 记录每次投递尝试(HTTP 状态码、延迟、错误)。可在 EmbedDialog 中查看,并通过「重试」按钮重发任何失败的投递 — 弥补每个 Zapier / n8n 集成最终都会遇到的运维盲点 |
| **分发统计(分享面使用分析)** | `GET /api/simulation/<id>/surface-stats` — 每个分享面的请求计数器(分享卡 / 回放 GIF / 转录 / 轨迹 / 推文串 / 观看页 / Atom / RSS / `reproduce.json` / `/lineage`),以及合成的 `total`。Webhook 日志在出站侧跟踪分发回路,本面则负责入站可观测性 |
| **可复现配置导出** | `GET /api/simulation/<id>/reproduce.json` — 分享面背后的引用基元。v1-schema 的 JSON 文档,携带另一位研究者复现同一次模拟所需的全部参数:情景、智能体数、轮次、平台切换、时序配置、导演事件、派生 / 反事实谱系。已完成模拟的多次导出在字节级别完全一致 — 文件哈希可作为稳定的引用键 |
| **Jupyter Notebook 导出** | `notebook.ipynb` 内嵌轨迹 CSV + 绘图单元;可离线运行,字节级稳定 |
| **谱系导航** | `GET /api/simulation/<id>/lineage` — 将 `parent_simulation_id` 指针转化为可导航的图。展示该模拟派生 / 分支自的父模拟,以及每一个把父级指回此模拟的公开子模拟。无需记住每个子模拟 ID,即可追踪一项结果的思想脉络 |
| **OriginTrail DKG 引用** | 可选:将情景、共识与 `reproduce.json` 的 SHA-256 锚定到 OriginTrail DKG,成为可验证的知识资产 |
| **WaybackClaw 归档** | 可选:把已完成的快照固定到 IPFS,并通过 WaybackClaw 在一次 POST 中广播一条 Nostr note |
| **生态系统 JSON 注册表** | `GET /api/ecosystem.json` — 在 MiroShark 之上构建的每一个外部项目、智能体与产品的机器可读名单;按字母排序、带分类、ETag 缓存 |

## 智能配置(情景自动建议)

模拟提示词输入框是上传文档与开始模拟之间唯一的"白纸难题"。智能配置把它移除:你刚把一个 `.md`/`.txt` 文件拖进来或者贴上一个 URL,MiroShark 就会把抽取出来的文本短预览(约 2K 字符)发给已配置的 LLM,大约 2 秒后返回三张预测市场风格的情景卡片 — 一张 **看涨**、一张 **看跌**、一张 **中立** 框架,每张都带一个具体的 YES/NO 问题、一个合理的初始概率区间,以及一句基于文档的简短理由。

点击任一卡片上的 **使用此项 →** 就能填进模拟提示词字段,或者忽略它们自己输入。建议会按文档缓存(预览的 SHA-256),所以离开页面再回来不会再一次调用 LLM。如果 LLM 调用失败或超时,这个面板会静默不显示 — 你输入的情景仍然完全可用。

- **端点:** `POST /api/simulation/suggest-scenarios`

## 热门(自动发现)

智能配置照顾的是带着文档来的用户。"热门"照顾的是另一半 — 想模拟点和 AI、加密、或地缘相关的*某事*,但手头没有具体文章的人。该面板位于 URL 导入框下方,展示一份可配置的公共 RSS/Atom 源中最新的 5 条目(默认:Reuters tech、The Verge、Hacker News、CoinDesk)。

点击任意卡片,MiroShark 会预填 URL 字段、抓取文章,并立刻基于抓取到的文本触发情景自动建议 — 一键就能从白纸到三张情景卡。运维者可以用 `TRENDING_FEEDS` 环境变量(逗号分隔的 URL)覆盖默认订阅列表。服务端缓存保留结果 15 分钟;如果所有源都报错,该面板会静默消失。

- **端点:** `GET /api/simulation/trending`

## 直接提问(纯问题模式)

没有文档,也没有特定文章在脑子里?在主页输入一个问题("欧盟 AI 法案的生物特征条款会在最终三方会谈中存活吗?"),MiroShark 会让 Smart 模型调研这一话题,并合成一段 1500–3000 字符的简报 — 中立、按 上下文 / 关键角色 / 近期事件 / 待解问题 结构组织。该简报作为 `miroshark://ask/...` 的种子文档进入 URL 列表并预填模拟提示词,这样下游流水线(本体 → 图谱 → 画像 → 模拟)按原样跑。每个问题缓存以便快速重跑。

- **端点:** `POST /api/simulation/ask`

## 可分享情景链接

之前的所有分享表面(`/share/<id>`、`/watch/<id>`、回放 GIF、转录、RSS、轨迹 CSV、画廊搜索)都把读者指向一次*已完成的*模拟。可分享情景链接覆盖了另一半 — *尚未运行的*情景。在推文、博客文章或 Discord 消息中放入这样一个 URL,读者就会落在已预填情景的「新建模拟」表单上,只差一键即可启动他们自己的运行,使用完全相同的设置。

该 URL 接受四个可选查询参数,每个都可独立使用:

| 参数 | 作用 | 上限 |
|---|---|---|
| `scenario` | 预填模拟提示词文本框 | 500 字符 |
| `url` | 自动抓取到 URL 导入列表(必须以 `http://` 或 `https://` 开头) | 2000 字符 |
| `ask` | 预填「直接提问」问题字段 — *不会*自动运行(避免意外的 LLM 费用) | 300 字符 |
| `template` | 自动启动指定的预设模板(完全跳过主页) | 仅限 slug |

任意组合都可以使用。`?scenario=模拟稳定币脱锚&url=https://example.com/incident-report` 会同时预填提示词*并且*在同一流程中抓取该文章。`?template=corporate_crisis` 直接跳到模板启动路径。当预填发生时,控制台上方会出现一条可关闭的橙色边线提示横幅,这样操作者在按下「启动」之前就知道表单是由分享链接填入的。

输入在读取时会经过净化 — HTML / `javascript:` URI / 控制字符会被剥除,长度上限避免兆字节级的载荷,`url=` 必须以 `http://` 或 `https://` 起头才会被接受。一旦表单填好,URL 参数会通过 `router.replace` 被剥除,这样刷新页面不会重放预填,从地址栏复制时反映的是用户编辑后的状态,而不是最初的分享链接。

反向方向住在两个地方。在主页,模拟提示词文本框下方有一个低调的 **🔗 分享为链接** 按钮 — 它会基于当前表单状态构造一个 `?scenario=...&url=...&ask=...` URL 并复制到剪贴板,是 `/watch` 与 `/share` 页面上 **派生此情景** 按钮的「未运行情景」对应版本。每张预设模板卡片上,启动按钮旁还有一个小 **🔗** 图标,点击即可复制一个 `?template=<slug>` URL — Aaron 的「试试这个模拟」推文也能拥有一键 CTA,直接把读者送入对应模板的启动流程。

纯前端实现;无后端改动。净化逻辑住在 `frontend/src/utils/urlParams.js` 中(由 DOMPurify 兜底),`/` 上的读取路径与主页 + 模板画廊上的写入路径都复用同一份。

## 反事实分支

跑完一次模拟,暂停查看,然后问:"如果 CEO 在第 24 轮辞职会怎样?" — 在模拟工作区点击 **⤷ 分支**,输入触发轮次和一段突发新闻注入,MiroShark 就会把模拟分叉一份,带着父级的全部智能体人群。当 runner 到达触发轮次时,该注入会被提升为一次导演事件,并以 BREAKING 区块的形式预置到每个智能体的观察提示词。可以用现有的 **对比** 视图把分支与原始版本并排比较。

预设模板可以声明 `counterfactual_branches`(例如 `ceo_resigns`、`class_action`、`rug_pull`、`sec_notice`),这样分支对话框会提供一键情景。

- **端点:** `POST /api/simulation/branch-counterfactual`

## 导演模式(实时事件注入)

分支会分叉出新的时间线;导演模式则编辑*当前*这一条。模拟运行期间,可以注入一条突发新闻事件,会落到每个智能体下一次观察提示词中 — 不分叉、不重启。适合在不消耗一次完整分支的算力下,对一个情景做压力测试("竞争对手开源了他们的模型"、"SEC 刚刚立案调查")。

每次模拟最多 10 条事件,每条最多 500 字符。UI 控件就在 run-status 头部旁边。事件随模拟状态一同持久化,并在单轮帧 API 中回放,所以它们也会出现在导出和嵌入中。

- **端点:** `POST /api/simulation/<id>/director/inject`、`GET /api/simulation/<id>/director/events`

## 预设模板

`backend/app/preset_templates/` 中自带六个经过基准的情景模板 — 一键起步点,会预填种子文档、模拟提示词、智能体组成,以及(可选的)`counterfactual_branches` 与 `oracle_tools`:

| 模板 | 这次运行的形态 |
|---|---|
| `crypto_launch` | 代币 / 协议发布 — 分析师、散户、KOL、交易者对 TGE 的反应 |
| `corporate_crisis` | 企业事件(数据泄露、产品故障、高管丑闻),媒体 + 市场参与 |
| `political_debate` | 政策 / 选举议题,意识形态光谱与媒体回路 |
| `product_announcement` | 主题演讲 / 功能发布 — 评测周期、开发者反馈、消费者上手 |
| `campus_controversy` | 学生 / 教职 / 行政围绕一起争议事件的互动 |
| `historical_whatif` | 反事实历史 — "如果事件 X 没有发生会怎样?" |

可以在配置页面的 **Templates** 画廊中浏览,或者调用 `GET /api/templates/list`。用 `GET /api/templates/<id>` 获取单个模板;附加 `?enrich=true` 会在返回前对所有声明的 `oracle_tools` 实时求值 FeedOracle。

## 实时 Oracle 数据(FeedOracle MCP)

可选启用 [FeedOracle MCP server](https://mcp.feedoracle.io/mcp) 提供的接地种子数据(484 个工具,覆盖 MiCA 合规、DORA 评估、宏观/FRED 数据、DEX 流动性、制裁、碳市场等)。模板声明它们想用的工具:

```json
"oracle_tools": [
  {"server": "feedoracle_core", "tool": "peg_deviation", "args": {"token_symbol": "USDT"}},
  {"server": "feedoracle_core", "tool": "macro_risk",    "args": {}}
]
```

把 `.env` 里的 `ORACLE_SEED_ENABLED=true`,在任意模板卡上勾选 **使用实时 oracle 数据**,MiroShark 就会派发这些调用,并在摄入前把结果以一个 markdown "Oracle Evidence" 区块附加到种子文档。禁用或调用失败时静默 no-op — 静态种子仍然能用。

## 单智能体 MCP 工具

可选启用,OpenMiro 风格:挑选出来的人设(记者、分析师、交易者)可以在模拟期间调用真实的 MCP 工具。在人设的 profile JSON 中标记 `"tools_enabled": true`,在 `config/mcp_servers.yaml` 配置服务器,并设置 `MCP_AGENT_TOOLS_ENABLED=true`。

每一轮 runner 会:

1. **注入**工具目录到智能体的系统消息(用标记分隔,这样每轮会刷新)。
2. **解析**智能体帖子里类似 `<mcp_call server="web_search" tool="search" args='{"q":"..."}' />` 的自闭合标签(每回合最多 2 次调用)。
3. 通过每个 server 一个的池化 stdio 子进程**派发**它们(每次模拟一个进程,反复复用)。
4. **把结果注入**回智能体的下一轮系统消息。

调用失败会变成 `{"_error": "..."}` 形式的 payload,而不是抛异常 — 智能体提示词保持良好结构。这座桥每次调用有 30 秒的超时(`MCP_CALL_TIMEOUT_SEC`),并在模拟结束时(或异常退出时通过 `atexit`)拆掉子进程。

## 人口学接地(Nemotron 锚定人设)

图谱接地的人设给每个智能体一个真实世界的*叙事*锚点 — 记者这个角色可以回溯到文档里的某个记者实体。人口学接地在此之上再加一个*人口学*锚点:当 `DEMOGRAPHICS_COUNTRY` 被设为某个已注册的国家代码(`sg`、`us`、……)时,人设生成器会从对应的 NVIDIA **Nemotron-Personas** parquet 数据集中为每个智能体抽取一行,并把它作为一个 `DEMOGRAPHIC ANCHOR` 块,与图谱上下文一起喂给 LLM。

最终得到的智能体仍由 LLM 撰写、仍接地于文档中的各种关系,但其年龄、性别、地域、职业、教育和行业则来自一行类似人口普查的数据,而非模型的默认值。对于组织类实体,同一行数据会被重新表述为 `AUDIENCE ANCHOR`,从而在让机构声音保持完整的同时,把语气本地化到目标人口群体。

国家包是 `backend/app/countries/` 下的 JSON 文件(默认随附新加坡和美国)。每个包声明 HuggingFace repo id、地域字段(`planning_area`、`state`)、合法取值,以及命名的地域分组(`north-east`、`west`、……)。要添加新国家,只需往该目录里丢一个新的 JSON 文件 — 无需改代码。

该功能纯属增量:环境变量为空 → 行为不变。缺少 `duckdb`/`huggingface_hub` 依赖 → 静默跳过。样本覆盖不完整 → 前 N 个智能体获得种子,其余使用仅图谱生成。

- **端点:** `GET /api/countries`、`GET /api/countries/<code>`
- **详情:** [DEMOGRAPHICS.zh-CN.md](DEMOGRAPHICS.zh-CN.md)

## 自定义 Wonderwall 端点

模拟循环是 MiroShark 中最重的模型消费者 — 每次运行 850–1650 次调用,7M+ tokens,全部走 CAMEL-AI 单智能体动作循环。Wonderwall 槽位有自己独立的 `WONDERWALL_BASE_URL` + `WONDERWALL_API_KEY` 环境变量(以及 **设置 → 高级 → Wonderwall** 中对应的输入),所以你可以把这些高频调用路由到任意 OpenAI 兼容端点,而不用动 Default/Smart/NER 槽位 — 把图谱构建、报告和实体抽取留在 OpenRouter/Anthropic,智能体那边则可以指向自部署的 vLLM、Modal/Replicate 部署、另一块 GPU 上的 Ollama 实例,或者你自己训的微调。

两个字段都可以独立省略。`WONDERWALL_BASE_URL` 留空就继承 `LLM_BASE_URL`;`WONDERWALL_API_KEY` 留空就继承 `LLM_API_KEY`。开放式端点(无鉴权)只要传一个非空占位符例如 `not-checked` 即可。

```bash
WONDERWALL_BASE_URL=https://your-endpoint.example.com/v1
WONDERWALL_API_KEY=not-checked
WONDERWALL_MODEL_NAME=your-model-id
```

接线在三个地方:(1) `backend/scripts/run_parallel_simulation.py`(以及 twitter / reddit 变体)在子进程启动读取环境时,会优先选 `WONDERWALL_*` 而非 `LLM_*`。(2) `backend/app/services/simulation_runner.py` 在 spawn 子进程时把 `Config.WONDERWALL_*` 转发到子进程 `env`,所以设置 UI 的更新无需重启 Flask 就能在下一次运行生效。(3) Settings API(`POST /api/settings`)以及 `SettingsPanel.vue` 中对应的部分接受这三个字段。

适用场景:
- Wonderwall 角色/人设提示词在你自己训过的微调上效果更好。
- 你想把成本绑定到一台固定费率的自部署 GPU,而不是按 token 计费。
- 你想通过保持除 Wonderwall 之外所有槽位不变的两次匹配模拟,来对比一个自定义小模型的信念漂移 / 连贯性 与一个托管基线之间的差异。

## 发布以供嵌入

`EmbedDialog` 上有一个 `公开 / 私有` 切换,背后由模拟状态上的 `is_public` 支撑。未发布的模拟在嵌入 URL 上返回 `403` — 把切换打开(或调用 `POST /api/simulation/<id>/publish`)就能让它们公开嵌入。默认私有,这样不会影响已有模拟。

## 预测准确度账本(已验证预测)

每个公开模拟都可以被打上它所做出预测的真实结果注解。从嵌入对话框选择 **预测正确 / 部分正确 / 预测错误**,粘贴证实结果的文章 / 推文 / dashboard URL,加一句话总结(≤280 字符)然后提交。该注解落到 `<sim_dir>/outcome.json`,并立即体现在以下位置:

- 画廊卡片上的 **📍 已验证** / **⚠ 预测错误** / **◑ 部分正确** 标签(若提供了 outcome URL,标签会直接跳到该链接)。
- 卡片左缘的彩色装饰条,这样在快速翻看时已验证墙能一眼读出来。
- `/explore` 上的 **仅看已验证** 过滤芯片,会把列表切到这套精选集合。
- 一个专门的 **`/verified`** URL — 与 `/explore` 同一组件但预过滤为准确预测墙。把这个链接丢进推文串里就有一页可以证明模拟是有效的。

这个注解故意做成开放式的 — 与二元的 `/resolve` 端点不同,后者是 YES/NO,且与 Polymarket 共识绑定。一次模拟可以两者都有:二元结算驱动现有的 accuracy_score,outcome 注解驱动画廊上的可信度展示面。

- **端点:** `POST /api/simulation/<id>/outcome`(受发布控制)、`GET /api/simulation/<id>/outcome`(只读,无控制)、`GET /api/simulation/public?verified=1`(过滤后的画廊)。
- **UI:** 嵌入对话框内的"标记结果"面板;`/explore` 上的 **仅看已验证** 过滤芯片 + 📍 标签;专门的 `/verified` 路由。

## 社交分享卡

模拟一旦发布,嵌入对话框还会暴露一张 **社交卡片**,可以被 Twitter/X、Discord、Slack、LinkedIn 以及任何支持 Open-Graph 的客户端自动展开。它由两个端点支撑:

- `GET /api/simulation/<id>/share-card.png` — 服务端渲染的 1200×630 PNG(Pillow)。展示情景标题、状态标签、可选的质量徽章 + 结算、智能体 / 轮次 指标,以及最终 看涨/中立/看跌 分布的堆叠条。与嵌入小部件相同的 `is_public` 控制。按内容哈希在磁盘上缓存,这样反复 unfurl 不会重复渲染。
- `GET /share/<id>` — 一张携带正确 `og:image` / `twitter:image` 元标签的公开落地页。爬虫读标签渲染卡片;真实浏览器跳转到 SPA 模拟视图(JS 优先,带 `<meta http-equiv="refresh">` 兜底)。

把 `/share/<id>` URL 贴到任何地方 — 帖子会以一张精致的卡片展开,而不是通用预览。

## 信念回放动图(GIF)

与分享卡同一画布(1200×630),但每轮一帧 — 看涨 / 中立 / 看跌 三条柱在每轮的分布之间滑动,配一个轮次计数器和进度条。Discord 和 Slack 会从直接文件 URL 自动播放 GIF,所以把链接丢进频道就能内联渲染动画。

- `GET /api/simulation/<id>/replay.gif` — 服务端渲染的动画 GIF(Pillow,无需 FFmpeg)。每帧持续 600 ms,最后一帧持续 3 倍长度,这样静止的共识就像点睛之笔。超过 60 轮的轨迹在整段运行上均匀子采样,且一定保留最后一帧。与分享卡相同的 `is_public` 控制。按内容哈希在磁盘上缓存。

嵌入对话框会渲染一张暂停的缩略图,带"点击播放"的提示(这样打开对话框时不会让每个观看者都拉一份 GIF),并暴露一个可复制的 URL 加上一个"下载 GIF"按钮,放在分享卡那行下方。

## 模拟转录导出

它是分享卡(预览)和回放 GIF(动态)的文本同伴 — 把同一次模拟做成一份可引用的逐轮智能体轨迹,这样研究论文、Substack 帖子、Discord 串可以直接引用智能体说过的话,而不必截图。

两个端点,同一份载荷,不同编码:

- `GET /api/simulation/<id>/transcript.md` — 带 YAML 前言区块(`sim_id`、`scenario`、`agent_count`、`total_rounds`、`consensus_label`、`quality_health`、`outcome_label`)的 Markdown。Notion、Obsidian、Bear、Substack 会把它当成页面元数据来读;正文按已记录的轮次,每个轮次一个 `## Round N` 段,每个智能体的帖子作为一段引用块,并用智能体的立场打标。超过约 80 轮的轨迹在 Markdown 渲染中省略中间轮次(并附一条注释指向 JSON 形式以获取完整序列),让文档保持可读。
- `GET /api/simulation/<id>/transcript.json` — 同一份载荷的结构化 JSON 文档,美化输出(`indent=2`),这样 `curl` 到一个文件就能立刻可读。面向 SDK 用户和下游流水线(LLM-as-judge 评测框架、Python 客户端 SDK 等)。

两个端点共享分享卡的发布控制(`is_public=true`)。每个智能体的立场标签使用与其他界面一致的 ±0.2 阈值 — 画廊上的"看涨"智能体在轨迹里也会打同样的 tag。嵌入对话框在回放 GIF 那行下方暴露"下载 .md" + "下载 .json"组合。

## 信念轨迹导出(CSV / JSONL)

继分享卡(预览)、回放 GIF(动态)、转录 Markdown(文字)和转录 JSON(SDK)之后的第五个分享面。前四个覆盖的是一次模拟的*定性*解读;轨迹 CSV / JSONL 覆盖的则是*定量*那一面 — 量化研究员粘进 notebook、用来计算方差、自相关或在多个复现之间作对比的、每轮一行的表格。

两个端点,同一行 schema,不同的序列化:

- `GET /api/simulation/<id>/trajectory.csv` — RFC 4180 CSV,每记录一轮一行。列顺序锁定:`round, round_timestamp, bullish_pct, neutral_pct, bearish_pct, participating_agents, total_posts, total_engagements, quality_health, participation_rate`。`pandas.read_csv("…/trajectory.csv")`、Excel「Get Data → From Web」、Tableau Web Data Connector、R 的 `read.csv()` 以及 Observable 的 `d3.csv()` 都能原生消费它。即便轨迹为空,CSV 也会发出表头行,这样下游消费者就不必为零行文件做特殊处理。
- `GET /api/simulation/<id>/trajectory.jsonl` — JSON Lines(换行分隔的 JSON),每行一个对象,字段形状与 CSV 行相同。这种格式可被 `pandas.read_json(lines=True)`、DuckDB 的 `read_json_auto` 以及流处理管线(Kafka、Beam、Materialize)原生消费,无需 CSV 到 DataFrame 的转换。空输入产出零字节 — 良构的 JSONL 没有表头这一概念。

与分享卡和转录相同的发布门控(`is_public=true`)。看涨 / 中立 / 看跌的百分比使用与其他每个分享面相同的 ±0.2 立场阈值,因此 CSV 里的某个数字与图库、分享卡、回放 GIF、转录、webhook 和信息流为同一轮所报的数字一致。嵌入对话框在转录那一行下方暴露了一对「Download .csv」+「Download .jsonl」,外加一个可复制的 CSV URL 和一段 `pd.read_csv("<url>")` 快速上手代码片段。

## Farcaster Frame v2

链上受众分享面。`$MIROSHARK` 落在 Base 上;Base 原生的社交层是 Farcaster / Warpcast。在此功能之前,当某个代币持有者、研究员或运维者把一个 `/share/<id>` URL 粘进 Farcaster cast 时,该 cast 会渲染成一张空白的链接卡片 — 其他每种粘贴场景(Twitter/X、Discord、Slack、LinkedIn、iMessage、Notion、Ghost、Substack)都能从既有的 Open Graph 块获得丰富展开,而 Farcaster 却什么都看不到,因为该规范使用它自己的 `fc:frame:*` meta 标签 schema。

分享页的 `<head>` 现在会在既有的 Open Graph / Twitter 标签之外再发出一个 Frame v2 块。`fc:frame:image` 指向逐轮信念轨迹图表 SVG(就是分享对话框在 `📈 Trajectory chart (SVG)` 下暴露的那一张),因此 cast 预览会以 2:1 的纵横比展示真实的看涨 / 中立 / 看跌曲线 — 在 Warpcast 信息流里无需展开就能读。一个单独的 `View Simulation →` 链接按钮让读者一次点击就抵达 SPA 分享落地页。尚未记录任何轮次的模拟会回退到 1.91:1 的分享卡 PNG,这样一个刚发布的模拟在轨迹累积期间仍能获得一份 Farcaster 就绪的展开。

后端纯标准库(`xml.etree.ElementTree` 本就驱动着图表 SVG;Frame 逻辑本身只是 `app/services/frame_metadata.py` 里的 dict 拼装 + meta 标签模板化)。零新增依赖 — 与 PR #82(sitemap)、PR #80(notebook)、PR #79(HMAC)、PR #85(chart SVG)同样的姿态。私有模拟会完全抑制 Frame 标签注入,因此对于运维者尚未明确发布的模拟,情景标题绝不会泄漏进某个 cast。

EmbedDialog 暴露了一个 `🟣 Farcaster Frame` 区段:一份惰性加载的 Frame 图像预览、一个预填了分享 URL 的 Warpcast composer 链接(让运维者在 cast 之前先预览 Frame 卡片),以及一个可复制、随时能粘进任意 Farcaster 客户端(Warpcast、Supercast、Coinbase Wallet 里的钱包内 Frame)的分享 URL。`frame-metadata` JSON 端点之所以存在,是为了让对话框能在不硬编码主机名的情况下构建 Warpcast 编辑链接,也为了让未来的 Frame 动作按钮(post 动作、mint 流程)可以通过后端配置添加,而非重新部署 HTML。

- **Frame meta 标签:** `fc:frame`、`fc:frame:image`、`fc:frame:image:aspect_ratio`、`fc:frame:button:1`、`fc:frame:button:1:action`、`fc:frame:button:1:target` — 对已发布的模拟由 `GET /share/<id>` 发出,对私有模拟则静默缺席。
- **端点:** `GET /api/simulation/<id>/frame-metadata` → `{frame_version, image_url, image_aspect_ratio, share_url, buttons, has_trajectory, sim_title}`。与图表 SVG 相同的发布门控 — 未发布的模拟返回 403,尚无轨迹的模拟返回 200 并附带分享卡回退。

## oEmbed 自动展开(Notion / Ghost / Substack / WordPress)

写作平台分发分享面。Open Graph 和 Twitter 标签覆盖了社交平台;Farcaster Frame v2 覆盖了 Warpcast。但研究员和分析师真正*发布*内容的平台 — Notion、Ghost、Substack、WordPress — 并不单靠 Open Graph 渲染;它们实现了 [oEmbed 1.0 规范](https://oembed.com),会去寻找一个发现用的 `<link>` 标签,然后回调到提供方以取得结构化的嵌入载荷。没有它,一个 MiroShark 链接粘进 Notion 页面或 Substack 草稿就会渲染成一条裸 URL。

`GET /oembed?url=<share-url>` 就是那个提供方。分享页的 `<head>` 现在会为已发布的模拟发出两个发现标签 — `<link rel="alternate" type="application/json+oembed">` 和 `text/xml+oembed` 变体(某些消费者,Notion 便是其一,会去探测 XML 链接) —  两者都指向挂载在根路径的 `/oembed` 端点。找到该标签的消费者会带着分享 URL 回调,并收到一份 `type: "rich"` 的载荷:1200×630 的分享卡 PNG 作为 `thumbnail_url`,以及一个套在既有 `/embed/<id>` SPA 路由之上的 800×500 iframe 作为 `html`。每一次自发的引用都变成一张丰富的预览卡,无需用户任何操作。

oEmbed 添加的是一套*协议*,而非一个渲染器 — 缩略图和 iframe 都指向本就发布了的分享面。后端纯标准库(`app/services/oembed_service.py` 里的 `re` + `urllib.parse` + `xml.etree.ElementTree`),零新增依赖。该端点从不解引用传入的 URL;它只从本部署所拥有的主机上的某个路径里提取一个 sim id,因此一个外域的 `url` 会返回 `404`,这个分享面也无法被指向另一个站点。私有和不存在的模拟同样返回 `404`(两者彼此无法区分),因此该端点绝不会确认某个私有模拟存在 — 与 OG / Frame 标签相同的门控姿态。

- **端点:** `GET /oembed?url=<share-url>&format=<json|xml>` → oEmbed `rich` 载荷。`format` 默认为 `json`;不受支持的格式按规范返回 `501`。挂载在根路径(无 `/api` 前缀)。遵循 `X-Forwarded-Proto` / `X-Forwarded-Host`。
- **发现标签:** `GET /share/<id>` 为已发布的模拟发出 `application/json+oembed` + `text/xml+oembed` 的 `<link>` 标签,对私有模拟则静默缺席。
- **计数器:** `oembed` 键加入了分享面统计 schema,这样运维者就能看到该端点驱动了多少次第三方展开。

## 轨迹图 SVG

轨迹 CSV / JSONL 数据导出的可缩放矢量伴侣。CSV 把原始数字交给 Pandas / Excel / Tableau / R,而 `GET /api/simulation/<id>/chart.svg` 则给所有其他平台一张现成的信念历程图像 — 看涨(`#22c55e`)、中立(`#6b7280`)、看跌(`#ef4444`)三条折线以轮次编号为横轴绘制在固定的 `viewBox="0 0 800 400"` 上,配有 5 条线的 y 轴网格、轮次编号 x 轴标签、三色样本图例,以及情景标题。

纯标准库 `xml.etree.ElementTree` 渲染器 — 无需 Cairo,无需 matplotlib,无需 Pillow,零新增依赖。与 sitemap(PR #82)和 Jupyter notebook(PR #80)采用相同的思路。输出是逐字节确定性的,因此字节哈希可以充当缓存键,就像 reproduce.json 哈希充当引用键一样。

凡是 `<img>` 能渲染的地方都可嵌入 — Notion、Substack、Ghost、GitHub README、LinkedIn 帖子、带图片附件的 Discord 嵌入,以及通过 `\includesvg{}` 嵌入的 LaTeX 论文。矢量意味着 5K 显示器上的读者看到的是清晰锐利的线条,而手机上的读者看到的是同一张图缩小后依然不丢失坐标轴标签的版本。`<img>` 意味着嵌入站点无需 JavaScript — 图表会像任何其他静态资源一样随页面加载。

与轨迹 CSV 采用相同的发布门控。当模拟尚未记录任何轮次时返回 `404`(嵌入站点可以渲染自己的占位符,而不是一张看起来像样式 bug 的空白 SVG)。嵌入对话框在轨迹 CSV 行下方暴露一个 `📈 Trajectory chart (SVG)` 区块:一个懒加载预览、一个「Download .svg」锚点、一个可复制的 URL,以及一段可直接粘贴的 `<img>` 嵌入代码片段。chart-svg 计数器加入分发统计 schema,这样运营者就能看到图表独立于分享卡片和重放 GIF 之外驱动了多少次嵌入。

## 交易信号 JSON

坐落于数据导出栈之上的动作原语。此前的各个分享面(轨迹 CSV、轨迹 JSONL、图表 SVG、文字记录、notebook、reproduce.json)描述的是*发生了什么*;`GET /api/simulation/<id>/signal.json` 则把同一批最终状态数字浓缩成单独一行,供量化工具、告警流水线,或 Zapier / Make / n8n 工作流直接消费。

返回一个稳定的 v1-schema JSON 文档:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "direction": "Bullish",
  "confidence_pct": 43.4,
  "risk_tier": "low-risk",
  "bullish_pct": 62.3,
  "neutral_pct": 17.7,
  "bearish_pct": 20.0,
  "quality_health": "excellent",
  "signal_generated_at": "2026-05-19T12:34:56Z"
}
```

- **`direction`** — `Bullish` / `Neutral` / `Bearish`,取自最终轮次信念分布中占多数的立场。平局的决胜顺序有文档记载且稳定:`bullish > bearish > neutral`,这样即便在罕见的均分轮次中,消费方也能预测输出。
- **`confidence_pct`** — 领先立场距离三向噪声底线有多远。`(leading_pct - 33.333) / 66.667 * 100`,钳制到 `[0, 100]` 并四舍五入到一位小数。33.3% 的领先立场为 0(纯均分);100% 的领先立场为 100(全体一致);66.7% 的领先立场约为 ~50(中点)。
- **`risk_tier`** — `low-risk` / `medium-risk` / `high-risk`,由 `quality_health` 映射而来:`excellent` → `low-risk`,`good` → `medium-risk`,其余任何情况(`fair`、`poor`、缺失、`"N/A"`)→ `high-risk`。默认归为高风险的姿态是刻意为之的 — 质量未知的信号会被下游消费方谨慎对待。
- **`bullish_pct` / `neutral_pct` / `bearish_pct`** — 底层细分,与其他每个分享面采用相同的 ±0.2 立场阈值。这里的「Bullish 62%」信号与同一模拟在图库卡片、分享卡片、重放 GIF 和轨迹 CSV 中报告的数值一致。
- **`signal_generated_at`** — ISO-8601 UTC 时间戳,记录信号*被计算*的时刻,而非底层模拟完成的时刻。每次请求都会重新推导(逐字节确定性并非此分享面的特性 — 这与 `reproduce.json` / `notebook.ipynb` 不同,后者的字节需要可作引用哈希)。

纯推导。无新计算。底层数字与 embed-summary 端点已经构建、图库卡片已经展示、分享卡片 PNG 已经渲染的数字完全相同。仅标准库(用 `datetime` 生成时间戳);`signal_service.py` 模块约 200 行代码,无新增依赖。

与其他每个分享面采用相同的发布门控(`is_public=true`)。当模拟尚未记录任何轮次时返回 `404`(embed summary 上没有 `belief.final` 区块),这样嵌入工具就能渲染一个「未就绪」占位符,而不是渲染一个告警流水线可能据此行动的半成品信号。缓存 5 分钟 — 一个实时模拟的最终立场可能逐轮反转,所以短缓存让告警流水线能看到新鲜信号,同时爬虫又不会反复冲击 embed-summary 的构建。

嵌入对话框在轨迹图表行下方暴露一个 `📡 Trading signal (JSON)` 区块:信号载荷的实时预览、一个「Download .json」锚点、一个可复制的 URL,以及一段可直接粘贴的 `curl` 代码片段。`signal_json` 计数器加入分发统计 schema,这样运营者就能看到信号独立于各视觉分享面之外驱动了多少条告警流水线。

弥合了*「一个模拟产出数据」*与*「一个模拟产出信号」*之间的鸿沟 — 这是量化受众在 MiroShark 的输出能够直接落入自动化流程(而非 notebook)之前所需要的最后一公里。

## 峰值轮次分析

`trajectory.csv` 把原始的逐轮信念分布交给分析师;`chart.svg` 把同一批数字画成折线。两者都没有回答量化运营者最先问的两个问题 — *「看涨在哪一轮见顶?」*和*「哪一轮波动最大?」* — 除非逐行解析。`GET /api/simulation/<id>/peak-round` 把整条轨迹浓缩成一份关于拐点的 O(n) 摘要。

返回一个稳定的 v1-schema JSON 文档:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "bullish": { "round": 4, "pct": 71.4 },
  "neutral": { "round": 1, "pct": 55.0 },
  "bearish": { "round": 9, "pct": 48.2 },
  "most_volatile_round": 4,
  "max_swing_pct": 38.6,
  "total_rounds": 12
}
```

- **`bullish` / `neutral` / `bearish`** — 每个立场达到其最大份额那一轮的 `{round, pct}`。平局时解析为*最早*的轮次(严格 `>` 比较),所以在平顶轨迹上输出是确定性的 — 它回答的是「看涨*首次*见顶是在何时」。
- **`most_volatile_round`** — 承载最大逐轮信念波动绝对值总和(`|Δbullish| + |Δneutral| + |Δbearish|`)的那一轮。第一轮没有前驱,所以其波动为零;平局时解析为最早的轮次。
- **`max_swing_pct`** — `most_volatile_round` 处的波动值,四舍五入到两位小数。对于单轮或完全平坦的轨迹为 `0.0`。
- **`total_rounds`** — 轨迹中可用轮次的数量。

纯推导。逐轮百分比来自 `trajectory.csv` 所用的同一个 `trajectory_export.compute_stance_split`(±0.2 阈值),所以这里的「看涨在第 4 轮见顶于 71.4%」与 CSV 的第 4 行一致。唯一的新信息是*形状*:一份机器可读的拐点摘要,而非重新计算。仅标准库(`json` + `os`);`peak_round.py` 约 190 行代码,无新增依赖。

与其他每个分享面采用相同的发布门控(`is_public=true`)。当模拟尚无轨迹数据时返回 `404`,这样消费方就能把「未就绪」的模拟(404)与「私有」的模拟(403)区分开来。缓存 5 分钟 — 与 `chart.svg` / `trajectory` / `signal.json` 的节奏一致。

嵌入对话框在交易信号行下方暴露一个 `📊 Peak beliefs (JSON)` 区块:一个实时预览(看涨 / 看跌峰值、波动最大的轮次、总轮数)、一个可复制的 URL,以及一段可直接粘贴的 `curl` 代码片段。`peak_round` 计数器加入分发统计 schema,这样运营者就能看到这份分析摘要独立于原始 CSV 之外被拉取了多少次。

补全了与 `trajectory.csv`(原始数据)、`chart.svg`(视觉)和 `signal.json`(最终状态动作原语)并列的分析象限 — 即那三者隐含未现的拐点视图。

## 信念波动度评分

`signal.json` 回答的是*这群智能体最终落在了哪里*(方向 + 置信度)。`peak-round` 挑出最具波动的那一个轮次。两者都没有回答量化操盘者会问的第三个问题 — *「通往共识的路径有多激烈?」*一个高波动的看涨结果(智能体在对齐前反复摇摆)与一个低波动的看涨结果(共识在第三轮形成并保持住)是两种截然不同的输入;对于一个仓位规模模型而言,相同的最终方向可以意味着大相径庭的东西。`GET /api/simulation/<id>/volatility` 描述了逐轮摆动的分布,使得波动这一维度终于能与方向和拐点并排可读。

返回一个稳定的 v1-schema JSON 文档:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "mean_delta_pct": 12.45,
  "std_dev_delta_pct": 8.16,
  "max_delta_pct": 38.6,
  "max_delta_round": 4,
  "volatility_index": 40.8,
  "trend": "converging",
  "total_rounds": 12,
  "delta_count": 11
}
```

- **`mean_delta_pct` / `std_dev_delta_pct` / `max_delta_pct`** — 逐轮的信念摆动绝对值之和的均值、总体标准差和最大值,全部四舍五入到两位小数。每一轮的摆动为 `|Δbullish| + |Δneutral| + |Δbearish|` — 正是 `peak-round` 用来挑选其唯一 `most_volatile_round` 的那个确切定义。
- **`max_delta_round`** — 承载 `max_delta_pct` 的那一轮。在相同输入上,按构造等于 `peak-round` 的 `most_volatile_round`;并列时取最早的轮次。
- **`volatility_index`** — 一个归一化的 0–100 激烈度评分:`min(std_dev_delta_pct × 5, 100)`。20 个百分点的标准差映射到 100,完全平坦的轨迹落在 0。这个 5× 乘数是一个校准旋钮 — 公式就写在 schema 里,这样集成方无需逆向工程即可重新缩放到不同区间。
- **`trend`** — 当 `std_dev_delta_pct < 3` 时为 `"stable"`(极紧密的聚集);当轨迹后半段的 delta 标准差严格低于前半段时为 `"converging"`(这群智能体平静了下来);否则为 `"contested"`。delta 数少于四个的轨迹会回退到仅按标准差分桶,因为没有诚实的前后半对比可言。
- **`total_rounds` / `delta_count`** — 可用轮次的数量,以及逐轮 delta 的数量(`total_rounds - 1`)。

纯推导,换了个角度:它不是挑出单个最大值(拐点视图),而是汇总*每一次*摆动的分布。仅标准库(`json` + `os` + 用于标准差的 `math`);`volatility_service.py` 没有新增依赖。

与其他每个分享面相同的发布门控(`is_public=true`)。当模拟少于两轮(没有 delta 可计算)时返回 `404`,这样消费方就能把「尚未就绪」的模拟(404)和「私有」的模拟(403)区分开。缓存 5 分钟 — 与 `chart.svg` / `trajectory` / `peak-round` / `signal.json` 的节奏一致。

嵌入对话框在交易信号行下方暴露了一个 `📈 Belief volatility (JSON)` 区块:一个实时预览(带渐变条的波动度指数、最大摆动、平均摆动、标准差、趋势标签),一个可复制的 URL,以及一段可直接粘贴的 `curl` 片段。`volatility` 计数器加入了分享面统计 schema,这样操作者就能看到激烈度视图被独立于原始 CSV 拉取的频次。

它闭合了三因子分析视图 — `signal.json` 给出*方向*,`peak-round` 给出*何时*,`volatility` 给出*有多激烈* — 这正是下游量化工具在原始轨迹之外所需要的。

## 单智能体信念迷你图

`chart.svg` 和嵌入摘要绘制的是*聚合*信念曲线 — 这群智能体逐轮得出的结论。`peak-round` 把那条聚合曲线坍缩成拐点。两者都没有暴露其下方的那一层:*每个单独智能体*的信念路径。一位研究群体收敛的研究者 — *「是哪个智能体锚定了共识?金融分析师阵营是否在散户交易者之前就对齐了?」* — 除了手工解析 `transcript.md` 之外别无分享面可用。`GET /api/simulation/<id>/agents/sparklines` 就是这个智能体层级的伙伴:每个智能体一条信念轨迹。

返回一个稳定的 v1-schema JSON 文档:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "agent_count": 24,
  "round_count": 12,
  "has_per_agent_data": true,
  "agents": [
    {
      "agent_id": 7,
      "name": "Skeptical Quant",
      "final_stance": "bullish",
      "final_position": 0.612,
      "color": "#22c55e",
      "trajectory": [
        { "round": 1, "position": 0.05 },
        { "round": 2, "position": 0.31 },
        { "round": 3, "position": 0.612 }
      ]
    }
  ]
}
```

- **`agents`** — 每个持有可用信念立场的智能体一个条目,按 `final_position` 从最看涨优先排序(并列时按 `agent_id` 打破),这样列表从上到下就是从最强的多头读到最强的空头。
- **`trajectory`** — 该智能体每一轮的标量信念立场,按轮次升序排列。每个 `position` 是该智能体各话题 `belief_positions` 的均值(大致在 `[-1, 1]`),四舍五入到三位小数 — 正是其他每个分享面在分桶前所平均的那个确切的 `_avg_position`。
- **`final_stance` / `color`** — 该智能体最后一轮立场在相同 ±0.2 立场阈值下的立场,加上匹配的十六进制颜色(`#22c55e` 看涨、`#6b7280` 中立、`#ef4444` 看跌),这样一条迷你图就与看涨的 `chart.svg` 线条同样是绿色。
- **`name`** — 来自 `reddit_profiles.json`(然后是 `polymarket_profiles.json`)的显示名;当没有对应的 profile 行时为 `"Agent <id>"`,这样一条迷你图永远不会是匿名的。
- **`has_per_agent_data`** — 仅当至少有一个智能体拥有 2 点轨迹(足以画一条线)时才为 `true`。单轮模拟会把智能体作为单个点返回,并将此标志置为 `false`,这样消费方就能显示一条「需要 ≥2 轮」的提示,而不是一排毫无意义的点。

纯推导,换了个角度:它不是把所有智能体分桶成每一轮一个百分比(聚合视图),而是逐轮追踪每个智能体一个标量。仅标准库(`json` + `os`);`agent_sparklines_service.py` 没有新增依赖。

与其他每个分享面相同的发布门控(`is_public=true`)。当尚无任何智能体持有可用信念立场时返回 `404` — 把「尚未就绪」的模拟(404)和「私有」的模拟(403)区分开。缓存 5 分钟 — 与 `chart.svg` / `trajectory` / `peak-round` 的节奏一致。

嵌入对话框在 peak-round 行下方暴露了一个 `🤖 Agent trajectories (JSON)` 区块:一个可滚动的智能体列表,每项是一个名字标签 + 一个内联 SVG 迷你图(信念立场随轮次变化,以该智能体的立场颜色描边)+ 最终立场标签,加上一个可复制的 URL 和一段可直接粘贴的 `curl` 片段。`agent_sparklines` 计数器加入了分享面统计 schema,这样操作者就能看到智能体层级视图被拉取的频次。

## Polymarket 就绪预测 JSON

第一个为特定外部集成方适配的分享面。`signal.json` 发出一个通用的动作基元(`direction` + `confidence_pct` + `risk_tier`);`GET /api/simulation/<id>/polymarket.json` 把那个基元重塑成一个 Polymarket 交易机器人在*「模拟结果」*和*「可执行市场信号」*之间所期望的二元 YES / NO 概率封套。

返回一个稳定的 v1-schema JSON 文档:

```json
{
  "schema_version": "1",
  "simulation_id": "<sim_id>",
  "direction": "Bullish",
  "yes_probability": 0.62,
  "no_probability": 0.38,
  "confidence_pct": 43.4,
  "confidence_tier": "moderate",
  "risk_tier": "low-risk",
  "bullish_pct": 62.0,
  "neutral_pct": 18.0,
  "bearish_pct": 20.0,
  "quality_health": "excellent",
  "suggested_market_title": "Will Aave pass the safety-module change?",
  "source_sim_id": "<sim_id>",
  "polymarket_generated_at": "2026-05-23T14:22:01Z"
}
```

- **`yes_probability` / `no_probability`** — 方向感知的。一群看涨的智能体发出一个高 `yes_probability`(`bullish_pct / 100`);一群看跌的智能体发出一个低的(`1 - bearish_pct / 100`);一群中立的智能体精确落在 `0.5`(抛硬币先验)。在浮点容差内 `yes + no == 1.0` — 这是 Polymarket 订单簿消费方所期望的不变式。两者都四舍五入到四位小数,与 Polymarket 的显示栏精度一致。
- **`confidence_tier`** — 叠加在 `signal.json` 连续的 `confidence_pct` 之上的四桶离散刻度。`<25` → `speculative`,`25-50` → `moderate`,`50-75` → `confident`,`≥75` → `high-conviction`。上界是排他的(`25.0` 是 `moderate`,不是 `speculative`)。机器人通常根据这个 tier 来门控仓位规模 — 对「speculative」和「high-conviction」采用不同的规模 — 而不是根据原始的连续值。
- **`suggested_market_title`** — 为 Polymarket 的显示栏合成为 `"Will {scenario}?"`。一个已经以 `"Will "` 开头的情景不会被双重加前缀;在 120 字符处截断之前会先剥去尾部标点(截断时带 `"…?"`)。缺失 / 空的情景回退为 `"Will resolve YES?"`。这是一个*建议的*标题 — 预期机器人作者会去打磨这个字符串。
- **`source_sim_id`** — 在 Polymarket 机器人回写到自己审计日志时所期望的字段名下回显模拟 id。规范的 `simulation_id` 键(其他每个分享面)携带相同的值,这样消费方可以读取任意一个。

纯推导,层叠在 `signal_service` 之上。`polymarket_service.py` 模块约 230 行标准库 Python — `compute_polymarket` 调用 `signal_service.compute_signal` 并重塑其输出。信号载荷所保证的每一项属性(打破并列的顺序、一位小数四舍五入、ISO-8601 时间戳格式)都会贯穿下来。一个「Bullish 62%」的模拟会在图库卡、分享卡、`signal.json`、`badge.svg` 和 `polymarket.json` 上发出完全相同的底层数字 — 只有*封套*改变。

比 `signal.json` 更严格的发布门控:只有 `status == "completed"` 的模拟才会发出载荷。一个根据运行中信号来确定仓位规模的 Polymarket 机器人会去追逐仍可能翻转的数字;仅限已完成的姿态防止了这个自踩脚的坑。运行中的模拟,以及刚发布但尚未记录任何轮次的模拟,都会返回 `404`。缓存 5 分钟 — 与 `signal.json` 的节奏一致,这样一个同时轮询两个分享面的机器人会看到一致的值。

嵌入对话框在交易信号行下方暴露了一个 `🎯 Polymarket prediction (JSON)` 区块:一个 YES / NO 概率的实时预览、置信度和风险 tier、建议的市场标题、一个「Download .json」锚点、一个可复制的 URL,以及一段可直接粘贴的 `curl | jq` 片段。`polymarket_json` 计数器加入了分享面统计 schema,这样操作者就能看到预测分享面独立于视觉分享面驱动了多少个 Polymarket 机器人。

零新增依赖(连续:31 个 PR)。第一个点名特定外部集成方的分享面 — 与 PR #83(「Discord/Slack 通知」 —  第一个点名 `@revaultdrops` 的功能)配对,并延续了驱动外部集成方采用的明确受众模式。

## 模拟克隆 JSON

其他每一个分享面返回的都是*输出* — 方向、图表、徽章、轨迹、波动率评分、智能体迷你折线图、Polymarket 区间。`GET /api/simulation/<id>/clone.json` 是第一个返回*输入*的分享面:一次模拟构建时所用的精确配置,其形态正是 `POST /api/simulation/create` 所接受的。

返回一个稳定的 v1-schema JSON 封套:

```json
{
  "schema_version": "1",
  "simulation_id": "sim_abc123",
  "project_id": "proj_xyz789",
  "graph_id": "miroshark_def456",
  "simulation_requirement": "Will Aave's reserve factor doubling reduce TVL?",
  "scenario_preview": "Will Aave's reserve factor doubling reduce TVL?",
  "clone_payload": {
    "project_id": "proj_xyz789",
    "graph_id": "miroshark_def456",
    "enable_twitter": true,
    "enable_reddit": true,
    "enable_polymarket": false,
    "polymarket_market_count": 1,
    "country": null,
    "demographic_filters": null
  },
  "example_curl": "curl -fsSL -X POST 'https://your-host/api/simulation/create' -H 'Content-Type: application/json' -d '{…}'"
}
```

- **与 `/api/simulation/create` 线缆兼容** — `clone_payload` 就是该端点所接受的字面请求体。一个持有相同 `project_id` 的调用方,用一句 `curl -X POST` 即可重跑模拟;一个对模拟做分叉的基准测试工作流,拨动一个旋钮再 POST 修改后的请求体即可。无需重新整形,无需手动重新录入开关或过滤器。
- **`simulation_requirement` 仅供参考** — 情景文本存活在项目层级(一个项目可以在同一图谱 + 情景下承载多个模拟)。`/api/simulation/create` 不接受 `simulation_requirement` 作为请求体字段 — 项目的取值会被复用。一个需要*不同*情景的分叉,要在 POST 克隆请求体之前先更新项目。该字段在封套里被回显出来,这样调用方就知道被克隆的模拟在辩论什么。
- **`country` + `demographic_filters` 一并带过去** — 当原始模拟锚定在某个 Nemotron 人口学包里时,克隆请求体会保留国家代码(小写化 + 去空白,与 `manager.create_simulation` 的归一化保持一致)以及过滤器字典(空过滤器字典会强制转为 `null`,因为它们在语义上等价于「不做过滤」)。一个想分叉到不同人口学的调用方,只需替换该字段并 POST。
- **`example_curl` 携带的是字面占位符 `https://your-host`** — 与分享面目录同一姿态。对示例的复制粘贴永远不会误打到内部 URL;运行前由运维替换成自己的部署主机。
- **`polymarket_market_count` 被钳制到 `[1, 5]`** — 与 `manager.create_simulation` 的钳制一致,因此一份手工编辑过的 state.json 也无法产出一个会被 create 处理器拒绝的克隆请求体。

纯派生。`clone_service.py` 模块约 250 行纯标准库 Python — `build_clone_payload` 读取 `state.json`(`/create` 所接受的结构性字段)与 `simulation_config.json`(情景文本)。没有新增依赖,没有 LLM 调用,没有图谱遍历 — 只是在每个已发布模拟都已有的两份磁盘工件上做纯文件 I/O。

与其他每一个分享面相同的发布门控(`is_public=true`)。当磁盘上不存在 `state.json` 时(准备中或已被裁剪)返回 `404`,这样消费方就能把「尚未就绪」的模拟(404)和「私有」的模拟(403)区分开。缓存一小时 — 克隆请求体是结构性的(project_id / graph_id / 开关 / country / demographic_filters)。不同于那些分析型分享面(峰值轮次 / 波动率 / signal),这些输入不会逐轮变化;对于一个「该模拟是如何配置的结构性快照」的分享面来说,一小时是恰当的节奏。

`clone_json` 计数器加入分享面统计 schema。它与现有的 `/api/simulation/compare` 端点配对:克隆输入、跑模拟,然后把输出与原始做 diff。它合上了那个仍未构建的「情景克隆按钮」工作流的 API 那一半。

## 共识状态徽章 SVG

回指一次模拟的最廉价的可见指针。此前的十二个分享面以递增的深度描述一次模拟(图表 SVG、回放 GIF、轨迹 CSV / JSONL、文字记录、notebook、signal.json、archive.zip、……);`GET /api/simulation/<id>/badge.svg` 则是*被动分发杠杆* — 一张扁平的、20 像素高的、与 Shields.io 兼容的 SVG,能嵌进任意 `<img>` 标签、Markdown 图片链接或 `<link rel="alternate">` 引用。每位研究者的 GitHub README、每个 Notion 页面、每位运维的个人站点,都能用一行 Markdown 嵌入一枚实时共识徽章:

```markdown
![MiroShark](https://your-host/api/simulation/<id>/badge.svg)
```

该徽章采用规范的 Shields.io 扁平布局:左半边是标准 `#555555` 灰色上的「MiroShark」,右半边是立场颜色上的 `{direction} {confidence_pct}%` — `#22c55e`(看涨)、`#6b7280`(中立)、`#ef4444`(看跌)。这套颜色词汇与其他每一个信念分享面(图表 SVG、社交卡片、回放 GIF、watch 页、邮件信念百分比)保持一致,因此一位在同一份 README 里看过图表的读者会立刻认出这枚徽章。方向 + 置信度派生自 `signal.json` 所用的同一条 `compute_signal` 管线 — 这里一枚「Bullish 72%」徽章与 signal 载荷、图库卡片、社交卡片逐字节一致。

纯标准库 `xml.etree.ElementTree` 渲染器(`app/services/badge_service.py` 约 330 行);零新增依赖 — 与 `chart_svg`、`frame_metadata`、`share_card` 以及其他每一个渲染器模块同一姿态。在相同输入下,渲染出的 SVG 跨调用按字节确定,因此未来的 ETag 层 / 磁盘缓存能拿到稳定的缓存键。

- **`viewBox="0 0 W 20"`** — Shields.io 扁平风格的规范高度。该徽章能在同一份 README 里紧挨着 GitHub-Actions / npm / PyPI 徽章排列,而不出现明显的高度不匹配。宽度随右侧标签长度伸缩(`Bullish 5%` 比 `Bearish 100%` 更窄)。
- **药丸形端头** — 通过一个带 `rx="3"` 的 `<clipPath>` 实现圆角,这样徽章能在每一个 `<img>` 消费方上正确渲染,包括较老的 Notion / Substack / GitHub Markdown 预览器。没有 `<linearGradient>` 或 `<defs>` — 扁平预设在字节上更小,并且在屏幕阅读器纯文本模式下渲染得一模一样。
- **无障碍** — `role="img"` + `aria-label="MiroShark: Bullish 72%"` + 一个 `<title>` 元素。屏幕阅读器会念出该状态;SEO 爬虫会抓到同一段文本。
- **对输入做防御** — 未知 / 缺失的方向会以中立灰 + 一个显式的 `Unknown` 标签渲染,而不是抛错。落在 `[0, 100]` 之外的置信度会被钳制;非数值变为 `0`。路由处理器在上游把「尚无轮次」当作 404 处理,这样嵌入的 `<img>` 会渲染一个破图占位符,而不是一枚误导性的 `Unknown 0%` 徽章。

与其他每一个分享面相同的发布门控(`is_public=true`)。`Cache-Control: public, max-age=60` — 一次实时模拟的立场翻转会在一个轮询周期内传播到每一枚嵌入的徽章(与 watch 页轮询节奏一致),因此一位把徽章嵌进 README 并刷新页面的研究者会看到最新的共识。这个时长足够短,能让运行途中的立场变动迅速到达读者;又足够长,使一份热门 README 不会用每次页面浏览一次的抓取把嵌入摘要的构建打爆。

嵌入对话框暴露了一个 `🏷️ Status badge (SVG)` 区段:一个原地的实时预览、一个可复制的徽章 URL、一段 `![MiroShark Belief Badge](...)` 的 Markdown 片段,以及一段 `<img height="20">` 的 HTML 片段。`badge_svg` 计数器加入分享面统计 schema,这样运维就能看到有多少 README / 博客 / Notion 嵌入把浏览引回了分享页。

它把每一个被分发出去的分享 URL 都变成了一个*引流点*,面向那些在某位研究者的 README 里看到徽章的新访客 — 这是第一个把模拟带*到*读者面前的分享面,而不是等着读者自己导航到分享页。

## 平台聚合统计

第一个描述平台本身而非单次模拟的端点。`GET /api/stats` 把磁盘上每一个满足 `is_public == true` 且 `status == "completed"` 的模拟塌缩进单个封套:模拟总数、共识分布(看涨 / 中立 / 看跌的计数 + 百分比)、整个语料库上的平均 `confidence_pct`、磁盘上每个 `surface-stats.json` 计数器的总和、这些模拟所跨越的不重复 `project_id` 数量,以及最新模拟的标识符 + 创建时间戳。一次读取即可驱动新闻资料包(「MiroShark 已运行 N 次模拟」)、外部仪表盘、LLM 智能体健康检查(*「这个 MiroShark 实例还活跃吗?」*),以及下面那枚平台 Shields.io 徽章。

```json
{
  "success": true,
  "data": {
    "schema_version": "1",
    "total_sims": 1247,
    "consensus_distribution": {
      "bullish": 612, "neutral": 308, "bearish": 327,
      "bullish_pct": 49.1, "neutral_pct": 24.7, "bearish_pct": 26.2
    },
    "avg_confidence_pct": 58.4,
    "total_surface_views": 41682,
    "unique_projects": 89,
    "newest_sim_id": "sim_e7c1b2f3a9d4",
    "newest_sim_created_at": "2026-05-24T15:42:11.103928"
  }
}
```

- **立场计数沿用单模拟级别的派生。** 把一次模拟的最终信念分布转成单模拟 `signal.json` 上一个 `direction` 的那套同样的多数 + 平局裁断规则(`bullish > bearish > neutral`),在这里产出平台级别的计数。一次在它的 `signal.json` 上被标为看涨的模拟,会在这份聚合里被计入 `bullish` 桶 — 两个分享面,一个真相之源。
- **是 `unique_projects`,而非 `unique_operators`。** `SimulationState` 不携带运维 / 创建者字段 — `project_id` 是最接近的稳定标识符。按惯例每个项目就是一个单独的研究 / 运维工作区,因此项目数对运维数而言是一个合理的代理,但字段名并不承诺模型支撑不了的数据。未来一次模型迁移可以加入一个专门的 `operator` 字段以及一个同级的 `unique_operators` 聚合,而不破坏这个分享面。
- **单次扫描,60 秒缓存。** 一个以模拟根目录为键的模块级缓存吸收突发的新闻展开 — 在 60 秒窗口内,第一次之后的每一次调用都是一次字典拷贝,而非一次磁盘扫描。该路由额外发出一个由 `total_sims` + `newest_sim_id` 派生的短 `ETag`;一个带 `If-None-Match` 的条件 GET 会短路到 `304 Not Modified`,无需重新序列化主体,因此一枚每分钟轮询一次的 README 徽章付出的大约就是每个窗口一次 HEAD 请求的代价。
- **空部署优雅降级。** 一个零已发布模拟的全新安装返回一个全部置零的封套,而非 404。一个渲染「*已运行 N 次模拟*」的消费方,不需要为部署的第一天做特殊处理。

纯标准库(`os` + `json` + `time` + `threading`,`app/services/platform_stats.py` 约 340 行);零新增依赖 — 与 `signal_service`、`badge_service` 以及其他每一个聚合模块同一姿态。该扫描直接遍历 `WONDERWALL_SIMULATION_DATA_DIR`;没有 Neo4j,没有 LLM,没有出站网络。

## 平台统计徽章 SVG

单模拟 `/badge.svg` 的平台级别同胞。`GET /api/stats/badge.svg` 返回一张扁平的 20 像素、与 Shields.io 兼容的药丸 — 标准 Shields.io 灰(`#555555`)上的 `MiroShark`,平台蓝(`#0ea5e9`)上的 `N simulations`。一行 Markdown 就把任意社区 README、Substack 页眉或运维作品集变成一个实时的平台活跃度指示器:

```markdown
![MiroShark](https://your-host/api/stats/badge.svg)
```

这个计数与 `/api/stats` 报告的 `total_sims` 取值相同 — 这两个分享面共享同一次扫描和同一个 60 秒缓存。平台蓝在视觉上与三种单模拟立场颜色(`#22c55e` / `#6b7280` / `#ef4444`)截然不同,因此读者绝不会把平台徽章误认成单模拟共识徽章 — 模拟徽章落在「这次具体运行看涨」的那一端;平台徽章落在「整个项目都活跃」的那一端。

一个零模拟的部署会渲染出一张有效的 `MiroShark | 0 simulations` 药丸,而非 404 — 一个全新安装实例上嵌入的 `<img>` 绝不会出现破图字形。与单模拟徽章相同的扁平布局、无障碍属性(`role="img"`、`aria-label="MiroShark: N simulations"`、`<title>` 元素)以及圆角 `<clipPath>` 药丸端头;唯一的区别是右半边的标签和填充颜色。在相同输入计数下跨调用按字节确定 — 未来的 ETag 层可以直接对响应字节做哈希。

一个二阶分发放大器:单模拟徽章(PR #94)是面向*特定模拟*的引流点;平台徽章则是面向 *MiroShark 本身*的引流点。每一位运行 Aeon 框架实例的运维、每一位拥有个人站点的研究者、每一篇关于群体模拟的 Substack 帖子,都成为一个表明平台正活跃并成长的实时信号。

## 分享面目录 API

这是第一个回答每位集成者上手第一天都会碰到的元问题的端点:*「这个部署上有什么可用?」*在此之前,答案要么得去读 `docs/FEATURES.md`、grep 路由,要么得去翻 PR 描述。`GET /api/surfaces.json` 把这份目录压缩成单个机器可读的响应 — 列出该部署暴露的每一个分享 / 平台分享面,并为每一项附上端点路径、HTTP 方法、类型类别、一行描述、来源 PR,以及一段可复制粘贴的 `curl` 示例。

```json
{
  "success": true,
  "data": {
    "schema_version": "1",
    "count": 28,
    "surfaces": [
      {
        "key": "signal_json",
        "endpoint": "/api/simulation/<simulation_id>/signal.json",
        "method": "GET",
        "type": "analytics",
        "description": "Direction + confidence + quality_health JSON — the trading-signal core payload.",
        "added_in_pr": 60,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/signal.json'"
      },
      {
        "key": "polymarket_json",
        "endpoint": "/api/simulation/<simulation_id>/polymarket.json",
        "method": "GET",
        "type": "integration",
        "description": "Polymarket-shaped trading signal — direction-aware yes/no probability + tier.",
        "added_in_pr": 99,
        "example_curl": "curl -fsSL 'https://your-host/api/simulation/<simulation_id>/polymarket.json'"
      },
      "..."
    ]
  }
}
```

- **静态且硬编码 — 出于设计。** 这份目录是 `services/surfaces_catalog.py` 中模块作用域里的一份字面列表;它不是从 `SURFACE_KEYS`(只跟踪带服务计数器的发布门控逐模拟分享面)自动派生的,也不是从 Flask URL 映射里扫描出来的(那会把目录绝不能对外宣传的私有变更路由也带进来)。一个新分享面要落地需改三处文件 — 路由处理器、若它是逐模拟且发布门控则还有 `SURFACE_KEYS`,以及这份目录。`test_unit_surfaces_catalog.py` 中的防漂移测试会把逐模拟子集与 `SURFACE_KEYS` 交叉核对,让任何一侧都无法悄悄漂移。
- **七个类型类别。** `analytics`(`signal.json`、`peak-round`、`volatility`、`agents/sparklines`、`lineage`)、`visualization`(`share-card.png`、`replay.gif`、`chart.svg`、`badge.svg`)、`export`(`transcript.*`、`trajectory.*`、`archive.zip`、`notebook.ipynb`、`reproduce.json`、`cite.bib`、`thread.*`)、`embed`(`/watch/<id>`、`/oembed`)、`integration`(`polymarket.json`)、`platform`(`/api/stats`、`/api/stats/badge.svg`、本端点),以及 `discovery`(`/api/feed.atom`、`/api/feed.rss`)。消费方可以通过对 `type` 过滤来把工作范围限定在某个类别 — `jq '.data.surfaces[] | select(.type == "analytics")'` 只返回分析类分享面。
- **可复制粘贴的 `example_curl`。** 每一项的 `example_curl` 都逐字引用该项的 `endpoint` — 消费方粘贴示例后命中的永远是目录所声明的同一条路径。由单元测试保障。占位主机是字面字符串 `https://your-host`,模拟 id 占位符是字面的 `<simulation_id>` — 没有任何条目包含真实主机或管理员令牌,因此消费方绝不会意外复制粘贴到内部 URL。
- **一小时缓存,ETag 驱动失效。** 目录仅在某个新 PR 上线新分享面时才变化;`Cache-Control: public, max-age=3600` 为上线与目录反映该变化之间的滞后划定了一个紧致上界。`ETag` 为 `surfaces-v<schema>-<count>` — 目录增长时递增。带条件的 `If-None-Match` GET 会短路为 `304 Not Modified`,因此轮询型消费方(Aeon 的每日分享面计数检查、集成者的仪表盘)在两次上线之间无需付出 JSON 主体的开销。
- **形状稳定,带 schema 版本。** 信封为 `{schema_version, count, surfaces}`;v1 是唯一已发布的版本。`surfaces` 内部的顺序大致按时间排列 — 最早的分享面在前,平台级 + 元条目分组在末尾。追加一个新条目是非破坏性的;重排现有条目是破坏性的,并会递增 `schema_version`。每个条目上的 `key` 字段为 snake_case,对逐模拟分享面而言与对应的 `surface_stats.SURFACE_KEYS` 成员相匹配,因此把目录条目与逐模拟 `/surface-stats` 计数器关联起来的消费方可以基于该字段做联结。
- **闭合了 README 工作开启的可发现性回路。** PR #118 与 #119 为人类读者精炼了 README 的首触可发现性;本端点为机器读者补上了同样的能力。Aeon 的每日分享面计数检查不再需要解析 FEATURES.md;查询某个部署以探测哪些分享面可用的集成者不再需要去抓取文档。

纯标准库(`services/surfaces_catalog.py` + `api/surfaces.py` 共约 370 LoC);零新增依赖 — 与 `platform_stats`、`surface_stats` 以及本目录树中其他每一个纯数据模块姿态一致。目录本身是一份字面列表;无磁盘扫描、无 Neo4j、无外发网络。始终返回 `200`(或 `304`)— 调用方提供任何输入都不会产生 `404`。

## 生态系统 JSON 注册表

[`ECOSYSTEM.md`](../ECOSYSTEM.md) 面向机器读者的对照端点。`GET /api/ecosystem.json` 把同一份策展的集成者名单 — 每一个被公开认定为在 MiroShark 之上构建的外部项目、智能体或产品 — 作为带类型的 JSON 信封返回。消费方再也无需解析 Markdown 表格来发现还有谁在平台上构建。

与 `/api/surfaces.json` 共用同一个蓝图。两个端点合起来回答每位集成者第一天都会碰到的两个元问题 — *「我可以调用哪些分享面?」*(surfaces.json)与 *「还有谁在这之上构建?」*(ecosystem.json)。

- **五个类别。** `product`(在 MiroShark 之上构建的面向公众的应用 — Capacitr、Echo Oracle、HivemindOS、RootAI、Xerg、ZER0)、`tool`(面向操作者的工具 — Crucible Sim)、`integration`(把 MiroShark 接入其他系统的 MCP 服务器、Aeon 技能包、Bags 风格的监视器 — Monitor、Noelclaw、Signa)、`agent`(运行 MiroShark 模拟的自主机器人 — Blue Agent、SyntheticsAI)、`benchmark`(在引擎之上构建的测试 / 评估流水线 — AntFleet)。消费方可以通过对 `category` 过滤来把工作范围限定在某个类别。
- **静态硬编码 — 出于设计。** 目录是 `services/ecosystem_catalog.py` 模块作用域内的字面列表;它 **不** 通过解析 `ECOSYSTEM.md` 自动派生 — Markdown 形状(单元格内含徽标、链接和自由文本)非常脆弱,解析器的悄然漂移会损害公开契约。新增一位集成者会落在两个文件里:`ECOSYSTEM.md` 的一行与本目录中的一条记录。`test_unit_ecosystem_catalog.py` 中的漂移守护测试会在两个来源之间交叉校验项目 `name` 集合,因此任何一侧都无法悄然漂移。
- **按 `name` 字母排序。** 与 `ECOSYSTEM.md` 的排序约定一致。消费方迭代该列表时看到的顺序与人类读者浏览 Markdown 表格时一致。顺序是公开契约的一部分 — 追加是非破坏性变更;重排现有条目是破坏性的。
- **`x_handle` 不带前导 `@`。** 消费方拼接 `https://x.com/<x_handle>` URL(信息流、批量关注脚本、情感监视器)时可直接得到干净的 URL,无需字符串裁剪。若集成者没有公开 X 账号,该值为 `null`。
- **`repo` 是 `https://github.com/…` URL 或 `null`。** 闭源集成者暴露 `null` 而非伪造 URL — 只迭代开源条目的消费方可以干净地用 `select(.repo != null)` 过滤。
- **一小时缓存,ETag 驱动失效。** 目录仅在某个新 PR 新增集成者时才变化;`Cache-Control: public, max-age=3600` 为上线与目录反映该变化之间的滞后划定了紧致上界。`ETag` 为 `ecosystem-v<schema>-<count>` — 目录增长时递增。带条件的 `If-None-Match` GET 会短路为 `304 Not Modified`。
- **形状稳定,带 schema 版本。** 信封为 `{schema_version, count, ecosystem}`;v1 是唯一已发布的版本。每条目的字段集(`name`、`url`、`description`、`category`、`x_handle`、`repo`)是锁定的。
- **闭合生态系统可发现性回路。** 2026-06-02 一天之内落地了四个生态系统 PR(HivemindOS / Echo Oracle / Capacitr / SyntheticsAI);生态系统的增长速度已经超过了服务它的工具。这个端点为「在集成者之上构建的集成者」提供了一个带类型的 API 起点。

纯标准库(`services/ecosystem_catalog.py` + `api/surfaces.py` 新增路由共约 250 LoC);零新增依赖 — 与 `surfaces_catalog`、`platform_stats`、`surface_stats` 以及本目录树中其他每一个纯数据模块姿态一致。目录本身是一份字面列表;无磁盘扫描、无 Markdown 解析、无 Neo4j、无外发网络。始终返回 `200`(或 `304`)— 调用方提供任何输入都不会产生 `404`。

## BibTeX 学术引用

闭合学术引用弧。`reproduce.json`(PR #79)携带第二位操作者重跑模拟所需的每一个参数;OriginTrail DKG 引用(PR #84)把这些字节锚定在链上作为加密溯源;`notebook.ipynb`(PR #80)把轨迹丢进研究者的 IDE。`GET /api/simulation/<id>/cite.bib` 补上缺失的一层 — 单次调用即得一个 BibTeX `@misc{…}` 条目,可直接放进 LaTeX 论文源文件,通过「Import from URL」干净地导入 Zotero / Mendeley(两个阅读器都能直接消费 HTTP URL 上的 `text/plain` BibTeX),并在 `note` 字段里携带 reproduce.json 的 SHA-256,使得审稿人多年后仍可通过 `sha256sum --check` 验证该引用指向的是同一份模拟参数。

```bibtex
@misc{miroshark-sim_abc123def4,
  title        = {What if Aave's reserve factor doubled overnight?},
  author       = {MiroShark},
  year         = {2026},
  month        = may,
  url          = {https://miroshark.example.com/share/sim_abc123def456},
  howpublished = {\url{https://miroshark.example.com/api/simulation/sim_abc123def456/reproduce.json}},
  note         = {Reproducibility SHA-256: 5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8},
  annote       = {OriginTrail DKG UAL: did:dkg:base:8453/0xabc/12345},
}
```

- **稳定的引用键。** `miroshark-{sim_id[:16]}`,并剥除非 `[A-Za-z0-9_-]` 字符 — BibTeX 文法在引用键中只允许这些字符。相同输入 → 跨多次重渲染得到相同的键,因此一旦把键固定下来的作者绝不会看到他们的 `\cite{}` 引用被悄悄重接。
- **转义七个 BibTeX 特殊字符。** `&`、`%`、`$`、`#`、`_` 走规范的反斜杠转义;`{` 和 `}` 走反斜杠括号转义;反斜杠本身走 `\textbackslash{}`;脱字符与波浪号走 `\^{}` / `\~{}`。一个包含 "100% APY & a flash_loan exploit" 的情景在 LaTeX 中可以干净解析,无需手动清洗这一步。
- **可用时 SHA-256 取自链上锚点。** DKG 引用(`<sim_dir>/dkg-citation.json`)以 `sha256:<hex>` 形式存储 reproduce.json 的哈希 — BibTeX 构建器剥掉前缀,把裸十六进制摘要落进 `note` 字段。当不存在 DKG 引用时,构建器会重新对规范的 reproduce.json 字节做哈希(通过独立 `/reproduce.json` 路由所用的同一个 `repro_export.render_json_bytes`),因此 `note` 值与 `curl reproduce.json | sha256sum` 会产出的结果相匹配。
- **`annote` 在存在时记录 DKG UAL。** 阅读引用的审稿人可以顺着 UAL 找到链上断言、取回 Knowledge Asset,并验证其中记录的 reproduce.json 哈希与本地哈希相匹配 — DOI 级别的溯源,无需出版社中介。
- **Zotero / Mendeley 导入 URL 即端点 URL。** 把 `https://miroshark.example.com/api/simulation/<id>/cite.bib` 粘进 Zotero →「File → Import from URL」或 Mendeley →「Web Importer」,条目就会落进库中且元数据已预填。无需手动 BibTeX 导出步骤。
- **对输入采取防御姿态。** 缺失情景 → "Untitled MiroShark simulation"。缺失 / 无法解析的 `created_at` → 当前 UTC 年 + 月。缺失 `simulation_id` → `miroshark-unknown`(此种情况下路由处理器仍返回 404 — 该回退是为孤立地驱动渲染器的单元测试而存在的)。路由处理器在这个分享面上绝不抛异常 — 即便辅助文件缺失,引用也必须可用。

纯标准库 `hashlib` + `datetime` + `re`(`app/services/bibtex_service.py` 中约 310 LoC);零新增依赖 — 与 `signal_service`、`badge_service`、`repro_export` 姿态一致。渲染出的字节在相同输入的多次调用间逐字节确定(唯一由时间戳驱动的内容是可选的生成注释,而路由处理器会省略它),因此针对该条目字节锚定的引用链(未来的 ETag 层 / 基于哈希的缓存)跨请求保持稳定。

与其他每个分享面相同的发布门控(`is_public=true`)。`Content-Type: text/plain; charset=utf-8`,以便 Zotero 的 URL 导入器挑到正确的解析器,并附 `Content-Disposition: inline; filename="miroshark-<id12>.bib"`,以便 `curl -OJ` 保存后即可放进 `\bibliography{}` 块。缓存 5 分钟 — 与 `reproduce.json` + notebook 的节奏一致;一旦模拟到达终态条目即稳定。

嵌入对话框在可复现性配置面板下方暴露一个 `📖 BibTeX citation (.bib)` 区块:一个可复制的 `cite.bib` URL、一段 `curl -fsSL '<url>' -o miroshark-<id>.bib` 片段、一段可粘贴即用的 `\cite{miroshark-...}` LaTeX 引用片段(引用键由模拟 id 确定性派生,因此论文内引用语法在 `.bib` 文件被取回之前就已正确),以及一个用于另存流程的「Download .bib」锚点。`cite_bib` 计数器加入分享面统计的 schema,因此操作者可以独立于其他分享面看到该模拟正在驱动多少学术引用 — 这里的尖峰表明该模拟正在被某篇论文草稿引用。

把「MiroShark 是一款研究工具」从一句定位口号变成同行审稿人真正能跟随的引用链。

## 模拟归档打包

带离线的复合体 — 一个 ZIP,里面装着每一个已发布的分享面。在此之前,完成一次模拟的研究者要把这套工件带离线,得串起多达九个独立的 `curl` 调用(`share-card.png`、`chart.svg`、`trajectory.csv`、`trajectory.jsonl`、`transcript.md`、`thread.txt`、`reproduce.json`、`notebook.ipynb`、`signal.json`)。`GET /api/simulation/<id>/archive.zip` 把每一个成功渲染的分享面折叠进一个带时间戳的 ZIP,外加一份 `manifest.json`,它为每个包含的文件配上其 SHA-256、字节大小、MIME 类型和规范源 URL。

```json
{
  "schema_version": "1",
  "simulation_id": "sim_abc123…",
  "archive_generated_at": "2026-05-20T12:34:56Z",
  "base_url": "https://miroshark.example.com",
  "file_count": 8,
  "files": [
    {
      "filename": "share-card.png",
      "sha256": "<hex>",
      "size_bytes": 12345,
      "source_url": "https://miroshark.example.com/api/simulation/sim_abc.../share-card.png",
      "mime_type": "image/png"
    },
    {
      "filename": "chart.svg",
      "sha256": "<hex>",
      "size_bytes": 8192,
      "source_url": "https://miroshark.example.com/api/simulation/sim_abc.../chart.svg",
      "mime_type": "image/svg+xml"
    }
  ]
}
```

**组合式,非重复式。** 每个打包进来的文件都来自独立分享面路由本就提供的同一个渲染器 — `share_card.render_share_card`、`chart_svg.render_chart_svg_bytes`、`trajectory_export.render_csv` / `render_jsonl`、`repro_export.render_json_bytes`、`notebook_export.render_notebook_bytes`、`signal_service.compute_signal`、`transcript.render_markdown_bytes`、`thread_formatter.render_thread_txt`。`archive.zip` 里的文件与从其独立 URL 取回的同一文件逐字节相同,因此清单里的 SHA-256 与「对规范 URL 做哈希」工作流会算出的结果相匹配。针对 `reproduce.json` 的 OriginTrail DKG 哈希(PR #84)锚定的引用链在两条分发路径上彼此对齐。

**尽力而为式组装。** 每个分享面构建器都包在 `try/except` 中,缺失或损坏的工件会产生一个被省略的条目而非 `500`。清单中的 `file_count` + `files` 数组精确枚举了 ZIP 里究竟装入了什么 — 需要某个特定文件的消费方可以分辨它被排除是因为底层工件尚未就绪,还是因为该运行有 `n=0` 轮。

**确定性的文件时间戳。** 每个 `ZipInfo` 条目都携带相同的固定 `date_time`(`1980-01-01T00:00:00`),因此归档字节中逐文件的那一部分在相同输入集的两次构建间可复现。`manifest.json` 携带 `archive_generated_at`,它是跨请求间唯一的漂移 — 需要比特级稳定归档的消费方可以对包含的文件逐个做哈希(每个都逐字节确定)并忽略清单时间戳。

纯标准库(`zipfile` + `hashlib` + `io` + `json` + `datetime`)。零新增依赖 — 与其他每个分享面模块姿态一致。`archive_service.py` 约 430 LoC。

与其他每个分享面相同的发布门控(`is_public=true`)。当尚无可导出的分享面可用时返回 `404`(一个刚发布、尚未记录任何轮次的模拟 — 连 `signal.json` 和 `reproduce.json` 也需要一个最终信念块才能组合)。缓存 5 分钟 — 与 notebook + reproduce.json 的节奏一致,使得一次实时运行不断增长的轨迹会在一个轮询周期内传播出去。

嵌入对话框在交易信号行下方暴露一个 `📦 Archive bundle (.zip)` 区块:一个实时文件计数徽章(从 `X-MiroShark-Archive-Files` 响应头读取,这样对话框无需为渲染预览而下载整个 ZIP)、一个摘要网格(文件数 + 压缩格式 + 引用保证)、一个「Download archive.zip」锚点、一个可复制的 URL,以及一段可粘贴即用、使用服务器提供的文件名的 `curl -OJ` 片段。`archive_zip` 计数器加入分享面统计的 schema,因此操作者可以独立于各个单独分享面看到该归档驱动了多少带离线工作流。

闭合了九个独立端点靠自身无法闭合的*「研究者如何把一次模拟带回家」*缺口。

## 图库搜索与筛选

`/explore` 是公开研究界面 — 每一次发布的 MiroShark 模拟,都以卡片网格浏览。当语料库突破几十条后,反向时间序列的滚动列表就不再是工具,因此图库现在自带索引:卡片之上有一个关键词搜索框、一组共识筛选芯片、一组质量筛选芯片以及一个排序下拉。激活的筛选集合保存在 URL 参数中(`?q=…&consensus=bearish&quality=excellent&sort=rounds`),因此任意筛选视图都可作为书签分享 — "每一次关于 Aave 的优秀质量看跌预言"成了一个可发推文的 URL。

- **`q`** — 不区分大小写的情景文本子串匹配。已修剪;上限 200 字符。
- **`consensus`** — `bullish` / `neutral` / `bearish`。基于与分享卡 / 回放 GIF / 转录 / Webhook / 订阅源一致的 ±0.2 阈值的最终轮主导立场进行筛选,与那些界面在同一模拟上报告的内容保持一致。
- **`quality`** — `excellent` / `good` / `fair` / `poor`。与 `quality_health` 首词进行不区分大小写比较。
- **`outcome`** — `correct` / `incorrect` / `partial`。隐含 `verified=1`(仅已验证)。
- **`sort`** — `date`(默认 — 最新优先)、`rounds`(当前轮次最多优先)、`agents`(种群最大优先)或 `trending`(累计分享面服务次数最高优先 — 累加 `surface-stats` 端点暴露的每一个计数器;按日期打破并列,使「服务最多且最新」浮于「服务最多但陈旧」之上)。`trending` 是从分发分析回流到发现排序的首条反馈回路 — 被分享得越多的模拟会更容易被发现。
- **`page`** — 1 起编号的页号;`offset` 的替代值。`page=1` 即偏移 0。两者组合方式一致:`total` 反映**已筛选**的计数(而非语料库大小),所以"加载更多""剩余 X 个"提示和 `has_more` 标志在当前筛选集合内保持准确。

`/verified` 路由保留 `verifiedOnly: true` 模式,并与所有筛选条件兼容 — `/verified?q=aave&consensus=bullish` 是有效的。通过头部芯片在「已验证」与「Explore」之间切换时,会跨越路由切换沿用激活的查询字符串,用户不会因切换「已验证」而丢失搜索。

- **接口:** `GET /api/simulation/public?q=…&consensus=bullish&quality=excellent&sort=rounds&page=2`
- **与 verified 组合:** `GET /api/simulation/public?verified=1&consensus=bearish` 返回每一次有结果记录的看跌预言。
- **实现:** 公共端点已组装的图库卡片之上的纯标准库内存内筛选。零新依赖。端点保持 30 秒缓存,因此繁忙的图库会在多次筛选请求间摊销每次模拟的卡片构建。

筛选激活后会出现「📊 重置」按钮;空状态(「没有模拟符合你的筛选条件」)指回同一个重置入口,而不是回到本不适用的「暂无公开模拟」消息。

## 公开画廊订阅(RSS / Atom)

`/explore` 渲染的同一批卡片,以聚合订阅的形式提供出来,让已经在用 Feedly / Readwise / Inoreader / NetNewsWire / Obsidian RSS 的研究者和工具,可以在他们已有的工具链里订阅 — 无需登录,无需 MiroShark 账户。每个新发布的模拟,以与 AI 通讯或 Substack 文章相同的方式落入他们的阅读器。

两个端点,同一份载荷,不同 XML 格式:

- `GET /api/feed.atom` — Atom 1.0(首选 — 现代阅读器 + 浏览器自动发现的默认目标)。
- `GET /api/feed.rss` — RSS 2.0(为更老的自部署聚合器和学术 RSS 流水线保留)。

每个条目把情景作为标题(超过 100 字符以省略号截断),把 看涨 / 中立 / 看跌 共识分布作为摘要行,把分享卡 PNG 作为 `<media:thumbnail>` + `<media:content>`(这样 River-view 聚合器会显示预览图),把回放 GIF 作为第二个 `<media:content>`(这样 Feedly 的杂志布局会显示动画)。Outcome 与 quality 暴露为 `<category>` 元素,订阅者可以在自己的阅读器里据此过滤。

- **仅已验证订阅:** 附加 `?verified=1` 即可获取那些被运维者标记过真实结果的精选流 — 是 `/verified` 的聚合订阅镜像。
- **挑选规则:** 与 `GET /api/simulation/public` 完全一致 — 最近 20 个已发布运行,按 `created_at` 降序,受发布控制。
- **自动发现:** SPA 的 `index.html` 声明了 `<link rel="alternate" type="application/atom+xml">`(以及 RSS 变体),所以浏览器会通过地址栏地球图标暴露这个订阅源。
- **缓存:** `Cache-Control: public, max-age=300` — 五分钟够短,新发布的模拟能在下一次聚合器轮询时出现;够长,可以承住激进轮询而不拖累画廊查询。
- **实现:** 纯标准库(`xml.etree.ElementTree` + `html`)。无新增依赖;立场阈值与其他界面一样是 ±0.2,所以"62% 看涨"字符串与画廊卡片字节对字节一致。

嵌入对话框有一条"通过 RSS 关注画廊"的提示,带 Atom 订阅、RSS 2.0 订阅、仅已验证 Atom 订阅的一键订阅链接。/explore 头部有一个"📡 通过 RSS 订阅"芯片,会镜像当前激活过滤(开启已验证过滤时也会跟随)。

## 搜索引擎站点地图(`/sitemap.xml` + `/robots.txt`)

为网络搜索自动生成的发现面。其他每一个分享面(`/share/<id>`、`/watch/<id>`、RSS / Atom、回放 GIF)都让某个*单独*的模拟能被已经拿到链接的人找到。站点地图补齐的是*另一半* — 那些还不知道该模拟存在、但会搜索情景关键词的研究者和操作者。

`GET /sitemap.xml` 每次请求都会遍历一遍公开模拟语料库,并产出 Googlebot / Bingbot / DuckDuckBot 所期望的 sitemaps.org 0.9 XML 文档:

- 每个已发布模拟的 `/share/<id>` 页面对应一个 `<url>` 块(优先级 `0.8`,规范的引用面)。
- 每个已发布模拟的 `/watch/<id>` 页面对应一个 `<url>` 块(优先级 `0.7`,实时直播面)。
- `<lastmod>` 采用 W3C `YYYY-MM-DD` 形式,沿 `state.json` 的 `updated_at` / `created_at` / 文件 mtime 回退链派生。
- 进行中的模拟标 `<changefreq>always</changefreq>`(信念条确实每一轮都在变);已完成的 share 条目标 `weekly`,已完成的 watch 条目标 `daily`(运行终止后观看页重渲染得没那么频繁)。
- 模拟按 `simulation_id` 升序排序,这样针对同一语料库连续两次渲染产出的 XML 字节级完全一致。

`GET /robots.txt` 是配套的发现文件。每个部署都会提供它(无论站点地图是否启用),这样守规矩的爬虫就能看到 `Disallow: /api/` 指令,把 JSON 命名空间挡在搜索索引之外。启用站点地图时,末尾会多出一行 `Sitemap: <PUBLIC_BASE_URL>/sitemap.xml`,把爬虫指向它以实现自动发现 — 向 Google Search Console 提交一次,每个新发布的模拟都会在下次抓取时变得可搜索。robots 文件始终为公开发现面带上 `Allow:` 行(`/share/`、`/watch/`、`/explore`、`/verified`、`/embed/`),这样爬虫就知道自己被邀请进入哪些路由。

- **退出选项:** `ENABLE_SITEMAP=false`(默认 `true`)会让 `/sitemap.xml` 返回 `404`,并从 `robots.txt` 中去掉 `Sitemap:` 行。运行私有 MiroShark 实例 — 或对敏感情景做索引 — 的操作者会翻动这个开关。
- **有上界:** 上限为 50,000 个 `<url>` 条目(规范规定的每文件天花板)。MiroShark 的公开语料库目前只有三位数那么小;这个上限是针对病态批量分叉模式的纵深防御,而非常规的截断场景。
- **缓存:** `Cache-Control: public, max-age=3600` — 一小时这个频率足够快,能让新发布的模拟在下次刷新时浮现给爬虫;也足够慢,使得嘈杂的爬虫不会拖累图库查询。
- **实现:** `app/services/sitemap.py`(约 270 行代码,纯标准库 `xml.etree.ElementTree` + `os` + `datetime`)+ `app/api/sitemap.py`(挂载在根路径的 Flask 蓝图,无 `/api` 前缀,镜像 `share_bp` / `watch_bp`)。零新增依赖。

嵌入对话框里有一个「🔍 Discoverable in web search」提示块 — 与上方的 RSS 订阅区块相区分 — 带一个「View sitemap.xml ↗」链接。该开关来自一个公开的 `GET /api/config/sitemap` 端点,这样当操作者选择退出时,对话框就能渲染正确的提示。

## 实时观看页(观众直播)

这是在同一个磁盘上 `sim_dir/` 文件夹之上的第七个轻量渲染器。前六个(图库卡片、分享卡片、回放 GIF、文字记录、RSS / Atom 订阅、轨迹 CSV / JSONL)呈现的都是*已完成*的模拟;观看页呈现的是*正在进行*的模拟 — 这正是 MiroShark 此前缺失、用于"在模拟跑到一半时发推分享"的那种格式。

`GET /watch/<simulation_id>` 返回一个自包含的、服务器端渲染的 HTML 页面,为实时观看而构建:一个极简的全视口视图,带信念条、轮次计数器、智能体数量、质量健康度、进度条,以及一个原生 JS 轮询器,它每隔 15 秒命中既有的 `/api/simulation/<id>/embed-summary` 和 `/api/simulation/<id>/run-status` REST 端点,就地更新 DOM。一旦运行器到达终止状态(`completed` / `failed` / `stopped`),轮询停止,并显示「View full simulation →」+「Fork this scenario →」两个 CTA。

- **OG / Twitter 展开:** 页面 body 携带 `og:type`、`og:title`、`og:description`、`og:image`(1200×630 分享卡片 PNG)、`twitter:card=summary_large_image` 等 — 与 `/share/<id>` 相同的自动展开行为。对进行中的运行,`og:description` 变为 "Round N/M · Bullish X% · Neutral Y% · Bearish Z% — watch live.";对空闲的运行回退为裸情景;在尚无任何内容发布时回退为一个通用字符串。
- **自包含:** 不依赖 SPA 构建。轮询器是原生 JS,样式是内联的。可在精简部署上运行,可在仅允许 `img-src 'self'` 的严格 CSP 之后运行,甚至在禁用 JS 时也能工作(SSR HTML 仍会展示一个有意义的画面)。
- **发布门控:** 底层的实时端点尊重 `is_public`,因此私有模拟只渲染裸直播画面(无情景、无实时数字)。某个带该 id 的私有模拟*存在*这一事实,绝不会透过页面外壳泄露出去。
- **立场阈值一致:** bootstrap 数据块暴露页面用于看涨 / 中立 / 看跌划分的 ±0.2 立场阈值 — 与其他每个面相同的阈值,这样观众在 Twitter 上看到分享卡片、点进 `/watch/<id>` 后,不会看到数字在流程中途发生偏移。
- **缓存:** `Cache-Control: public, max-age=60` — 足够短,能让展开内容在新发布运行后保持合理的新鲜度;也足够长,能吸纳爬虫负载。
- **实现:** `app/services/watch_renderer.py`(纯标准库 `html` + `json`)+ `app/api/watch.py`(挂载在根路径的 Flask 蓝图,无 `/api` 前缀,镜像 `share_bp`)。零新增依赖。

嵌入对话框里有一个「Watch live (broadcast page)」提示块 — 与上方的分享卡片区块相区分 — 带一个「Open watch page ↗」按钮和一个可复制的 URL。该提示块受发布门控,以使这个可供性与底层行为相匹配。

## 推文串导出(X / Twitter)

继分享卡(视觉)、回放 GIF(动态)、转录(长文本)、轨迹 CSV/JSONL(数据)、实时观看页(直播)之后的第六种分享形式。前五种界面覆盖长篇、结构化或实时格式,这一个则是 X / Twitter 原生使用的**短文本通道** — 也是 Aaron 主要分发渠道所采用的格式。

两个端点,同一份载荷,不同序列化:

- `GET /api/simulation/<id>/thread.txt` — 纯文本推文串,每条推文一段,中间用单独一行 `---` 分隔,每条 ≤280 字符。可直接复制粘贴到 X 撰写框,或上传到按 `---` 分隔的推文排程器(Typefully、Hypefury、Tweet Hunter、Twittascope)。
- `GET /api/simulation/<id>/thread.json` — 同样的内容以 `{tweets: [string], total: int, inflections_recorded: int, truncated: bool}` 返回。程序消费者可直接遍历 `tweets`,无需按分隔符拆分。

推文串结构:

1. **介绍推文** — 情景摘要(超过约 200 字符以省略号截断)+ 规模(`N rounds · M agents`)+ 最终共识标签(`Consensus: Bullish` / `Neutral` / `Bearish` / `split`)+ 串号 `1/`。
2. **正文** — 每个**信念转折点**(主导立场跨越 ±0.2 阈值并领先次位 ≥0.2pp 的轮次;持平 / 无主导的轮次作为噪音被跳过)对应一条推文。格式:`"Round N: stance shifted to <label>"` + 立场行 `"↑ Bullish X% · → Neutral Y% · ↓ Bearish Z%"`。
3. **结尾推文** — `Final: <label> consensus` + 同一立场行 + `Quality: <health>` + `Watch the replay: <watch_url>` + `Run this scenario: <share_url>`。

正文转折点超过 `MAX_THREAD_TWEETS - 2 = 13` 条时,会被截断为前 3 + 后 3 个转折点,加一条桥接行(`… N more flips between here and the close …`);JSON 形式的 `truncated: true` 会标记此情况发生。与分享卡一致的发布控制(`is_public=true`);与其他界面一致的 ±0.2 立场阈值;结尾推文的 watch + share URL 遵循 `X-Forwarded-Proto` / `X-Forwarded-Host`。

嵌入对话框在轨迹那行下方有「🧵 推文串」区块:一个「复制整串」按钮(用 `\n---\n` 拼接每条推文,一次粘贴即可生成有效的 X 推文串)、`.txt` 与 `.json` 两种形式的下载链接,以及一个内联的推文列表(每条推文都有独立的复制按钮和字符计数器),让运维者挑选要发布的单条推文。

实现:`app/services/thread_formatter.py`(纯标准库 `json` + `os`,~430 行)+ `app/api/simulation.py` 中的 `_serve_thread()` 共享函数体,镜像 `_serve_transcript` / `_serve_trajectory` 模式。零新增依赖。

## 分发统计(分享面使用分析)

第一个**入站**可观测性界面,与出站 Webhook 投递日志相对应。每一次成功的分享面响应都会在磁盘上(`<sim_dir>/surface-stats.json`)递增一个计数器;`GET /api/simulation/<id>/surface-stats` 返回每个分享面的计数,让运维 MiroShark 的 DeFi 基金或研究小组,能看到他们的受众实际上使用的是哪一个面。

跟踪的计数器(每个分享面一个):

- `share_card` — `share-card.png` 服务次数
- `replay_gif` — `replay.gif` 服务次数
- `transcript_md` / `transcript_json` — `transcript.md` / `transcript.json` 服务次数
- `trajectory_csv` / `trajectory_jsonl` — `trajectory.csv` / `trajectory.jsonl` 服务次数
- `chart_svg` — `chart.svg` 服务次数(可缩放的逐轮信念图 SVG)
- `thread_txt` / `thread_json` — `thread.txt` / `thread.json` 服务次数
- `watch_page` — `/watch/<id>` 服务次数(仅公开模拟)
- `feed_atom` / `feed_rss` — 此模拟出现在已渲染的 Atom 或 RSS 订阅源中的次数
- `reproduce_json` — `reproduce.json` 服务次数(引用基元 — 每次抓取都对应一次复现尝试)
- `lineage` — `/lineage` 服务次数(谱系导航 — 每次抓取都对应一次研究者在派生树上的浏览)

以及一个合成的 `total` 字段汇总所有计数器。每个键都始终存在(零默认),因此前端无需为缺失字段做特殊处理。

实现:

- **原子写入。** 每次递增是一个通过 tempfile + `os.replace` 的读-改-写过程,确保两个并发请求不会把 JSON 截断为 `{` 而丢失全部历史计数。与 webhook 投递日志使用同一模式。
- **有界。** 单个小型 JSON 对象 — 仅 `SURFACE_KEYS` 中的键被持久化;来自调用方的未知键会被静默丢弃,绝不会写入。
- **fire-and-forget。** 递增永远不抛异常;损坏的计数器文件会被静默重置为零。即使分析层故障(只读挂载、磁盘满、暂存文件被杀毒锁定),服务路径也始终成功。
- **仅标准库。** `json` + `os` + `tempfile`。零新增依赖。

嵌入对话框有「📊 分发统计」面板(默认折叠,点击 ▾ 展开)— 一个有序的两列表(分享面 · 计数,按计数倒序排序),一个「总服务数:N」行,以及一个「↻ 刷新」按钮。该面板有发布门控;私有模拟会显示「发布模拟以查看分发统计。」。与每个其他分享面一样的发布门控(`is_public=true`)。

## 可复现配置导出

每个分享面背后的**引用基元**。十个分享面中的六个(转录、轨迹、推文串、观看页、GIF、分享卡)让一次完成的模拟可被引用 — 但在此端点上线前,它们都没有携带复现该次运行所需的参数。PR #71 的可分享情景 URL 携带了情景文本与模板 slug;此 blob 携带其余的一切,以一份美化打印的文件呈现,适用于论文附录或推文截图。

`GET /api/simulation/<id>/reproduce.json` 返回一份 v1-schema 的 JSON 文档,字段包括:

- **`schema_version`** — 字面量 `"1"`。破坏性变更时升级;v1 解析器应拒绝其他值。
- **`exported_at`** — 导出时刻的 UTC ISO-8601 时间戳。
- **`simulation_id`** — 回显的模拟 ID。
- **`scenario`** — 模拟需求 / 情景文本。对于将 `simulation_requirement` 写入 state 而非生成配置的旧模拟,会回退至 state 字段。
- **`agent_count`** — 该次运行生成的智能体档案数(对应 `state.profiles_count`)。
- **`total_rounds`** — 模拟运行(或配置运行)的总轮次。优先取 runner 记录的总数;当 runner 尚未填充该字段时回退至 `time_config.total_simulation_hours * 60 / time_config.minutes_per_round`。
- **`platforms`** — 决定智能体发帖到哪些渠道的四个布尔 / 整数参数:`twitter`、`reddit`、`polymarket`、`polymarket_market_count`。
- **`time_config`** — 驱动模拟时序包络的四个节拍旋钮:`minutes_per_round`、`total_simulation_hours`、`peak_hours`、`off_peak_hours`。字段集刻意收窄:LLM 生成的完整配置还包含每代理发帖频率 + 事件计划 + 平台调优,但那些是从实体图谱派生的,并非研究者手工复现的参数。
- **`director_events`** — 操作者注入的情景事件(如第 15 轮的「流动性危机」),它们形塑了信念曲线。当未注入事件时为 `null`(常见情形)。每个事件携带 `round`、`label` 与可选 `description`。
- **`lineage`** — 描述此次模拟的创建路径。`kind` 取值之一:`original`(经标准 prepare 流程创建)、`fork`(经 `POST /api/simulation/fork` 创建,代理种群相同、新模拟 ID)、`counterfactual`(经 `POST /api/simulation/branch-counterfactual` 创建,即 fork 加上某一轮调度的注入事件)。携带 `parent_simulation_id`,对反事实分支额外携带 `counterfactual` 子对象,内含 `trigger_round` / `label` / 140 字符 `preview`,使徽章可在不二次请求的情况下渲染头条。
- **`config_reasoning`** — prepare 时刻捕获的 LLM 选择各旋钮的理由。未持久化此理由的旧模拟为空字符串。

实现:

- **仅标准库。** `json` + `os`。零新增依赖;辅助函数位于 `app/services/repro_export.py`。
- **只读。** 该服务从磁盘工件(`state.json`、`simulation_config.json`、`counterfactual_injection.json`、可选的 director 事件)组装该 blob — 永不写入。
- **schema 锁定。** `SCHEMA_VERSION` 常量 + `REQUIRED_KEYS` 冻结集 — 下游消费者可以通过 `validate_blob(blob)` 廉价校验。
- **纵深防御。** 工件损坏时降级为 `null`,而不让导出 500 — 引用面必须在辅助文件缺失时仍可用。
- **字节级稳定。** 美化打印(indent=2、sort_keys=True)— 同一已完成模拟的多次导出在字节层面完全一致。文件哈希因此可作为稳定的引用键。

缓存 5 分钟;模拟到达终止状态后,blob 不再变化。与其他分享面一样的发布门控 — 要求模拟为公开(`is_public=true`)。

嵌入对话框有「🔬 可复现配置」面板(默认折叠)— 概要网格(Schema 版本 · 智能体 · 轮次 · 平台 · 导演事件 · 谱系)、可一键复制的「使用 curl 复现」片段、`下载 reproduce.json` 按钮,以及(当模拟为派生或反事实分支时)标题旁的小型内联谱系徽章 — `🪐 派生` 或 `🔀 反事实`。徽章 tooltip 展示父模拟规范 ID,操作者无需阅读 JSON 即可获取它供 `/share/<id>` 或 `/watch/<id>` 使用。

## Jupyter Notebook 导出

这是可复现性配置的**可供分析**伴侣 — 第二个面向机构的导出。轨迹 CSV 告诉分析师*"这是数据"*;notebook 告诉他们*"这是分析,开箱即跑。"*落到某个已发布模拟上的机构观察者(Lorimer-Ventures 这一层级)下载单个 `.ipynb` 文件,在 JupyterLab / VS Code / Google Colab 中打开 — 无需自己写 `pd.read_csv()` + `import matplotlib.pyplot as plt` + 坐标轴配置这类样板代码。

`GET /api/simulation/<id>/notebook.ipynb` 返回一个 nbformat 4 JSON 文档,带一个锁定的七单元格序列:

1. **Markdown 头部。** 模拟 id、以引用块呈现的情景、运行元数据表(智能体 · 轮次 · 平台 · 谱系 · 质量健康度 · generated_at)、可复现性 URL 链接。
2. **代码:导入。** 一行被注释掉的 `%pip install --quiet pandas matplotlib`,供尚未装这些包的内核使用;外加 `import io / pandas as pd / matplotlib.pyplot as plt`。
3. **代码:轨迹加载。** 完整的 `trajectory.csv` 内容作为 Python 字符串字面量(通过 `repr()`,因此任何字节序列 — 包括任意数量的连续引号、反斜杠、内嵌换行 — 都能正确往返)直接嵌入 notebook 内部,然后通过 `pd.read_csv(io.StringIO(TRAJECTORY_CSV))` 读取。任何运行该单元格的人,拿到的字节都与 `trajectory.csv` 端点所提供的相同。该单元格以 `df.head()` 收尾,用于预览 DataFrame。
4. **代码:信念演化图。** 三线图(看涨 / 中立 / 看跌百分比随轮次变化),使用与其他每个面相同的 `#22c55e` / `#6b7280` / `#ef4444` 调色板,这样此图的截图与分享卡片可粘贴兼容。
5. **代码:最终轮共识。** 最终立场分布的柱状图,每根柱带百分比标注。
6. **代码:质量 + 参与度摘要。** 一个小的 `pd.DataFrame`,汇总行数、首/末轮次、唯一的 `quality_health` 取值,以及最后一个非空的 `participation_rate`。一眼即可看到运行健康度,无需扫描整个 DataFrame。
7. **Markdown 尾部。** 可复现性元数据(notebook schema 版本、模拟 id、轨迹 SHA-256 哈希、完整的 reproduce.json 链接)。SHA-256 让评审者能验证嵌入数据在文件下载后未被篡改。

实现:

- **可独立运行。** 轨迹数据存在 notebook 本身内部 — 点击 Run All 时无需回连 MiroShark 主机做网络调用。这对论文附录的附件,以及评审内核被沙箱化的学术归档环境(还有那些企业防火墙阻断出站 HTTP 的机构分析师)都很重要。
- **纯标准库。** `json` + `os` + `hashlib`,外加复用 `trajectory_export.build_rows` 来组装 CSV 行,使嵌入的数据与 `trajectory.csv` 所提供的字节级一致。图表代码单元格是字符串 — Matplotlib 是在用户运行的单元格内部被引用的,在生成时绝不导入。零新增依赖。辅助函数在 `app/services/notebook_export.py`。
- **字节级稳定。** 与可复现性配置相同的 `sort_keys=True + indent=2 + 尾随换行` 模式,因此对同一个已完成模拟的两次导出会产出字节级一致的 notebook。该文件哈希因此是一个稳定的引用键,与 `reproduce.json` 数据块具有相同的性质。
- **schema 锁定。** `SCHEMA_VERSION = "1"`,外加一个固定单元格类型序列的 `CELL_ORDER` 常量。那些钉死"图表单元格在索引 4"的下游工具,在小幅重构后依然正确。
- **纵深防御。** 缺失的产物(模拟仍在运行、轨迹损坏、无质量文件)会优雅降级 — notebook 仍会渲染,只是嵌入的 CSV 行数可能更少。

缓存 5 分钟;与其他每个分享面相同的发布门控 — 要求 `is_public=true`。嵌入对话框里有一个「📓 Jupyter notebook」面板,位于可复现性配置下方 — 一段可复制的「Download via curl」代码片段、一个「Download notebook.ipynb」按钮,以及一个「Copy URL」按钮。这个下载面有意保持纯粹 — 没有内联预览,因为 `.ipynb` body 是一个 30 KB 以上的 JSON 文档,SPA 不该仅仅为了渲染一个按钮就把它拉下来。

## 模拟谱系导航

弥补 PR #75 可复现配置导出留下的导航空白。每个派生 / 反事实分支磁盘上都有 `parent_simulation_id` 指针,但谱系是**单向的** — 子模拟知道父级,父级却看不到子级。某位研究者跑完一个基础情景后,触发了三个反事实分支,他必须记住每个子模拟的 ID;无法从父级直接「跳到第 12 轮分叉的三条分支」。

`GET /api/simulation/<id>/lineage` 返回以请求模拟为根的谱系图切片:

- **`simulation_id`** — 回显请求 ID。
- **`lineage_kind`** — `"original"` / `"fork"` / `"counterfactual"`。镜像 reproduce.json 的 `lineage.kind`。
- **`parent`** — 父模拟条目(`simulation_id`、截至 80 字符的 `scenario_preview`、`created_at`、`is_public`),原始模拟为 `null`。如果父级事后被取消发布,条目仍保留但 `is_public=false` 且 `scenario_preview` 为空,前端可据此渲染占位行。
- **`children`** — `parent_simulation_id` 指回当前模拟的所有**公开**模拟。每个子级携带自己的 `kind`(`fork` / `counterfactual`)以及可选的 `counterfactual` 子对象(`trigger_round` + `label`),让徽章可直接渲染「🔀 第 12 轮反事实(ceo_resigns)」。按 `created_at` 升序排序 — 最早派生在前,符合自然叙事顺序。最多 50 条。
- **`total_children`** — 仅公开模拟的全部数量,即使响应被上限截断也保持准确。
- **`counterfactual`** — 当请求模拟自身就是反事实分支时,触发轮 + 标签随响应一同返回,面板无需再次请求 `reproduce.json` 即可显示标题。

实现:

- **纯标准库。** `json` + `os`。辅助逻辑在 `app/services/lineage_service.py`,零新依赖。
- **只读。** 服务由请求模拟和候选子集的磁盘 `state.json` 文件组成响应,从不写入。
- **仅公开子级。** 操作者私下派生的进行中分支不会泄漏到已被推文的父级谱系视图中。
- **纵深防御。** 扫描时 `state.json` 正在写入或损坏的子模拟会被静默跳过 — 谱系视图永远不会让加载崩溃。手工编辑后自指向自己的边缘情况不会引发递归。
- **有上限。** `MAX_CHILDREN = 50` 上限是针对病理性派生的纵深防御;突破上限的模拟极为罕见,`total_children` 仍反映未截断的真实计数,UI 可显示「显示前 N / 共 M」。

缓存 5 分钟;父模拟和分支到达终止状态后,图切片不再变化。与其他分享面相同的发布门控 — 要求模拟公开(`is_public=true`)。

嵌入对话框有「🌳 谱系」面板,只要存在可导航对象(父级、若干子级或两者)就会自动显示。无派生的原始模拟看不到此面板 — 对话框保持发布前的紧凑度。面板把父级渲染为单行卡片(60 字符情景预览 + 「打开父级 ↗」链接),每个公开子级渲染为可点击行,标签为 `🪐 派生` 或 `🔀 反事实`。反事实行内联触发轮 + 标签(「第 12 轮(ceo_resigns)· 情景预览…」),让此行读起来更像叙事事件,而非略有不同的情景。点击任意行会在新标签页打开对应模拟的 `/watch/<id>` 页面。

## Webhook 投递日志

每一次 Webhook 投递尝试(在 **设置 → 集成 → Webhook** 中配置,详见 [WEBHOOKS.zh-CN.md](WEBHOOKS.zh-CN.md))都会在 `<sim_dir>/webhook-log.jsonl` 追加一行 JSON。每行记录:

- **`attempt`** — 1 起单调递增计数器(磁盘截断到 50 行后仍持续递增)。
- **`timestamp`** — 投递完成的 UTC ISO-8601 时间。
- **`url_masked`** — `scheme://host/***`。Slack / Discord webhook URL 路径中的密钥**绝不**写入磁盘。
- **`event`** / **`status`** — 投递载荷的 `event` 字段(`simulation.completed` / `simulation.failed`)与运行到达的终止状态。
- **`status_code`** — 下游端点返回的 HTTP 状态码,对网络错误 / 超时为 `null`(便于把真实 5xx 与 TCP 重置区分开)。
- **`ok`** — 2xx 响应为 `true`,其他情况为 `false`。
- **`latency_ms`** — HTTP 调用的实测耗时(毫秒)。
- **`error`** — 失败时的可读上游错误字符串(例如 `HTTP 503`、`URL error: timeout`);成功时为 `null`。
- **`trigger`** — runner 自动触发为 `auto`,运维者通过重试端点驱动为 `retry`。

两个端点暴露日志:

- **`GET /api/simulation/<id>/webhook-log`** — 需管理员 token。返回最近 10 条记录(从新到旧)+ 全程 `total_attempts` 计数器 + 磁盘留存上限(`max_retained: 50`)。运维者据此核对 webhook 是否触发、看 HTTP 状态 / 延迟,以及决定是否重试。
- **`POST /api/simulation/<id>/webhook-retry`** — 需管理员 token。重发已经处于终止状态的模拟的完成 webhook(原投递偶发 5xx、URL 当时配错、消费集成当时宕机时有用)。重发载荷带 `retry: true`,下游消费者可据此对重放去重。绕过自动触发路径使用的进程内 `(sim_id, status)` 去重门(那道门只防止 runner 的两条终止代码路径自动双发;运维者显式重试理应总能通过)。未配置 webhook URL 时返回 400,模拟尚未到达终止状态时返回 409。

嵌入对话框在 outcome 行下方有一个 **📡 Webhook 投递历史** 面板(需管理员 token,默认折叠以保持对话框紧凑,适配未配置 webhook 的用户)。每次投递渲染为状态 chip(✓ 绿色对应 2xx,✗ 红色对应 4xx/5xx,⏱ 琥珀色对应超时),含 HTTP 状态码、延迟、触发标签和时间戳。**刷新** 重新拉取日志;**重试投递** 重发 webhook 并在短暂延迟后刷新,以便新一次投递自动出现。

调度器在 POST 返回(或超时)之后才写盘,所以投递路径仍是 fire-and-forget — 日志写入永远不会阻塞模拟 runner。日志写入采用读-改-重命名模式(通过 `os.replace` 原子化),日志永远不会因部分写入而损坏。URL 在序列化前就掩码,所以 Slack / Discord URL 中的密钥落盘那刻便已不存在。

实现:`app/services/webhook_service.py` 中的辅助(`_record_delivery`、`_append_log_entry`、`read_webhook_log`、`retry_webhook_for_simulation`)+ `_start_dispatch_thread` 在自动触发与重试路径间共享。零新增依赖(纯标准库 `json` + `os` + `time` + `threading`)。磁盘上限 50 行;旧投递自动滚出,日志永不无界增长。

## Webhook 签名验证

当配置了 `WEBHOOK_SECRET` 时,每一份出站 webhook 载荷都会被 HMAC 签名,摘要通过 `X-MiroShark-Signature: sha256=<hex>` 头部和现有的 `X-MiroShark-Event` / `X-MiroShark-Sim-Id` 一起送出。消费方可以据此证明载荷确实来自这台 MiroShark — Stripe 和 GitHub 的出站 webhook 用的就是同一套方案,消费侧用三行 stdlib `hmac` 就能完成校验。

- **对原始 body 签名。** 摘要是基于走线的字节计算的,在消费侧做任何重新序列化*之前*。消费方必须在解析 JSON 之前完成验证 — 重新序列化可能改变字段顺序或空白,从而破坏摘要。
- **`sha256=<64 个十六进制字符>` 格式。** 与 Stripe / GitHub 同形。永远小写十六进制;摘要固定 64 字符长度。
- **向后兼容。** 当 `WEBHOOK_SECRET` 未设置或留空时,头部会被完全省略,已有集成无需任何改动即可继续工作。未配置密钥的消费方应当把「没有签名头」当作「未配置签名」处理,自行决定是否接受未签名的投递。
- **仅用于传输层。** 密钥永远不会写入投递日志(`webhook-log.jsonl` 只记录脱敏 URL,绝不保存密钥或签名)。在两端同时轮换密钥是零停机操作 — 在飞行中的重试会使用调度时刻已设置的值。
- **重试各自签名。** 重试端点会向载荷加入 `retry: true`,body 字节随之改变,签名也随之改变。每次投递(自动触发或运维者重试)都会带上为其自身 body 计算的签名。
- **常数时间验证。** 公开的 `verify_signature` 辅助(在 `app/services/webhook_service.py` 中)使用 `hmac.compare_digest`,网络上的攻击者无法通过时序差侧信道试出签名。[WEBHOOKS.zh-CN.md](WEBHOOKS.zh-CN.md) → 「验证 webhook 签名」中的代码片段遵循同样的模式。

实现:`compute_signature(payload_bytes, secret=None)` 在调用时读取 `WEBHOOK_SECRET`(所以一次 Settings 变更或环境变量改动会立即生效),返回 `"sha256=" + hmac.sha256(secret, body).hexdigest()` 或在留空时返回 `None`。`_post_json` 仅在 `compute_signature` 返回非 None 时才注入头部 — 自动触发、重试、以及「发送测试事件」按钮共享同一条调度路径,所以三条路径的签名行为完全一致。零新增依赖(纯标准库 `hmac` + `hashlib`)。

## Webhook 事件过滤

当设置了 `WEBHOOK_EVENTS` 时,MiroShark 在源头过滤分发 — 每个完成载荷在守护线程被派生之前,都会针对这份逗号分隔的允许列表做评估,不匹配的载荷会被记录并丢弃。当某个集成方只关心整条流中的一个切片时很有用:订阅了 `bullish,bearish,high_confidence` 的 Polymarket 机器人、订阅了 `excellent_quality` 的研究流水线、订阅了 `bearish` 的看跌翻转告警器。原有行为被保留 — 空白或未设置的 `WEBHOOK_EVENTS` 会像以前一样在每次完成时触发。

- **三个类别。** 方向 token(`bullish` / `neutral` / `bearish`)在各自内部取 OR;置信度 token(`high_confidence` >= 75%,`medium_confidence` 50–75%)在各自内部取 OR;质量 token(`excellent_quality`、`good_quality` = good 或 excellent)在各自内部取 OR。类别之间以 AND 组合:`bullish,high_confidence,excellent_quality` 意味着三者都必须成立。
- **方向派生方式一致。** 主导立场规则与分享卡片颜色、Discord 嵌入边框,以及其他每个报告"看涨 / 中立 / 看跌"的面相匹配 — 这里的 `bullish` 指的就是观看者会称之为看涨的那批模拟。
- **失败的模拟总会触发。** `simulation.failed` 绕过每条规则。一个会吞掉操作者添加 webhook 正是为了捕获的那一条告警的过滤器,会比完全没有过滤器更糟糕。
- **未知 token 被忽略。** 像 `WEBHOOK_EVENTS=bulish` 这样的拼写错误会作为"无可识别规则"落空并正常分发 — 过滤器绝不会悄悄把自己禁用掉。
- **延迟绑定。** `WEBHOOK_EVENTS` 在每次分发尝试时读取(与 `WEBHOOK_URL` 和 `WEBHOOK_SECRET` 相同的 `os.environ` 延迟绑定),这样操作者无需重启就能翻动过滤规则。
- **被抑制的投递只记录、不持久化。** 被过滤掉的触发会发出一行 `info` 日志,带解析出的 token 集合、载荷的派生值,以及未通过的类别 — 但不会向 `webhook-log.jsonl` 写入任何行(只有被尝试的投递才会写;检视该日志的操作者只会看到实际发出去的内容)。

实现:`_resolve_event_filter()` 把 `WEBHOOK_EVENTS` 解析为小写 token 集合;`payload_passes_event_filter(payload, events)` 返回 `(bool, trace_dict)`,使用与既有分享卡片 / Discord 嵌入渲染器共享语义的辅助函数(`_payload_direction`、`_payload_confidence_pct`、`_payload_quality_key`)来评估方向 / 置信度 / 质量规则。`fire_webhook_for_simulation` 在 `_mark_fired` 和 `_start_dispatch_thread` 之间调用该过滤器;手动重试端点有意绕过过滤器(由操作者驱动,与去重绕过类似)。零新增依赖。向后兼容 — 空白的 `WEBHOOK_EVENTS` 会字节级返回原有代码路径。

## 频道原生完成通知(Discord + Slack + Email)

通用 webhook(`WEBHOOK_URL`)推送的是原始 JSON — 对 Zapier / Make / n8n 完美匹配,但 Discord 不会从 JSON 渲染任何东西,Slack 会把它原样塞进一个难看的代码块。三条频道原生路径把已格式化的卡片(或邮件)分别送到对应平台:

- **Discord 富嵌入** — 设置 `DISCORD_WEBHOOK_URL`(Discord → 服务器设置 → 集成 → Webhooks)。MiroShark 推送一份 Discord embed:情景标题、按共识着色的边框(`#22c55e` bullish / `#6b7280` neutral / `#ef4444` bearish / `#f59e0b` failed)、Bullish / Neutral / Bearish / Quality / Rounds / Agents 字段、分享卡缩略图、可点击的分享页链接。失败运行会附加截断后的退出码错误作为 `Error` 字段。
- **Slack Block Kit** — 设置 `SLACK_WEBHOOK_URL`(api.slack.com/apps → Incoming Webhooks)。MiroShark 推送一条 Block Kit 消息:情景标题块、状态动词上下文行、`mrkdwn` 信念条(`█████░░░░░ 52.0%`)、Quality / Scale / Resolution 字段,以及一个 "View simulation" 操作按钮。失败运行会附加一个 fenced-code 错误段。
- **SMTP 完成邮件** — 设置 `SMTP_HOST` 与 `SMTP_TO`(逗号分隔的收件人列表)。MiroShark 发出一封 `multipart/alternative` 邮件:主题为 `[MiroShark] Bullish: <情景>`,邮箱过滤规则只看主题就能按方向分流;纯文本部分使用与 Slack 相同的 Unicode 块字符信念条;HTML 部分采用与 Discord 同色系的内联色块,以及按共识着色的「View simulation →」CTA。`SMTP_USER` / `SMTP_PASSWORD` 可选,支持无认证中继(`localhost:25`、自建 Postfix);587 端口尝试 STARTTLS,STARTTLS 失败时若已设置凭据会拒绝明文发送。这是唯一一个零平台依赖的通知通道 — 每位运营者都已经有邮箱。

四个通道彼此独立。设置一个、两个、三个或全部四个 — 每个通道都在每次 `simulation.completed` / `simulation.failed` 事件上独立触发,按 `(sim_id, status)` 去重,所以 runner 的两条终止代码路径不会产生重复卡片。SPA 通过 `GET /api/config/notifications` 暴露 `{webhook_configured, discord_configured, slack_configured, email_configured}`,EmbedDialog 据此在分享 / 嵌入面上实时显示状态指示。纯标准库 `urllib.request` + `smtplib` — 零新增依赖。完整接入指南见 [NOTIFICATIONS.zh-CN.md](NOTIFICATIONS.zh-CN.md)。

## 文章生成

模拟结束后,点击 **Write Article**,MiroShark 会让 Smart 模型写一篇 400–600 字的 Substack 风格报道,基于真实发生的事件 — 关键发现、市场动态、信念变化和影响。文章会缓存到 `generated_article.json`,这样重新打开不会再消耗 token;传 `force_regenerate=true` 可以刷新。

- **端点:** `POST /api/simulation/<id>/article`

## 交互网络与人口分布

两个不需要 LLM 调用的事后分析:

- **交互网络**(`GET /api/simulation/<id>/interaction-network`) — 从点赞/转发/回复/提及构建一张智能体之间的图,带度中心性、桥接得分和回声室指标。缓存到 `network.json`。在 **InteractionNetwork** 面板上以力导向图渲染。
- **人口分布**(`GET /api/simulation/<id>/demographics`) — 把智能体聚类成原型(分析师、KOL、散户、观察者……)并报告每个桶的分布 + 参与度。适合定位是哪个原型在主导某个叙事。

## 模拟质量诊断

每次运行都会在 `GET /api/simulation/<id>/quality` 拿到一个健康分数 — 参与度密度、信念连贯性、智能体多样性、动作方差。展示这次运行是跑到了距离还是塌成了噪声/沉默。如果连贯性低,报告大概率单薄。

## 历史数据库

**HistoryDatabase** 面板(从任意视图通过数据库图标进入)是一个面向所有本地模拟的功能完备浏览器 — 按提示词/文档/标签搜索、按状态过滤、克隆现有运行连同其智能体人群、导出为 JSON,或删除。背后由 `GET /api/simulation/list`、`GET /api/simulation/history`、`GET /api/simulation/<id>/export` 与 `POST /api/simulation/fork` 支撑。

## 轨迹访谈(调试)

普通的人设对话只显示智能体回复。轨迹访谈则展示整条链 — 观察提示词、LLM 思考、解析后的动作、有调用就连工具调用一起 — 针对某个智能体在某个时间点。当一次访谈回答看起来不对劲时,这对解释*为什么*智能体说了它说的话非常宝贵。

- **端点:** `POST /api/simulation/<id>/agents/<agent_name>/trace-interview`、`GET /api/simulation/<id>/interviews/<agent_name>`

## 推送通知(PWA)

前端注册了一个 Service Worker,在长时间运行的工作完成时(图谱构建完成、模拟结束、报告就绪)可以触发 web-push 提醒。在被提示时授予通知权限即可启用;后端在 `GET /api/simulation/push/vapid-public-key` 提供 VAPID key,在 `POST /api/simulation/push/subscribe` 接受订阅。用 `POST /api/simulation/push/test` 测试。如果你不需要可以放心忽略 — 不主动启用就是静默 no-op。
