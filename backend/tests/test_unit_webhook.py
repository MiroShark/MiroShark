"""Unit tests for the outbound completion webhook.

Pure offline tests — no Flask app, no real HTTP. They cover the four
properties the runner depends on:

  1. ``build_payload`` reads the same on-disk artifacts the share card +
     gallery card consume, and degrades gracefully when files are missing
     or malformed (the webhook must never raise).
  2. URL validation accepts ``http(s)://`` and rejects everything else.
  3. URL masking only echoes scheme + host (the path of a Slack or
     Discord webhook URL is the secret).
  4. ``fire_webhook_for_simulation`` is fire-and-forget, deduped per
     ``(sim_id, status)``, and a no-op when no URL is configured — even
     when the network would 500.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Payload tests ──────────────────────────────────────────────────────────


@pytest.fixture
def populated_sim_dir(tmp_path: Path) -> Path:
    """A simulation directory with every artifact the webhook reads."""
    (tmp_path / "simulation_config.json").write_text(json.dumps({
        "simulation_requirement": "Will the SEC approve a spot Solana ETF before Q3 2026?",
        "time_config": {"minutes_per_round": 60, "total_simulation_hours": 20},
    }))
    (tmp_path / "quality.json").write_text(json.dumps({
        "health": "Excellent",
        "participation_rate": 0.92,
    }))
    (tmp_path / "trajectory.json").write_text(json.dumps({
        "snapshots": [
            {
                "round_num": 0,
                "belief_positions": {
                    "a": {"topic": 0.0},
                    "b": {"topic": 0.0},
                    "c": {"topic": 0.0},
                },
            },
            {
                "round_num": 1,
                "belief_positions": {
                    "a": {"topic": 0.6},
                    "b": {"topic": 0.4},
                    "c": {"topic": -0.5},
                    "d": {"topic": 0.0},
                },
            },
        ],
    }))
    (tmp_path / "resolution.json").write_text(json.dumps({
        "actual_outcome": "YES",
        "predicted_consensus": "YES",
        "accuracy_score": 1.0,
    }))
    (tmp_path / "state.json").write_text(json.dumps({
        "profiles_count": 248,
        "created_at": "2026-04-26T10:12:34",
        "parent_simulation_id": None,
    }))
    return tmp_path


def test_payload_reads_every_artifact(populated_sim_dir: Path):
    from app.services.webhook_service import build_payload

    payload = build_payload(
        "sim_abc123",
        "completed",
        str(populated_sim_dir),
        completed_at="2026-04-26T10:35:11",
    )

    assert payload["event"] == "simulation.completed"
    assert payload["sim_id"] == "sim_abc123"
    assert payload["status"] == "completed"
    assert payload["scenario"].startswith("Will the SEC approve")
    assert payload["total_rounds"] == 20  # 20h * 60m / 60m
    assert payload["agent_count"] == 248
    assert payload["created_at"] == "2026-04-26T10:12:34"
    assert payload["completed_at"] == "2026-04-26T10:35:11"
    assert payload["quality_health"] == "Excellent"
    assert payload["resolution_outcome"] == "YES"
    # 2/4 stances > 0.2 = bullish; 1/4 < -0.2 = bearish; 1/4 neutral.
    assert payload["final_consensus"] == {"bullish": 50.0, "neutral": 25.0, "bearish": 25.0}
    assert payload["share_path"] == "/share/sim_abc123"
    assert payload["share_card_path"] == "/api/simulation/sim_abc123/share-card.png"
    # No base_url passed → no absolute URL fields.
    assert "share_url" not in payload
    assert "share_card_url" not in payload


def test_payload_includes_absolute_urls_when_base_set(populated_sim_dir: Path):
    from app.services.webhook_service import build_payload

    payload = build_payload(
        "sim_xyz",
        "completed",
        str(populated_sim_dir),
        base_url="https://miroshark.app/",  # trailing slash should be stripped
    )

    assert payload["share_url"] == "https://miroshark.app/share/sim_xyz"
    assert payload["share_card_url"] == "https://miroshark.app/api/simulation/sim_xyz/share-card.png"


def test_payload_truncates_long_scenario(tmp_path: Path):
    from app.services.webhook_service import build_payload, WEBHOOK_MAX_SCENARIO_CHARS

    long_text = "A " * 400  # 800 chars
    (tmp_path / "simulation_config.json").write_text(json.dumps({
        "simulation_requirement": long_text,
        "time_config": {"minutes_per_round": 60, "total_simulation_hours": 5},
    }))

    payload = build_payload("sim_x", "completed", str(tmp_path))
    assert len(payload["scenario"]) <= WEBHOOK_MAX_SCENARIO_CHARS
    assert payload["scenario"].endswith("…")


def test_payload_failure_includes_truncated_error(populated_sim_dir: Path):
    from app.services.webhook_service import build_payload

    long_err = "stack trace " * 200
    payload = build_payload(
        "sim_err",
        "failed",
        str(populated_sim_dir),
        error=long_err,
    )

    assert payload["event"] == "simulation.failed"
    assert payload["status"] == "failed"
    assert "error" in payload
    assert len(payload["error"]) <= 1000
    assert payload["error"].endswith("…")


def test_payload_falls_back_to_state_json_when_no_state_object(populated_sim_dir: Path):
    """When the runner doesn't pass an in-memory state, agent_count and
    created_at must come from the on-disk state.json."""
    from app.services.webhook_service import build_payload

    payload = build_payload("sim_disk", "completed", str(populated_sim_dir))
    assert payload["agent_count"] == 248
    assert payload["created_at"] == "2026-04-26T10:12:34"


def test_payload_state_object_takes_precedence(populated_sim_dir: Path):
    from app.services.webhook_service import build_payload

    class _State:
        profiles_count = 999
        created_at = "2026-04-26T11:00:00"
        parent_simulation_id = "sim_parent"
        current_round = 17
        total_rounds = 30

    payload = build_payload(
        "sim_pref",
        "completed",
        str(populated_sim_dir),
        state=_State(),
    )
    assert payload["agent_count"] == 999
    assert payload["created_at"] == "2026-04-26T11:00:00"
    assert payload["parent_simulation_id"] == "sim_parent"
    assert payload["current_round"] == 17
    assert payload["total_rounds"] == 30  # state.total_rounds wins over config


def test_payload_handles_missing_artifacts(tmp_path: Path):
    """Empty sim_dir → all-optional fields are None / 0, no exception."""
    from app.services.webhook_service import build_payload

    payload = build_payload("sim_empty", "completed", str(tmp_path))
    assert payload["scenario"] == ""
    assert payload["quality_health"] is None
    assert payload["final_consensus"] is None
    assert payload["resolution_outcome"] is None
    assert payload["agent_count"] == 0
    assert payload["total_rounds"] == 0


def test_payload_handles_corrupt_artifacts(tmp_path: Path):
    """Malformed JSON anywhere doesn't take the webhook down."""
    from app.services.webhook_service import build_payload

    (tmp_path / "simulation_config.json").write_text("{not json")
    (tmp_path / "quality.json").write_text("totally broken")
    (tmp_path / "trajectory.json").write_text("[[[")
    (tmp_path / "resolution.json").write_text("{")
    (tmp_path / "state.json").write_text("nope")

    payload = build_payload("sim_corrupt", "completed", str(tmp_path))
    assert payload["sim_id"] == "sim_corrupt"
    assert payload["scenario"] == ""
    assert payload["quality_health"] is None
    assert payload["final_consensus"] is None


