"""Unit tests for the MCP onboarding API.

These tests are pure offline checks against the helpers in
``app/api/mcp.py``. The ``GET /api/mcp/status`` route is a thin Flask
wrapper around ``build_status_payload`` — verifying the helper covers the
shape contract that the SettingsPanel.vue frontend relies on. Live Flask /
Neo4j integration is exercised by the integration suite.

We cover:

  1. The tool catalog matches what ``backend/mcp_server.py`` actually
     registers (drift here means the Settings panel would advertise tools
     that don't exist or hide ones that do).
  2. Every supported MCP client gets a valid, non-empty config snippet
     whose paths can be JSON-serialized (the frontend pretty-prints them).
  3. The Neo4j probe defaults are conservative when no probe is supplied
     — the endpoint must always return a payload, never raise.
  4. The resolved Python interpreter and mcp_server.py paths point at
     real, on-disk locations under the backend dir.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Tool catalog drift ──────────────────────────────────────────────────


def _tool_names_from_mcp_server() -> set:
    """Extract every ``Tool(name="...")`` from mcp_server.py without
    importing it (importing would pull in the MCP SDK and Neo4j driver).
    """
    src = (_BACKEND / "mcp_server.py").read_text(encoding="utf-8")
    return set(re.findall(r'Tool\(\s*name=\"([a-z_]+)\"', src))


def test_tool_catalog_matches_mcp_server():
    """The Settings panel's advertised tool list must equal mcp_server.py's
    actual registrations — no phantom tools, no missing tools."""
    from app.api.mcp import _TOOLS

    api_names = {t["name"] for t in _TOOLS}
    server_names = _tool_names_from_mcp_server()

    assert api_names == server_names, (
        f"Tool catalog drift!\n"
        f"  in api/mcp.py only: {api_names - server_names}\n"
        f"  in mcp_server.py only: {server_names - api_names}"
    )


def test_every_tool_has_nonempty_description():
    """Empty descriptions render as a blank cell in the AI Integration
    panel — not useful and visually broken."""
    from app.api.mcp import _TOOLS

    for tool in _TOOLS:
        assert tool["description"].strip(), f"Tool {tool['name']!r} has empty description"


# ── Status payload shape ────────────────────────────────────────────────


def test_status_payload_has_required_top_level_keys():
    from app.api.mcp import build_status_payload

    payload = build_status_payload()

    for key in ("enabled", "transport", "paths", "tools", "tool_count", "clients", "neo4j", "docs_url"):
        assert key in payload, f"missing key {key!r} in payload"

    assert payload["enabled"] is True
    assert payload["transport"] == "stdio"
    assert payload["tool_count"] == len(payload["tools"])
    assert payload["docs_url"].startswith("https://")


def test_paths_block_resolves_to_real_files():
    """The snippet stamps these absolute paths into the user's MCP client
    config. They must point at on-disk locations under the backend dir,
    otherwise the snippet is broken on first paste."""
    from app.api.mcp import build_status_payload

    paths = build_status_payload()["paths"]

    backend_dir = Path(paths["backend_dir"])
    mcp_script = Path(paths["mcp_script"])
    py_executable = Path(paths["python_executable"])

    assert backend_dir.is_dir(), f"backend_dir {backend_dir} is not a directory"
    assert mcp_script == backend_dir / "mcp_server.py"
    assert mcp_script.is_file(), "mcp_server.py was not packaged with backend"
    assert paths["mcp_script_exists"] is True
    # Don't require .is_file() on the interpreter — pytest may run under a
    # frozen / shimmed binary on some platforms — but it must be absolute.
    assert py_executable.is_absolute(), f"python_executable {py_executable} is not absolute"


# ── Client snippets ─────────────────────────────────────────────────────


_REQUIRED_CLIENTS = ("claude_desktop", "cursor", "windsurf", "continue", "fallback_direct")


@pytest.mark.parametrize("client_key", _REQUIRED_CLIENTS)
def test_each_client_snippet_is_present_and_serializable(client_key):
    """Every client supported by the Settings panel must have a snippet
    that round-trips through json.dumps without raising — that's what the
    frontend ``formatJson(config)`` call relies on."""
    from app.api.mcp import build_status_payload

    clients = build_status_payload()["clients"]
    assert client_key in clients, f"missing client {client_key!r}"

    entry = clients[client_key]
    assert entry["label"], f"{client_key} missing label"
    assert entry["config"], f"{client_key} has empty config"
    # Round-trips cleanly — frontend uses JSON.stringify with the same data.
    serialized = json.dumps(entry["config"], indent=2)
    assert serialized
    # Parsable back into the same dict.
    assert json.loads(serialized) == entry["config"]


def test_mcpServers_snippets_reference_miroshark_entry():
    """All four mcpServers-shaped snippets must register under the key
    'miroshark' so the docs/UI guidance stays consistent."""
    from app.api.mcp import build_status_payload

    clients = build_status_payload()["clients"]
    for key in ("claude_desktop", "cursor", "windsurf", "fallback_direct"):
        cfg = clients[key]["config"]
        assert "mcpServers" in cfg, f"{key} snippet missing mcpServers wrapper"
        assert "miroshark" in cfg["mcpServers"], f"{key} snippet missing 'miroshark' entry"


def test_continue_snippet_uses_modelContextProtocolServers():
    """Continue uses a different config shape than Claude Desktop / Cursor —
    if this regresses, Continue users get an empty MCP server list."""
    from app.api.mcp import build_status_payload

    cfg = build_status_payload()["clients"]["continue"]["config"]
    servers = cfg.get("experimental", {}).get("modelContextProtocolServers")
    assert isinstance(servers, list) and servers, "continue: missing or empty server list"
    assert servers[0]["transport"]["type"] == "stdio"
    assert "command" in servers[0]["transport"]
    assert "args" in servers[0]["transport"]


def test_fallback_direct_snippet_uses_python_interpreter_directly():
    """The fallback path is for users without uv on PATH — it must wire the
    snippet to the actual Python interpreter, not the uv wrapper."""
    from app.api.mcp import build_status_payload

    payload = build_status_payload()
    fallback = payload["clients"]["fallback_direct"]["config"]["mcpServers"]["miroshark"]
    assert fallback["command"] == payload["paths"]["python_executable"]
    assert fallback["args"] == [payload["paths"]["mcp_script"]]


# ── Defensive defaults ──────────────────────────────────────────────────


def test_payload_includes_neo4j_block_even_without_probe():
    """The endpoint must always return 200 with a complete payload —
    the Settings panel renders error guidance from the neo4j block when
    things are down."""
    from app.api.mcp import build_status_payload

    neo4j = build_status_payload()["neo4j"]
    for key in ("connected", "uri", "user", "graph_count", "entity_count", "error"):
        assert key in neo4j, f"missing neo4j key {key!r}"
    # No probe was supplied → connected must be False, error explained.
    assert neo4j["connected"] is False
    assert neo4j["error"]


def test_supplied_probe_is_passed_through_unchanged():
    """When the route's _probe_neo4j() succeeds, its dict must reach the
    UI verbatim so we don't double-mask connection state."""
    from app.api.mcp import build_status_payload

    probe = {
        "connected": True,
        "uri": "bolt://localhost:7687",
        "user": "neo4j",
        "graph_count": 7,
        "entity_count": 1234,
        "error": None,
    }
    payload = build_status_payload(neo4j_probe=probe)
    assert payload["neo4j"] == probe
