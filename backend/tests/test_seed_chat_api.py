"""Tests for /api/seed-chat endpoints."""

from unittest.mock import patch, MagicMock

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


# ---- Phase B (v2): /launch endpoint ----


def test_launch_returns_brief_and_saves_to_session(client):
    fake_session = {
        "id": "abc",
        "title": "Test",
        "created_at": "t1",
        "updated_at": "t2",
        "messages": [{"role": "user", "content": "X"}],
        "seed_state": {
            "topic": "X",
            "intent": "Y",
            "stakeholders": [
                {"name": "A", "role": "r", "stance": "neutral"},
                {"name": "B", "role": "r", "stance": "neutral"},
            ],
            "decision_branches": [],
            "contested_claims": [],
            "output_format": "pros_cons",
        },
        "ready_to_launch": True,
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.write_brief", return_value="# Brief\n\n...") as mock_writer:
        mock_store.load.return_value = fake_session
        response = client.post(
            "/api/seed-chat/launch",
            json={"session_id": "abc"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["session_id"] == "abc"
    assert body["brief_markdown"].startswith("# Brief")

    mock_writer.assert_called_once()
    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    assert saved["brief"] == "# Brief\n\n..."


def test_launch_404_when_session_missing(client):
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = None
        response = client.post(
            "/api/seed-chat/launch",
            json={"session_id": "missing"},
        )
    assert response.status_code == 404


def test_launch_400_when_required_slots_missing(client):
    incomplete_session = {
        "id": "abc", "title": "x", "created_at": "t", "updated_at": "t",
        "messages": [],
        "seed_state": {
            "topic": "X", "intent": "", "stakeholders": [],
            "decision_branches": [], "contested_claims": [], "output_format": "",
        },
        "ready_to_launch": False,
    }
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = incomplete_session
        response = client.post(
            "/api/seed-chat/launch",
            json={"session_id": "abc"},
        )
    assert response.status_code == 400


def test_launch_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/launch", json={})
    assert response.status_code == 400


# ---- /research endpoint ----


def test_research_returns_report_and_saves(client):
    fake_session = {
        "id": "abc",
        "title": "Test",
        "created_at": "t1",
        "updated_at": "t2",
        "messages": [],
        "seed_state": {
            "topic": "X",
            "intent": "Y",
            "stakeholders": [
                {"name": "A", "role": "r", "stance": "neutral"},
                {"name": "B", "role": "r", "stance": "neutral"},
            ],
            "decision_branches": [],
            "contested_claims": ["claim 1"],
            "output_format": "pros_cons",
        },
        "ready_to_launch": True,
    }
    fake_report = {
        "topic": "X",
        "intent": "Y",
        "gaps": [],
        "content_assessment": "",
        "queries": ["q1"],
        "results": [
            {"url": "https://example.com/a", "title": "A", "snippet": "...",
             "text_length": 1000, "score": 0.9, "fetch_error": None},
        ],
        "total_chars": 1000,
        "fetched_count": 1,
    }

    fake_result = MagicMock()
    fake_result.url = "https://example.com/a"
    fake_result.title = "A"
    fake_result.snippet = "..."
    fake_result.text = "full body text"
    fake_result.score = 0.9
    fake_result.fetch_error = None

    fake_report_obj = MagicMock()
    fake_report_obj.to_dict.return_value = fake_report
    fake_report_obj.results = [fake_result]

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.research_with_intent", return_value=fake_report_obj) as mock_research:
        mock_store.load.return_value = fake_session
        response = client.post(
            "/api/seed-chat/research",
            json={"session_id": "abc"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["session_id"] == "abc"
    assert body["report"] == fake_report

    mock_research.assert_called_once()
    call_kwargs = mock_research.call_args.kwargs
    if call_kwargs:
        assert call_kwargs.get("topic") == "X"
    else:
        # positional args
        assert mock_research.call_args.args[0] == "X"

    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    # Session now stores full result bodies; check key fields are present
    assert saved["research_report"]["topic"] == "X"
    saved_results = saved["research_report"]["results"]
    assert len(saved_results) == 1
    assert saved_results[0]["url"] == "https://example.com/a"
    assert saved_results[0]["text"] == "full body text"


def test_research_404_when_session_missing(client):
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = None
        response = client.post(
            "/api/seed-chat/research",
            json={"session_id": "missing"},
        )
    assert response.status_code == 404


def test_research_400_when_required_slots_missing(client):
    incomplete = {
        "id": "x", "title": "", "created_at": "t", "updated_at": "t",
        "messages": [],
        "seed_state": {
            "topic": "", "intent": "", "stakeholders": [],
            "decision_branches": [], "contested_claims": [], "output_format": "",
        },
        "ready_to_launch": False,
    }
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = incomplete
        response = client.post(
            "/api/seed-chat/research",
            json={"session_id": "x"},
        )
    assert response.status_code == 400


def test_research_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/research", json={})
    assert response.status_code == 400


def test_launch_with_use_sources_passes_research_to_writer(client):
    fake_session = {
        "id": "abc",
        "title": "Test",
        "created_at": "t1",
        "updated_at": "t2",
        "messages": [{"role": "user", "content": "X"}],
        "seed_state": {
            "topic": "X",
            "intent": "Y",
            "stakeholders": [
                {"name": "A", "role": "r", "stance": "neutral"},
                {"name": "B", "role": "r", "stance": "neutral"},
            ],
            "decision_branches": [],
            "contested_claims": [],
            "output_format": "pros_cons",
        },
        "research_report": {
            "results": [
                {"url": "u1", "title": "T1", "snippet": "s",
                 "text": "body1", "fetch_error": None},
            ],
        },
        "ready_to_launch": True,
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.write_brief", return_value="# Sourced") as mock_writer:
        mock_store.load.return_value = fake_session
        response = client.post(
            "/api/seed-chat/launch",
            json={"session_id": "abc", "use_sources": True},
        )

    assert response.status_code == 200
    mock_writer.assert_called_once()
    call_kwargs = mock_writer.call_args.kwargs
    sources = call_kwargs.get("research_sources")
    if sources is None:
        # might have been passed positionally; check args
        if len(mock_writer.call_args.args) >= 3:
            sources = mock_writer.call_args.args[2]
    assert sources is not None
    assert len(sources) == 1
    assert sources[0]["title"] == "T1"


# ---- /research-claim endpoint ----


def test_research_claim_appends_sources_with_focus_tag(client):
    fake_session = {
        "id": "abc",
        "title": "Test",
        "created_at": "t1",
        "updated_at": "t2",
        "messages": [],
        "seed_state": {
            "topic": "Resources tax",
            "intent": "Y",
            "stakeholders": [
                {"name": "A", "role": "r", "stance": "neutral"},
                {"name": "B", "role": "r", "stance": "neutral"},
            ],
            "decision_branches": [],
            "contested_claims": ["Will trigger 50k job losses"],
            "output_format": "media_landscape",
        },
        "research_report": {
            "topic": "Resources tax",
            "intent": "Y",
            "queries": [],
            "gaps": [],
            "content_assessment": "",
            "results": [
                {"url": "u-existing", "title": "existing", "snippet": "s",
                 "text": "old body", "text_length": 100, "score": 0.5,
                 "fetch_error": None},
            ],
            "total_chars": 100,
            "fetched_count": 1,
        },
        "ready_to_launch": True,
    }

    fake_report_obj = MagicMock()
    fake_report_obj.results = [
        MagicMock(
            url="u-new", title="New source", snippet="snippet",
            text="new source body", score=0.8, fetch_error=None,
        ),
    ]

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.research_with_intent", return_value=fake_report_obj) as mock_research:
        mock_store.load.return_value = fake_session
        response = client.post(
            "/api/seed-chat/research-claim",
            json={"session_id": "abc", "claim_text": "Will trigger 50k job losses"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert "report" in body
    results = body["report"]["results"]
    # Existing result + new claim-focused result
    assert len(results) == 2
    new = [r for r in results if r["url"] == "u-new"][0]
    assert new["claim_focus"] == "Will trigger 50k job losses"

    # research_with_intent called with claim-targeted intent
    mock_research.assert_called_once()
    call_kwargs = mock_research.call_args.kwargs
    intent_arg = call_kwargs.get("intent") if call_kwargs.get("intent") is not None else (
        mock_research.call_args.args[1] if len(mock_research.call_args.args) >= 2 else ""
    )
    assert "50k job losses" in intent_arg

    # session saved
    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    saved_results = saved["research_report"]["results"]
    assert any(r["url"] == "u-new" and r.get("claim_focus") == "Will trigger 50k job losses"
               for r in saved_results)


def test_research_claim_404_when_session_missing(client):
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = None
        response = client.post(
            "/api/seed-chat/research-claim",
            json={"session_id": "missing", "claim_text": "x"},
        )
    assert response.status_code == 404


def test_research_claim_400_when_claim_text_missing(client):
    response = client.post("/api/seed-chat/research-claim", json={"session_id": "abc"})
    assert response.status_code == 400


def test_research_claim_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/research-claim", json={"claim_text": "x"})
    assert response.status_code == 400


# ---- /ad-scripts endpoint ----


def test_ad_scripts_returns_and_persists(client):
    fake_session = {
        "id": "abc",
        "title": "Test",
        "created_at": "t1",
        "updated_at": "t2",
        "messages": [],
        "seed_state": {
            "topic": "X",
            "intent": "Y",
            "stakeholders": [
                {"name": "A", "role": "r", "stance": "neutral"},
                {"name": "B", "role": "r", "stance": "neutral"},
            ],
            "decision_branches": [],
            "contested_claims": [],
            "output_format": "media_landscape",
        },
        "brief": "# Existing brief\n\n...",
        "research_report": {
            "results": [
                {"url": "u1", "title": "T1", "snippet": "s",
                 "text": "body1", "fetch_error": None},
            ],
        },
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.write_ad_scripts", return_value="## Script 1\n[0:00] ..."):
        mock_store.load.return_value = fake_session
        response = client.post(
            "/api/seed-chat/ad-scripts",
            json={"session_id": "abc"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["session_id"] == "abc"
    assert body["ad_scripts"].startswith("## Script 1")

    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    assert saved["ad_scripts"] == "## Script 1\n[0:00] ..."


def test_ad_scripts_400_when_no_brief(client):
    fake_session = {
        "id": "abc", "title": "", "created_at": "t", "updated_at": "t",
        "messages": [],
        "seed_state": {"topic": "X", "intent": "Y", "stakeholders": [],
                       "decision_branches": [], "contested_claims": [],
                       "output_format": "pros_cons"},
        "brief": "",
    }
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = fake_session
        response = client.post("/api/seed-chat/ad-scripts", json={"session_id": "abc"})
    assert response.status_code == 400
    assert "brief" in response.get_json().get("error", "").lower()


def test_ad_scripts_404_when_session_missing(client):
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = None
        response = client.post("/api/seed-chat/ad-scripts", json={"session_id": "missing"})
    assert response.status_code == 404


def test_ad_scripts_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/ad-scripts", json={})
    assert response.status_code == 400


# ---- /tree endpoints ----


def _tree_session_fixture():
    return {
        "id": "tree-1",
        "title": "Tree session",
        "created_at": "t1",
        "updated_at": "t2",
        "messages": [],
        "seed_state": {
            "topic": "Should Australia tax gas more?",
            "intent": "Pros/cons",
            "stakeholders": [
                {"name": "A", "role": "r", "stance": "neutral"},
                {"name": "B", "role": "r", "stance": "neutral"},
            ],
            "decision_branches": [
                {"label": "25%", "description": "as proposed"},
            ],
            "contested_claims": ["50k jobs"],
            "output_format": "media_landscape",
        },
    }


def test_tree_init_creates_tree_on_session(client):
    session = _tree_session_fixture()
    saved_sessions = []

    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        mock_store.save.side_effect = lambda s: saved_sessions.append(s)
        response = client.post("/api/seed-chat/tree/init",
                                json={"session_id": "tree-1"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["tree"]["type"] == "central"
    assert body["tree"]["question"] == "Should Australia tax gas more?"
    assert "tree" in saved_sessions[-1]


def test_tree_init_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/tree/init", json={})
    assert response.status_code == 400


def test_tree_init_404_when_session_missing(client):
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = None
        response = client.post("/api/seed-chat/tree/init",
                                json={"session_id": "missing"})
    assert response.status_code == 404


def test_tree_expand_appends_children(client):
    session = _tree_session_fixture()
    # Pre-populate a tree
    from app.services.decision_tree import initialise_tree
    session["tree"] = initialise_tree(session["seed_state"])
    target_id = session["tree"]["children"][0]["id"]

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.propose_subquestions",
               return_value=[
                   {"id": "n1", "type": "free", "question": "Q1",
                    "user_notes": "", "evidence": [], "children": []},
                   {"id": "n2", "type": "free", "question": "Q2",
                    "user_notes": "", "evidence": [], "children": []},
               ]):
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/expand",
            json={"session_id": "tree-1", "node_id": target_id},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["added"] == 2


def test_tree_expand_404_when_node_missing(client):
    session = _tree_session_fixture()
    from app.services.decision_tree import initialise_tree
    session["tree"] = initialise_tree(session["seed_state"])

    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/expand",
            json={"session_id": "tree-1", "node_id": "no-such-node"},
        )
    assert response.status_code == 404


def test_tree_update_node_patches_fields(client):
    session = _tree_session_fixture()
    from app.services.decision_tree import initialise_tree, find_node
    session["tree"] = initialise_tree(session["seed_state"])
    target_id = session["tree"]["children"][0]["id"]

    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/update-node",
            json={
                "session_id": "tree-1",
                "node_id": target_id,
                "fields": {"user_notes": "my note"},
            },
        )

    assert response.status_code == 200
    body = response.get_json()
    target = find_node(body["tree"], target_id)
    assert target["user_notes"] == "my note"


def test_tree_research_attaches_evidence(client):
    session = _tree_session_fixture()
    from app.services.decision_tree import initialise_tree
    session["tree"] = initialise_tree(session["seed_state"])
    target_id = session["tree"]["children"][0]["id"]

    fake_report = MagicMock()
    fake_report.results = [
        MagicMock(url="u1", title="t", snippet="s",
                  text="body", score=0.9, fetch_error=None),
    ]

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.research_with_intent", return_value=fake_report):
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/research",
            json={"session_id": "tree-1", "node_id": target_id},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert any(e["url"] == "u1" for e in body["evidence"])


def test_tree_synthesize_attaches_summary(client):
    session = _tree_session_fixture()
    from app.services.decision_tree import initialise_tree
    session["tree"] = initialise_tree(session["seed_state"])
    target_id = session["tree"]["children"][0]["id"]

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.synthesise_node",
               return_value="## Summary\n\nBody."):
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/synthesize",
            json={"session_id": "tree-1", "node_id": target_id},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"].startswith("## Summary")
    mock_store.save.assert_called_once()


def test_tree_synthesize_404_when_node_missing(client):
    session = _tree_session_fixture()
    from app.services.decision_tree import initialise_tree
    session["tree"] = initialise_tree(session["seed_state"])

    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/synthesize",
            json={"session_id": "tree-1", "node_id": "no-such"},
        )
    assert response.status_code == 404


def test_tree_synthesize_400_when_required_missing(client):
    response = client.post("/api/seed-chat/tree/synthesize", json={})
    assert response.status_code == 400


def test_tree_compile_foresight_returns_doc_and_persists(client):
    session = _tree_session_fixture()
    from app.services.decision_tree import initialise_tree
    session["tree"] = initialise_tree(session["seed_state"])

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.compile_foresight",
               return_value="# Foresight\n\n## TL;DR\n..."):
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/compile-foresight",
            json={"session_id": "tree-1"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["foresight"].startswith("# Foresight")
    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    assert saved["foresight"].startswith("# Foresight")


def test_tree_compile_foresight_400_when_tree_not_initialised(client):
    session = _tree_session_fixture()
    # No tree
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/compile-foresight",
            json={"session_id": "tree-1"},
        )
    assert response.status_code == 400


def test_tree_compile_foresight_404_when_session_missing(client):
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = None
        response = client.post(
            "/api/seed-chat/tree/compile-foresight",
            json={"session_id": "missing"},
        )
    assert response.status_code == 404


def test_tree_compile_foresight_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/tree/compile-foresight", json={})
    assert response.status_code == 400


def test_tree_score_attaches_scores(client):
    session = _tree_session_fixture()
    from app.services.decision_tree import initialise_tree
    session["tree"] = initialise_tree(session["seed_state"])
    target_id = session["tree"]["children"][0]["id"]

    fake_scores = {
        "confidence": "medium",
        "contestedness": "contested",
        "salience": "high",
        "stance_summary": "Evidence is mixed.",
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.score_node", return_value=fake_scores):
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/score",
            json={"session_id": "tree-1", "node_id": target_id},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["scores"] == fake_scores
    mock_store.save.assert_called_once()


def test_tree_score_404_when_node_missing(client):
    session = _tree_session_fixture()
    from app.services.decision_tree import initialise_tree
    session["tree"] = initialise_tree(session["seed_state"])

    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/score",
            json={"session_id": "tree-1", "node_id": "no-such"},
        )
    assert response.status_code == 404


def test_tree_score_400_when_required_missing(client):
    response = client.post("/api/seed-chat/tree/score", json={})
    assert response.status_code == 400


def test_tree_infographics_plan_returns_and_persists(client):
    session = _tree_session_fixture()
    session["tree"] = {
        "id": "root",
        "type": "central",
        "question": "Should Australia tax gas more?",
        "summary": "Debate summary.",
        "evidence": [],
        "children": [
            {
                "id": "branch-1",
                "type": "downstream",
                "question": "25% windfall tax",
                "summary": "Tax option summary.",
                "evidence": [],
                "children": [],
            }
        ],
    }

    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/plan",
            json={"session_id": "tree-1"},
        )

    assert response.status_code == 200
    body = response.get_json()
    plan = body["infographic_plan"]
    assert plan["schema_version"] == "infographic-plan/v1"
    assert plan["slide_count"] == len(plan["sequence"])
    assert plan["sequence"][0]["image_prompt"]
    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    assert saved["infographic_plan"]["schema_version"] == "infographic-plan/v1"


def test_tree_infographics_plan_400_when_tree_not_initialised(client):
    session = _tree_session_fixture()
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/plan",
            json={"session_id": "tree-1"},
        )
    assert response.status_code == 400


def test_tree_infographics_plan_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/tree/infographics/plan", json={})
    assert response.status_code == 400


def test_tree_infographics_render_returns_image_metadata(client):
    session = _tree_session_fixture()
    session["tree"] = {
        "id": "root",
        "type": "central",
        "question": "Should Australia tax gas more?",
        "summary": "Debate summary.",
        "evidence": [],
        "children": [],
    }
    fake_render = {
        "filename": "slide-01.png",
        "mime_type": "image/png",
        "bytes": 123,
        "model": "gemini-3.1-flash-image-preview",
        "aspect_ratio": "16:9",
        "image_size": "1K",
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.render_infographic_slide", return_value=fake_render):
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/render",
            json={"session_id": "tree-1", "slide_index": 0},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["render"]["url"].endswith("/slide-01.png")
    assert body["render"]["slide_index"] == 0
    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    assert saved["infographic_renders"]["0"]["filename"] == "slide-01.png"


def test_tree_infographics_render_400_when_slide_index_bad(client):
    session = _tree_session_fixture()
    session["tree"] = {"id": "root", "type": "central", "question": "Q", "children": []}
    session["infographic_plan"] = {"sequence": []}
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/render",
            json={"session_id": "tree-1", "slide_index": 99},
        )
    assert response.status_code == 400


def test_tree_augment_big_picture_adds_nodes_and_clears_infographic_plan(client):
    session = _tree_session_fixture()
    session["tree"] = {
        "id": "root",
        "type": "central",
        "question": "Should Australia tax gas more?",
        "user_notes": "",
        "evidence": [],
        "children": [],
    }
    session["infographic_plan"] = {"old": True}
    session["infographic_renders"] = {"0": {"url": "old"}}

    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/augment-big-picture",
            json={"session_id": "tree-1"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["added"] >= 8
    questions = [c["question"] for c in body["tree"]["children"]]
    assert "Where does government tax money come from?" in questions
    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    assert "infographic_plan" not in saved
    assert "infographic_renders" not in saved


def test_tree_augment_big_picture_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/tree/augment-big-picture", json={})
    assert response.status_code == 400


def test_tree_infographics_render_openai_provider(client):
    session = _tree_session_fixture()
    session["tree"] = {
        "id": "root",
        "type": "central",
        "question": "Should Australia tax gas more?",
        "summary": "Debate summary.",
        "evidence": [],
        "children": [],
    }
    fake_render = {
        "filename": "slide-01.png",
        "mime_type": "image/png",
        "bytes": 456,
        "model": "gpt-image-2",
        "provider": "openai",
        "aspect_ratio": "9:16",
        "size": "1024x1536",
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.render_openai_infographic_slide", return_value=fake_render) as mock_render:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/render",
            json={"session_id": "tree-1", "slide_index": 0, "provider": "openai", "aspect_ratio": "9:16"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["render"]["provider"] == "openai"
    mock_render.assert_called_once()


def test_tree_infographics_render_strict_reference_mode(client, tmp_path):
    session = _tree_session_fixture()
    session["tree"] = {"id": "root", "type": "central", "question": "Q", "children": []}
    session["infographic_plan"] = {
        "output_format": "tiktok",
        "aspect_ratio": "9:16",
        "sequence": [{
            "slide_type": "spending_breakdown_welfare",
            "title": "Breakdown: welfare",
            "template_id": "SPENDING_BREAKDOWN",
            "render_contract": {
                "map_to_reference_blocks": {
                    "left_category_label": "Welfare",
                    "left_category_value": "$291b",
                    "middle_bucket_1": {"label": "Seniors", "value": "$65b"},
                    "middle_bucket_2": {"label": "NDIS", "value": "$52b"},
                    "middle_bucket_3": {"label": "Aged care", "value": "$41b"},
                    "middle_bucket_4": {"label": "Why it grows", "value": "ageing"},
                    "right_benefits": ["income security"],
                    "right_negatives": ["cost growth"],
                    "bottom_debt_marker": "Why it grows: ageing",
                }
            },
        }],
    }
    reference_dir = tmp_path / "tree-1"
    reference_dir.mkdir(parents=True)
    (reference_dir / "reference-three-tile-polished.png").write_bytes(b"ref")
    fake_render = {
        "filename": "strict-breakdown-slide-01.png",
        "mime_type": "image/png",
        "bytes": 456,
        "model": "gpt-image-2",
        "provider": "openai-strict-reference-edit",
        "aspect_ratio": "9:16",
        "size": "1024x1536",
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat._INFOGRAPHICS_DIR", tmp_path), \
         patch("app.api.seed_chat.render_openai_infographic_slide_edit", return_value=fake_render) as mock_render:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/render",
            json={"session_id": "tree-1", "slide_index": 0, "provider": "openai", "render_mode": "strict", "aspect_ratio": "9:16"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["render"]["provider"] == "openai-strict-reference-edit"
    assert body["render"]["filename"] == "strict-breakdown-slide-01.png"
    mock_render.assert_called_once()
    assert mock_render.call_args.kwargs["reference_image"].name == "reference-three-tile-polished.png"


def test_tree_infographics_accounting_endpoint(client):
    session = _tree_session_fixture()
    session["render_accounting"] = {
        "total": {"openai": 2},
        "daily": {},
        "events": [],
    }
    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.get("/api/seed-chat/tree/infographics/accounting?session_id=tree-1")

    assert response.status_code == 200
    body = response.get_json()
    assert body["render_accounting"]["total"]["openai"] == 2


def test_tree_infographics_accounting_400_when_session_id_missing(client):
    response = client.get("/api/seed-chat/tree/infographics/accounting")
    assert response.status_code == 400


def test_tree_infographics_narration_plan_returns_and_persists(client):
    session = _tree_session_fixture()
    session["tree"] = {"id": "root", "type": "central", "question": "Q", "children": []}
    fake_script = {
        "schema_version": "narration-script/v1",
        "slides": [],
        "full_voiceover": "Hello narration",
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.plan_narration", return_value=fake_script) as mock_plan:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/narration/plan",
            json={"session_id": "tree-1", "format": "tiktok", "target_seconds": 60},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["narration_script"] == fake_script
    mock_plan.assert_called_once()
    assert mock_plan.call_args.kwargs["target_seconds"] == 60
    saved = mock_store.save.call_args.args[0]
    assert saved["narration_script"]["schema_version"] == "narration-script/v1"


def test_tree_infographics_audio_render_uses_omnivoice_and_persists(client):
    session = _tree_session_fixture()
    session["tree"] = {"id": "root", "type": "central", "question": "Q", "children": []}
    session["infographic_plan"] = {"output_format": "landscape", "sequence": []}
    session["narration_script"] = {"full_voiceover": "Hello narration"}
    fake_render = {
        "filename": "narration.wav",
        "provider": "omnivoice_hf_space",
        "bytes": 789,
        "status": "ok",
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.render_piper_audio", return_value=fake_render) as mock_render:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/audio/render",
            json={"session_id": "tree-1"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["audio_render"]["url"].endswith("/narration.wav")
    mock_render.assert_called_once()
    assert mock_render.call_args.args[0] == "Hello narration"
    saved = mock_store.save.call_args.args[0]
    assert saved["audio_renders"]["narration"]["provider"] == "omnivoice_hf_space"


def test_tree_infographics_audio_render_400_without_session_id(client):
    response = client.post("/api/seed-chat/tree/infographics/audio/render", json={})
    assert response.status_code == 400


def test_tree_augment_story_depth_adds_nodes_and_clears_generated_media(client):
    session = _tree_session_fixture()
    session["tree"] = {
        "id": "root",
        "type": "central",
        "question": "Should Australia tax gas more?",
        "user_notes": "",
        "evidence": [],
        "children": [],
    }
    session["infographic_plan"] = {"old": True}
    session["infographic_renders"] = {"0": {"url": "old"}}
    session["narration_script"] = {"full_voiceover": "old"}
    session["audio_renders"] = {"narration": {"url": "old"}}

    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/augment-story-depth",
            json={"session_id": "tree-1"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["added"] >= 8
    questions = [c["question"] for c in body["tree"]["children"]]
    assert "What misinformation or misleading claims commonly appear in resource-tax debates?" in questions
    saved = mock_store.save.call_args.args[0]
    assert "infographic_plan" not in saved
    assert "infographic_renders" not in saved
    assert "narration_script" not in saved
    assert "audio_renders" not in saved


def test_tree_augment_story_depth_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/tree/augment-story-depth", json={})
    assert response.status_code == 400


def test_tree_infographics_audio_render_can_render_single_slide_clip(client):
    session = _tree_session_fixture()
    session["tree"] = {"id": "root", "type": "central", "question": "Q", "children": []}
    session["infographic_plan"] = {"output_format": "landscape", "sequence": []}
    session["narration_script"] = {
        "full_voiceover": "Full narration",
        "slides": [
            {"slide_index": 0, "voiceover": "Slide one clip"},
            {"slide_index": 1, "voiceover": "Slide two clip"},
        ],
    }
    fake_render = {
        "filename": "audio-slide-02.wav",
        "provider": "omnivoice_hf_space",
        "bytes": 321,
        "status": "ok",
    }

    with patch("app.api.seed_chat._store") as mock_store, \
         patch("app.api.seed_chat.render_piper_audio", return_value=fake_render) as mock_render:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/audio/render",
            json={"session_id": "tree-1", "slide_index": 1},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["audio_render"]["slide_index"] == 1
    assert body["audio_render"]["url"].endswith("/audio-slide-02.wav")
    assert mock_render.call_args.args[0] == "Slide two clip"
    saved = mock_store.save.call_args.args[0]
    assert saved["audio_renders"]["slides"]["1"]["bytes"] == 321


def test_tree_infographics_audio_render_can_use_omnivoice_provider(client):
    session = _tree_session_fixture()
    session["tree"] = {"id": "root", "type": "central", "question": "Q", "children": []}
    session["infographic_plan"] = {"output_format": "landscape", "sequence": []}
    session["narration_script"] = {"full_voiceover": "Hello narration"}
    fake_render = {
        "filename": "narration.wav",
        "provider": "omnivoice_hf_space",
        "bytes": 789,
        "status": "ok",
    }

    with patch("app.api.seed_chat._store") as mock_store,          patch("app.api.seed_chat.render_omnivoice_audio", return_value=fake_render) as mock_render:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/tree/infographics/audio/render",
            json={"session_id": "tree-1", "provider": "omnivoice"},
        )

    assert response.status_code == 200
    mock_render.assert_called_once()
    assert response.get_json()["audio_render"]["provider"] == "omnivoice_hf_space"


def test_education_plan_returns_generic_infographic_plan(client):
    session = _tree_session_fixture()
    session["seed_state"]["contested_claims"] = ["They collect more tax every year but never pay down debt"]

    with patch("app.api.seed_chat._store") as mock_store:
        mock_store.load.return_value = session
        response = client.post(
            "/api/seed-chat/education/plan",
            json={"session_id": "tree-1", "format": "tiktok"},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["education_plan"]["schema_version"] == "education-plan/v1"
    assert body["infographic_plan"]["planner"] == "generic_education"
    assert body["infographic_plan"]["aspect_ratio"] == "9:16"
    assert body["infographic_plan"]["sequence"][0]["slide_id"] == "education.surface_claim"
    normalization = body["education_plan"]["normalizations"][0]
    assert normalization["normalization_id"] == "australia_tax_per_resident_2006_2025"
    assert normalization["comparison"]["start"]["per_capita"] == pytest.approx(10.366, abs=0.001)
    assert normalization["comparison"]["end"]["per_capita"] == pytest.approx(23.822, abs=0.001)
    assert "source_facts" in normalization
    mock_store.save.assert_called_once()
    saved = mock_store.save.call_args.args[0]
    assert saved["education_plan"]["schema_version"] == "education-plan/v1"


def test_education_plan_400_when_session_id_missing(client):
    response = client.post("/api/seed-chat/education/plan", json={})
    assert response.status_code == 400
