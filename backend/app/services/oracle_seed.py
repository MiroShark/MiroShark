"""FeedOracle MCP connector — grounded data for simulation seeds.

The sibling `mirofish-oracle-seeds` repo exposes 484 MCP tools across 44
oracle servers (MiCA, DORA, macro, DEX liquidity, sanctions, carbon, etc.).
MiroShark templates can opt into a subset by declaring::

    "oracle_tools": [
        {"server": "feedoracle_core", "tool": "mica_status",     "args": {"token_symbol": "USDT"}},
        {"server": "feedoracle_core", "tool": "peg_deviation",   "args": {"token_symbol": "USDT"}},
        {"server": "feedoracle_core", "tool": "macro_risk",      "args": {}}
    ]

At template-use time, ``resolve_oracle_tools`` dispatches each call against
the FeedOracle MCP HTTP endpoint (``FEEDORACLE_MCP_URL``, default
``https://mcp.feedoracle.io/mcp``) and returns a markdown-formatted evidence
block to be appended to the template's ``seed_document`` before graph build.

Opt-in. Disabled by default (``ORACLE_SEED_ENABLED=false``). Silently
returns an empty block on any failure — the template still works without
oracle data.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

try:  # httpx is already pulled in via OpenAI SDK — but we import defensively.
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

from ..utils.logger import get_logger

logger = get_logger("miroshark.oracle_seed")


_DEFAULT_ENDPOINT = "https://mcp.feedoracle.io/mcp"
_DEFAULT_TIMEOUT_SEC = 15.0


def _enabled() -> bool:
    return (os.environ.get("ORACLE_SEED_ENABLED", "false").lower() == "true")


def _endpoint() -> str:
    return (os.environ.get("FEEDORACLE_MCP_URL") or _DEFAULT_ENDPOINT).rstrip("/")


def _api_key() -> Optional[str]:
    return os.environ.get("FEEDORACLE_API_KEY") or None


class _MCPClient:
    """Minimal stateless MCP client (JSON-RPC over HTTP). Mirrors the sibling repo."""

    def __init__(self, endpoint: str, api_key: Optional[str]):
        if httpx is None:
            raise RuntimeError("httpx is not installed")
        self.endpoint = endpoint
        self.api_key = api_key
        self.session_id: Optional[str] = None
        self.client = httpx.Client(timeout=_DEFAULT_TIMEOUT_SEC)

    def _rpc(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex[:8],
            "method": method,
            "params": params or {},
        }
        resp = self.client.post(self.endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self.session_id = sid
        return resp.json()

    def initialize(self) -> None:
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "miroshark", "version": "1.0"},
            },
        )

    def call_tool(self, name: str, arguments: Optional[Dict] = None) -> Any:
        args: Dict[str, Any] = dict(arguments or {})
        if self.api_key:
            args.setdefault("api_key", self.api_key)
        # Note: the sibling repo uses the bare tool name. Some deployments
        # namespace via "server__tool" — we accept both forms in resolve_*.
        result = self._rpc("tools/call", {"name": name, "arguments": args})
        content = (result.get("result") or {}).get("content") or []
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict) and first.get("text"):
                try:
                    return json.loads(first["text"])
                except json.JSONDecodeError:
                    return first["text"]
        return result

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass


def resolve_oracle_tools(template: Dict[str, Any]) -> str:
    """Dispatch ``template['oracle_tools']`` and return a markdown evidence block.

    Returns an empty string if oracle seeds are disabled, the list is empty,
    or any dispatch fails — the caller can safely concatenate the result onto
    the seed document without worrying about None.
    """
    tools = template.get("oracle_tools") or []
    if not tools or not _enabled() or httpx is None:
        return ""

    endpoint = _endpoint()
    api_key = _api_key()
    results: List[Dict[str, Any]] = []

    try:
        client = _MCPClient(endpoint, api_key)
    except Exception as exc:
        logger.warning(f"oracle_seed: init failed ({exc}) — skipping oracle enrichment")
        return ""

    try:
        client.initialize()
    except Exception as exc:
        logger.warning(f"oracle_seed: initialize failed ({exc}) — skipping")
        client.close()
        return ""

    for entry in tools:
        if not isinstance(entry, dict):
            continue
        server = (entry.get("server") or "").strip()
        name = (entry.get("tool") or "").strip()
        if not name:
            continue
        args = entry.get("args") or {}
        # Support both namespaced and bare tool names.
        fq_name = f"{server}__{name}" if server else name
        try:
            data = client.call_tool(fq_name, args)
        except Exception as exc:
            logger.info(f"oracle_seed: {fq_name} failed ({exc}) — trying bare name")
            try:
                data = client.call_tool(name, args)
            except Exception as exc2:
                logger.warning(f"oracle_seed: {name} failed ({exc2}) — skipping this tool")
                continue
        results.append({"server": server, "tool": name, "args": args, "data": data})

    client.close()

    if not results:
        return ""

    lines = ["", "## Oracle Evidence (live at ingest time)", ""]
    for r in results:
        label = f"{r['server']}/{r['tool']}" if r["server"] else r["tool"]
        args_str = ", ".join(f"{k}={v}" for k, v in (r["args"] or {}).items()) or "(no args)"
        lines.append(f"### {label}  —  {args_str}")
        data = r["data"]
        try:
            pretty = json.dumps(data, ensure_ascii=False, indent=2, default=str)[:1500]
        except Exception:
            pretty = str(data)[:1500]
        lines.append("```json")
        lines.append(pretty)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)
