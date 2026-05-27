"""Unit tests for the Telegram Bot notifier.

Pure offline — no Flask boot, no real Telegram endpoint. Same shape
as ``test_unit_slack_notify.py`` / ``test_unit_discord_notify.py``:

  1. Module constants stay pinned.
  2. ``belief_bar`` renders a width-controlled Unicode block bar with
     a trailing percentage label, clamps out-of-range inputs.
  3. ``build_telegram_message`` produces a well-formed Bot API
     ``sendMessage`` body — HTML parse mode, scenario header,
     belief bars, key/value fields, inline-keyboard button.
  4. ``notify_if_configured`` no-ops without ``TELEGRAM_BOT_TOKEN`` or
     ``TELEGRAM_CHAT_ID`` and fires once per ``(sim_id, status)``
     pair when both are set.
  5. ``send_test_notification`` rejects a blank token / chat id and
     POSTs an HTML-mode body otherwise.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch



_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import telegram_notify  # noqa: E402


# ── Module-level invariants ────────────────────────────────────────────


def test_env_var_names_pinned():
    """The env var names are part of the public contract — operators
    paste them into ``.env`` files and CI secrets; a rename breaks
    every deployment."""
    assert telegram_notify.TELEGRAM_BOT_TOKEN_ENV_VAR == "TELEGRAM_BOT_TOKEN"
    assert telegram_notify.TELEGRAM_CHAT_ID_ENV_VAR == "TELEGRAM_CHAT_ID"


def test_bar_width_pinned():
    """A change to the bar width changes how the message renders on
    every Telegram client — pin it so a casual refactor doesn't drift
    the look, and keep it aligned with the Slack notifier."""
    assert telegram_notify.BAR_WIDTH == 10
    assert telegram_notify.BAR_FILLED == "█"
    assert telegram_notify.BAR_EMPTY == "░"


def test_api_base_pinned():
    """Operators sometimes route Telegram through a private proxy
    (``api.telegram.org`` blocked by an ISP). The constant lives in
    one place so a future ``TELEGRAM_API_BASE_URL`` env knob has an
    obvious hook."""
    assert telegram_notify.TELEGRAM_API_BASE == "https://api.telegram.org"


def test_text_max_under_telegram_limit():
    """Telegram caps text messages at 4096 chars."""
    assert 0 < telegram_notify.TELEGRAM_TEXT_MAX_CHARS <= 4096


# ── belief_bar ─────────────────────────────────────────────────────────


def test_belief_bar_zero():
    bar = telegram_notify.belief_bar(0)
    assert bar == "░" * 10 + " 0.0%"


def test_belief_bar_full():
    bar = telegram_notify.belief_bar(100)
    assert bar == "█" * 10 + " 100.0%"


def test_belief_bar_half():
    bar = telegram_notify.belief_bar(50)
    assert bar == "█" * 5 + "░" * 5 + " 50.0%"


def test_belief_bar_clamps_negative_and_overflow():
    assert telegram_notify.belief_bar(-30).startswith("░")
    assert telegram_notify.belief_bar(150).endswith(" 100.0%")


def test_belief_bar_handles_non_numeric_input():
    bar = telegram_notify.belief_bar(None)
    assert "0.0%" in bar


# ── HTML escape helper ────────────────────────────────────────────────


def test_escape_handles_html_metachars():
    """Telegram HTML parse-mode rejects the whole message on a tag
    parse failure — a scenario containing ``<`` must not break it."""
    out = telegram_notify._escape("Will TVL <$1B by EOY? AT&T weighs in.")
    assert "<" not in out
    assert ">" not in out
    assert "&lt;" in out
    assert "&amp;" in out


def test_escape_none_returns_empty():
    assert telegram_notify._escape(None) == ""


# ── Message builder ────────────────────────────────────────────────────


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
        "fired_at": "2026-05-15T12:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_build_message_uses_html_parse_mode():
    body = telegram_notify.build_telegram_message(_payload())
    assert body["parse_mode"] == "HTML"
    assert body["disable_web_page_preview"] is True


def test_build_message_header_is_bold_scenario():
    body = telegram_notify.build_telegram_message(_payload())
    text = body["text"]
    assert text.startswith("<b>Will the SEC approve XYZ?</b>")


def test_build_message_context_line_carries_status_and_sim_id():
    body = telegram_notify.build_telegram_message(_payload())
    text = body["text"]
    assert "<i>Completed</i>" in text
    assert "<code>sim_x</code>" in text


def test_build_message_belief_bars_rendered():
    body = telegram_notify.build_telegram_message(_payload())
    text = body["text"]
    assert "<b>Bullish</b>" in text
    assert "<b>Neutral</b>" in text
    assert "<b>Bearish</b>" in text
    # Unicode block bar must appear inside the body.
    assert "█" in text or "░" in text


def test_build_message_skips_belief_section_when_consensus_missing():
    body = telegram_notify.build_telegram_message(_payload(final_consensus=None))
    text = body["text"]
    assert "Bullish" not in text


def test_build_message_quality_scale_outcome_fields():
    body = telegram_notify.build_telegram_message(
        _payload(resolution_outcome="YES @ 1.00")
    )
    text = body["text"]
    assert "<b>Quality:</b> Excellent" in text
    assert "248 agents" in text
    assert "20 rounds" in text
    assert "<b>Outcome:</b> YES @ 1.00" in text


def test_build_message_inline_keyboard_button_uses_absolute_url():
    body = telegram_notify.build_telegram_message(_payload())
    markup = body.get("reply_markup")
    assert markup is not None
    buttons = markup["inline_keyboard"]
    assert len(buttons) == 1 and len(buttons[0]) == 1
    button = buttons[0][0]
    assert button["text"] == "View simulation"
    assert button["url"] == "https://miroshark.app/share/sim_x"


def test_build_message_drops_button_for_relative_path_only():
    body = telegram_notify.build_telegram_message(_payload(share_url=None))
    # Telegram rejects inline-keyboard buttons whose URL isn't
    # http(s):// — better to omit the markup than ship an invalid one.
    assert "reply_markup" not in body


def test_build_message_escapes_html_in_scenario():
    body = telegram_notify.build_telegram_message(
        _payload(scenario="Will TVL <$1B by EOY? AT&T weighs in.")
    )
    text = body["text"]
    assert "<$1B" not in text
    assert "&lt;$1B" in text
    assert "AT&amp;T" in text


def test_build_message_truncates_long_scenario():
    body = telegram_notify.build_telegram_message(_payload(scenario="x" * 500))
    text = body["text"]
    # The header line ends at the first newline; that line must be
    # within the scenario cap (+ surrounding ``<b>``…``</b>`` tags).
    first_line = text.split("\n", 1)[0]
    assert len(first_line) <= telegram_notify.TELEGRAM_SCENARIO_MAX_CHARS + len("<b></b>")
    assert "…</b>" in first_line


def test_build_message_failed_status_includes_error_block():
    body = telegram_notify.build_telegram_message(
        _payload(
            status="failed",
            error="Process exit code 1: simulation segfault",
            final_consensus=None,
        )
    )
    text = body["text"]
    assert "<b>Error</b>" in text
    assert "<pre>" in text
    assert "segfault" in text


def test_build_message_falls_back_when_scenario_empty():
    body = telegram_notify.build_telegram_message(_payload(scenario=""))
    text = body["text"]
    assert text.startswith("<b>Simulation sim_x</b>")


# ── notify_if_configured behaviour ─────────────────────────────────────


def test_notify_if_configured_noop_when_token_unset(monkeypatch):
    monkeypatch.delenv(telegram_notify.TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setenv(telegram_notify.TELEGRAM_CHAT_ID_ENV_VAR, "-100123456789")
    telegram_notify.reset_dedup_for_tests()
    with patch.object(telegram_notify, "_start_dispatch_thread") as start:
        telegram_notify.notify_if_configured(
            "sim_unset", "completed", sim_dir="/nonexistent"
        )
    assert start.call_count == 0


def test_notify_if_configured_noop_when_chat_id_unset(monkeypatch):
    monkeypatch.setenv(telegram_notify.TELEGRAM_BOT_TOKEN_ENV_VAR, "111:AAAaaa")
    monkeypatch.delenv(telegram_notify.TELEGRAM_CHAT_ID_ENV_VAR, raising=False)
    telegram_notify.reset_dedup_for_tests()
    with patch.object(telegram_notify, "_start_dispatch_thread") as start:
        telegram_notify.notify_if_configured(
            "sim_unset", "completed", sim_dir="/nonexistent"
        )
    assert start.call_count == 0


def test_notify_if_configured_ignores_unknown_status(monkeypatch):
    monkeypatch.setenv(telegram_notify.TELEGRAM_BOT_TOKEN_ENV_VAR, "111:AAAaaa")
    monkeypatch.setenv(telegram_notify.TELEGRAM_CHAT_ID_ENV_VAR, "-100123456789")
    telegram_notify.reset_dedup_for_tests()
    with patch.object(telegram_notify, "_start_dispatch_thread") as start:
        telegram_notify.notify_if_configured(
            "sim_running", "running", sim_dir="/nonexistent"
        )
    assert start.call_count == 0


def test_notify_if_configured_fires_once_per_sim_status_pair(monkeypatch, tmp_path):
    monkeypatch.setenv(telegram_notify.TELEGRAM_BOT_TOKEN_ENV_VAR, "111:AAAaaa")
    monkeypatch.setenv(telegram_notify.TELEGRAM_CHAT_ID_ENV_VAR, "-100123456789")
    telegram_notify.reset_dedup_for_tests()

    sim_dir = tmp_path / "sim_dedup_telegram"
    sim_dir.mkdir()

    captured: list[dict] = []

    def fake_start(*, token, chat_id, body, thread_name):
        captured.append(
            {"token": token, "chat_id": chat_id, "body": body, "thread_name": thread_name}
        )

    with patch.object(telegram_notify, "_start_dispatch_thread", side_effect=fake_start):
        telegram_notify.notify_if_configured(
            "sim_dedup_telegram", "completed", sim_dir=str(sim_dir)
        )
        telegram_notify.notify_if_configured(
            "sim_dedup_telegram", "completed", sim_dir=str(sim_dir)
        )
    assert len(captured) == 1
    assert captured[0]["chat_id"] == "-100123456789"
    assert "text" in captured[0]["body"]


# ── HTTP wiring ────────────────────────────────────────────────────────


def test_send_message_url_includes_bot_prefix():
    url = telegram_notify._send_message_url("123:abc")
    assert url == "https://api.telegram.org/bot123:abc/sendMessage"


def test_dispatch_thread_posts_send_message_body():
    sent: list[tuple] = []

    def fake_post(url, body, timeout):
        sent.append((url, body, timeout))
        return True, "HTTP 200"

    body = {"text": "<b>x</b>", "parse_mode": "HTML"}

    with patch.object(telegram_notify, "_post_json", side_effect=fake_post):
        telegram_notify._start_dispatch_thread(
            token="111:AAAaaa",
            chat_id="-100123456789",
            body=body,
            thread_name="telegram-smoke",
        )

        deadline = time.time() + 2.0
        while not sent and time.time() < deadline:
            time.sleep(0.01)

    assert len(sent) == 1
    url, posted_body, timeout = sent[0]
    assert url == "https://api.telegram.org/bot111:AAAaaa/sendMessage"
    assert posted_body["chat_id"] == "-100123456789"
    assert posted_body["text"] == "<b>x</b>"
    assert posted_body["parse_mode"] == "HTML"
    assert timeout == telegram_notify.TELEGRAM_TIMEOUT_SECONDS


def test_post_json_swallows_url_error():
    import urllib.error

    def boom(*_a, **_kw):
        raise urllib.error.URLError("dns failed")

    with patch.object(telegram_notify.urllib.request, "urlopen", side_effect=boom):
        ok, msg = telegram_notify._post_json(
            "https://api.telegram.org/bot111:AAAaaa/sendMessage",
            {"chat_id": "-1", "text": "x"},
            timeout=1.0,
        )
    assert ok is False
    assert "URL error" in msg


def test_post_json_surfaces_telegram_error_description():
    """Telegram returns the diagnostic in the response body — surface
    it so a malformed-HTML payload is debuggable from the log line."""
    import io
    import json as _json
    import urllib.error

    body = _json.dumps({"ok": False, "error_code": 400, "description": "Bad Request: can't parse entities"}).encode("utf-8")

    def boom(*_a, **_kw):
        raise urllib.error.HTTPError(
            url="https://api.telegram.org/bot/x/sendMessage",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(body),
        )

    with patch.object(telegram_notify.urllib.request, "urlopen", side_effect=boom):
        ok, msg = telegram_notify._post_json(
            "https://api.telegram.org/bot111:AAAaaa/sendMessage",
            {"chat_id": "-1", "text": "<b>"},
            timeout=1.0,
        )
    assert ok is False
    assert "HTTP 400" in msg
    assert "can't parse entities" in msg


# ── Test event ─────────────────────────────────────────────────────────


def test_send_test_notification_rejects_blank_token(monkeypatch):
    monkeypatch.delenv(telegram_notify.TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setenv(telegram_notify.TELEGRAM_CHAT_ID_ENV_VAR, "-100123456789")
    result = telegram_notify.send_test_notification(token="")
    assert result == {"ok": False, "message": "Telegram bot token is empty"}


def test_send_test_notification_rejects_blank_chat_id(monkeypatch):
    monkeypatch.setenv(telegram_notify.TELEGRAM_BOT_TOKEN_ENV_VAR, "111:AAAaaa")
    monkeypatch.delenv(telegram_notify.TELEGRAM_CHAT_ID_ENV_VAR, raising=False)
    result = telegram_notify.send_test_notification(chat_id="")
    assert result == {"ok": False, "message": "Telegram chat id is empty"}


def test_send_test_notification_posts_when_credentials_given():
    with patch.object(
        telegram_notify, "_post_json", return_value=(True, "HTTP 200")
    ) as mock_post:
        result = telegram_notify.send_test_notification(
            token="111:AAAaaa", chat_id="-100123456789"
        )
    assert result == {"ok": True, "message": "HTTP 200"}
    assert mock_post.called
    _, args, _ = mock_post.mock_calls[0]
    url, body, _timeout = args
    assert url == "https://api.telegram.org/bot111:AAAaaa/sendMessage"
    assert body["chat_id"] == "-100123456789"
    assert body["parse_mode"] == "HTML"


# ── Module discoverability ─────────────────────────────────────────────


def test_notify_function_is_exported():
    assert callable(telegram_notify.notify_if_configured)
    assert callable(telegram_notify.is_configured)
    assert callable(telegram_notify.build_telegram_message)
    assert callable(telegram_notify.send_test_notification)


def test_is_configured_requires_both_env_vars(monkeypatch):
    monkeypatch.delenv(telegram_notify.TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.delenv(telegram_notify.TELEGRAM_CHAT_ID_ENV_VAR, raising=False)
    assert telegram_notify.is_configured() is False

    monkeypatch.setenv(telegram_notify.TELEGRAM_BOT_TOKEN_ENV_VAR, "111:AAAaaa")
    assert telegram_notify.is_configured() is False

    monkeypatch.setenv(telegram_notify.TELEGRAM_CHAT_ID_ENV_VAR, "-100123456789")
    assert telegram_notify.is_configured() is True
