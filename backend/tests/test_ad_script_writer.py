"""Tests for ad_script_writer.write_ad_scripts."""

from unittest.mock import patch, MagicMock


SEED = {
    "topic": "Topic X",
    "intent": "Pros/cons brief",
    "stakeholders": [
        {"name": "Industry", "role": "lobby", "stance": "opposing"},
        {"name": "Advocacy", "role": "advocate", "stance": "supporting"},
    ],
    "decision_branches": [],
    "contested_claims": ["Claim A: 50k jobs lost"],
    "output_format": "media_landscape",
}


def test_write_ad_scripts_passes_seed_brief_and_sources_to_llm():
    from app.services.ad_script_writer import write_ad_scripts

    with patch("app.services.ad_script_writer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "## Script 1\n[0:00] NARRATOR: ..."
        mock_factory.return_value = mock_client

        result = write_ad_scripts(
            SEED,
            brief="# Brief\n\nfacts here",
            sources=[
                {"url": "u1", "title": "Source 1", "snippet": "s",
                 "text": "Source body content", "fetch_error": None},
            ],
        )

    sent = mock_client.chat.call_args.kwargs.get("messages") or mock_client.chat.call_args.args[0]
    system = next((m for m in sent if m["role"] == "system"), None)
    user = next((m for m in sent if m["role"] == "user"), None)

    assert system is not None
    assert "both sides" in system["content"].lower() or "both" in system["content"].lower()
    assert "compromise" in system["content"].lower() or "sensible" in system["content"].lower()
    assert user is not None
    assert "Topic X" in user["content"]
    assert "facts here" in user["content"]
    assert "Source 1" in user["content"]
    assert "Source body content" in user["content"]
    assert result.startswith("## Script 1")


def test_write_ad_scripts_strips_code_fences():
    from app.services.ad_script_writer import write_ad_scripts

    with patch("app.services.ad_script_writer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "```markdown\n## Script 1\n...\n```"
        mock_factory.return_value = mock_client

        result = write_ad_scripts(SEED, brief="x", sources=[])

    assert "```" not in result
    assert result.strip().startswith("## Script 1")


def test_write_ad_scripts_skips_sources_with_fetch_errors_or_empty_text():
    from app.services.ad_script_writer import write_ad_scripts

    with patch("app.services.ad_script_writer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "## Script 1\n..."
        mock_factory.return_value = mock_client

        write_ad_scripts(
            SEED,
            brief="b",
            sources=[
                {"url": "u1", "title": "Bad", "snippet": "s", "text": "", "fetch_error": "404"},
                {"url": "u2", "title": "Good", "snippet": "s", "text": "Body content"},
            ],
        )

    user_msg = next(
        m for m in (
            mock_factory.return_value.chat.call_args.kwargs.get("messages")
            or mock_factory.return_value.chat.call_args.args[0]
        ) if m["role"] == "user"
    )
    assert "Good" in user_msg["content"]
    assert "Bad" not in user_msg["content"]
