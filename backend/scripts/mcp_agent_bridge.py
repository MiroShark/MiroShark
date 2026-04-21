"""Runtime MCP bridge for tools_enabled personas.

Given an ``MCPServerSpec`` registry (loaded via
``app.services.agent_mcp_tools.load_registry``), this module spawns each
configured MCP server as a persistent stdio subprocess and exposes
``call(server_name, tool_name, args)`` / ``list_tools(server_name)``.

Design points:
- **One subprocess per server, pooled**: MCP servers are stateful (auth,
  session), so we initialize once and reuse for the full simulation.
- **stdio JSON-RPC**: per the Model Context Protocol; no HTTP assumption.
- **Per-call timeout**: 30s by default. A hung server doesn't stall the sim.
- **Graceful error results**: a failed tool returns ``{"_error": "..."}``
  rather than raising, so agent observation prompts stay well-formed.
- **Shutdown-safe**: register ``atexit`` so Python teardown kills subprocesses.

**Parser**: call strings are embedded in agent completions as::

    <mcp_call server="web_search" tool="search" args='{"q":"something"}' />

which we extract with a simple regex. One line per call; agents emit up to
MAX_CALLS_PER_TURN per round (default 2).

See ``backend/app/services/agent_mcp_tools.py`` for the persona side.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


MAX_CALLS_PER_TURN = int(os.environ.get("MCP_MAX_CALLS_PER_TURN", "2"))
DEFAULT_CALL_TIMEOUT_SEC = float(os.environ.get("MCP_CALL_TIMEOUT_SEC", "30"))


_CALL_RE = re.compile(
    r"""<mcp_call\s+
        server=(?P<q1>["'])(?P<server>[\w\-\.]+)(?P=q1)\s+
        tool=(?P<q2>["'])(?P<tool>[\w\-\.]+)(?P=q2)
        (?:\s+args=(?P<q3>["'])(?P<args>.*?)(?P=q3))?
        \s*/?>""",
    re.VERBOSE | re.DOTALL,
)


@dataclass
class MCPCallRequest:
    server: str
    tool: str
    args: Dict[str, Any]


@dataclass
class MCPCallResult:
    server: str
    tool: str
    ok: bool
    data: Any
    latency_ms: int


def parse_tool_calls(text: str, max_calls: int = MAX_CALLS_PER_TURN) -> List[MCPCallRequest]:
    """Extract up to max_calls ``<mcp_call .../>`` blocks from agent output.

    Malformed ``args`` JSON is tolerated (empty dict). Returns [] if none.
    """
    if not text:
        return []
    out: List[MCPCallRequest] = []
    for m in _CALL_RE.finditer(text):
        raw_args = m.group("args") or ""
        try:
            args = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError:
            args = {}
        if not isinstance(args, dict):
            args = {}
        out.append(MCPCallRequest(
            server=m.group("server"),
            tool=m.group("tool"),
            args=args,
        ))
        if len(out) >= max_calls:
            break
    return out


class _MCPProcess:
    """A single long-lived MCP server subprocess over stdio JSON-RPC."""

    def __init__(self, name: str, command: str, args: List[str], env: Dict[str, str]):
        self.name = name
        merged_env = dict(os.environ)
        merged_env.update(env or {})
        self._proc = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
            env=merged_env,
            text=False,
        )
        self._lock = threading.Lock()
        self._initialized = False
        self._cached_tools: Optional[List[Dict[str, Any]]] = None

    def _send(self, obj: Dict[str, Any]) -> None:
        assert self._proc.stdin is not None
        data = (json.dumps(obj) + "\n").encode("utf-8")
        self._proc.stdin.write(data)
        self._proc.stdin.flush()

    def _recv(self, timeout: float) -> Dict[str, Any]:
        assert self._proc.stdout is not None
        # Naive line read with a watchdog thread. subprocess.PIPE's readline
        # blocks indefinitely; we guard with a timeout thread.
        result_box: Dict[str, Any] = {}
        done = threading.Event()

        def _reader():
            try:
                line = self._proc.stdout.readline()
                if not line:
                    result_box["err"] = "EOF from MCP server"
                else:
                    try:
                        result_box["data"] = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError as e:
                        result_box["err"] = f"bad JSON from MCP: {e}"
            except Exception as e:
                result_box["err"] = f"read failed: {e}"
            finally:
                done.set()

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        if not done.wait(timeout=timeout):
            raise TimeoutError(f"MCP server {self.name} did not respond in {timeout}s")
        if "err" in result_box:
            raise RuntimeError(result_box["err"])
        return result_box["data"]

    def _rpc(self, method: str, params: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        with self._lock:
            msg = {
                "jsonrpc": "2.0",
                "id": uuid.uuid4().hex[:8],
                "method": method,
                "params": params,
            }
            self._send(msg)
            return self._recv(timeout)

    def initialize(self, timeout: float = 10.0) -> None:
        if self._initialized:
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "miroshark-runner", "version": "1.0"},
            },
            timeout=timeout,
        )
        self._initialized = True

    def list_tools(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        if self._cached_tools is not None:
            return self._cached_tools
        resp = self._rpc("tools/list", {}, timeout=timeout)
        tools = (resp.get("result") or {}).get("tools") or []
        self._cached_tools = tools
        return tools

    def call_tool(self, name: str, args: Dict[str, Any], timeout: float) -> Any:
        resp = self._rpc("tools/call", {"name": name, "arguments": args}, timeout=timeout)
        result = resp.get("result") or {}
        # Standard MCP content shape: [{"type": "text", "text": "..."}]
        content = result.get("content") or []
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                try:
                    return json.loads(first["text"])
                except json.JSONDecodeError:
                    return first["text"]
        return result

    def shutdown(self) -> None:
        try:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        except Exception:
            pass


class MCPAgentBridge:
    """Pool of MCP server processes usable during a simulation run.

    Construct once at simulation start, pass to agent observation code,
    :meth:`dispatch_calls` on agent output, and ``shutdown()`` when the sim
    completes. ``atexit`` also tears everything down on abnormal exit.
    """

    def __init__(self, registry: Dict[str, Any]):  # MCPServerSpec
        self._servers: Dict[str, _MCPProcess] = {}
        self._registry = registry
        self._lock = threading.Lock()
        atexit.register(self.shutdown)

    def _ensure(self, name: str) -> Optional[_MCPProcess]:
        if name not in self._registry:
            return None
        with self._lock:
            if name in self._servers:
                return self._servers[name]
            spec = self._registry[name]
            try:
                proc = _MCPProcess(
                    name=name,
                    command=spec.command,
                    args=list(spec.args or []),
                    env=dict(spec.env or {}),
                )
                proc.initialize()
                self._servers[name] = proc
                return proc
            except Exception as e:
                print(f"[mcp_bridge] Failed to start MCP server {name}: {e}", file=sys.stderr)
                return None

    def tool_catalogue(self, server_names: List[str]) -> str:
        """Human-readable summary of tools available on the given servers."""
        lines: List[str] = []
        for name in server_names:
            proc = self._ensure(name)
            if proc is None:
                lines.append(f"- {name}: (unavailable)")
                continue
            try:
                tools = proc.list_tools()
            except Exception as e:
                lines.append(f"- {name}: (list failed: {e})")
                continue
            for t in tools[:8]:  # cap — we don't want to bloat the prompt
                tname = t.get("name", "?")
                desc = (t.get("description") or "").splitlines()[0][:80]
                lines.append(f"- {name}/{tname}: {desc}")
        return "\n".join(lines) if lines else "(no tools available)"

    def dispatch_calls(
        self,
        calls: List[MCPCallRequest],
        timeout_sec: float = DEFAULT_CALL_TIMEOUT_SEC,
    ) -> List[MCPCallResult]:
        """Run each call against its server. Never raises — failures become ok=False."""
        results: List[MCPCallResult] = []
        for call in calls:
            proc = self._ensure(call.server)
            if proc is None:
                results.append(MCPCallResult(
                    server=call.server,
                    tool=call.tool,
                    ok=False,
                    data={"_error": f"unknown or unavailable server: {call.server}"},
                    latency_ms=0,
                ))
                continue
            t0 = time.perf_counter()
            try:
                data = proc.call_tool(call.tool, call.args, timeout=timeout_sec)
                results.append(MCPCallResult(
                    server=call.server,
                    tool=call.tool,
                    ok=True,
                    data=data,
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                ))
            except Exception as e:
                results.append(MCPCallResult(
                    server=call.server,
                    tool=call.tool,
                    ok=False,
                    data={"_error": str(e)},
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                ))
        return results

    @staticmethod
    def format_results_for_prompt(results: List[MCPCallResult]) -> str:
        """Render results as a prompt-ready observation block."""
        if not results:
            return ""
        lines = ["[Tool results from last turn]"]
        for r in results:
            status = "OK" if r.ok else "ERR"
            try:
                body = json.dumps(r.data, ensure_ascii=False, default=str)[:600]
            except Exception:
                body = str(r.data)[:600]
            lines.append(f"- {r.server}/{r.tool} [{status}, {r.latency_ms}ms]: {body}")
        return "\n".join(lines)

    def shutdown(self) -> None:
        with self._lock:
            for proc in self._servers.values():
                proc.shutdown()
            self._servers.clear()
