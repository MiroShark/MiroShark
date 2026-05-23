"""Unit tests for ``GET /api/config/notifications``.

The endpoint is a pure projection over three env vars (or, in the
case of the generic webhook, the cached ``Config.WEBHOOK_URL``
attribute). We exercise it via a minimal Flask app that mounts
*only* the notifications blueprint so the test doesn't need
``create_app`` (which would boot Neo4j and the simulation runner —
both unavailable in the unit environment).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _make_app():
    """Standalone Flask app that only knows about ``notifications_bp``.

    Mirrors the helper pattern in ``test_unit_admin_auth.py`` —
    mounting the blueprint on a throwaway app exercises the same
    code path with zero infra.
    """
    from flask import Flask
    from app.api.notifications import notifications_bp

    app = Flask(__name__)
    app.register_blueprint(notifications_bp)
    return app


@pytest.fixture
def client():
    app = _make_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _payload(client):
    resp = client.get("/api/config/notifications")
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body["success"] is True
    return body["data"]


def _clear_dkg(monkeypatch):
    """Reset the four DKG_* config attributes back to the unset shape.

    The notifications probe reads DKG state via ``dkg_publisher.is_configured()``
    which late-binds through ``Config`` — so a test that toggles DKG must
    clear it both ways or earlier cases leak into later ones via attribute
    state on the Config class.
    """
    from app.config import Config
    monkeypatch.setattr(Config, "DKG_API_URL", "", raising=False)
    monkeypatch.setattr(Config, "DKG_AUTH_TOKEN", "", raising=False)
    monkeypatch.setattr(Config, "DKG_CONTEXT_GRAPH_ID", "", raising=False)
    monkeypatch.setattr(Config, "DKG_NETWORK", "testnet", raising=False)


def _clear_email(monkeypatch):
    """Reset SMTP_* env vars so the email channel reads as unconfigured."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_TO", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.delenv("SMTP_USE_TLS", raising=False)


