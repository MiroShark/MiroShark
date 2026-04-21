"""Per-agent MCP tools — OpenMiro-style pluggable toolset for personas.

Grants select personas (journalists, analysts, traders) access to real MCP
tools during simulation. Disabled by default: gated by
``MCP_AGENT_TOOLS_ENABLED`` at runtime, and further per-persona by the
``tools_enabled`` flag on :class:`OasisAgentProfile`.

## Wiring

1. Set ``MCP_AGENT_TOOLS_ENABLED=true`` in ``.env``.
2. Drop a YAML manifest at ``MCP_SERVERS_CONFIG`` (default ``config/mcp_servers.yaml``).
   Schema (OpenMiro-compatible)::

       mcp_servers:
         - name: web_search
           command: python
           args: ["-m", "mcp_web_search"]
           env:
             BRAVE_API_KEY: "${BRAVE_KEY}"
         - name: price_feed
           command: npx
           args: ["-y", "@feedoracle/mcp-remote"]

3. In preset templates or at simulation-config time, mark personas with
   ``tools_enabled: true`` and optionally ``allowed_tools: [name,...]``.

The simulation loop should call :func:`build_agent_toolset` per round and
pass the resulting dispatcher to the agent's prompt builder. Full OASIS
integration requires changes to the wonderwall runner; this module provides
the primitive so that work can proceed without blocking the feature flag.

Keeps dependencies soft: if ``pyyaml`` is missing, returns an empty registry
with a warning (rather than crashing the Flask app on import).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger("miroshark.agent_mcp")


@dataclass
class MCPServerSpec:
    """Parsed MCP server entry from the YAML manifest."""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)


def _enabled() -> bool:
    return os.environ.get("MCP_AGENT_TOOLS_ENABLED", "false").lower() == "true"


def _manifest_path() -> str:
    return os.environ.get("MCP_SERVERS_CONFIG") or os.path.join(
        os.getcwd(), "config", "mcp_servers.yaml"
    )


def load_registry() -> Dict[str, MCPServerSpec]:
    """Parse the manifest into a name → MCPServerSpec map.

    Returns an empty dict when the feature is off, the file is missing,
    ``pyyaml`` isn't installed, or the file is malformed. Never raises.
    """
    if not _enabled():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        logger.warning("agent_mcp: pyyaml not installed — per-agent MCP tools disabled")
        return {}

    path = _manifest_path()
    if not os.path.exists(path):
        logger.info(f"agent_mcp: manifest not found at {path} — no tools registered")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except Exception as exc:
        logger.warning(f"agent_mcp: failed to parse {path} ({exc})")
        return {}

    servers: Dict[str, MCPServerSpec] = {}
    entries = raw.get("mcp_servers") or raw.get("servers") or []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        command = (entry.get("command") or "").strip()
        if not name or not command:
            continue
        raw_env = entry.get("env") or {}
        resolved_env = {}
        for k, v in raw_env.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                resolved_env[k] = os.environ.get(v[2:-1], "")
            else:
                resolved_env[k] = str(v)
        servers[name] = MCPServerSpec(
            name=name,
            command=command,
            args=list(entry.get("args") or []),
            env=resolved_env,
        )

    logger.info(f"agent_mcp: loaded {len(servers)} MCP server(s) from {path}")
    return servers


def build_agent_toolset(
    profile,  # OasisAgentProfile-like duck type
    registry: Optional[Dict[str, MCPServerSpec]] = None,
) -> Dict[str, MCPServerSpec]:
    """Return the subset of the registry this persona may call.

    An empty return means the agent has no tools (either globally off,
    persona opted out, or allowlist narrows to nothing). Callers don't need
    to check ``_enabled()`` themselves.
    """
    if not _enabled() or not getattr(profile, "tools_enabled", False):
        return {}
    reg = registry if registry is not None else load_registry()
    if not reg:
        return {}
    allowed = list(getattr(profile, "allowed_tools", None) or [])
    if not allowed:
        return dict(reg)  # persona with no allowlist → all tools
    return {name: spec for name, spec in reg.items() if name in allowed}


def summarize_toolset(tools: Dict[str, MCPServerSpec]) -> str:
    """Short human-readable listing suitable for an agent system prompt."""
    if not tools:
        return "(no MCP tools available this round)"
    lines = ["Available MCP tools:"]
    for name, spec in tools.items():
        args_str = " ".join(spec.args)
        lines.append(f"  - {name}: {spec.command} {args_str}".rstrip())
    return "\n".join(lines)
