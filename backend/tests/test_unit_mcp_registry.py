"""Unit tests for the per-agent MCP registry loader. No network."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from app.services import agent_mcp_tools as amt


@dataclass
class _FakeProfile:
    tools_enabled: bool = False
    allowed_tools: list = None  # type: ignore


def test_load_registry_off_by_default(monkeypatch):
    monkeypatch.delenv("MCP_AGENT_TOOLS_ENABLED", raising=False)
    assert amt.load_registry() == {}


def test_load_registry_missing_file(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MCP_AGENT_TOOLS_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVERS_CONFIG", str(tmp_path / "does_not_exist.yaml"))
    assert amt.load_registry() == {}


def test_load_registry_parses_manifest(monkeypatch, tmp_path: Path):
    pytest.importorskip("yaml")
    manifest = tmp_path / "mcp_servers.yaml"
    manifest.write_text(
        """
mcp_servers:
  - name: web_search
    command: python
    args: ["-m", "mcp_web"]
  - name: no_command
    args: []
"""
    )
    monkeypatch.setenv("MCP_AGENT_TOOLS_ENABLED", "true")
    monkeypatch.setenv("MCP_SERVERS_CONFIG", str(manifest))
    reg = amt.load_registry()
    # Entry without command is dropped; valid entry survives.
    assert list(reg.keys()) == ["web_search"]
    assert reg["web_search"].command == "python"
    assert reg["web_search"].args == ["-m", "mcp_web"]


def test_build_toolset_respects_tools_enabled(monkeypatch):
    monkeypatch.setenv("MCP_AGENT_TOOLS_ENABLED", "true")
    reg = {
        "web_search": amt.MCPServerSpec(name="web_search", command="python"),
        "price_feed": amt.MCPServerSpec(name="price_feed", command="node"),
    }
    # Disabled persona → empty toolset even when registry is full.
    profile = _FakeProfile(tools_enabled=False)
    assert amt.build_agent_toolset(profile, registry=reg) == {}


def test_build_toolset_allowlist_filters(monkeypatch):
    monkeypatch.setenv("MCP_AGENT_TOOLS_ENABLED", "true")
    reg = {
        "web_search": amt.MCPServerSpec(name="web_search", command="python"),
        "price_feed": amt.MCPServerSpec(name="price_feed", command="node"),
    }
    profile = _FakeProfile(tools_enabled=True, allowed_tools=["price_feed"])
    got = amt.build_agent_toolset(profile, registry=reg)
    assert list(got.keys()) == ["price_feed"]


def test_build_toolset_no_allowlist_means_all(monkeypatch):
    monkeypatch.setenv("MCP_AGENT_TOOLS_ENABLED", "true")
    reg = {
        "web_search": amt.MCPServerSpec(name="web_search", command="python"),
    }
    profile = _FakeProfile(tools_enabled=True, allowed_tools=[])
    assert amt.build_agent_toolset(profile, registry=reg) == reg


def test_summarize_empty_tools():
    assert "no MCP tools" in amt.summarize_toolset({})
