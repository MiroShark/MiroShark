# MCP

MiroShark ships two MCP surfaces: a **standalone MCP server** so you can query your knowledge graphs from Claude Desktop, Cursor, Windsurf, or Continue, and a set of **report agent tools** used internally by the ReACT report agent.

> **Tip:** open MiroShark → **Settings → AI Integration · MCP** for an auto-generated, copy-paste-ready config snippet for each client. The Settings panel reads `GET /api/mcp/status` and stamps the snippet with the absolute paths on your machine.

## What's exposed

`backend/mcp_server.py` runs over **stdio** (no port to open, no daemon to keep alive — your MCP client launches it on demand) and uses your existing `.env` for Neo4j + LLM credentials.

| Tool | What it does |
|---|---|
| `list_graphs` | Survey graphs + entity/edge counts |
| `search_graph` | Full hybrid + rerank pipeline with `kinds` / `as_of` filters |
| `browse_clusters` | Community zoom-out (auto-builds on first call) |
| `search_communities` | Direct semantic search over cluster summaries |
| `get_community` | Expand one cluster with members |
| `list_reports` | Reports generated on a graph |
| `list_report_sections` | Sections of a report |
| `get_reasoning_trace` | Full ReACT decision chain for one section |

**Example prompt:** *"List my MiroShark graphs, browse clusters on the biggest one for anything about oracle exploits, then show me the reasoning trace from the most recent report on that graph."*

---

## Claude Desktop

Open **Claude Desktop → Settings → Developer → Edit Config**. The file lives at:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

Add (or merge into) the `mcpServers` block — replace `/absolute/path/to/MiroShark/backend` with the path on your machine:

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

Restart Claude Desktop. The `miroshark` tools appear in the hammer / 🛠️ menu.

> **No `uv`?** Use the Python interpreter directly:
> ```json
> "command": "/absolute/path/to/MiroShark/backend/.venv/bin/python",
> "args": ["/absolute/path/to/MiroShark/backend/mcp_server.py"]
> ```

---

## Cursor

Cursor reads `mcpServers` from either:

- a workspace config: `.cursor/mcp.json` in the repo you're working in, **or**
- a global config: `~/.cursor/mcp.json`

Add:

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

Reload the Cursor window (`Cmd/Ctrl+Shift+P → Reload Window`). The miroshark tools appear when you `@mention` MCP in chat.

---

## Windsurf

Windsurf reads MCP servers from `~/.codeium/windsurf/mcp_config.json`:

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

Then open **Cascade → MCP Servers → Refresh**. The miroshark tools become callable from Cascade conversations.

---

## Continue (VS Code / JetBrains)

Continue ≥ 0.9.x supports MCP via `~/.continue/config.json`:

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

Reload your editor after saving.

---

## Verifying it works

1. Start your MCP client. Within a few seconds it should spawn `mcp_server.py` as a child process.
2. Ask: *"Use the `list_graphs` tool to show my MiroShark graphs."* — the assistant should respond with one row per graph and entity/edge counts. If the response is empty (`No graphs found.`), build at least one graph in the MiroShark UI first (Step 1: Graph Build).
3. The MiroShark UI's **Settings → AI Integration · MCP** panel surfaces the same Neo4j health probe — if the panel says *Neo4j down*, the MCP tools will fail the same way.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `uv: command not found` in your client's MCP logs | `uv` is not on the PATH the client inherited | Switch to the **No uv?** snippet (direct interpreter path), or install `uv` system-wide. |
| `No graphs found.` from `list_graphs` | Empty Neo4j | Run a simulation in the MiroShark UI to populate at least one graph. |
| `Neo.ClientError.Security.Unauthorized` | Stale `NEO4J_PASSWORD` in `.env` | Update `.env` and restart any client that already spawned the server. |
| Server starts then dies immediately | `mcp` Python package missing | The MCP SDK is in `pyproject.toml` — make sure `uv sync` (or `pip install -e backend/`) ran cleanly. |
| Snippet shows `mcp_script: missing` in the Settings panel | You're running the backend from a different checkout than the one with `mcp_server.py` | Re-clone or `git pull` so `backend/mcp_server.py` exists. |

## Report Agent Tools

The ReACT report agent exposes these tools internally (configured via `REPORT_AGENT_MAX_TOOL_CALLS`):

| Tool | Purpose |
|---|---|
| `insight_forge` | Multi-round deep analysis on a specific question |
| `panorama_search` | Hybrid vector + BM25 + graph retrieval |
| `quick_search` | Lightweight keyword search |
| `interview_agents` | Live conversation with sim agents |
| `analyze_trajectory` | Belief drift — convergence, polarization, turning points |
| `analyze_equilibrium` | Nash equilibria on a 2-player stance game fit to the final belief distribution — reveals whether observed outcomes are consistent with self-interested play (requires `nashpy`) |
| `analyze_graph_structure` | Centrality / community / bridge analysis |
| `find_causal_path` | Graph traversal between two entities |
| `detect_contradictions` | Conflicting edges in the graph |
| `simulation_feed` | Raw action log filter by platform / query / round |
| `market_state` | Polymarket prices, trades, portfolios |
| `browse_clusters` | Community zoom-out (orienting) |
