"""Tests for the pure-Python pieces of the MCP runtime bridge — the
``<mcp_call .../>`` parser and the system-message injection markers. Does
not spawn subprocesses.
"""

from __future__ import annotations

import pytest

from mcp_agent_bridge import MCPCallResult, parse_tool_calls
from mcp_agent_injection import (
    inject_mcp_catalogue,
    inject_mcp_results,
    strip_mcp_call_tags,
)


class _FakeMsg:
    def __init__(self, content: str):
        self.content = content


class _FakeAgent:
    def __init__(self, content: str = ""):
        self.system_message = _FakeMsg(content)


def test_parser_no_calls():
    assert parse_tool_calls("just a post with no tool calls") == []


def test_parser_simple_call():
    calls = parse_tool_calls(
        '<mcp_call server="web_search" tool="search" args=\'{"q":"polymarket"}\' />'
    )
    assert len(calls) == 1
    assert calls[0].server == "web_search"
    assert calls[0].tool == "search"
    assert calls[0].args == {"q": "polymarket"}


def test_parser_tolerates_bad_args_json():
    calls = parse_tool_calls(
        '<mcp_call server="s" tool="t" args=\'this is not json\' />'
    )
    assert calls[0].args == {}


def test_parser_respects_max_calls():
    text = " ".join(
        f'<mcp_call server="s" tool="t{i}" args=\'{{}}\' />' for i in range(5)
    )
    got = parse_tool_calls(text, max_calls=2)
    assert len(got) == 2
    assert [c.tool for c in got] == ["t0", "t1"]


def test_parser_handles_missing_args():
    calls = parse_tool_calls('<mcp_call server="s" tool="list" />')
    assert len(calls) == 1
    assert calls[0].args == {}


def test_strip_removes_call_tags():
    raw = 'hi <mcp_call server="s" tool="t" args=\'{}\' /> bye'
    assert strip_mcp_call_tags(raw) == "hi  bye"


def test_strip_is_noop_when_no_tag():
    assert strip_mcp_call_tags("nothing here") == "nothing here"


def test_inject_catalogue_appends_block():
    agent = _FakeAgent("You are an analyst.")
    inject_mcp_catalogue(agent, "- web/search: web\n- price/get: price")
    assert "MCP TOOLS AVAILABLE" in agent.system_message.content
    assert "web/search" in agent.system_message.content
    # Original content preserved.
    assert "You are an analyst." in agent.system_message.content


def test_inject_catalogue_replaces_previous_block():
    agent = _FakeAgent("hi")
    inject_mcp_catalogue(agent, "first catalogue")
    inject_mcp_catalogue(agent, "second catalogue")
    # Old block removed, new one present.
    assert agent.system_message.content.count("MCP TOOLS AVAILABLE") == 1
    assert "second catalogue" in agent.system_message.content
    assert "first catalogue" not in agent.system_message.content


def test_inject_results_formats_ok_and_error():
    agent = _FakeAgent("")
    inject_mcp_results(agent, [
        MCPCallResult(server="w", tool="search", ok=True, data={"hits": 3}, latency_ms=42),
        MCPCallResult(server="p", tool="price", ok=False, data={"_error": "timeout"}, latency_ms=30000),
    ])
    body = agent.system_message.content
    assert "MCP TOOL RESULTS" in body
    assert "w/search [OK, 42ms]" in body
    assert "p/price [ERR, 30000ms]" in body
    assert "timeout" in body


def test_inject_results_empty_clears_previous():
    agent = _FakeAgent("hi")
    inject_mcp_results(agent, [
        MCPCallResult(server="w", tool="s", ok=True, data={}, latency_ms=5),
    ])
    assert "MCP TOOL RESULTS" in agent.system_message.content
    inject_mcp_results(agent, [])
    assert "MCP TOOL RESULTS" not in agent.system_message.content
