<sup>[English](FEATURES.md) · 中文</sup>

# 特性

每个特性的深入介绍。一个特性一个标题,大致按你在一次典型运行中遇到它们的顺序排列。

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

## 模拟轨迹导出

它是分享卡(预览)和回放 GIF(动态)的文本同伴 — 把同一次模拟做成一份可引用的逐轮智能体轨迹,这样研究论文、Substack 帖子、Discord 串可以直接引用智能体说过的话,而不必截图。

两个端点,同一份载荷,不同编码:

- `GET /api/simulation/<id>/transcript.md` — 带 YAML 前言区块(`sim_id`、`scenario`、`agent_count`、`total_rounds`、`consensus_label`、`quality_health`、`outcome_label`)的 Markdown。Notion、Obsidian、Bear、Substack 会把它当成页面元数据来读;正文按已记录的轮次,每个轮次一个 `## Round N` 段,每个智能体的帖子作为一段引用块,并用智能体的立场打标。超过约 80 轮的轨迹在 Markdown 渲染中省略中间轮次(并附一条注释指向 JSON 形式以获取完整序列),让文档保持可读。
- `GET /api/simulation/<id>/transcript.json` — 同一份载荷的结构化 JSON 文档,美化输出(`indent=2`),这样 `curl` 到一个文件就能立刻可读。面向 SDK 用户和下游流水线(LLM-as-judge 评测框架、Python 客户端 SDK 等)。

两个端点共享分享卡的发布控制(`is_public=true`)。每个智能体的立场标签使用与其他界面一致的 ±0.2 阈值 — 画廊上的"看涨"智能体在轨迹里也会打同样的 tag。嵌入对话框在回放 GIF 那行下方暴露"下载 .md" + "下载 .json"组合。

## 图库搜索与筛选

`/explore` 是公开研究界面 — 每一次发布的 MiroShark 模拟,都以卡片网格浏览。当语料库突破几十条后,反向时间序列的滚动列表就不再是工具,因此图库现在自带索引:卡片之上有一个关键词搜索框、一组共识筛选芯片、一组质量筛选芯片以及一个排序下拉。激活的筛选集合保存在 URL 参数中(`?q=…&consensus=bearish&quality=excellent&sort=rounds`),因此任意筛选视图都可作为书签分享 — "每一次关于 Aave 的优秀质量看跌预言"成了一个可发推文的 URL。

- **`q`** — 不区分大小写的情景文本子串匹配。已修剪;上限 200 字符。
- **`consensus`** — `bullish` / `neutral` / `bearish`。基于与分享卡 / 回放 GIF / 转录 / Webhook / 订阅源一致的 ±0.2 阈值的最终轮主导立场进行筛选,与那些界面在同一模拟上报告的内容保持一致。
- **`quality`** — `excellent` / `good` / `fair` / `poor`。与 `quality_health` 首词进行不区分大小写比较。
- **`outcome`** — `correct` / `incorrect` / `partial`。隐含 `verified=1`(仅已验证)。
- **`sort`** — `date`(默认 — 最新优先)、`rounds`(当前轮次最多优先)或 `agents`(种群最大优先)。
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
