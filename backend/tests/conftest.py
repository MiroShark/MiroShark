"""Pytest fixtures for MiroShark backend tests."""

import pytest


@pytest.fixture
def fake_llm_response():
    """Returns a callable that builds a fake LLM JSON envelope."""
    def _build(reply: str, slots: dict, ready: bool = False):
        return {"reply": reply, "slots": slots, "ready": ready}
    return _build


@pytest.fixture
def empty_seed_state():
    """A blank seed state matching the schema."""
    return {
        "topic": "",
        "intent": "",
        "stakeholders": [],
        "decision_branches": [],
        "contested_claims": [],
        "output_format": "",
    }
