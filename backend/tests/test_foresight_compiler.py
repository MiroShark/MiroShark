"""Tests for foresight_compiler.compile_foresight."""

from unittest.mock import patch, MagicMock


def _seed_for_tests():
    return {
        "topic": "Australia 25% windfall gas tax",
        "intent": "Pros/cons brief, balanced",
        "stakeholders": [],
        "decision_branches": [],
        "contested_claims": [],
        "output_format": "media_landscape",
    }


def _tree_for_tests():
    return {
        "id": "root",
        "type": "central",
        "question": "Should Australia tax gas more?",
        "user_notes": "",
        "summary": "",
        "evidence": [],
        "children": [
            {
                "id": "u1",
                "type": "upstream",
                "question": "Should the state collect more tax at all?",
                "summary": "Sources are split. Public-finance economists argue Australia is undertaxing resource rents; libertarian framings note the burden falls on consumers.",
                "user_notes": "",
                "evidence": [],
                "children": [],
            },
            {
                "id": "d1",
                "type": "downstream",
                "question": "What if a 25% flat rate is enacted?",
                "summary": "Modelling suggests $X bn in additional revenue with limited investment flight risk.",
                "user_notes": "",
                "evidence": [],
                "children": [
                    {
                        "id": "d1c1",
                        "type": "downstream",
                        "question": "Effects on regional WA towns?",
                        "summary": "Mining payroll concentration is high in 4 LGAs; carve-outs may be needed.",
                        "user_notes": "",
                        "evidence": [],
                        "children": [],
                    },
                ],
            },
            {
                "id": "a1",
                "type": "analogy",
                "question": "What did Norway do?",
                "summary": "Norway taxes petroleum at 78% effective rate. Operators have not exited.",
                "user_notes": "",
                "evidence": [],
                "children": [],
            },
            {
                "id": "f1",
                "type": "free",
                "question": "Is the '50k jobs lost' claim accurate?",
                "summary": "No credible model produces a 50k figure; the strongest scenarios show 5-12k regional impacts over a decade.",
                "user_notes": "",
                "evidence": [],
                "children": [],
            },
        ],
    }


def test_compile_foresight_passes_grouped_tree_to_llm():
    from app.services.foresight_compiler import compile_foresight

    seed = _seed_for_tests()
    tree = _tree_for_tests()

    with patch("app.services.foresight_compiler.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "# Foresight\n\n## TL;DR\n..."
        mock_factory.return_value = mock_client

        result = compile_foresight(seed, tree)

    sent = mock_client.chat.call_args.kwargs.get("messages") or mock_client.chat.call_args.args[0]
    user_msg = next(m for m in sent if m["role"] == "user")
    # All four type sections should be referenced in the user message
    assert "Upstream" in user_msg["content"]
    assert "Downstream" in user_msg["content"]
    assert "Analogy" in user_msg["content"]
    assert "Free" in user_msg["content"]
    # Summaries should be passed through
    assert "78%" in user_msg["content"]
    assert "50k" in user_msg["content"]
    assert result.startswith("# Foresight")


def test_compile_foresight_handles_tree_without_summaries():
    from app.services.foresight_compiler import compile_foresight

    seed = _seed_for_tests()
    tree = {
        "id": "root", "type": "central", "question": "Q?",
        "user_notes": "", "summary": "", "evidence": [],
        "children": [
            {"id": "u1", "type": "upstream", "question": "?",
             "summary": "", "user_notes": "", "evidence": [], "children": []},
        ],
    }

    with patch("app.services.foresight_compiler.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "## TL;DR\nNot enough exploration yet."
        mock_factory.return_value = mock_client

        result = compile_foresight(seed, tree)

    sent = mock_client.chat.call_args.kwargs.get("messages") or mock_client.chat.call_args.args[0]
    user_msg = next(m for m in sent if m["role"] == "user")
    # When a node has no summary, the message should say so explicitly
    assert "not yet synthesised" in user_msg["content"].lower()
    assert result == "## TL;DR\nNot enough exploration yet."


def test_compile_foresight_strips_code_fences():
    from app.services.foresight_compiler import compile_foresight

    with patch("app.services.foresight_compiler.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "```markdown\n# Doc\n```"
        mock_factory.return_value = mock_client

        result = compile_foresight(_seed_for_tests(), _tree_for_tests())

    assert "```" not in result
    assert result.strip().startswith("# Doc")


def test_compile_foresight_passes_subnode_summaries():
    """Sub-questions and sub-summaries from expanded children should appear."""
    from app.services.foresight_compiler import compile_foresight

    with patch("app.services.foresight_compiler.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat.return_value = "ok"
        mock_factory.return_value = mock_client

        compile_foresight(_seed_for_tests(), _tree_for_tests())

    user_msg = next(m for m in (
        mock_factory.return_value.chat.call_args.kwargs.get("messages")
        or mock_factory.return_value.chat.call_args.args[0]
    ) if m["role"] == "user")
    # The expanded sub-question + sub-summary from d1c1 should be in the prompt
    assert "regional WA towns" in user_msg["content"]
    assert "Mining payroll concentration" in user_msg["content"]
