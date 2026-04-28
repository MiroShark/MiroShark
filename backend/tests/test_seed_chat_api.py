"""Tests for /api/seed-chat endpoints."""

from unittest.mock import patch

import pytest


@pytest.fixture
def client():
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_turn_endpoint_happy_path(client):
    fake_state = {
        "topic": "X",
        "intent": "Y",
        "stakeholders": [{"name": "A", "role": "r", "stance": "neutral"}],
        "decision_branches": [],
        "contested_claims": [],
        "output_format": "pros_cons",
    }

    with patch("app.api.seed_chat.process_turn") as mock_pt:
        mock_pt.return_value = ("Next question?", fake_state, False)

        response = client.post(
            "/api/seed-chat/turn",
            json={"messages": [{"role": "user", "content": "hi"}], "seed_state": {}},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["assistant_message"] == "Next question?"
    assert body["updated_seed_state"] == fake_state
    assert body["ready_to_launch"] is False


def test_turn_endpoint_rejects_missing_messages(client):
    response = client.post("/api/seed-chat/turn", json={"seed_state": {}})
    assert response.status_code == 400


def test_turn_endpoint_returns_503_on_llm_init_failure(client):
    with patch("app.api.seed_chat.process_turn", side_effect=RuntimeError("claude not installed")):
        response = client.post(
            "/api/seed-chat/turn",
            json={"messages": [{"role": "user", "content": "x"}], "seed_state": {}},
        )

    assert response.status_code == 503
    assert "claude" in response.get_json().get("error", "").lower()
