"""Seed-chat API routes."""

from flask import jsonify, request

from . import seed_chat_bp
from ..services.seed_extractor import process_turn, EMPTY_STATE
from ..utils.logger import get_logger

logger = get_logger("miroshark.api.seed_chat")


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
