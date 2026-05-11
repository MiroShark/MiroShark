<sup>[English](WEBHOOKS.md) · 中文</sup>

# Webhook

MiroShark 会在某次模拟到达终态(`completed` 或 `failed`)的瞬间,向你指定的 URL 发起一次出站 HTTP **POST**。载荷包含情景、最终共识、质量评估,以及一个公开的分享卡 URL — 这样 Slack 和 Discord 等消费方能自动展开成富预览。

> **提示:** 打开 MiroShark → **设置 → Integrations · Webhook**,即可在不离开应用的情况下粘贴你的 URL 并触发一次测试事件。同一个 URL 也会被 runner 在真实运行时读取。

---

## 为什么要有 webhook

完成回调 webhook 是 MiroShark 之外一切外部世界的集成面:

- **Slack / Discord / Teams** — 粘贴一个 Incoming Webhook URL;每次长时间模拟一结束,聊天频道就会亮起来,并自带分享卡片图。
- **Zapier / Make / n8n / IFTTT** — 把 Zap/Scenario/Workflow 指向 MiroShark,然后从那里发散开:邮件摘要、Notion 行、Airtable 记录、Google 表格更新、自定义仪表板。
- **自定义应用** — 你自己的 Cloud Run / Lambda / Express 端点收到 JSON;之后随便你怎么处理(启动下游分析、追加到队列、写 BigQuery 等)。

无 bot、无 OAuth、无托管基础设施。只要一个 URL 字段。

---

## 配置

要么在启动 MiroShark 之前设置环境变量:

```bash
WEBHOOK_URL=https://hooks.slack.com/services/T0XXX/B0YYY/abcSECRETxyz
PUBLIC_BASE_URL=https://miroshark.app           # optional, see below
WEBHOOK_SECRET=                                  # optional,见下方「验证 webhook 签名」
```

……要么打开 **设置 → Integrations · Webhook** 在那里粘贴 URL。设置改动会在运行时生效 — 无需重启。

`PUBLIC_BASE_URL` 是你 MiroShark 部署对外公开可达的根地址(例如 `https://miroshark.app`)。设置之后,载荷会包含绝对路径的 `share_url` 与 `share_card_url` 字段,让 Slack / Discord 自动展开模拟卡片。如果你只需要相对路径并且消费方能自己拼绝对 URL,留空即可。

