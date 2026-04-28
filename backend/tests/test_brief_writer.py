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


def test_write_brief_includes_sources_when_provided():
    from app.services.brief_writer import write_brief

    seed = {
        "topic": "X",
        "intent": "Y",
        "stakeholders": [{"name": "A", "role": "r", "stance": "neutral"}],
        "decision_branches": [],
        "contested_claims": [],
        "output_format": "pros_cons",
    }
    sources = [
        {
            "url": "https://example.com/article1",
            "title": "First source",
            "snippet": "snippet 1",
            "text": "Body of source 1.",
        },
        {
            "url": "https://example.com/article2",
            "title": "Second source",
            "snippet": "snippet 2",
            "text": "Body of source 2.",
            "fetch_error": None,
        },
    ]

    with patch("app.services.brief_writer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "# Sourced brief"
        mock_factory.return_value = mock_client

        result = write_brief(seed, [], research_sources=sources)

    sent = mock_client.chat.call_args.kwargs.get("messages") or mock_client.chat.call_args.args[0]
    system = next((m for m in sent if m["role"] == "system"), None)
    assert system is not None
    assert "First source" in system["content"]
    assert "https://example.com/article1" in system["content"]
    assert "cite" in system["content"].lower() or "citation" in system["content"].lower()
    assert result == "# Sourced brief"


def test_write_brief_skips_sources_with_fetch_errors_or_empty_text():
    from app.services.brief_writer import write_brief

    seed = {
        "topic": "X", "intent": "Y",
        "stakeholders": [{"name": "A", "role": "r", "stance": "neutral"}],
        "decision_branches": [], "contested_claims": [],
        "output_format": "pros_cons",
    }
    sources = [
        {"url": "u1", "title": "T1", "snippet": "s", "text": "", "fetch_error": "404"},
        {"url": "u2", "title": "T2", "snippet": "s", "text": "valid body"},
    ]

    with patch("app.services.brief_writer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "ok"
        mock_factory.return_value = mock_client

        write_brief(seed, [], research_sources=sources)

    sent = mock_client.chat.call_args.kwargs.get("messages") or mock_client.chat.call_args.args[0]
    system_content = next(m["content"] for m in sent if m["role"] == "system")
    assert "T2" in system_content
    assert "T1" not in system_content
