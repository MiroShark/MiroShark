"""Unit tests for Wonderwall SocialAgent OpenAI message filtering."""

import json

from app.utils.llm_message_filter import (
    filter_openai_messages_for_api,
    repair_tool_call_arguments,
)


def test_filter_drops_empty_user_turns():
    messages = [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": ""},
        {"role": "user", "content": "Observe the platform."},
    ]
    filtered = filter_openai_messages_for_api(messages)
    assert filtered == [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": "Observe the platform."},
    ]


def test_filter_keeps_assistant_tool_calls_with_empty_content():
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "create_post", "arguments": "{}"},
        }
    ]
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": None, "tool_calls": tool_calls},
        {"role": "tool", "tool_call_id": "call_1", "content": '{"ok": true}'},
    ]
    filtered = filter_openai_messages_for_api(messages)
    assert filtered == messages


def test_filter_keeps_multi_iteration_tool_chain():
    """Regression: stripping empty assistant tool_calls caused Azure 400s."""
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "round 1"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "a", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "result"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "b", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c2", "content": "result2"},
    ]
    filtered = filter_openai_messages_for_api(messages)
    assert len(filtered) == 6
    assert filtered[2]["role"] == "assistant" and filtered[2]["tool_calls"]
    assert filtered[4]["role"] == "assistant" and filtered[4]["tool_calls"]


def test_filter_empty_context_fallback():
    assert filter_openai_messages_for_api([]) == [
        {"role": "user", "content": "(empty context)"}
    ]


def test_repair_leaves_valid_arguments_untouched():
    """Well-formed arguments need no repair, so the helper reports None."""
    for valid in ("{}", '{"a": 1}', '{"nested": {"x": [1, 2]}}', "[]"):
        assert repair_tool_call_arguments(valid) is None


def test_repair_drops_trailing_garbage():
    """Regression: DeepSeek-V4-Flash appends stray data after valid JSON."""
    repaired = repair_tool_call_arguments('{}""')
    assert repaired is not None
    new_args, dropped = repaired
    assert json.loads(new_args) == {}
    assert dropped == '""'


def test_repair_keeps_first_value_and_reserializes():
    repaired = repair_tool_call_arguments('{"count": 3}  <trailing>')
    assert repaired is not None
    new_args, dropped = repaired
    assert json.loads(new_args) == {"count": 3}
    assert dropped == "  <trailing>"


def test_repair_returns_none_for_unrecoverable_arguments():
    """No leading valid JSON value → nothing we can salvage; caller raises."""
    for bad in ("", "not json at all", "{unquoted: key}"):
        assert repair_tool_call_arguments(bad) is None