`WEBHOOK_SECRET` 是用于对每次出站载荷做 HMAC 签名的共享密钥 — 详见下文[验证 webhook 签名](#验证-webhook-签名)。留空可跳过签名(已有集成无需任何改动即可继续工作)。用 `python -c 'import secrets; print(secrets.token_hex(32))'` 生成一个新的随机值,并把它同时设置到 MiroShark 的 `.env` 和你的消费端环境中。

---

## 载荷结构

```json
{
  "event": "simulation.completed",
  "sim_id": "sim_abc123def456",
  "scenario": "Will the SEC approve a spot Solana ETF before Q3 2026?",
  "status": "completed",
  "current_round": 20,
  "total_rounds": 20,
  "agent_count": 248,
  "quality_health": "Excellent",
  "final_consensus": {
    "bullish": 62.0,
    "neutral": 13.0,
    "bearish": 25.0
  },
  "resolution_outcome": "YES",
  "share_path": "/share/sim_abc123def456",
  "share_card_path": "/api/simulation/sim_abc123def456/share-card.png",
  "share_url": "https://miroshark.app/share/sim_abc123def456",
  "share_card_url": "https://miroshark.app/api/simulation/sim_abc123def456/share-card.png",
  "created_at": "2026-04-26T10:12:34",
  "completed_at": "2026-04-26T10:35:11",
  "parent_simulation_id": null,
  "fired_at": "2026-04-26T10:35:11.842113+00:00"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `event` | string | `simulation.completed`、`simulation.failed` 或 `simulation.test` |
| `sim_id` | string | 稳定标识符 — 同时也在 `X-MiroShark-Sim-Id` 头部里 |
| `scenario` | string | 截断到 280 字符,带 Unicode 省略号 |
| `status` | string | `completed`、`failed` 或 `test` |
| `current_round` | int | 完成时已结束的最后一轮 |
| `total_rounds` | int | 配置的总轮数 — 未知时为 `0` |
| `agent_count` | int | 智能体画像数量 |
| `quality_health` | string \| null | `Excellent` / `Good` / `Fair` / `Poor`,跳过评估时为 `null` |
| `final_consensus` | object \| null | 最后一份信念快照中的 看涨 / 中立 / 看跌 百分比 |
| `resolution_outcome` | string \| null | 当本次运行有 polymarket 结算时存在(`YES` / `NO`) |
| `share_path` | string | 永远是相对路径;打日志安全 |
| `share_card_path` | string | 永远是相对路径 |
| `share_url` | string \| absent | 仅在设置了 `PUBLIC_BASE_URL` 时存在 |
| `share_card_url` | string \| absent | 仅在设置了 `PUBLIC_BASE_URL` 时存在 |
| `created_at` | string \| null | ISO 8601,模拟创建时间 |
| `completed_at` | string \| null | ISO 8601,达到终态的时间 |
| `parent_simulation_id` | string \| null | 当此次运行是从其他运行分叉而来时存在 |
| `fired_at` | string | 带时区的 ISO 8601,webhook 离开 MiroShark 的时间 |
| `error` | string \| absent | 仅在 `simulation.failed` 上 — 截断到 1000 字符 |
| `test` | bool \| absent | 仅在 `simulation.test` 事件上为 `true` |

### HTTP 头

| 头 | 值 |
|---|---|
| `Content-Type` | `application/json; charset=utf-8` |
| `User-Agent` | `MiroShark-Webhook/1.0` |
| `X-MiroShark-Event` | 与 `event` 相同的值 |
| `X-MiroShark-Sim-Id` | 与 `sim_id` 相同的值 |
| `X-MiroShark-Signature` | 原始 body 的 `sha256=<hex>` HMAC。仅在设置了 `WEBHOOK_SECRET` 时存在。详见[验证 webhook 签名](#验证-webhook-签名)。 |

---

## 投递语义

- **发了就忘** — POST 跑在守护线程上,所以慢的接收端永远不会拖慢模拟 runner。
- **尽力而为,不重试** — 单次尝试,5 秒超时。需要可靠送达的消费方应该把 webhook 接进队列,并尽快用 HTTP 2xx 应答。
- **进程内去重** — runner 会通过两条路径检测完成(进程退出码 + 各平台的 `simulation_end` 事件)。两者都会调进 webhook 服务;每个 `(sim_id, status)` 只有第一次会真的发出。
- **只送 `completed` 与 `failed`** — 暂停 / 恢复 / running 事件*不*下发。
- **2xx 即成功** — 其他都会被记录为投递失败,但永远不会抛出。
- **投递日志** — 每次投递尝试(自动触发*或*手动重发)都会在 `<sim_dir>/webhook-log.jsonl` 追加一行 JSON,包含时间戳、掩码 URL、HTTP 状态码、延迟和触发标签。磁盘上限 50 行;`GET /api/simulation/<id>/webhook-log`(需管理员 token)返回最近 10 条记录(从新到旧)以及全程 `total_attempts` 计数器。
- **手动重试** — `POST /api/simulation/<id>/webhook-retry`(需管理员 token)重发已经处于终止状态的模拟的完成 webhook。原投递偶发 5xx、URL 当时配错、消费集成当时宕机时有用。重发载荷带 `retry: true`,下游消费者可据此对重放去重。重发会绕过自动触发使用的进程内 `(sim_id, status)` 去重门(那道门只防止 runner 的两条终止代码路径自动双发;运维者显式重试理应总能通过)。未配置 webhook URL 时返回 400,模拟尚未到达终止状态时返回 409。

---

## 验证 webhook 签名

当你的 MiroShark 实例配置了 `WEBHOOK_SECRET` 时,每一份出站载荷都会用 HMAC-SHA256 签名,签名通过 `X-MiroShark-Signature` 头部一并送达。签名让消费方能够证明载荷确实来自你的 MiroShark 实例、并且在传输途中没有被伪造 — [Stripe](https://stripe.com/docs/webhooks/signatures) 和 [GitHub](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries) 用的就是同一套方案。

签名是对**原始请求 body**(不是解析后的 JSON)计算的,所以消费方必须在解析*之前*完成验证 — 重新序列化 JSON 可能改变字段顺序或空白,从而破坏摘要。

**向后兼容。** 当 MiroShark 一侧未设置或留空 `WEBHOOK_SECRET` 时,签名头部会被完全省略,已有的集成无需任何改动即可继续工作。消费方应当把「没有签名头」当作「未配置签名」处理,自行决定是否接受未签名的投递。

生成一个强随机密钥,并在两边设置**相同的值**:

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
# → 64 个十六进制字符;把它粘贴到两端的 WEBHOOK_SECRET
```

### Python(Flask / FastAPI / 纯 WSGI)

```python
import hashlib, hmac, os

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"].encode()

def verify(raw_body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(WEBHOOK_SECRET, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")
```

`hmac.compare_digest` 是常数时间比较,所以网络上的攻击者无法通过时序差侧信道试出签名。

### Node.js(Express)

```javascript
const crypto = require('crypto');
const SECRET = process.env.WEBHOOK_SECRET;

function verify(rawBody, header) {
  const expected = 'sha256=' + crypto.createHmac('sha256', SECRET).update(rawBody).digest('hex');
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(header || ''));
}
```

在 Express 中要给路由附加 `express.raw({ type: 'application/json' })`,这样 `req.body` 会是一个 `Buffer` — 在 `JSON.parse` 之前完成验证。

### Bash / curl + openssl

终端里的一次性手动校验 — 当你在 Slack 应急频道里想知道「这条 webhook 真的来自我那台 MiroShark 吗?」时很有用:

```bash
SIGNATURE=$(curl -fsSL -X POST https://your-app.example.com/miroshark-webhook \
  -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  -D - -o /dev/null | grep -i '^x-miroshark-signature:' | cut -d' ' -f2 | tr -d '\r')

EXPECTED=sha256=$(openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -hex payload.json | awk '{print $2}')

[ "$SIGNATURE" = "$EXPECTED" ] && echo OK || echo TAMPERED
```

---

## 示例

### Slack

```bash
WEBHOOK_URL=https://hooks.slack.com/services/T0XXX/B0YYY/abcSECRETxyz
PUBLIC_BASE_URL=https://miroshark.example.com
```

Slack 消息会自动把 `share_url` 展开成 `GET /api/simulation/<id>/share-card.png` 生成的 OG 卡(1200×630 PNG,带情景、共识分布、质量徽章)。无需额外格式化。

### Discord

```bash
WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abcSECRETxyz
PUBLIC_BASE_URL=https://miroshark.example.com
```

Discord 频道 webhook 接受同一份 JSON body。`share_url` 会在频道里展开。

### Zapier / Make / n8n

创建一个"Webhook by Zapier" / "Webhooks · Custom webhook" / "Webhook" 触发节点,把它的 URL 复制到 `WEBHOOK_URL`。每次模拟完成都会成为一次新的触发事件,带上面完整的载荷 — 然后扇出到邮件、Notion、表格,或者它们提供的 5,000+ 集成中的任何一个。

### 自定义监听端(Python)

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/miroshark-webhook")
async def receive(req: Request):
    payload = await req.json()
    if payload["event"] == "simulation.completed":
        print(f"{payload['sim_id']}: {payload['scenario']!r} → {payload['final_consensus']}")
    return {"ok": True}
```

---

## 测试你的端点

最快的路径是 **设置 → Integrations · Webhook** 中的 **发送测试事件** 按钮 — 它会以同一份结构 POST `event: "simulation.test"` 与 `test: true`,并就地显示响应状态 / 延迟。

同样的调用也以 `POST /api/settings/test-webhook` 的形式暴露,便于脚本化:

```bash
curl -s -X POST http://localhost:5000/api/settings/test-webhook \
     -H 'Content-Type: application/json' \
     -d '{"url": "https://example.com/hook"}'
```

响应:

```json
{
  "success": true,
  "message": "HTTP 200",
  "latency_ms": 142,
  "url_masked": "https://example.com/***"
}
```

省略 body 即可测试当前已保存的 `WEBHOOK_URL`。

---

## 安全说明

- 完整的 webhook URL 被视为密钥 — `GET /api/settings` 只返回脱敏形式(`https://hooks.slack.com/***`)。路径永远不会被回显。
- Webhook 调用直接从你的 MiroShark 实例打到你的端点 — 不经过 Anthropic 或任何第三方中转。
- 校验会拒绝任何不以 `http://` 或 `https://` 开头的 URL。JavaScript / file / FTP URL 在 API 层就被拦掉。
- `WEBHOOK_SECRET` 仅用于**传输层** — 每次投递都会用它签名,但永远不会写入每个模拟的投递日志(`webhook-log.jsonl` 只记录脱敏 URL,绝不保存密钥),也不会被任何 API 端点回显。任意时刻都可以通过在两端同时设置新值来轮换;在飞行中的重试会使用重试时刻已设置的密钥。
