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
| `frame <sim_id> <round>` | 单轮的紧凑快照 |
| `publish <sim_id> [--unpublish]` | 切换嵌入公开标志 |
| `report <sim_id>` | 渲染分析报告 |
| `cost <sim_id>` | 预估美元成本 + token/调用次数(每次运行的「$1」主张) |
| `trending` | 拉取 RSS/Atom 热门条目 |
| `health` | Ping `/health` |

所有命令都接受 `--json` 以便脚本化使用。

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
