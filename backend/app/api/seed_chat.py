"""Seed-chat API routes."""

from flask import jsonify, request

from . import seed_chat_bp
from ..services.seed_extractor import process_turn, EMPTY_STATE
from ..services.brief_writer import write_brief
from ..services.research_agent import research_with_intent
from ..services.ad_script_writer import write_ad_scripts
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
from ..services.tree_synthesizer import synthesise_node
from ..services.node_scorer import score_node
from ..services.foresight_compiler import compile_foresight
from ..services.narration_planner import plan_narration
from ..services.omnivoice_renderer import OmniVoiceRenderError, render_omnivoice_audio
from ..services.piper_renderer import PiperConfigError, PiperRenderError, render_piper_audio
from ..services.nano_banana_renderer import (
    NanoBananaConfigError,
    NanoBananaRenderError,
    render_infographic_slide,
)
from ..services.openai_image_renderer import (
    OpenAIImageConfigError,
    OpenAIImageRenderError,
    render_openai_infographic_slide,
    render_openai_infographic_slide_edit,
)
from ..utils.logger import get_logger

logger = get_logger("miroshark.api.seed_chat")

# Legacy route modules still honor tests/tools that patch these symbols on app.api.seed_chat.
from .seed_chat_common import _INFOGRAPHICS_DIR, store as _store


@seed_chat_bp.route("/turn", methods=["POST"])
def turn():
    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages")
    seed_state = payload.get("seed_state") or dict(EMPTY_STATE)
    session_id = payload.get("session_id")

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "messages must be a non-empty list"}), 400

    try:
        reply, updated, ready = process_turn(messages, seed_state)
    except RuntimeError as exc:
        logger.error("seed-chat turn failed: %s", exc)
        return jsonify({"error": f"claude_cli_unavailable: {exc}"}), 503

    response_body = {
        "assistant_message": reply,
        "updated_seed_state": updated,
        "ready_to_launch": ready,
    }

    if session_id:
        session = _store.load(session_id)
        if session is not None:
            session["messages"] = list(messages) + [
                {"role": "assistant", "content": reply}
            ]
            session["seed_state"] = updated
            session["ready_to_launch"] = ready
            if not session.get("title"):
                first_user = next(
                    (m["content"] for m in messages if m.get("role") == "user"),
                    "",
                )
                session["title"] = first_user[:80]
            _store.save(session)
            response_body["session_id"] = session_id

    return jsonify(response_body)


@seed_chat_bp.route("/sessions", methods=["POST"])
def create_session():
    session = _store.create()
    return jsonify(session)


@seed_chat_bp.route("/sessions", methods=["GET"])
def list_sessions():
    return jsonify({"sessions": _store.list()})


