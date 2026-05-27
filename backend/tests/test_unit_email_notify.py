"""Unit tests for the SMTP completion notifier.

Pure offline — no Flask boot, no real SMTP relay. The tests cover the
same shape as ``test_unit_discord_notify.py`` and
``test_unit_slack_notify.py``:

  1. Module constants and env-var names stay pinned.
  2. ``is_configured`` requires both ``SMTP_HOST`` and ``SMTP_TO``.
  3. Subject / plain / html builders produce well-formed parts.
  4. ``notify_if_configured`` no-ops without env vars and fires once
     per ``(sim_id, status)`` pair when set.
  5. ``send_email`` dispatches via the right SMTP class for the port,
     skips auth when credentials are blank, and never raises on
     network errors.
  6. ``send_test_notification`` rejects a blank host and a blank
     recipient list.
"""

from __future__ import annotations

import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from unittest.mock import MagicMock, patch



_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import email_notify  # noqa: E402


# ── Module-level invariants ────────────────────────────────────────────


def test_env_var_names_pinned():
    """Renaming any of these silently breaks every operator's `.env`."""
    assert email_notify.SMTP_HOST_ENV_VAR == "SMTP_HOST"
    assert email_notify.SMTP_PORT_ENV_VAR == "SMTP_PORT"
    assert email_notify.SMTP_USER_ENV_VAR == "SMTP_USER"
    assert email_notify.SMTP_PASSWORD_ENV_VAR == "SMTP_PASSWORD"
    assert email_notify.SMTP_FROM_ENV_VAR == "SMTP_FROM"
    assert email_notify.SMTP_TO_ENV_VAR == "SMTP_TO"
    assert email_notify.SMTP_USE_TLS_ENV_VAR == "SMTP_USE_TLS"


def test_default_port_is_submission_port():
    """587 (submission) is the safest default — works with Gmail,
    Mailgun, SendGrid, and any modern hosted relay."""
    assert email_notify.SMTP_DEFAULT_PORT == 587


def test_bar_width_matches_slack():
    """Recipients comparing the Slack card and the email body should
    see identical bars — pin so a refactor of one doesn't drift the
    other."""
    assert email_notify.BAR_WIDTH == 10
    assert email_notify.BAR_FILLED == "█"
    assert email_notify.BAR_EMPTY == "░"


# ── is_configured ──────────────────────────────────────────────────────


