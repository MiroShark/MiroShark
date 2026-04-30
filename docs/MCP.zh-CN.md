<sup>[English](MCP.md) · 中文</sup>

# MCP

MiroShark 提供两套 MCP 表面:一个**独立 MCP server**,让你可以在 Claude Desktop、Cursor、Windsurf 或 Continue 里查询自己的知识图谱;还有一组**报告智能体工具**,被 ReACT 报告智能体内部使用。

> **提示:** 打开 MiroShark → **设置 → AI Integration · MCP**,可以为每个客户端拿到自动生成的、可直接复制粘贴的配置片段。设置面板会调用 `GET /api/mcp/status`,并把你机器上的绝对路径打进片段里。

## 暴露了什么

`backend/mcp_server.py` 跑在 **stdio** 上(无需开端口、无需常驻守护进程 — 你的 MCP 客户端按需启动它),并使用你已有的 `.env` 中的 Neo4j + LLM 凭据。

| 工具 | 作用 |
|---|---|
| `list_graphs` | 浏览图谱 + 实体/边数量 |
| `search_graph` | 完整的混合 + 重排流水线,带 `kinds` / `as_of` 过滤 |
| `browse_clusters` | 社区缩放(首次调用时自动构建) |
| `search_communities` | 直接在簇摘要上做语义检索 |
| `get_community` | 展开一个簇及其成员 |
| `list_reports` | 某个图谱上生成过的报告 |
| `list_report_sections` | 一份报告的各个章节 |
| `get_reasoning_trace` | 一个章节的完整 ReACT 决策链 |

**示例提示词:** *"列出我的 MiroShark 图谱,在最大的那个上 browse clusters 找任何与 oracle 漏洞相关的内容,然后给我看那个图谱上最近一份报告的推理链。"*

---

## Claude Desktop

打开 **Claude Desktop → Settings → Developer → Edit Config**。文件位置:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

把下面这块加进 `mcpServers`(或合并进去) — 把 `/absolute/path/to/MiroShark/backend` 替换成你机器上的路径:

```json
{
  "mcpServers": {
    "miroshark": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/MiroShark/backend",
        "python",
        "mcp_server.py"
      ]
    }
  }
}
```

重启 Claude Desktop。`miroshark` 工具会出现在锤子 / 🛠️ 菜单里。

> **没有 `uv`?** 直接用 Python 解释器:
> ```json
> "command": "/absolute/path/to/MiroShark/backend/.venv/bin/python",
> "args": ["/absolute/path/to/MiroShark/backend/mcp_server.py"]
> ```

---

## Cursor

Cursor 从下面任意一处读 `mcpServers`:

- 工作区配置:你正在工作的仓库里 `.cursor/mcp.json`,**或者**
- 全局配置:`~/.cursor/mcp.json`

加上:

```json
{
  "mcpServers": {
    "miroshark": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/MiroShark/backend",
        "python",
        "mcp_server.py"
      ]
    }
  }
}
```

重新加载 Cursor 窗口(`Cmd/Ctrl+Shift+P → Reload Window`)。当你在聊天里 `@mention` MCP 时,miroshark 工具就会出现。

---

## Windsurf

Windsurf 从 `~/.codeium/windsurf/mcp_config.json` 读 MCP 服务器:

```json
{
  "mcpServers": {
    "miroshark": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/MiroShark/backend",
        "python",
        "mcp_server.py"
      ]
    }
  }
}
```

然后打开 **Cascade → MCP Servers → Refresh**。miroshark 工具就可以从 Cascade 对话中调用了。

---

## Continue(VS Code / JetBrains)

Continue ≥ 0.9.x 通过 `~/.continue/config.json` 支持 MCP:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "uv",
          "args": [
            "run",
            "--directory",
            "/absolute/path/to/MiroShark/backend",
            "python",
            "mcp_server.py"
          ]
        }
      }
    ]
  }
}
```

保存后重新加载你的编辑器。

---

## 验证它能跑

1. 启动你的 MCP 客户端。几秒内它应该会以子进程方式启动 `mcp_server.py`。
2. 提问:*"用 `list_graphs` 工具列出我的 MiroShark 图谱。"* — 助手应当返回每个图谱一行,以及实体/边数量。如果返回为空(`No graphs found.`),先在 MiroShark UI 中至少构建一个图谱(步骤 1:图谱构建)。
3. MiroShark UI 中 **设置 → AI Integration · MCP** 面板暴露了相同的 Neo4j 健康探测 — 如果面板说 *Neo4j down*,MCP 工具会以同样的方式失败。

## 故障排查

| 现象 | 可能原因 | 修复 |
|---|---|---|
| 客户端 MCP 日志中出现 `uv: command not found` | `uv` 不在客户端继承的 PATH 上 | 切换到 **没有 uv?** 那段(直接解释器路径),或者全局安装 `uv`。 |
| `list_graphs` 返回 `No graphs found.` | Neo4j 是空的 | 在 MiroShark UI 跑一次模拟,至少写入一个图谱。 |
| `Neo.ClientError.Security.Unauthorized` | `.env` 中的 `NEO4J_PASSWORD` 已过期 | 更新 `.env` 并重启任何已经派发过该 server 的客户端。 |
| Server 启动后立刻退出 | 缺少 `mcp` Python 包 | MCP SDK 在 `pyproject.toml` 中 — 确认 `uv sync`(或 `pip install -e backend/`)正常完成。 |
| 设置面板上片段显示 `mcp_script: missing` | 你正在跑后端的 checkout 与含 `mcp_server.py` 的 checkout 不是同一个 | 重新克隆或 `git pull`,确保 `backend/mcp_server.py` 存在。 |

## 报告智能体工具

ReACT 报告智能体在内部暴露这些工具(通过 `REPORT_AGENT_MAX_TOOL_CALLS` 配置):

| 工具 | 用途 |
|---|---|
| `insight_forge` | 围绕一个具体问题做多轮深度分析 |
| `panorama_search` | 混合 vector + BM25 + 图谱检索 |
| `quick_search` | 轻量关键词检索 |
| `interview_agents` | 与模拟智能体实时对话 |
| `analyze_trajectory` | 信念漂移 — 收敛、极化、转折点 |
| `analyze_equilibrium` | 在拟合到最终信念分布的 2 人立场博弈上求纳什均衡 — 揭示观察到的结果是否与自利博弈一致(需要 `nashpy`) |
| `analyze_graph_structure` | 中心性 / 社区 / 桥接分析 |
| `find_causal_path` | 两个实体之间的图谱遍历 |
| `detect_contradictions` | 图中互相冲突的边 |
| `simulation_feed` | 原始动作日志,按平台 / 查询 / 轮次过滤 |
| `market_state` | Polymarket 价格、交易、组合 |
| `browse_clusters` | 社区缩放(用于全局定位) |
