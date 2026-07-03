"""Unit tests for Wonderwall SocialAgent OpenAI message filtering."""

from app.utils.llm_message_filter import filter_openai_messages_for_api


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
