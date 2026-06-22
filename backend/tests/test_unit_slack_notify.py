"""Unit tests for the Slack Block Kit notifier.

Pure offline — no Flask boot, no real Slack endpoint. The tests
cover the same shape as ``test_unit_discord_notify.py``:

  1. Module constants stay pinned.
  2. ``belief_bar`` renders a width-controlled Unicode block bar with
     a trailing percentage label, clamps out-of-range inputs.
  3. ``build_slack_message`` produces a well-formed Block Kit body
     with header / context / section / actions blocks, honours the
     scenario truncation, and degrades cleanly when fields are missing.
  4. ``notify_if_configured`` no-ops without ``SLACK_WEBHOOK_URL`` and
     fires once per ``(sim_id, status)`` pair when set.
  5. ``send_test_notification`` rejects a blank URL and POSTs a
     ``{blocks: [...]}`` body otherwise.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch



_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import slack_notify  # noqa: E402


# ── Module-level invariants ────────────────────────────────────────────


def test_env_var_name_pinned():
    assert slack_notify.SLACK_WEBHOOK_URL_ENV_VAR == "SLACK_WEBHOOK_URL"


def test_bar_width_pinned():
    """A change to the bar width changes how the message renders on
    every Slack client — pin it so a casual refactor doesn't drift
    the look."""
    assert slack_notify.BAR_WIDTH == 10
    assert slack_notify.BAR_FILLED == "█"
    assert slack_notify.BAR_EMPTY == "░"


def test_header_max_chars_under_slack_limit():
    """Slack caps header blocks at 150 chars."""
    assert 0 < slack_notify.SLACK_HEADER_MAX_CHARS <= 150


# ── belief_bar ─────────────────────────────────────────────────────────


def test_belief_bar_zero():
    bar = slack_notify.belief_bar(0)
    assert bar == "░" * 10 + " 0.0%"


def test_belief_bar_full():
    bar = slack_notify.belief_bar(100)
    assert bar == "█" * 10 + " 100.0%"


def test_belief_bar_half():
    bar = slack_notify.belief_bar(50)
    assert bar == "█" * 5 + "░" * 5 + " 50.0%"


def test_belief_bar_decimal():
    bar = slack_notify.belief_bar(62.5)
    # 6 filled blocks rounds the 6.25 share up; the label preserves
    # the original decimal so the operator can still read the source
    # number.
    assert bar.endswith(" 62.5%")
    assert bar.startswith("█")


def test_belief_bar_clamps_negative_and_overflow():
    assert slack_notify.belief_bar(-30).startswith("░")
    assert slack_notify.belief_bar(150).endswith(" 100.0%")


def test_belief_bar_handles_non_numeric_input():
    """A ``None`` from a missing trajectory snapshot should degrade
    into a zero-filled bar, not crash."""
    bar = slack_notify.belief_bar(None)
    assert "0.0%" in bar


# ── Block Kit builder ──────────────────────────────────────────────────


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


def test_build_slack_message_has_header_block():
    msg = slack_notify.build_slack_message(_payload())
    assert msg["blocks"][0]["type"] == "header"
    assert msg["blocks"][0]["text"]["text"] == "Will the SEC approve XYZ?"


def test_build_slack_message_context_carries_status():
    msg = slack_notify.build_slack_message(_payload())
    ctx = msg["blocks"][1]
    assert ctx["type"] == "context"
    text = ctx["elements"][0]["text"]
    assert "*Completed*" in text
    assert "sim_x" in text


def test_build_slack_message_belief_bars_in_section_fields():
    msg = slack_notify.build_slack_message(_payload())
    section = next(b for b in msg["blocks"] if b.get("type") == "section")
    field_texts = [f["text"] for f in section["fields"]]
    joined = "\n".join(field_texts)
    assert "*Bullish*" in joined
    assert "*Neutral*" in joined
    assert "*Bearish*" in joined
    # Unicode block bar must be rendered inside the section fields.
    assert "█" in joined or "░" in joined


def test_build_slack_message_skips_belief_section_when_consensus_missing():
    msg = slack_notify.build_slack_message(_payload(final_consensus=None))
    # The section block should still exist (quality, scale fields),
    # but its text should not include bullish/neutral/bearish.
    section_fields_text = ""
    for b in msg["blocks"]:
        if b.get("type") == "section" and "fields" in b:
            section_fields_text += "\n".join(f["text"] for f in b["fields"])
    assert "*Bullish*" not in section_fields_text


def test_build_slack_message_action_button_uses_absolute_share_url():
    msg = slack_notify.build_slack_message(_payload())
    actions = next((b for b in msg["blocks"] if b.get("type") == "actions"), None)
    assert actions is not None
    btn = actions["elements"][0]
    assert btn["type"] == "button"
    assert btn["url"] == "https://miroshark.app/share/sim_x"


def test_build_slack_message_drops_action_button_for_relative_path_only():
    msg = slack_notify.build_slack_message(_payload(share_url=None))
    actions = next((b for b in msg["blocks"] if b.get("type") == "actions"), None)
    # Slack rejects buttons whose URL isn't http(s):// — better to
    # omit the action block than ship an invalid one.
    assert actions is None


def test_build_slack_message_truncates_long_scenario():
    msg = slack_notify.build_slack_message(_payload(scenario="x" * 250))
    header = msg["blocks"][0]["text"]["text"]
    assert len(header) <= slack_notify.SLACK_HEADER_MAX_CHARS
    assert header.endswith("…")


def test_build_slack_message_failed_status_includes_error_block():
    msg = slack_notify.build_slack_message(
        _payload(
            status="failed",
            error="Process exit code 1: simulation segfault",
            final_consensus=None,
        )
    )
    error_sections = [
        b for b in msg["blocks"]
        if b.get("type") == "section"
        and "text" in b
        and "Error" in b.get("text", {}).get("text", "")
    ]
    assert len(error_sections) == 1
    assert "segfault" in error_sections[0]["text"]["text"]


def test_build_slack_message_falls_back_when_scenario_empty():
    msg = slack_notify.build_slack_message(_payload(scenario=""))
    assert msg["blocks"][0]["text"]["text"] == "Simulation sim_x"


# ── notify_if_configured behaviour ─────────────────────────────────────


def test_notify_if_configured_noop_when_env_unset(monkeypatch):
    monkeypatch.delenv(slack_notify.SLACK_WEBHOOK_URL_ENV_VAR, raising=False)
    slack_notify.reset_dedup_for_tests()
    with patch.object(slack_notify, "_start_dispatch_thread") as start:
        slack_notify.notify_if_configured(
            "sim_unset", "completed", sim_dir="/nonexistent"
        )
    assert start.call_count == 0


def test_notify_if_configured_ignores_unknown_status(monkeypatch):
    monkeypatch.setenv(
        slack_notify.SLACK_WEBHOOK_URL_ENV_VAR,
        "https://hooks.slack.com/services/T0/B0/abc",
    )
    slack_notify.reset_dedup_for_tests()
    with patch.object(slack_notify, "_start_dispatch_thread") as start:
        slack_notify.notify_if_configured(
            "sim_running", "running", sim_dir="/nonexistent"
        )
    assert start.call_count == 0


def test_notify_if_configured_fires_once_per_sim_status_pair(monkeypatch, tmp_path):
    monkeypatch.setenv(
        slack_notify.SLACK_WEBHOOK_URL_ENV_VAR,
        "https://hooks.slack.com/services/T0/B0/abc",
    )
    slack_notify.reset_dedup_for_tests()

    sim_dir = tmp_path / "sim_dedup_slack"
    sim_dir.mkdir()

    captured: list[dict] = []

    def fake_start(*, url, message, thread_name):
        captured.append({"url": url, "message": message, "thread_name": thread_name})

    with patch.object(slack_notify, "_start_dispatch_thread", side_effect=fake_start):
        slack_notify.notify_if_configured("sim_dedup_slack", "completed", sim_dir=str(sim_dir))
        slack_notify.notify_if_configured("sim_dedup_slack", "completed", sim_dir=str(sim_dir))
    assert len(captured) == 1
    assert "blocks" in captured[0]["message"]


def test_dispatch_thread_posts_blocks_body():
    sent: list[tuple] = []

    def fake_post(url, body, timeout):
        sent.append((url, body, timeout))
        return True, "HTTP 200"

    message = {"blocks": [{"type": "header", "text": {"type": "plain_text", "text": "x"}}]}

    with patch.object(slack_notify, "_post_json", side_effect=fake_post):
        slack_notify._start_dispatch_thread(
            url="https://hooks.slack.com/services/T0/B0/abc",
            message=message,
            thread_name="slack-smoke",
        )

        deadline = time.time() + 2.0
        while not sent and time.time() < deadline:
            time.sleep(0.01)

    assert len(sent) == 1
    url, body, timeout = sent[0]
    assert url == "https://hooks.slack.com/services/T0/B0/abc"
    assert body == message
    assert timeout == slack_notify.SLACK_TIMEOUT_SECONDS


def test_post_json_swallows_url_error():
    import urllib.error

    def boom(*_a, **_kw):
        raise urllib.error.URLError("dns failed")

    with patch("urllib.request.urlopen", side_effect=boom):
        ok, msg = slack_notify._post_json(
            "https://hooks.slack.com/services/T0/B0/abc",
            {"blocks": []},
            timeout=1.0,
        )
    assert ok is False
    assert "URL error" in msg


# ── Test event ─────────────────────────────────────────────────────────


def test_send_test_notification_rejects_blank(monkeypatch):
    monkeypatch.delenv(slack_notify.SLACK_WEBHOOK_URL_ENV_VAR, raising=False)
    result = slack_notify.send_test_notification("")
    assert result == {"ok": False, "message": "Slack webhook URL is empty"}


def test_send_test_notification_posts_when_url_given():
    with patch.object(
        slack_notify, "_post_json", return_value=(True, "HTTP 200")
    ) as mock_post:
        result = slack_notify.send_test_notification(
            "https://hooks.slack.com/services/T0/B0/abc"
        )
    assert result == {"ok": True, "message": "HTTP 200"}
    assert mock_post.called
    _, args, _ = mock_post.mock_calls[0]
    url, body, _timeout = args
    assert url.startswith("https://hooks.slack.com/")
    assert "blocks" in body


# ── Module discoverability ─────────────────────────────────────────────


def test_notify_function_is_exported():
    assert callable(slack_notify.notify_if_configured)
    assert callable(slack_notify.is_configured)
    assert callable(slack_notify.build_slack_message)
