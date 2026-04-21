"""Tests for LLMClient's Anthropic prompt-cache wrapping helper. No network."""

from __future__ import annotations

from app.utils.llm_client import LLMClient


def test_wrap_converts_system_string_to_cache_block():
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "hi"},
    ]
    out = LLMClient._maybe_cache_wrap_messages(msgs)
    # System now a list with cache_control on the single text block.
    sys_msg = out[0]
    assert sys_msg["role"] == "system"
    assert isinstance(sys_msg["content"], list)
    assert sys_msg["content"][0]["text"] == "You are a helpful assistant."
    assert sys_msg["content"][0]["cache_control"] == {"type": "ephemeral"}
    # User message untouched.
    assert out[1] == {"role": "user", "content": "hi"}


def test_wrap_is_noop_when_no_system_message():
    msgs = [{"role": "user", "content": "hi"}]
    out = LLMClient._maybe_cache_wrap_messages(msgs)
    assert out == msgs


def test_wrap_only_touches_first_system_message():
    msgs = [
        {"role": "system", "content": "first"},
        {"role": "user", "content": "q1"},
        {"role": "system", "content": "second"},
    ]
    out = LLMClient._maybe_cache_wrap_messages(msgs)
    assert isinstance(out[0]["content"], list)
    assert out[2] == {"role": "system", "content": "second"}


def test_wrap_ignores_already_listed_content():
    msgs = [
        {"role": "system", "content": [{"type": "text", "text": "x"}]},
        {"role": "user", "content": "hi"},
    ]
    out = LLMClient._maybe_cache_wrap_messages(msgs)
    # Leaves the pre-wrapped content alone (no cache_control injected).
    assert out[0]["content"] == [{"type": "text", "text": "x"}]


def test_wrap_empty_messages():
    assert LLMClient._maybe_cache_wrap_messages([]) == []
