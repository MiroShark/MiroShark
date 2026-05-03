"""Tests for decision_tree helpers."""

from unittest.mock import patch, MagicMock


def _seed_for_tests():
    return {
        "topic": "Should Australia tax gas more?",
        "intent": "Pros/cons brief",
        "stakeholders": [],
        "decision_branches": [
            {"label": "25% flat", "description": "as proposed"},
            {"label": "Status quo", "description": "no new tax"},
        ],
        "contested_claims": ["Will trigger 50k job losses"],
        "output_format": "media_landscape",
    }


def test_initialise_tree_creates_central_root_with_topic():
    from app.services.decision_tree import initialise_tree

    tree = initialise_tree(_seed_for_tests())
    assert tree["type"] == "central"
    assert tree["question"] == "Should Australia tax gas more?"
    assert tree["user_notes"] == "Pros/cons brief"
    assert "id" in tree


def test_initialise_tree_seeds_upstream_downstream_analogy_and_free():
    from app.services.decision_tree import initialise_tree

    tree = initialise_tree(_seed_for_tests())
    types = [c["type"] for c in tree["children"]]
    assert "upstream" in types
    assert "analogy" in types
    assert types.count("downstream") >= 2
    assert types.count("free") >= 1
    questions = [c["question"] for c in tree["children"]]
    assert "Where does government tax money come from?" in questions
    assert "Why might the current government avoid this tax?" in questions


def test_find_node_returns_node_by_id():
    from app.services.decision_tree import initialise_tree, find_node

    tree = initialise_tree(_seed_for_tests())
    target = tree["children"][0]
    found = find_node(tree, target["id"])
    assert found is target


def test_find_node_returns_none_for_unknown_id():
    from app.services.decision_tree import initialise_tree, find_node
    tree = initialise_tree(_seed_for_tests())
    assert find_node(tree, "no-such-id") is None


def test_update_node_patches_question_and_notes():
    from app.services.decision_tree import initialise_tree, update_node, find_node

    tree = initialise_tree(_seed_for_tests())
    target = tree["children"][0]
    ok = update_node(tree, target["id"], {"question": "new q", "user_notes": "n"})
    assert ok is True
    refreshed = find_node(tree, target["id"])
    assert refreshed["question"] == "new q"
    assert refreshed["user_notes"] == "n"


def test_update_node_returns_false_for_unknown_id():
    from app.services.decision_tree import initialise_tree, update_node
    tree = initialise_tree(_seed_for_tests())
    assert update_node(tree, "no-id", {"question": "x"}) is False


def test_attach_evidence_dedupes_by_url():
    from app.services.decision_tree import initialise_tree, attach_evidence, find_node

    tree = initialise_tree(_seed_for_tests())
    target = tree["children"][0]
    attach_evidence(tree, target["id"], [
        {"url": "u1", "title": "A", "text": "...", "fetch_error": None},
        {"url": "u1", "title": "A dup", "text": "...", "fetch_error": None},
        {"url": "u2", "title": "B", "text": "...", "fetch_error": None},
    ])
    refreshed = find_node(tree, target["id"])
    urls = [e["url"] for e in refreshed["evidence"]]
    assert urls == ["u1", "u2"]


def test_propose_subquestions_returns_child_nodes_with_inherited_type():
    from app.services.decision_tree import propose_subquestions

    parent = {"id": "p", "type": "downstream", "question": "Effects?",
              "user_notes": "", "evidence": [], "children": []}
    seed = _seed_for_tests()

    with patch("app.services.decision_tree.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.return_value = {
            "questions": ["Q1?", "Q2?", "Q3?"],
        }
        mock_factory.return_value = mock_client

        children = propose_subquestions(parent, seed)

    assert len(children) == 3
    assert all(c["type"] == "downstream" for c in children)
    assert all("id" in c and "question" in c for c in children)


def test_propose_subquestions_returns_empty_on_malformed_response():
    from app.services.decision_tree import propose_subquestions

    parent = {"id": "p", "type": "central", "question": "?",
              "user_notes": "", "evidence": [], "children": []}

    with patch("app.services.decision_tree.create_llm_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.chat_json.side_effect = ValueError("bad json")
        mock_factory.return_value = mock_client

        children = propose_subquestions(parent, {})

    assert children == []


def test_set_summary_writes_to_node():
    from app.services.decision_tree import initialise_tree, set_summary, find_node

    tree = initialise_tree(_seed_for_tests())
    target = tree["children"][0]
    ok = set_summary(tree, target["id"], "## Summary\nBody")
    assert ok is True
    assert find_node(tree, target["id"])["summary"] == "## Summary\nBody"


def test_set_summary_returns_false_for_unknown_id():
    from app.services.decision_tree import initialise_tree, set_summary
    tree = initialise_tree(_seed_for_tests())
    assert set_summary(tree, "no-id", "x") is False


def test_set_scores_writes_to_node():
    from app.services.decision_tree import initialise_tree, set_scores, find_node

    tree = initialise_tree(_seed_for_tests())
    target = tree["children"][0]
    scores = {
        "confidence": "high",
        "contestedness": "settled",
        "salience": "moderate",
        "stance_summary": "Sample stance.",
    }
    ok = set_scores(tree, target["id"], scores)
    assert ok is True
    assert find_node(tree, target["id"])["scores"] == scores


def test_set_scores_returns_false_for_unknown_id():
    from app.services.decision_tree import initialise_tree, set_scores
    tree = initialise_tree(_seed_for_tests())
    assert set_scores(tree, "no-id", {}) is False


def test_add_big_picture_nodes_appends_missing_only():
    from app.services.decision_tree import initialise_tree, add_big_picture_nodes

    tree = initialise_tree(_seed_for_tests())
    original_count = len(tree["children"])
    # initialise_tree already includes the big-picture scaffold
    assert add_big_picture_nodes(tree) == 0
    assert len(tree["children"]) == original_count

    target_question = "Where does government tax money come from?"
    tree["children"] = [c for c in tree["children"] if c["question"] != target_question]
    assert add_big_picture_nodes(tree) == 1
    assert any(c["question"] == target_question for c in tree["children"])


def test_add_story_depth_nodes_appends_deeper_research_scaffold():
    from app.services.decision_tree import initialise_tree, add_story_depth_nodes

    tree = initialise_tree(_seed_for_tests())
    original_count = len(tree["children"])
    added = add_story_depth_nodes(tree)

    assert added == 8
    assert len(tree["children"]) == original_count + 8
    questions = [c["question"] for c in tree["children"]]
    assert "How have gas and mining companies influenced public debate or campaigns?" in questions
    assert "How has Australian government debt changed since 2006, and who was in power?" in questions
    assert add_story_depth_nodes(tree) == 0
