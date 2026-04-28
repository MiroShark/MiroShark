"""Tests for brief_writer.write_brief."""

from unittest.mock import patch, MagicMock


def test_write_brief_calls_llm_with_seed_and_history():
    from app.services.brief_writer import write_brief

    seed = {
        "topic": "X",
        "intent": "pros/cons",
        "stakeholders": [{"name": "A", "role": "r", "stance": "neutral"}],
        "decision_branches": [],
        "contested_claims": [],
        "output_format": "pros_cons",
    }
    messages = [
        {"role": "user", "content": "I want X"},
        {"role": "assistant", "content": "OK, who are the stakeholders?"},
    ]

    with patch("app.services.brief_writer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "# Brief on X\n\n## Pros\n- ...\n## Cons\n- ..."
        mock_factory.return_value = mock_client

        result = write_brief(seed, messages)

    mock_client.chat.assert_called_once()
    sent_messages = mock_client.chat.call_args.kwargs.get("messages") or mock_client.chat.call_args.args[0]
    assert any(m["role"] == "system" for m in sent_messages)
    assert any("X" in m.get("content", "") for m in sent_messages)
    assert result.startswith("# Brief on X")


def test_write_brief_strips_code_fences():
    from app.services.brief_writer import write_brief

    seed = {
        "topic": "X",
        "intent": "Y",
        "stakeholders": [{"name": "A", "role": "r", "stance": "neutral"}],
        "decision_branches": [],
        "contested_claims": [],
        "output_format": "pros_cons",
    }

    with patch("app.services.brief_writer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "```markdown\n# Title\n\nbody\n```"
        mock_factory.return_value = mock_client

        result = write_brief(seed, [])

    assert "```" not in result
    assert result.strip().startswith("# Title")
