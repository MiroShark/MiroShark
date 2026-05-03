"""Public decision-tree API routes for seed-chat sessions."""

from flask import jsonify, request

from . import seed_chat_bp
from .seed_chat_common import current_store
from ..services.decision_tree import (
    initialise_tree,
    find_node,
    update_node as tree_update_node,
    attach_evidence,
    attach_children,
    propose_subquestions,
    set_summary,
    set_scores,
    add_big_picture_nodes,
    add_story_depth_nodes,
)
from ..services.foresight_compiler import compile_foresight
from ..services.node_scorer import score_node
from ..services.research_agent import research_with_intent
from ..services.tree_synthesizer import synthesise_node
from ..utils.logger import get_logger

logger = get_logger("miroshark.api.decision_tree_public")


def _compat_attr(name: str, default):
    """Honor legacy tests/tools that patch app.api.seed_chat.<name>."""
    try:
        from . import seed_chat as seed_chat_module
        return getattr(seed_chat_module, name, default)
    except Exception:
        return default

@seed_chat_bp.route("/tree/init", methods=["POST"])
def tree_init():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    seed_state = session.get("seed_state") or {}
    if not (seed_state.get("topic") or "").strip():
        return jsonify({"error": "session has no topic"}), 400

    tree = _compat_attr("initialise_tree", initialise_tree)(seed_state)
    session["tree"] = tree
    current_store().save(session)
    return jsonify({"session_id": session_id, "tree": tree})


@seed_chat_bp.route("/tree/augment-big-picture", methods=["POST"])
def tree_augment_big_picture():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    added = _compat_attr("add_big_picture_nodes", add_big_picture_nodes)(tree)
    session["tree"] = tree
    # Existing infographic/audio plans may not include the new story context.
    if added > 0:
        session.pop("infographic_plan", None)
        session.pop("infographic_renders", None)
        session.pop("narration_script", None)
        session.pop("audio_renders", None)
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "tree": tree,
        "added": added,
    })


@seed_chat_bp.route("/tree/augment-story-depth", methods=["POST"])
def tree_augment_story_depth():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    added = _compat_attr("add_story_depth_nodes", add_story_depth_nodes)(tree)
    session["tree"] = tree
    # Deeper story nodes change the media arc, so derived assets should be regenerated.
    if added > 0:
        session.pop("infographic_plan", None)
        session.pop("infographic_renders", None)
        session.pop("narration_script", None)
        session.pop("audio_renders", None)
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "tree": tree,
        "added": added,
    })