@seed_chat_bp.route("/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    session = _store.load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404
    return jsonify(session)


REQUIRED_LAUNCH_SLOTS = ("topic", "intent", "output_format")
MIN_LAUNCH_STAKEHOLDERS = 2


def _seed_ready_for_launch(seed_state: dict) -> bool:
    for key in REQUIRED_LAUNCH_SLOTS:
        if not seed_state.get(key):
            return False
    if len(seed_state.get("stakeholders") or []) < MIN_LAUNCH_STAKEHOLDERS:
        return False
    return True


@seed_chat_bp.route("/launch", methods=["POST"])
def launch():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    use_sources = bool(payload.get("use_sources", False))
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = _store.load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    seed_state = session.get("seed_state") or {}
    if not _seed_ready_for_launch(seed_state):
        return jsonify({"error": "seed missing required slots"}), 400

    research_sources = None
    if use_sources:
        report = session.get("research_report") or {}
        research_sources = report.get("results") or None

    try:
        brief = write_brief(
            seed_state,
            session.get("messages") or [],
            research_sources=research_sources,
        )
    except RuntimeError as exc:
        logger.error("brief generation failed: %s", exc)
        return jsonify({"error": f"claude_unavailable: {exc}"}), 503

    session["brief"] = brief
    _store.save(session)

    return jsonify({
        "session_id": session_id,
        "brief_markdown": brief,
    })


def _compose_research_intent(seed_state: dict) -> str:
    """Build the intent string passed to research_with_intent from the seed."""
    parts = [seed_state.get("intent", "").strip()]
    claims = seed_state.get("contested_claims") or []
    if claims:
        parts.append("Contested claims to investigate:")
        parts.extend(f"- {c}" for c in claims)
    fmt = seed_state.get("output_format")
    if fmt:
        parts.append(f"Output format: {fmt}")
    return "\n".join(p for p in parts if p)


@seed_chat_bp.route("/research", methods=["POST"])
def research():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = _store.load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    seed_state = session.get("seed_state") or {}
    if not _seed_ready_for_launch(seed_state):
        return jsonify({"error": "seed missing required slots"}), 400

    composed_intent = _compose_research_intent(seed_state)
    try:
        report = research_with_intent(
            topic=seed_state["topic"],
            intent=composed_intent,
            max_sources=10,
        )
    except RuntimeError as exc:
        logger.error("research failed: %s", exc)
        return jsonify({"error": f"research_failed: {exc}"}), 503

    trimmed_for_response = report.to_dict()
    # Store full text bodies so /launch?use_sources=true can cite them.
    # The response to the frontend still uses the trimmed form (text_length, not text).
    report_dict_for_storage = {
        **trimmed_for_response,
        "results": [
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
        ],
    }
    session["research_report"] = report_dict_for_storage
    _store.save(session)

    return jsonify({
        "session_id": session_id,
        "report": trimmed_for_response,
    })


@seed_chat_bp.route("/research-claim", methods=["POST"])
def research_claim():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    claim_text = (payload.get("claim_text") or "").strip()
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    if not claim_text:
        return jsonify({"error": "claim_text required"}), 400

    session = _store.load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    seed_state = session.get("seed_state") or {}
    topic = (seed_state.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "session has no topic"}), 400

    claim_intent = (
        f"Investigate this specific claim, looking for evidence both "
        f"supporting and refuting it: {claim_text}"
    )

    try:
        new_report = research_with_intent(
            topic=topic,
            intent=claim_intent,
            max_sources=5,
        )
    except RuntimeError as exc:
        logger.error("claim research failed: %s", exc)
        return jsonify({"error": f"research_failed: {exc}"}), 503

    # Build per-source dicts WITH the claim_focus tag and full text
    new_results = [
        {
            "url": r.url,
            "title": r.title,
            "snippet": r.snippet,
            "text": r.text,
            "text_length": len(r.text),
            "score": r.score,
            "fetch_error": r.fetch_error,
            "claim_focus": claim_text,
        }
        for r in new_report.results
    ]

    # Merge into session.research_report
    existing_report = session.get("research_report") or {
        "topic": topic,
        "intent": "",
        "queries": [],
        "gaps": [],
        "content_assessment": "",
        "results": [],
        "total_chars": 0,
        "fetched_count": 0,
    }
    existing_results = list(existing_report.get("results") or [])
    existing_urls = {r.get("url") for r in existing_results}
    appended = [r for r in new_results if r["url"] not in existing_urls]
    existing_report["results"] = existing_results + appended
    existing_report["fetched_count"] = sum(
        1 for r in existing_report["results"]
        if r.get("text_length", 0) > 0 and not r.get("fetch_error")
    )
    existing_report["total_chars"] = sum(
        r.get("text_length", 0) for r in existing_report["results"]
    )
    session["research_report"] = existing_report
    _store.save(session)

    # Build response with the same shape /research returns (trimmed for FE)
    response_report = {
        **existing_report,
        "results": [
            {k: v for k, v in r.items() if k != "text"}
            for r in existing_report["results"]
        ],
    }

    return jsonify({
        "session_id": session_id,
        "report": response_report,
        "appended_count": len(appended),
    })


@seed_chat_bp.route("/ad-scripts", methods=["POST"])
def ad_scripts():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = _store.load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    brief = (session.get("brief") or "").strip()
    if not brief:
        return jsonify({
            "error": "no brief — generate a brief first via /launch",
        }), 400

    sources = (session.get("research_report") or {}).get("results") or []

    try:
        scripts = write_ad_scripts(
            seed=session.get("seed_state") or {},
            brief=brief,
            sources=sources,
        )
    except RuntimeError as exc:
        logger.error("ad-script generation failed: %s", exc)
        return jsonify({"error": f"claude_unavailable: {exc}"}), 503

    session["ad_scripts"] = scripts
    _store.save(session)

    return jsonify({
        "session_id": session_id,
        "ad_scripts": scripts,
    })


