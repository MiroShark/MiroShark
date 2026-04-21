"""Unit tests for the FeedOracle-seed connector. No network."""

from __future__ import annotations

import os

from app.services import oracle_seed


def test_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setenv("ORACLE_SEED_ENABLED", "false")
    out = oracle_seed.resolve_oracle_tools(
        {"oracle_tools": [{"server": "x", "tool": "y", "args": {}}]}
    )
    assert out == ""


def test_returns_empty_when_no_tools(monkeypatch):
    monkeypatch.setenv("ORACLE_SEED_ENABLED", "true")
    assert oracle_seed.resolve_oracle_tools({"oracle_tools": []}) == ""
    assert oracle_seed.resolve_oracle_tools({}) == ""


def test_returns_empty_when_httpx_missing(monkeypatch):
    monkeypatch.setenv("ORACLE_SEED_ENABLED", "true")
    monkeypatch.setattr(oracle_seed, "httpx", None)
    out = oracle_seed.resolve_oracle_tools(
        {"oracle_tools": [{"server": "x", "tool": "y", "args": {}}]}
    )
    assert out == ""


def test_returns_empty_on_init_failure(monkeypatch):
    monkeypatch.setenv("ORACLE_SEED_ENABLED", "true")

    class _BoomClient:
        def __init__(self, *a, **kw):
            raise RuntimeError("boom")

    monkeypatch.setattr(oracle_seed, "_MCPClient", _BoomClient)
    out = oracle_seed.resolve_oracle_tools(
        {"oracle_tools": [{"server": "x", "tool": "y", "args": {}}]}
    )
    assert out == ""


def test_formats_markdown_block(monkeypatch):
    monkeypatch.setenv("ORACLE_SEED_ENABLED", "true")

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def initialize(self):
            pass

        def call_tool(self, name, args):
            return {"price": 1.002, "deviation_bps": 20}

        def close(self):
            pass

    monkeypatch.setattr(oracle_seed, "_MCPClient", _FakeClient)
    out = oracle_seed.resolve_oracle_tools({
        "oracle_tools": [
            {"server": "feedoracle_core", "tool": "peg_deviation", "args": {"token_symbol": "USDT"}},
        ],
    })
    assert "## Oracle Evidence" in out
    assert "feedoracle_core/peg_deviation" in out
    assert "token_symbol=USDT" in out
    assert "price" in out and "1.002" in out
