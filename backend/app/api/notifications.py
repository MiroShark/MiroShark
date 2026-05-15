"""Public ``GET /api/config/notifications`` config endpoint.

Tells the SPA which notification *channels* are wired up on this
deployment without exposing the values themselves (the webhook URLs
often carry an opaque secret in the path). Mirrors the existing
``GET /api/config/sitemap`` pattern: a small boolean envelope the
``EmbedDialog`` reads on mount and uses to render the right status
chips beside the share-and-embed surfaces.

Three independent channels, each gated by a separate env var so
operators can opt in to any subset:

* ``WEBHOOK_URL``         — generic JSON ``POST`` (PR #46)
* ``DISCORD_WEBHOOK_URL`` — Discord rich-embed cards
* ``SLACK_WEBHOOK_URL``   — Slack Block Kit messages

Each ``*_configured`` boolean is ``True`` iff the corresponding env
var is set to a non-empty value. No URL ever leaves the backend.

Sandbox note: pure stdlib (env reads + ``flask.jsonify``). No
outbound network — the route never raises and never blocks on
Neo4j / LLM calls.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify

from ..services import discord_notify, slack_notify
from ..services import webhook_service
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.notifications")

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/api/config/notifications", methods=["GET"])
def notifications_config() -> Response:
    """Expose which notification channels are configured.

    Returns ``{success, data: {webhook_configured, discord_configured,
    slack_configured}}``. No URL values are leaked — only presence
    booleans, so this endpoint is safe to call from the SPA without
    auth.
    """
    webhook_url = webhook_service._resolve_webhook_url()
    data = {
        "webhook_configured": bool(webhook_url),
        "discord_configured": discord_notify.is_configured(),
        "slack_configured": slack_notify.is_configured(),
    }
    response = jsonify({"success": True, "data": data})
    # No caching — channel status flips the moment an operator pastes
    # a URL into the Settings modal. The endpoint is cheap (three env
    # reads) so paying the round-trip on every dialog open is fine.
    response.headers["Cache-Control"] = "no-store"
    return response
