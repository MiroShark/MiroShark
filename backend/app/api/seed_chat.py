"""Seed-chat API routes."""

from pathlib import Path

from flask import jsonify, request

from . import seed_chat_bp
from ..services.seed_extractor import process_turn, EMPTY_STATE
from ..services.brief_writer import write_brief
from ..services.research_agent import research_with_intent
from ..storage.session_store import SessionStore
from ..utils.logger import get_logger

logger = get_logger("miroshark.api.seed_chat")

# Sessions persist as JSON files at <backend>/sessions/.
# `__file__` is backend/app/api/seed_chat.py — go up 3 levels to reach backend/.
_SESSIONS_DIR = Path(__file__).resolve().parents[2] / "sessions"
_store = SessionStore(base_dir=_SESSIONS_DIR)


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
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    session = _store.load(session_id)
    if session is None:
        return jsonify({"error": "session_not_found"}), 404

    seed_state = session.get("seed_state") or {}
    if not _seed_ready_for_launch(seed_state):
        return jsonify({"error": "seed missing required slots"}), 400

    try:
        brief = write_brief(seed_state, session.get("messages") or [])
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

    report_dict = report.to_dict()
    session["research_report"] = report_dict
    _store.save(session)

    return jsonify({
        "session_id": session_id,
        "report": report_dict,
    })
