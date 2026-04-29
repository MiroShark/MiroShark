"""Tests for tree_synthesizer.synthesise_node."""

from unittest.mock import patch, MagicMock


def test_synthesise_node_passes_question_and_evidence_to_llm():
    from app.services.tree_synthesizer import synthesise_node

    node = {
        "id": "n1",
        "question": "Will the tax trigger 50k job losses?",
        "user_notes": "Industry claim from APPEA.",
        "evidence": [
            {"url": "https://example.com/a", "title": "Source A",
             "text": "Body of source A.", "fetch_error": None},
        ],
    }

    with patch("app.services.tree_synthesizer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "## Summary\n\nBody."
        mock_factory.return_value = mock_client

        result = synthesise_node(node)

    sent = mock_client.chat.call_args.kwargs.get("messages") or mock_client.chat.call_args.args[0]
    user_msg = next(m for m in sent if m["role"] == "user")
    assert "Will the tax trigger 50k job losses?" in user_msg["content"]
    assert "Source A" in user_msg["content"]
    assert "Body of source A." in user_msg["content"]
    assert "APPEA" in user_msg["content"]
    assert result.startswith("## Summary")


def test_synthesise_node_handles_empty_evidence():
    from app.services.tree_synthesizer import synthesise_node

    node = {"id": "n1", "question": "Q?", "user_notes": "", "evidence": []}

    with patch("app.services.tree_synthesizer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "Synthesis with note about no sources."
        mock_factory.return_value = mock_client

        result = synthesise_node(node)

    user_msg = next(m for m in (
        mock_factory.return_value.chat.call_args.kwargs.get("messages")
        or mock_factory.return_value.chat.call_args.args[0]
    ) if m["role"] == "user")
    assert "no web sources" in user_msg["content"].lower() or "no fetched" in user_msg["content"].lower()
    assert result == "Synthesis with note about no sources."


def test_synthesise_node_skips_evidence_with_fetch_errors():
    from app.services.tree_synthesizer import synthesise_node

    node = {
        "id": "n1", "question": "Q?", "user_notes": "",
        "evidence": [
            {"url": "u1", "title": "Bad", "text": "", "fetch_error": "404"},
            {"url": "u2", "title": "Good", "text": "real body"},
        ],
    }

    with patch("app.services.tree_synthesizer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "ok"
        mock_factory.return_value = mock_client

        synthesise_node(node)

    user_msg = next(m for m in (
        mock_factory.return_value.chat.call_args.kwargs.get("messages")
        or mock_factory.return_value.chat.call_args.args[0]
    ) if m["role"] == "user")
    assert "Good" in user_msg["content"]
    assert "Bad" not in user_msg["content"]


def test_synthesise_node_strips_code_fences():
    from app.services.tree_synthesizer import synthesise_node

    node = {"id": "n1", "question": "Q", "user_notes": "",
            "evidence": [{"url": "u", "title": "T", "text": "x"}]}

    with patch("app.services.tree_synthesizer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "```markdown\n## S\n```"
        mock_factory.return_value = mock_client

        result = synthesise_node(node)

    assert "```" not in result
    assert result.strip().startswith("## S")