def _clear_telegram(monkeypatch):
    """Reset TELEGRAM_* env vars so the channel reads as unconfigured."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)


def _clear_waybackclaw(monkeypatch):
    """Reset ``WAYBACKCLAW_AGENT_TOKEN`` so the channel reads as unconfigured.

    ``is_configured()`` returns True iff the agent token is set, so this
    one env var is the entire surface. Keeping a helper (rather than an
    inline delenv) matches the pattern used by the other channels and
    makes it easy to extend if WaybackClaw ever grows additional
    required vars.
    """
    monkeypatch.delenv("WAYBACKCLAW_AGENT_TOKEN", raising=False)


def test_notifications_config_all_unset(monkeypatch, client):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    _clear_email(monkeypatch)
    _clear_telegram(monkeypatch)
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)
    _clear_dkg(monkeypatch)
    _clear_waybackclaw(monkeypatch)

    data = _payload(client)
    assert data == {
        "webhook_configured": False,
        "discord_configured": False,
        "slack_configured": False,
        "email_configured": False,
        "telegram_configured": False,
        "dkg_configured": False,
        "dkg_network": None,
        "waybackclaw_configured": False,
    }


def test_notifications_config_discord_only(monkeypatch, client):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    _clear_email(monkeypatch)
    _clear_telegram(monkeypatch)
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)
    _clear_dkg(monkeypatch)
    _clear_waybackclaw(monkeypatch)

    data = _payload(client)
    assert data == {
        "webhook_configured": False,
        "discord_configured": True,
        "slack_configured": False,
        "email_configured": False,
        "telegram_configured": False,
        "dkg_configured": False,
        "dkg_network": None,
        "waybackclaw_configured": False,
    }


def test_notifications_config_slack_only(monkeypatch, client):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.setenv(
        "SLACK_WEBHOOK_URL",
        "https://hooks.slack.com/services/T0/B0/abc",
    )
    _clear_email(monkeypatch)
    _clear_telegram(monkeypatch)
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)
    _clear_dkg(monkeypatch)
    _clear_waybackclaw(monkeypatch)

    data = _payload(client)
    assert data == {
        "webhook_configured": False,
        "discord_configured": False,
        "slack_configured": True,
        "email_configured": False,
        "telegram_configured": False,
        "dkg_configured": False,
        "dkg_network": None,
        "waybackclaw_configured": False,
    }


def test_notifications_config_email_only(monkeypatch, client):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_TO", "alerts@example.com")
    _clear_telegram(monkeypatch)
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)
    _clear_dkg(monkeypatch)
    _clear_waybackclaw(monkeypatch)

    data = _payload(client)
    assert data == {
        "webhook_configured": False,
        "discord_configured": False,
        "slack_configured": False,
        "email_configured": True,
        "telegram_configured": False,
        "dkg_configured": False,
        "dkg_network": None,
        "waybackclaw_configured": False,
    }


def test_notifications_config_email_requires_both_host_and_to(monkeypatch, client):
    """SMTP_HOST alone (no SMTP_TO) is not a usable channel — the SPA
    chip should stay off so an operator doesn't think email is wired
    when nothing would actually ship."""
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.delenv("SMTP_TO", raising=False)
    _clear_telegram(monkeypatch)
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)
    _clear_dkg(monkeypatch)

    data = _payload(client)
    assert data["email_configured"] is False


def test_notifications_config_telegram_only(monkeypatch, client):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    _clear_email(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "111:AAAaaa")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123456789")
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)
    _clear_dkg(monkeypatch)
    _clear_waybackclaw(monkeypatch)

    data = _payload(client)
    assert data == {
        "webhook_configured": False,
        "discord_configured": False,
        "slack_configured": False,
        "email_configured": False,
        "telegram_configured": True,
        "dkg_configured": False,
        "dkg_network": None,
        "waybackclaw_configured": False,
    }


def test_notifications_config_telegram_requires_both_token_and_chat_id(monkeypatch, client):
    """TELEGRAM_BOT_TOKEN alone (no TELEGRAM_CHAT_ID) is not a usable
    channel — the bot has nowhere to send. Same posture as the
    SMTP_HOST/SMTP_TO pairing."""
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    _clear_email(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "111:AAAaaa")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)
    _clear_dkg(monkeypatch)

    data = _payload(client)
    assert data["telegram_configured"] is False


def test_notifications_config_all_five_configured(monkeypatch, client):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    monkeypatch.setenv(
        "SLACK_WEBHOOK_URL",
        "https://hooks.slack.com/services/T0/B0/abc",
    )
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_TO", "alerts@example.com")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "111:AAAaaa")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123456789")
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "https://example.com/hook", raising=False)
    _clear_dkg(monkeypatch)
    _clear_waybackclaw(monkeypatch)

    data = _payload(client)
    assert data == {
        "webhook_configured": True,
        "discord_configured": True,
        "slack_configured": True,
        "email_configured": True,
        "telegram_configured": True,
        "dkg_configured": False,
        "dkg_network": None,
        "waybackclaw_configured": False,
    }


def test_notifications_config_blank_env_var_treated_as_unset(monkeypatch, client):
    """Operators sometimes leave an empty assignment in ``.env``
    (``DISCORD_WEBHOOK_URL=``) — that must read as unset, not as a
    malformed configured channel."""
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "   ")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
    monkeypatch.setenv("SMTP_HOST", "  ")
    monkeypatch.setenv("SMTP_TO", "   ")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "  ")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "  ", raising=False)
    _clear_dkg(monkeypatch)
    _clear_waybackclaw(monkeypatch)

    data = _payload(client)
    assert data == {
        "webhook_configured": False,
        "discord_configured": False,
        "slack_configured": False,
        "email_configured": False,
        "telegram_configured": False,
        "dkg_configured": False,
        "dkg_network": None,
        "waybackclaw_configured": False,
    }


def test_notifications_config_dkg_configured(monkeypatch, client):
    """All three DKG_* required vars set → dkg_configured is True and
    dkg_network reports whichever chain the operator labelled."""
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    _clear_email(monkeypatch)
    _clear_telegram(monkeypatch)
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)
    monkeypatch.setattr(Config, "DKG_API_URL", "http://127.0.0.1:9200", raising=False)
    monkeypatch.setattr(Config, "DKG_AUTH_TOKEN", "abc123def456", raising=False)
    monkeypatch.setattr(Config, "DKG_CONTEXT_GRAPH_ID", "cg-miroshark", raising=False)
    monkeypatch.setattr(Config, "DKG_NETWORK", "mainnet", raising=False)
    _clear_waybackclaw(monkeypatch)

    data = _payload(client)
    assert data == {
        "webhook_configured": False,
        "discord_configured": False,
        "slack_configured": False,
        "email_configured": False,
        "telegram_configured": False,
        "dkg_configured": True,
        "dkg_network": "mainnet",
        "waybackclaw_configured": False,
    }


def test_notifications_config_dkg_partial_treated_as_unconfigured(monkeypatch, client):
    """Missing any one of the three required vars → not configured.
    Catches the footgun where an operator sets DKG_API_URL but forgets
    the token — the SPA should not surface a broken publish button."""
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    _clear_email(monkeypatch)
    _clear_telegram(monkeypatch)
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)
    monkeypatch.setattr(Config, "DKG_API_URL", "http://127.0.0.1:9200", raising=False)
    monkeypatch.setattr(Config, "DKG_AUTH_TOKEN", "", raising=False)
    monkeypatch.setattr(Config, "DKG_CONTEXT_GRAPH_ID", "cg-miroshark", raising=False)
    monkeypatch.setattr(Config, "DKG_NETWORK", "testnet", raising=False)

    data = _payload(client)
    assert data["dkg_configured"] is False
    # Network metadata is suppressed when the integration isn't usable —
    # showing "testnet" with no daemon would be misleading.
    assert data["dkg_network"] is None


def test_notifications_config_no_store_cache_header(monkeypatch, client):
    """A Settings-modal save flips the booleans the moment it lands;
    a cache header would leave stale chips in the dialog until a hard
    reload."""
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    _clear_email(monkeypatch)
    _clear_telegram(monkeypatch)
    from app.config import Config
    monkeypatch.setattr(Config, "WEBHOOK_URL", "", raising=False)

    resp = client.get("/api/config/notifications")
    assert resp.status_code == 200
    cache_control = resp.headers.get("Cache-Control", "")
    assert "no-store" in cache_control


# ── Wiring guards ──────────────────────────────────────────────────────


def test_notifications_route_decorator_present():
    """Drift guard — the route decorator must stay on the
    notifications blueprint so the URL keeps resolving."""
    api_path = _BACKEND / "app" / "api" / "notifications.py"
    text = api_path.read_text(encoding="utf-8")
    assert '@notifications_bp.route("/api/config/notifications"' in text
    assert "def notifications_config(" in text


def test_app_factory_registers_notifications_blueprint():
    """The factory must mount the blueprint — catches the failure
    mode where the file exists but never got registered."""
    init_path = _BACKEND / "app" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    assert "notifications_bp" in text
    assert "app.register_blueprint(notifications_bp)" in text


def test_blueprint_module_exports_notifications_bp():
    api_init = _BACKEND / "app" / "api" / "__init__.py"
    text = api_init.read_text(encoding="utf-8")
    assert "from .notifications import notifications_bp" in text