@seed_chat_bp.route("/tree/expand", methods=["POST"])
def tree_expand():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    node_id = payload.get("node_id")
    if not session_id or not node_id:
        return jsonify({"error": "session_id and node_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    parent = _compat_attr("find_node", find_node)(tree, node_id)
    if parent is None:
        return jsonify({"error": "node_not_found"}), 404

    try:
        children = _compat_attr("propose_subquestions", propose_subquestions)(parent, session.get("seed_state") or {})
    except RuntimeError as exc:
        logger.error("tree expand failed: %s", exc)
        return jsonify({"error": f"claude_unavailable: {exc}"}), 503

    _compat_attr("attach_children", attach_children)(tree, node_id, children)
    session["tree"] = tree
    current_store().save(session)
    return jsonify({"session_id": session_id, "tree": tree, "added": len(children)})


@seed_chat_bp.route("/tree/research", methods=["POST"])
def tree_research():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    node_id = payload.get("node_id")
    if not session_id or not node_id:
        return jsonify({"error": "session_id and node_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    node = _compat_attr("find_node", find_node)(tree, node_id)
    if node is None:
        return jsonify({"error": "node_not_found"}), 404

    seed_state = session.get("seed_state") or {}
    topic = (seed_state.get("topic") or "").strip()
    question = (node.get("question") or "").strip()
    if not topic or not question:
        return jsonify({"error": "topic and question required for research"}), 400

    lower_question = question.lower()
    if any(key in lower_question for key in ("tax money", "federal", "state", "welfare", "spend", "spending", "government avoid", "albanese", "political risks", "who pays now", "how much extra money", "countries", "where did", "worked", "backfire", "rspt", "mrrt", "campaign", "misinformation", "misleading", "debt", "2006", "royalties", "prrt", "export profits", "fair compromise")):
        intent = (
            f"Investigate this story-depth context question for a general audience: {question}. "
            f"Find credible evidence, examples where it worked and did not work, campaign/disinformation context where relevant, "
            f"budget/tax figures where available, and plain-English explanations of why this tangent matters to the gas-tax debate. "
            f"Prefer official, parliamentary, regulator, academic, or primary sources when possible."
        )
    else:
        intent = (
            f"Investigate this question, looking for evidence both supporting "
            f"and refuting common framings: {question}"
        )
    try:
        report = _compat_attr("research_with_intent", research_with_intent)(topic=topic, intent=intent, max_sources=5)
    except RuntimeError as exc:
        logger.error("tree research failed: %s", exc)
        return jsonify({"error": f"research_failed: {exc}"}), 503

    new_sources = [
        {
            "url": r.url,
            "title": r.title,
            "snippet": r.snippet,
            "text": r.text,
            "text_length": len(r.text),
            "score": r.score,
            "fetch_error": r.fetch_error,
        }
        for r in report.results
    ]
    _compat_attr("attach_evidence", attach_evidence)(tree, node_id, new_sources)
    session["tree"] = tree
    current_store().save(session)

    response_node = _compat_attr("find_node", find_node)(tree, node_id) or node
    response_evidence = [
        {k: v for k, v in s.items() if k != "text"}
        for s in (response_node.get("evidence") or [])
    ]
    return jsonify({
        "session_id": session_id,
        "node_id": node_id,
        "evidence": response_evidence,
    })


@seed_chat_bp.route("/tree/update-node", methods=["POST"])
def tree_update():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    node_id = payload.get("node_id")
    fields = payload.get("fields") or {}
    if not session_id or not node_id:
        return jsonify({"error": "session_id and node_id required"}), 400
    if not isinstance(fields, dict) or not fields:
        return jsonify({"error": "fields object required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    ok = _compat_attr("tree_update_node", tree_update_node)(tree, node_id, fields)
    if not ok:
        return jsonify({"error": "node_not_found"}), 404

    session["tree"] = tree
    current_store().save(session)
    return jsonify({"session_id": session_id, "tree": tree})


@seed_chat_bp.route("/tree/synthesize", methods=["POST"])
def tree_synthesize():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    node_id = payload.get("node_id")
    if not session_id or not node_id:
        return jsonify({"error": "session_id and node_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    node = _compat_attr("find_node", find_node)(tree, node_id)
    if node is None:
        return jsonify({"error": "node_not_found"}), 404

    try:
        summary = _compat_attr("synthesise_node", synthesise_node)(node)
    except RuntimeError as exc:
        logger.error("tree synthesis failed: %s", exc)
        return jsonify({"error": f"claude_unavailable: {exc}"}), 503

    _compat_attr("set_summary", set_summary)(tree, node_id, summary)
    session["tree"] = tree
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "node_id": node_id,
        "summary": summary,
    })


@seed_chat_bp.route("/tree/compile-foresight", methods=["POST"])
def tree_compile_foresight():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    seed_state = session.get("seed_state") or {}
    try:
        foresight = _compat_attr("compile_foresight", compile_foresight)(seed_state, tree)
    except RuntimeError as exc:
        logger.error("foresight compile failed: %s", exc)
        return jsonify({"error": f"claude_unavailable: {exc}"}), 503

    session["foresight"] = foresight
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "foresight": foresight,
    })


@seed_chat_bp.route("/tree/score", methods=["POST"])
def tree_score():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    node_id = payload.get("node_id")
    if not session_id or not node_id:
        return jsonify({"error": "session_id and node_id required"}), 400

    session = current_store().load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    tree = session.get("tree")
    if not tree:
        return jsonify({"error": "tree not initialised"}), 400

    node = _compat_attr("find_node", find_node)(tree, node_id)
    if node is None:
        return jsonify({"error": "node_not_found"}), 404

    try:
        scores = _compat_attr("score_node", score_node)(node)
    except RuntimeError as exc:
        logger.error("node scoring failed: %s", exc)
        return jsonify({"error": f"claude_unavailable: {exc}"}), 503

    _compat_attr("set_scores", set_scores)(tree, node_id, scores)
    session["tree"] = tree
    current_store().save(session)

    return jsonify({
        "session_id": session_id,
        "node_id": node_id,
        "scores": scores,
    })
