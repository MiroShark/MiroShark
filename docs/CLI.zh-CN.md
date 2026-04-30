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
| `trending` | 拉取 RSS/Atom 热门条目 |
| `health` | Ping `/health` |

所有命令都接受 `--json` 以便脚本化使用。
