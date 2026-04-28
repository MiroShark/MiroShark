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


# ---- Phase C: session endpoints ----


def test_post_sessions_creates_new_session(client):
    fake_session = {
        "id": "abc123",
        "title": "",
        "created_at": "2026-04-29T10:00:00+00:00",
        "updated_at": "2026-04-29T10:00:00+00:00",
        "messages": [],
        "seed_state": {},
        "ready_to_launch": False,
    }
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.create.return_value = fake_session
        response = client.post("/api/seed-chat/sessions")

    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == "abc123"
    assert body["messages"] == []


def test_get_sessions_returns_summary_list(client):
    fake_summaries = [
        {"id": "s1", "title": "First", "created_at": "t1", "updated_at": "t2"},
        {"id": "s2", "title": "Second", "created_at": "t1", "updated_at": "t1"},
    ]
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.list.return_value = fake_summaries
        response = client.get("/api/seed-chat/sessions")

    assert response.status_code == 200
    body = response.get_json()
    assert body["sessions"] == fake_summaries


def test_get_session_by_id_returns_full_session(client):
    fake = {
        "id": "abc123",
        "title": "Loaded",
        "created_at": "t1",
        "updated_at": "t2",
        "messages": [{"role": "user", "content": "hi"}],
        "seed_state": {"topic": "X"},
        "ready_to_launch": False,
    }
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = fake
        response = client.get("/api/seed-chat/sessions/abc123")

    assert response.status_code == 200
    body = response.get_json()
    assert body == fake


def test_get_session_missing_returns_404(client):
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = None
        response = client.get("/api/seed-chat/sessions/missing")

    assert response.status_code == 404


def test_turn_with_session_id_autosaves(client):
    """When /turn includes session_id, the post-turn state is saved to the store."""
    fake_existing = {
        "id": "abc123",
        "title": "",
        "created_at": "t0",
        "updated_at": "t0",
        "messages": [],
        "seed_state": {},
        "ready_to_launch": False,
    }
    post_turn_state = {
        "topic": "X",
        "intent": "Y",
        "stakeholders": [],
        "decision_branches": [],
        "contested_claims": [],
        "output_format": "",
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.process_turn") as mock_pt:
        mock_store.load.return_value = fake_existing
        mock_pt.return_value = ("Reply", post_turn_state, False)

        response = client.post(
            "/api/seed-chat/turn",
            json={
                "messages": [{"role": "user", "content": "I want a brief on X"}],
                "seed_state": {},
                "session_id": "abc123",
            },
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["session_id"] == "abc123"
    assert body["assistant_message"] == "Reply"

    # save() called once with the updated session
    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    assert saved["id"] == "abc123"
    assert saved["seed_state"] == post_turn_state
    assert saved["ready_to_launch"] is False
    # messages should now include both turns
    assert len(saved["messages"]) == 2
    assert saved["messages"][0] == {"role": "user", "content": "I want a brief on X"}
    assert saved["messages"][1] == {"role": "assistant", "content": "Reply"}
    # title auto-populated from first user message (truncated)
    assert saved["title"] != ""