def test_is_configured_requires_host_and_recipients(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_TO", raising=False)
    assert email_notify.is_configured() is False

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_TO", "")
    assert email_notify.is_configured() is False

    monkeypatch.setenv("SMTP_TO", "alerts@example.com")
    assert email_notify.is_configured() is True


def test_is_configured_treats_blank_as_unset(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "   ")
    monkeypatch.setenv("SMTP_TO", "  ")
    assert email_notify.is_configured() is False


# ── env-var resolution ────────────────────────────────────────────────


def test_resolve_port_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("SMTP_PORT", raising=False)
    assert email_notify._resolve_port() == 587


def test_resolve_port_parses_integer(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "465")
    assert email_notify._resolve_port() == 465


def test_resolve_port_falls_back_on_garbage(monkeypatch):
    """A typo in the env var should not crash the dispatch path."""
    monkeypatch.setenv("SMTP_PORT", "not-a-number")
    assert email_notify._resolve_port() == 587


def test_resolve_port_clamps_out_of_range(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "999999")
    assert email_notify._resolve_port() == 587


def test_resolve_recipients_splits_csv(monkeypatch):
    monkeypatch.setenv("SMTP_TO", "a@x.com, b@x.com ,c@x.com")
    addrs = email_notify._resolve_recipients()
    assert addrs == ["a@x.com", "b@x.com", "c@x.com"]


def test_resolve_recipients_drops_empties(monkeypatch):
    monkeypatch.setenv("SMTP_TO", "a@x.com,,, b@x.com")
    addrs = email_notify._resolve_recipients()
    assert addrs == ["a@x.com", "b@x.com"]


def test_resolve_from_defaults_to_noreply_at_host(monkeypatch):
    monkeypatch.delenv("SMTP_FROM", raising=False)
    assert email_notify._resolve_from("relay.example.com") == "miroshark-notify@relay.example.com"


def test_resolve_from_honours_explicit_value(monkeypatch):
    monkeypatch.setenv("SMTP_FROM", "alerts@miroshark.app")
    assert email_notify._resolve_from("relay.example.com") == "alerts@miroshark.app"


def test_use_tls_defaults_true(monkeypatch):
    monkeypatch.delenv("SMTP_USE_TLS", raising=False)
    assert email_notify._resolve_use_tls() is True


def test_use_tls_false_when_disabled(monkeypatch):
    monkeypatch.setenv("SMTP_USE_TLS", "false")
    assert email_notify._resolve_use_tls() is False


# ── Subject / body builders ───────────────────────────────────────────


def _payload(**overrides):
    base = {
        "event": "simulation.completed",
        "sim_id": "sim_x",
        "scenario": "Will the SEC approve XYZ?",
        "status": "completed",
        "current_round": 20,
        "total_rounds": 20,
        "agent_count": 248,
        "quality_health": "Excellent",
        "final_consensus": {"bullish": 60.0, "neutral": 20.0, "bearish": 20.0},
        "resolution_outcome": None,
        "share_path": "/share/sim_x",
        "share_card_path": "/api/simulation/sim_x/share-card.png",
        "share_url": "https://miroshark.app/share/sim_x",
        "share_card_url": "https://miroshark.app/api/simulation/sim_x/share-card.png",
        "fired_at": "2026-05-17T12:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_subject_carries_direction_and_scenario():
    subject = email_notify.build_subject(_payload())
    assert subject.startswith("[MiroShark] Bullish:")
    assert "Will the SEC approve XYZ?" in subject


def test_subject_for_failed_says_failed():
    subject = email_notify.build_subject(_payload(status="failed", final_consensus=None))
    assert subject.startswith("[MiroShark] Failed:")


def test_subject_falls_back_when_scenario_empty():
    subject = email_notify.build_subject(_payload(scenario=""))
    assert subject == "[MiroShark] Bullish: Simulation sim_x"


def test_subject_truncates_long_scenario():
    subject = email_notify.build_subject(_payload(scenario="x" * 250))
    # Subject has fixed "[MiroShark] Direction: " prefix plus capped scenario.
    assert subject.endswith("…")
    assert len(subject) <= len("[MiroShark] Bullish: ") + email_notify.SUBJECT_SCENARIO_MAX_CHARS


def test_plain_body_includes_bullish_block_bar():
    text = email_notify.build_plain_body(_payload())
    assert "Bullish:" in text
    assert "60.0%" in text
    # Belief bar at 60% renders 6 filled blocks under BAR_WIDTH=10.
    assert "█" in text and "░" in text


def test_plain_body_includes_share_url():
    text = email_notify.build_plain_body(_payload())
    assert "https://miroshark.app/share/sim_x" in text


def test_plain_body_skips_belief_when_consensus_missing():
    text = email_notify.build_plain_body(_payload(final_consensus=None))
    assert "Bullish:" not in text


def test_plain_body_includes_error_on_failed():
    text = email_notify.build_plain_body(
        _payload(
            status="failed",
            error="exit code 1: segfault",
            final_consensus=None,
        )
    )
    assert "Error:" in text
    assert "segfault" in text


def test_html_body_has_bullish_percentage_and_swatch():
    html = email_notify.build_html_body(_payload())
    assert "60.0%" in html
    # Bullish swatch is rendered via the inline-styled color.
    assert email_notify.COLOR_BULLISH in html


def test_html_body_has_view_cta_for_absolute_share_url():
    html = email_notify.build_html_body(_payload())
    assert 'href="https://miroshark.app/share/sim_x"' in html
    assert "View simulation" in html


def test_html_body_omits_cta_when_share_url_is_relative_only():
    html = email_notify.build_html_body(_payload(share_url=None))
    # Should not render a CTA button when no absolute URL is available.
    assert "View simulation" not in html


def test_html_body_escapes_scenario():
    html = email_notify.build_html_body(_payload(scenario="<script>x</script>"))
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_build_email_message_attaches_both_parts():
    msg = email_notify.build_email_message(
        _payload(),
        from_addr="alerts@example.com",
        to_addrs=["a@x.com", "b@x.com"],
    )
    parts = msg.get_payload()
    types = [p.get_content_type() for p in parts]
    assert "text/plain" in types
    assert "text/html" in types
    assert msg["To"] == "a@x.com, b@x.com"
    assert msg["X-MiroShark-Sim-Id"] == "sim_x"
    assert msg["X-MiroShark-Event"] == "simulation.completed"


# ── notify_if_configured behaviour ─────────────────────────────────────


def test_notify_if_configured_noop_without_host(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setenv("SMTP_TO", "alerts@example.com")
    email_notify.reset_dedup_for_tests()
    with patch.object(email_notify, "_start_dispatch_thread") as start:
        email_notify.notify_if_configured("sim_unset", "completed", sim_dir="/nonexistent")
    assert start.call_count == 0


def test_notify_if_configured_noop_without_recipients(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.delenv("SMTP_TO", raising=False)
    email_notify.reset_dedup_for_tests()
    with patch.object(email_notify, "_start_dispatch_thread") as start:
        email_notify.notify_if_configured("sim_unset", "completed", sim_dir="/nonexistent")
    assert start.call_count == 0


def test_notify_if_configured_ignores_unknown_status(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_TO", "alerts@example.com")
    email_notify.reset_dedup_for_tests()
    with patch.object(email_notify, "_start_dispatch_thread") as start:
        email_notify.notify_if_configured("sim_running", "running", sim_dir="/nonexistent")
    assert start.call_count == 0


def test_notify_if_configured_fires_once_per_pair(monkeypatch, tmp_path):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_TO", "alerts@example.com")
    email_notify.reset_dedup_for_tests()

    sim_dir = tmp_path / "sim_dedup_email"
    sim_dir.mkdir()

    captured: list[dict] = []

    def fake_start(**kwargs):
        captured.append(kwargs)

    with patch.object(email_notify, "_start_dispatch_thread", side_effect=fake_start):
        email_notify.notify_if_configured(
            "sim_dedup_email", "completed", sim_dir=str(sim_dir)
        )
        email_notify.notify_if_configured(
            "sim_dedup_email", "completed", sim_dir=str(sim_dir)
        )
    assert len(captured) == 1
    assert captured[0]["host"] == "smtp.example.com"
    assert captured[0]["to_addrs"] == ["alerts@example.com"]


def test_dispatch_thread_calls_send_email(monkeypatch):
    sent: list[tuple] = []

    def fake_send(message, **kwargs):
        sent.append((message, kwargs))
        return True, "sent to 1 recipient(s)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "x"

    with patch.object(email_notify, "send_email", side_effect=fake_send):
        email_notify._start_dispatch_thread(
            message=msg,
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addrs=["to@example.com"],
            user="",
            password="",
            use_tls=True,
            thread_name="email-smoke",
        )
        deadline = time.time() + 2.0
        while not sent and time.time() < deadline:
            time.sleep(0.01)

    assert len(sent) == 1
    _captured_msg, captured_kwargs = sent[0]
    assert captured_kwargs["host"] == "smtp.example.com"
    assert captured_kwargs["port"] == 587


# ── send_email transport behaviour ────────────────────────────────────


def test_send_email_uses_smtp_ssl_for_port_465():
    msg = email_notify.build_email_message(
        _payload(), from_addr="from@example.com", to_addrs=["to@example.com"],
    )
    with patch.object(email_notify.smtplib, "SMTP_SSL") as smtp_ssl_cls:
        conn = MagicMock()
        smtp_ssl_cls.return_value.__enter__.return_value = conn
        ok, message = email_notify.send_email(
            msg,
            host="smtp.example.com",
            port=465,
            from_addr="from@example.com",
            to_addrs=["to@example.com"],
        )
    assert ok is True
    assert "sent to 1 recipient(s)" in message
    assert smtp_ssl_cls.called
    assert conn.sendmail.called


def test_send_email_uses_starttls_for_port_587():
    msg = email_notify.build_email_message(
        _payload(), from_addr="from@example.com", to_addrs=["to@example.com"],
    )
    with patch.object(email_notify.smtplib, "SMTP") as smtp_cls:
        conn = MagicMock()
        smtp_cls.return_value.__enter__.return_value = conn
        ok, _msg = email_notify.send_email(
            msg,
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addrs=["to@example.com"],
            use_tls=True,
        )
    assert ok is True
    conn.starttls.assert_called()
    conn.sendmail.assert_called()


def test_send_email_skips_starttls_when_disabled():
    msg = email_notify.build_email_message(
        _payload(), from_addr="from@example.com", to_addrs=["to@example.com"],
    )
    with patch.object(email_notify.smtplib, "SMTP") as smtp_cls:
        conn = MagicMock()
        smtp_cls.return_value.__enter__.return_value = conn
        ok, _msg = email_notify.send_email(
            msg,
            host="smtp.example.com",
            port=25,
            from_addr="from@example.com",
            to_addrs=["to@example.com"],
            use_tls=False,
        )
    assert ok is True
    conn.starttls.assert_not_called()
    conn.sendmail.assert_called()


def test_send_email_skips_login_when_credentials_blank():
    msg = email_notify.build_email_message(
        _payload(), from_addr="from@example.com", to_addrs=["to@example.com"],
    )
    with patch.object(email_notify.smtplib, "SMTP") as smtp_cls:
        conn = MagicMock()
        smtp_cls.return_value.__enter__.return_value = conn
        ok, _msg = email_notify.send_email(
            msg,
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addrs=["to@example.com"],
            user="",
            password="",
        )
    assert ok is True
    conn.login.assert_not_called()


def test_send_email_calls_login_when_credentials_provided():
    msg = email_notify.build_email_message(
        _payload(), from_addr="from@example.com", to_addrs=["to@example.com"],
    )
    with patch.object(email_notify.smtplib, "SMTP") as smtp_cls:
        conn = MagicMock()
        smtp_cls.return_value.__enter__.return_value = conn
        ok, _msg = email_notify.send_email(
            msg,
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addrs=["to@example.com"],
            user="apikey",
            password="abc",
        )
    assert ok is True
    conn.login.assert_called_with("apikey", "abc")


def test_send_email_refuses_to_leak_credentials_on_starttls_failure():
    msg = email_notify.build_email_message(
        _payload(), from_addr="from@example.com", to_addrs=["to@example.com"],
    )
    with patch.object(email_notify.smtplib, "SMTP") as smtp_cls:
        conn = MagicMock()
        smtp_cls.return_value.__enter__.return_value = conn
        conn.starttls.side_effect = smtplib.SMTPException("STARTTLS refused")
        ok, message = email_notify.send_email(
            msg,
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addrs=["to@example.com"],
            user="apikey",
            password="abc",
            use_tls=True,
        )
    assert ok is False
    assert "refusing to send credentials" in message
    conn.login.assert_not_called()
    conn.sendmail.assert_not_called()


def test_send_email_swallows_smtp_exception():
    msg = email_notify.build_email_message(
        _payload(), from_addr="from@example.com", to_addrs=["to@example.com"],
    )
    with patch.object(email_notify.smtplib, "SMTP") as smtp_cls:
        smtp_cls.side_effect = smtplib.SMTPException("connection refused")
        ok, message = email_notify.send_email(
            msg,
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addrs=["to@example.com"],
        )
    assert ok is False
    assert "SMTP error" in message


def test_send_email_swallows_os_error():
    msg = email_notify.build_email_message(
        _payload(), from_addr="from@example.com", to_addrs=["to@example.com"],
    )
    with patch.object(email_notify.smtplib, "SMTP") as smtp_cls:
        smtp_cls.side_effect = OSError("dns lookup failed")
        ok, message = email_notify.send_email(
            msg,
            host="smtp.example.com",
            port=587,
            from_addr="from@example.com",
            to_addrs=["to@example.com"],
        )
    assert ok is False
    assert "Connection error" in message


def test_send_email_rejects_empty_host():
    msg = MIMEMultipart("alternative")
    ok, message = email_notify.send_email(
        msg, host="", port=587, from_addr="", to_addrs=["to@example.com"],
    )
    assert ok is False
    assert "SMTP_HOST" in message


def test_send_email_rejects_empty_recipients():
    msg = MIMEMultipart("alternative")
    ok, message = email_notify.send_email(
        msg, host="smtp.example.com", port=587, from_addr="from@example.com", to_addrs=[],
    )
    assert ok is False
    assert "SMTP_TO" in message


# ── send_test_notification ────────────────────────────────────────────


def test_send_test_notification_rejects_blank_host(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setenv("SMTP_TO", "alerts@example.com")
    result = email_notify.send_test_notification(host="")
    assert result["ok"] is False
    assert "SMTP_HOST" in result["message"]


def test_send_test_notification_rejects_blank_recipients(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.delenv("SMTP_TO", raising=False)
    result = email_notify.send_test_notification(to=[])
    assert result["ok"] is False
    assert "SMTP_TO" in result["message"]


def test_send_test_notification_dispatches_on_valid_config(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_TO", "alerts@example.com")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    with patch.object(email_notify, "send_email", return_value=(True, "sent to 1 recipient(s)")) as mock_send:
        result = email_notify.send_test_notification()
    assert result == {"ok": True, "message": "sent to 1 recipient(s)"}
    assert mock_send.called
    call_kwargs = mock_send.mock_calls[0].kwargs
    assert call_kwargs["host"] == "smtp.example.com"
    assert call_kwargs["to_addrs"] == ["alerts@example.com"]


# ── Module discoverability ─────────────────────────────────────────────


def test_notify_function_is_exported():
    assert callable(email_notify.notify_if_configured)
    assert callable(email_notify.is_configured)
    assert callable(email_notify.build_email_message)
    assert callable(email_notify.send_email)
    assert callable(email_notify.send_test_notification)
