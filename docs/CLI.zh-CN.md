<sup>[English](CLI.md) · 中文</sup>

# CLI

为运行中的 MiroShark 后端提供一个依赖极少的 HTTP 客户端。

## 安装

```bash
# From a checkout with the backend installed:
pip install -e backend/
miroshark-cli ask "Will the EU AI Act survive trilogue?"

# Or run directly — no install, no third-party deps:
python backend/cli.py --help
```

设置 `MIROSHARK_API_URL` 即可指向远程部署。

## 命令

| 命令 | 作用 |
|---|---|
| `ask "<question>"` | 从一个问题合成种子简报 |
| `list` | 列出模拟 / 项目 |
| `status <sim_id>` | runner 状态 + 当前轮次/总数 |
| `wait <sim_id> [--interval N] [--timeout N]` | 阻塞直到运行结束,然后以 0/1 退出 |
| `stop <sim_id>` | 取消正在运行的模拟 |
| `frame <sim_id> <round>` | 单轮的紧凑快照 |
| `publish <sim_id> [--unpublish]` | 切换嵌入公开标志 |
| `report <sim_id>` | 渲染分析报告 |
| `cost <sim_id>` | 预估美元成本 + token/调用次数(每次运行的「$1」主张) |
| `trending` | 拉取 RSS/Atom 热门条目 |
| `health` | Ping `/health` |

所有命令都接受 `--json` 以便脚本化使用。

## 等待(wait)

`wait <sim_id>` 会轮询 `/api/simulation/<id>/run-status`,直到运行进入终止状态,
这样脚本就能阻塞等待运行中的模拟,然后在结果上继续操作,而无需自己实现轮询循环:

```bash
# sim_id 来自 `list`(或网页界面)
SIM=$(python backend/cli.py --json list | jq -r '.[0].simulation_id')
python backend/cli.py wait "$SIM" && python backend/cli.py report "$SIM"
```

进度行(`[running] round 12/144`)打印到 **stderr**,因此 stdout 保持干净,便于
`--json` 管道。退出码:运行**完成**为 `0`,运行**失败**或被**停止**为 `1`,
**超时**为 `2`。可用 `--interval`(轮询间隔秒数,默认 `5`)和 `--timeout`
(最长等待秒数,默认 `600`)调节轮询。加上 `--json` 可在退出时打印最终的
run-status 负载。

## 停止(stop)

`stop <sim_id>` 会向 `/api/simulation/stop` 发送 POST 请求,取消正在运行的模拟 ——
这正是 `wait` 此前缺失的退出口。`wait` 会阻塞直到运行进入终止状态,但无法**结束**
一个卡住、超时或不再需要的运行。把两者配合使用,即可为运行设定上限并在超时后清理:

```bash
# 最多等待 10 分钟;若超时(或失败),则停止它。
python backend/cli.py wait "$SIM" --timeout 600 || python backend/cli.py stop "$SIM"
```

成功时打印 `<sim_id> stopped` 并以 `0` 退出;出错(未知 id、服务器错误)时以 `1` 退出。
`--json` 是全局标志,需置于子命令之前(`python backend/cli.py --json stop "$SIM"`)才能获取原始的 `/stop` 负载。

## 成本

`cost <sim_id>` 在命令行中展示单次运行的成本预估(对应 `/api/simulation/<id>/cost.json`
端点),让「用 $1 模拟任何事」这一主张可以通过脚本核实:

```bash
$ python backend/cli.py cost sim_abc123
~$0.9213  (1,284,902 tokens, 871 LLM calls)
  graph_build      ~$0.1204
  simulation       ~$0.7100
  report           ~$0.0909
```

`~` 前缀表示该数字是下限预估 —— 价格表中缺失的模型调用按 `$0` 计算。该模拟必须已发布
(`publish <sim_id>`)。退出码:成功为 `0`,私有/服务器错误为 `1`,成本尚不可用
(运行尚未记录任何 LLM 调用)为 `2`。加上 `--json` 可获取完整明细。
