"""Unit tests for the Discord rich-embed notifier.

Pure offline — no Flask boot, no real Discord endpoint. The notifier
is a thin projection over :func:`webhook_service.build_payload`, so
the tests cover:

  1. Module constants (colours, env var name, title cap) stay pinned
     so a refactor doesn't silently drift the public contract.
  2. ``_consensus_color`` picks the right colour for bullish / neutral
     / bearish / failed / empty-trajectory payloads.
  3. ``build_discord_embed`` produces a well-formed embed dict with
     the expected fields, title truncation, thumbnail URL, and link.
  4. ``notify_if_configured`` no-ops when ``DISCORD_WEBHOOK_URL`` is
     unset and POSTs exactly once per ``(sim_id, status)`` pair when
     set.
  5. ``send_test_notification`` returns ``ok=False`` for an unset env
     var and constructs a valid Block-Kit-shaped body otherwise.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


from app.services import discord_notify  # noqa: E402


# ── Module-level invariants ────────────────────────────────────────────


def test_env_var_name_pinned():
    """The env var name is part of the public contract — operators
    paste it into ``.env`` files and CI secrets; a rename breaks
    every deployment."""
    assert discord_notify.DISCORD_WEBHOOK_URL_ENV_VAR == "DISCORD_WEBHOOK_URL"


def test_color_constants_match_spa():
    """Embed colours match the green/grey/red palette the SPA uses
    so the Discord card reads as the same colour system."""
    assert discord_notify.COLOR_BULLISH == 0x22C55E
    assert discord_notify.COLOR_NEUTRAL == 0x6B7280
    assert discord_notify.COLOR_BEARISH == 0xEF4444
    assert discord_notify.COLOR_FAILED == 0xF59E0B


def test_title_max_chars_clamped_under_discord_limit():
    """Discord caps embed titles at 256; we clamp lower so the
    truncation reads cleanly with the trailing ``…`` glyph."""
    assert 0 < discord_notify.DISCORD_TITLE_MAX_CHARS <= 256


# ── Consensus-colour helper ────────────────────────────────────────────


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


def test_consensus_color_bullish():
    assert discord_notify._consensus_color(_payload()) == discord_notify.COLOR_BULLISH


def test_consensus_color_bearish():
    payload = _payload(final_consensus={"bullish": 10.0, "neutral": 20.0, "bearish": 70.0})
    assert discord_notify._consensus_color(payload) == discord_notify.COLOR_BEARISH


def test_consensus_color_neutral_when_neutral_wins():
    payload = _payload(final_consensus={"bullish": 20.0, "neutral": 60.0, "bearish": 20.0})
    assert discord_notify._consensus_color(payload) == discord_notify.COLOR_NEUTRAL


def test_consensus_color_neutral_when_trajectory_missing():
    payload = _payload(final_consensus=None)
    assert discord_notify._consensus_color(payload) == discord_notify.COLOR_NEUTRAL


def test_consensus_color_failed_is_amber_regardless_of_trajectory():
    payload = _payload(status="failed")
    assert discord_notify._consensus_color(payload) == discord_notify.COLOR_FAILED


# ── Embed builder ──────────────────────────────────────────────────────


def test_build_discord_embed_basic_shape():
    embed = discord_notify.build_discord_embed(_payload())
    assert embed["type"] == "rich"
    assert embed["title"] == "Will the SEC approve XYZ?"
    assert embed["color"] == discord_notify.COLOR_BULLISH
    assert embed["url"] == "https://miroshark.app/share/sim_x"
    assert embed["thumbnail"] == {
        "url": "https://miroshark.app/api/simulation/sim_x/share-card.png"
    }
    assert embed["footer"] == {"text": "MiroShark"}
    assert embed["timestamp"] == "2026-05-15T12:00:00+00:00"


def test_build_discord_embed_includes_belief_fields():
    embed = discord_notify.build_discord_embed(_payload())
    field_names = [f["name"] for f in embed["fields"]]
    assert "Bullish" in field_names
    assert "Neutral" in field_names
    assert "Bearish" in field_names
    # Inline by default so Discord renders them in one row.
    for f in embed["fields"]:
        if f["name"] in ("Bullish", "Neutral", "Bearish"):
            assert f["inline"] is True


def test_build_discord_embed_truncates_long_scenario():
    long_scenario = "x" * 250
    embed = discord_notify.build_discord_embed(_payload(scenario=long_scenario))
    assert len(embed["title"]) <= discord_notify.DISCORD_TITLE_MAX_CHARS
    assert embed["title"].endswith("…")


def test_build_discord_embed_falls_back_when_scenario_empty():
    embed = discord_notify.build_discord_embed(_payload(scenario=""))
    assert embed["title"] == "Simulation sim_x"


def test_build_discord_embed_drops_thumbnail_for_relative_url():
    payload = _payload(share_card_url=None)
    embed = discord_notify.build_discord_embed(payload)
    assert "thumbnail" not in embed


def test_build_discord_embed_uses_share_path_when_no_absolute_url():
    payload = _payload(share_url=None)
    embed = discord_notify.build_discord_embed(payload)
    # No absolute URL ⇒ embed has no ``url`` key (relative paths
    # would not render as a clickable card title in Discord).
    assert "url" not in embed


def test_build_discord_embed_failed_status_carries_error_field():
    payload = _payload(
        status="failed",
        error="Process exit code 1: simulation segfault",
        final_consensus=None,
    )
    embed = discord_notify.build_discord_embed(payload)
    assert embed["color"] == discord_notify.COLOR_FAILED
    error_field = next((f for f in embed["fields"] if f["name"] == "Error"), None)
    assert error_field is not None
    assert "segfault" in error_field["value"]


def test_build_discord_embed_includes_quality_rounds_agents():
    embed = discord_notify.build_discord_embed(_payload())
    field_map = {f["name"]: f["value"] for f in embed["fields"]}
    assert field_map.get("Quality") == "Excellent"
    assert field_map.get("Rounds") == "20"
    assert field_map.get("Agents") == "248"


# ── notify_if_configured behaviour ─────────────────────────────────────


def test_notify_if_configured_noop_when_env_unset(monkeypatch):
    monkeypatch.delenv(discord_notify.DISCORD_WEBHOOK_URL_ENV_VAR, raising=False)
    discord_notify.reset_dedup_for_tests()

    with patch.object(discord_notify, "_start_dispatch_thread") as start:
        discord_notify.notify_if_configured(
            "sim_unset",
            "completed",
            sim_dir="/nonexistent",
        )
        assert start.call_count == 0


def test_notify_if_configured_ignores_unknown_status(monkeypatch):
    monkeypatch.setenv(
        discord_notify.DISCORD_WEBHOOK_URL_ENV_VAR,
        "https://discord.example/webhook",
    )
    discord_notify.reset_dedup_for_tests()

    with patch.object(discord_notify, "_start_dispatch_thread") as start:
        discord_notify.notify_if_configured(
            "sim_running",
            "running",  # not a terminal status
            sim_dir="/nonexistent",
        )
        assert start.call_count == 0


def test_notify_if_configured_fires_once_per_sim_status_pair(monkeypatch, tmp_path):
    monkeypatch.setenv(
        discord_notify.DISCORD_WEBHOOK_URL_ENV_VAR,
        "https://discord.example/webhook",
    )
    discord_notify.reset_dedup_for_tests()

    sim_dir = tmp_path / "sim_dedup"
    sim_dir.mkdir()

    captured: list[dict] = []

    def fake_start(*, url, embed, thread_name):
        captured.append({"url": url, "embed": embed, "thread_name": thread_name})

    with patch.object(discord_notify, "_start_dispatch_thread", side_effect=fake_start):
        discord_notify.notify_if_configured(
            "sim_dedup",
            "completed",
            sim_dir=str(sim_dir),
            completed_at="2026-05-15T13:00:00",
        )
        discord_notify.notify_if_configured(
            "sim_dedup",
            "completed",
            sim_dir=str(sim_dir),
            completed_at="2026-05-15T13:00:01",
        )

    assert len(captured) == 1
    assert captured[0]["url"] == "https://discord.example/webhook"
    assert captured[0]["embed"]["type"] == "rich"


def test_notify_if_configured_completed_and_failed_dispatched_independently(monkeypatch, tmp_path):
    """Same ``sim_id`` with two distinct statuses (which only happens
    in pathological setups, but the dedup keys on the *pair*) fires
    twice — once per status."""
    monkeypatch.setenv(
        discord_notify.DISCORD_WEBHOOK_URL_ENV_VAR,
        "https://discord.example/webhook",
    )
    discord_notify.reset_dedup_for_tests()

    sim_dir = tmp_path / "sim_paths"
    sim_dir.mkdir()

    with patch.object(discord_notify, "_start_dispatch_thread") as start:
        discord_notify.notify_if_configured(
            "sim_paths",
            "completed",
            sim_dir=str(sim_dir),
        )
        discord_notify.notify_if_configured(
            "sim_paths",
            "failed",
            sim_dir=str(sim_dir),
            error="late failure",
        )
    assert start.call_count == 2


def test_dispatch_thread_calls_send_discord_payload(monkeypatch):
    """The daemon-thread path POSTs the embed via
    :func:`send_discord_payload`. We verify the wiring by spying on
    the post and joining the thread."""
    embed = {"type": "rich", "title": "smoke test"}

    sent: list[tuple] = []

    def fake_post(url, body, timeout):
        sent.append((url, body, timeout))
        return True, "HTTP 204"

    with patch.object(discord_notify, "_post_json", side_effect=fake_post):
        discord_notify._start_dispatch_thread(
            url="https://discord.example/webhook",
            embed=embed,
            thread_name="discord-smoke",
        )

        # The daemon thread runs ~instantly for an in-process fake.
        deadline = time.time() + 2.0
        while not sent and time.time() < deadline:
            time.sleep(0.01)

    assert len(sent) == 1
    url, body, timeout = sent[0]
    assert url == "https://discord.example/webhook"
    assert body == {"embeds": [embed]}
    assert timeout == discord_notify.DISCORD_TIMEOUT_SECONDS


def test_post_json_never_raises_on_url_error():
    """The post helper swallows URL errors and returns ``(False, msg)``
    so the caller never has to wrap it in try/except."""
    import urllib.error

    def boom(*_args, **_kwargs):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", side_effect=boom):
        ok, msg = discord_notify._post_json(
            "https://discord.example/webhook",
            {"embeds": []},
            timeout=1.0,
        )
    assert ok is False
    assert "URL error" in msg


# ── Test event ─────────────────────────────────────────────────────────


def test_send_test_notification_rejects_blank(monkeypatch):
    monkeypatch.delenv(discord_notify.DISCORD_WEBHOOK_URL_ENV_VAR, raising=False)
    result = discord_notify.send_test_notification("")
    assert result == {"ok": False, "message": "Discord webhook URL is empty"}


def test_send_test_notification_posts_when_url_given():
    with patch.object(
        discord_notify,
        "_post_json",
        return_value=(True, "HTTP 204"),
    ) as mock_post:
        result = discord_notify.send_test_notification(
            "https://discord.example/webhook"
        )
    assert result == {"ok": True, "message": "HTTP 204"}
    assert mock_post.called
    _, args, _ = mock_post.mock_calls[0]
    url, body, timeout = args
    assert url == "https://discord.example/webhook"
    assert "embeds" in body
    assert isinstance(body["embeds"], list)
    assert len(body["embeds"]) == 1


# ── Module discoverability ─────────────────────────────────────────────


def test_notify_function_is_exported():
    """The runner imports ``notify_if_configured`` by name — guard the
    symbol so a rename doesn't silently break the dispatch site."""
    assert callable(discord_notify.notify_if_configured)
    assert callable(discord_notify.is_configured)
    assert callable(discord_notify.build_discord_embed)
