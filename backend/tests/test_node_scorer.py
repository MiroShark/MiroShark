"""Tests for node_scorer.score_node."""

from unittest.mock import patch, MagicMock


def _node_for_tests():
    return {
        "id": "n1",
        "question": "Will the tax trigger 50k job losses?",
        "summary": "Sources disagree. Industry models say yes; independent modelling says 5-12k.",
        "user_notes": "",
        "evidence": [
            {"url": "u1", "title": "T1", "text": "Body of T1.", "fetch_error": None},
        ],
    }


def test_score_node_returns_normalised_scores():
    from app.services.node_scorer import score_node

    with patch("app.services.node_scorer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {
            "confidence": "Medium",
            "contestedness": "DISPUTED",
            "salience": "high",
            "stance_summary": "Industry's 50k figure is unsupported by independent models.",
        }
        mock_factory.return_value = mock_client

        scores = score_node(_node_for_tests())

    assert scores["confidence"] == "medium"
    assert scores["contestedness"] == "disputed"
    assert scores["salience"] == "high"
    assert "Industry" in scores["stance_summary"]


def test_score_node_falls_back_to_defaults_on_invalid_values():
    from app.services.node_scorer import score_node

    with patch("app.services.node_scorer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {
            "confidence": "very high",  # invalid
            "contestedness": "??",       # invalid
            "salience": "niche",
            "stance_summary": "ok",
        }
        mock_factory.return_value = mock_client

        scores = score_node(_node_for_tests())

    assert scores["confidence"] == "low"        # default
    assert scores["contestedness"] == "contested"  # default
    assert scores["salience"] == "niche"
    assert scores["stance_summary"] == "ok"


def test_score_node_handles_malformed_llm_response():
    from app.services.node_scorer import score_node

    with patch("app.services.node_scorer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.side_effect = ValueError("bad json")
        mock_factory.return_value = mock_client

        scores = score_node(_node_for_tests())

    # Falls through to defaults
    assert scores["confidence"] == "low"
    assert scores["contestedness"] == "contested"
    assert scores["salience"] == "moderate"
    assert scores["stance_summary"] == ""


def test_score_node_includes_question_summary_and_evidence_in_prompt():
    from app.services.node_scorer import score_node

    with patch("app.services.node_scorer.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {
            "confidence": "high",
            "contestedness": "settled",
            "salience": "moderate",
            "stance_summary": "ok",
        }
        mock_factory.return_value = mock_client

        score_node(_node_for_tests())

    sent = mock_client.chat_json.call_args.kwargs.get("messages") or mock_client.chat_json.call_args.args[0]
    user_msg = next(m for m in sent if m["role"] == "user")
    assert "50k job losses" in user_msg["content"]
    assert "Industry models say yes" in user_msg["content"]
    assert "Body of T1." in user_msg["content"]
