"""Seed-chat API routes."""

from pathlib import Path

from flask import jsonify, request

from . import seed_chat_bp
from ..services.seed_extractor import process_turn, EMPTY_STATE
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

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "messages must be a non-empty list"}), 400

    try:
        reply, updated, ready = process_turn(messages, seed_state)
    except RuntimeError as exc:
        logger.error("seed-chat turn failed: %s", exc)
        return jsonify({"error": f"claude_cli_unavailable: {exc}"}), 503

    return jsonify({
        "assistant_message": reply,
        "updated_seed_state": updated,
        "ready_to_launch": ready,
    })


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
