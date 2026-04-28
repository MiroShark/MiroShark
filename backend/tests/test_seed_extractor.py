"""Tests for seed_extractor.process_turn."""

from unittest.mock import patch, MagicMock

import pytest


def test_process_turn_fills_topic_from_first_message(empty_seed_state):
    from app.services.seed_extractor import process_turn

    fake_envelope = {
        "reply": "Got it. Who are the key stakeholders we should model?",
        "slots": {
            **empty_seed_state,
            "topic": "Australia 25% resources tax",
            "intent": "pros/cons brief",
        },
        "ready": False,
    }

    with patch("app.services.seed_extractor.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.return_value = fake_envelope
        mock_factory.return_value = mock_client

        messages = [
            {"role": "user", "content": "I want a pros/cons brief on Australia's 25% resources tax"}
        ]
        reply, updated, ready = process_turn(messages, empty_seed_state)

    assert reply == "Got it. Who are the key stakeholders we should model?"
    assert updated["topic"] == "Australia 25% resources tax"
    assert updated["intent"] == "pros/cons brief"
    assert ready is False


def test_process_turn_marks_ready_when_required_slots_filled(empty_seed_state):
    from app.services.seed_extractor import process_turn

    fake_envelope = {
        "reply": "I think we have what we need. Review and launch?",
        "slots": {
            "topic": "Australia 25% resources tax",
            "intent": "pros/cons brief",
            "stakeholders": [
                {"name": "Minerals Council", "role": "lobby", "stance": "opposing"},
                {"name": "ACTU", "role": "union", "stance": "supporting"},
            ],
            "decision_branches": [],
            "contested_claims": [],
            "output_format": "pros_cons",
        },
        "ready": True,
    }

    with patch("app.services.seed_extractor.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.return_value = fake_envelope
        mock_factory.return_value = mock_client

        _reply, _updated, ready = process_turn([{"role": "user", "content": "x"}], empty_seed_state)

    assert ready is True


def test_process_turn_not_ready_when_required_slot_missing(empty_seed_state):
    """If LLM says ready=True but required slots are missing, force ready=False."""
    from app.services.seed_extractor import process_turn

    fake_envelope = {
        "reply": "Done.",
        "slots": {
            "topic": "X",
            "intent": "Y",
            "stakeholders": [],  # required but empty
            "decision_branches": [],
            "contested_claims": [],
            "output_format": "pros_cons",
        },
        "ready": True,
    }

    with patch("app.services.seed_extractor.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.return_value = fake_envelope
        mock_factory.return_value = mock_client

        _reply, _updated, ready = process_turn([{"role": "user", "content": "x"}], empty_seed_state)

    assert ready is False, "Backend must override LLM ready flag when required slots empty"


def test_process_turn_preserves_state_on_malformed_json(empty_seed_state):
    """If LLM raises (malformed JSON), state is preserved and assistant reply degrades."""
    from app.services.seed_extractor import process_turn

    with patch("app.services.seed_extractor.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.side_effect = ValueError("malformed JSON")
        mock_factory.return_value = mock_client

        messages = [{"role": "user", "content": "hi"}]
        prior = {**empty_seed_state, "topic": "X"}
        reply, updated, ready = process_turn(messages, prior)

    assert updated == prior
    assert ready is False
    assert "had trouble" in reply.lower() or "try again" in reply.lower()
