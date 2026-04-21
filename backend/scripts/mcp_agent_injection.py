"""Inject per-agent MCP tool state into the agent's system message.

Two things happen around each round for a ``tools_enabled`` agent:

1. **Pre-round**: the tool catalogue is injected into the system message so
   the agent knows what calls it can make. Format mirrors the director /
   belief injection pattern (marker-delimited block that gets replaced each
   round, so the system message doesn't grow unbounded).

2. **Post-round**: the runner parses the agent's output for ``<mcp_call>``
   blocks, dispatches them through :class:`MCPAgentBridge`, and writes the
   results back — the next round's system message includes them so the agent
   can reason over what it just fetched.

Kept separate from the bridge so unit tests can exercise the injection
markers without spawning subprocesses.
"""

from __future__ import annotations

from typing import List

from mcp_agent_bridge import MCPCallResult


_MCP_CATALOGUE_MARKER = "\n\n# MCP TOOLS AVAILABLE"
_MCP_RESULTS_MARKER = "\n\n# MCP TOOL RESULTS"

_CATALOGUE_INSTRUCTION = (
    "\nYou may invoke at most 2 of these tools per turn by emitting one or two "
    "self-closing tags anywhere in your reply — for example:\n"
    '  <mcp_call server="web_search" tool="search" args=\'{"q": "something"}\' />\n'
    "The tags are parsed out before your post is sent. Use the tools only "
    "when they'd meaningfully improve your next action; do not spam."
)


def _strip_markered_block(content: str, marker: str) -> str:
    """Remove a block delimited by marker at start and "\\n\\n# " next."""
    pos = content.find(marker)
    if pos == -1:
        return content
    next_marker = content.find("\n\n# ", pos + len(marker))
    if next_marker != -1:
        return content[:pos] + content[next_marker:]
    return content[:pos]


def inject_mcp_catalogue(agent, catalogue_text: str) -> None:
    """Attach/refresh the MCP tool catalogue block on an agent's system message."""
    if not catalogue_text:
        return
    content = agent.system_message.content
    content = _strip_markered_block(content, _MCP_CATALOGUE_MARKER)
    block = (
        f"{_MCP_CATALOGUE_MARKER}\n"
        f"{catalogue_text}\n"
        f"{_CATALOGUE_INSTRUCTION}"
    )
    agent.system_message.content = content + block


def inject_mcp_results(agent, results: List[MCPCallResult]) -> None:
    """Attach/refresh the tool-results block on an agent's system message."""
    if not results:
        # Clear any stale block from the previous round so the prompt stays
        # tight when the agent makes no calls this turn.
        agent.system_message.content = _strip_markered_block(
            agent.system_message.content, _MCP_RESULTS_MARKER
        )
        return

    content = agent.system_message.content
    content = _strip_markered_block(content, _MCP_RESULTS_MARKER)

    lines = [_MCP_RESULTS_MARKER]
    for r in results:
        status = "OK" if r.ok else "ERR"
        try:
            import json
            body = json.dumps(r.data, ensure_ascii=False, default=str)[:600]
        except Exception:
            body = str(r.data)[:600]
        lines.append(f"- {r.server}/{r.tool} [{status}, {r.latency_ms}ms]: {body}")
    agent.system_message.content = content + "\n".join(lines)


def strip_mcp_call_tags(text: str) -> str:
    """Remove ``<mcp_call .../>`` tags from agent output before it's posted.

    Complements :func:`mcp_agent_bridge.parse_tool_calls`: we parse and
    dispatch, but the tags themselves shouldn't appear in the agent's
    simulated post. A simple regex strip is enough — shapes are bounded.
    """
    if not text or "<mcp_call" not in text:
        return text
    import re
    return re.sub(
        r"<mcp_call\s+[^>]*?/?>",
        "",
        text,
        flags=re.DOTALL,
    ).strip()