def test_payload_event_name_matches_status():
    """The ``event`` field is the conventional ``noun.verb`` shape — keep
    it in sync with ``status`` so consumers can route on either."""
    from app.services.webhook_service import build_payload

    completed = build_payload("sim_a", "completed", "/nonexistent")
    failed = build_payload("sim_b", "failed", "/nonexistent")
    assert completed["event"] == "simulation.completed"
    assert failed["event"] == "simulation.failed"


# ── URL validation + masking ───────────────────────────────────────────────


def test_validate_url_accepts_http_and_https():
    from app.services.webhook_service import validate_url

    assert validate_url("https://hooks.slack.com/services/T0/B0/abc") is None
    assert validate_url("http://internal.svc:8080/hook") is None
    # Empty disables the webhook — that's a valid configuration.
    assert validate_url("") is None
    assert validate_url("   ") is None


def test_validate_url_rejects_other_schemes():
    from app.services.webhook_service import validate_url

    assert validate_url("ftp://example.com/hook") is not None
    assert validate_url("javascript:alert(1)") is not None
    assert validate_url("file:///etc/passwd") is not None
    assert validate_url("hooks.slack.com/abc") is not None  # no scheme


def test_validate_url_rejects_overlong():
    from app.services.webhook_service import validate_url

    assert validate_url("https://x.com/" + "a" * 5000) is not None


def test_mask_url_hides_path():
    from app.services.webhook_service import mask_url

    masked = mask_url("https://hooks.slack.com/services/T0XXX/B0YYY/abcSECRETxyz")
    assert masked == "https://hooks.slack.com/***"
    assert "abcSECRETxyz" not in masked
    assert "T0XXX" not in masked


def test_mask_url_handles_empty_and_garbage():
    from app.services.webhook_service import mask_url

    assert mask_url("") == ""
    assert mask_url("not a url") == "***"


# ── fire_webhook_for_simulation behavior ───────────────────────────────────


def test_fire_is_no_op_without_configured_url(populated_sim_dir: Path):
    """If WEBHOOK_URL is empty, the function must not call _post_json."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    with patch.object(webhook_service, '_resolve_webhook_url', return_value=''), \
         patch.object(webhook_service, '_post_json') as mock_post:
        webhook_service.fire_webhook_for_simulation(
            "sim_noop",
            "completed",
            sim_dir=str(populated_sim_dir),
        )
    assert mock_post.call_count == 0


def test_fire_dispatches_in_background_thread(populated_sim_dir: Path):
    """The POST happens on a daemon thread — the call returns immediately
    even if the network would block forever."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    started = threading.Event()
    finished = threading.Event()

    def slow_post(url, payload, timeout):
        started.set()
        # Simulate a slow webhook endpoint — but bounded so the test
        # actually completes if something goes wrong.
        finished.wait(timeout=2.0)
        return True, "HTTP 200"

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json', side_effect=slow_post):
        webhook_service.fire_webhook_for_simulation(
            "sim_async",
            "completed",
            sim_dir=str(populated_sim_dir),
        )
        # The fire call must have returned even though _post_json is still
        # blocked. Wait briefly for the daemon thread to pick up the work.
        assert started.wait(timeout=2.0), "Background thread never ran"
        finished.set()  # let the mocked POST return


def test_fire_dedups_per_sim_and_status(populated_sim_dir: Path):
    """Two fire_webhook calls with the same (sim_id, status) → one POST.
    Different status (completed vs failed) → two POSTs."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    calls: list = []
    done = threading.Event()
    counter = {'n': 0}

    def record_post(url, payload, timeout):
        calls.append(payload['event'])
        counter['n'] += 1
        if counter['n'] >= 2:
            done.set()
        return True, "HTTP 200"

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json', side_effect=record_post):
        webhook_service.fire_webhook_for_simulation(
            "sim_dedup", "completed", sim_dir=str(populated_sim_dir),
        )
        webhook_service.fire_webhook_for_simulation(
            "sim_dedup", "completed", sim_dir=str(populated_sim_dir),
        )
        webhook_service.fire_webhook_for_simulation(
            "sim_dedup", "failed", sim_dir=str(populated_sim_dir),
        )
        # Wait for both expected fires (completed + failed) — the second
        # completed call is deduped and never reaches _post_json.
        assert done.wait(timeout=3.0), f"Only {counter['n']} POSTs fired"

    assert sorted(calls) == ["simulation.completed", "simulation.failed"]


def test_fire_swallows_post_failures(populated_sim_dir: Path):
    """A POST that raises mid-flight must not crash the background thread
    or propagate to the caller."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    finished = threading.Event()

    def boom(url, payload, timeout):
        finished.set()
        raise RuntimeError("simulated network blip")

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json', side_effect=boom):
        # The fire call itself must not raise even though _post_json will.
        webhook_service.fire_webhook_for_simulation(
            "sim_boom", "completed", sim_dir=str(populated_sim_dir),
        )
        assert finished.wait(timeout=2.0)


def test_fire_ignores_unknown_status(populated_sim_dir: Path):
    """Only ``completed`` / ``failed`` are valid terminal statuses."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json') as mock_post:
        webhook_service.fire_webhook_for_simulation(
            "sim_running", "running", sim_dir=str(populated_sim_dir),
        )
    assert mock_post.call_count == 0


# ── send_test_webhook ──────────────────────────────────────────────────────


def test_test_webhook_returns_validation_error_for_bad_url():
    from app.services.webhook_service import send_test_webhook

    result = send_test_webhook("not-a-url")
    assert result["ok"] is False
    assert "http://" in result["message"]


def test_test_webhook_posts_sample_payload():
    from app.services import webhook_service

    captured: dict = {}

    def capture(url, payload, timeout):
        captured["url"] = url
        captured["payload"] = payload
        return True, "HTTP 204"

    with patch.object(webhook_service, '_post_json', side_effect=capture):
        result = webhook_service.send_test_webhook(
            "https://example.com/hook",
            base_url="https://miroshark.app",
        )

    assert result["ok"] is True
    assert "latency_ms" in result
    assert captured["url"] == "https://example.com/hook"
    assert captured["payload"]["event"] == "simulation.test"
    assert captured["payload"]["test"] is True
    assert captured["payload"]["share_url"].startswith("https://miroshark.app/share/")


# ── Sanity that the runner's import path still works ──────────────────────


def test_runner_can_import_webhook_service():
    """Catches accidental rename / refactor that would break the late
    import inside SimulationRunner._monitor_simulation."""
    from app.services.webhook_service import fire_webhook_for_simulation
    assert callable(fire_webhook_for_simulation)
