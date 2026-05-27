"""Unit tests for the per-simulation webhook delivery log.

Covers the operational visibility layer that PR #46 (the outbound
completion webhook) shipped without: every dispatch attempt should
land in ``<sim_dir>/webhook-log.jsonl`` so an operator can verify
deliveries, see latency / status codes, and replay failures.

Pure offline tests — no Flask app, no real HTTP, no Neo4j. We patch
``_post_json`` so the dispatch path runs end-to-end (including the
log write inside the daemon thread) without network.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch



_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Helpers ──────────────────────────────────────────────────────────────


def _wait_for_log_lines(sim_dir: Path, expected: int, timeout: float = 3.0) -> int:
    """Poll for the log to reach ``expected`` lines (the daemon thread
    writes on its own schedule). Returns the actual line count."""
    deadline = time.monotonic() + timeout
    log = sim_dir / "webhook-log.jsonl"
    last = 0
    while time.monotonic() < deadline:
        if log.exists():
            try:
                last = sum(1 for line in log.read_text().splitlines() if line.strip())
            except OSError:
                last = 0
            if last >= expected:
                return last
        time.sleep(0.02)
    return last


def _read_log(sim_dir: Path) -> list[dict]:
    log = sim_dir / "webhook-log.jsonl"
    if not log.exists():
        return []
    out = []
    for line in log.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


# ── Direct helper tests ──────────────────────────────────────────────────


def test_log_path_uses_filename_constant(tmp_path: Path):
    from app.services.webhook_service import (
        webhook_log_path,
        WEBHOOK_LOG_FILENAME,
    )
    assert webhook_log_path(str(tmp_path)) == str(tmp_path / WEBHOOK_LOG_FILENAME)


def test_read_webhook_log_empty_when_no_file(tmp_path: Path):
    from app.services.webhook_service import (
        read_webhook_log,
        WEBHOOK_LOG_MAX_LINES,
    )
    result = read_webhook_log(str(tmp_path))
    assert result == {
        "entries": [],
        "total_attempts": 0,
        "max_retained": WEBHOOK_LOG_MAX_LINES,
    }


def test_append_and_read_round_trip(tmp_path: Path):
    """A series of appends should produce monotonic ``attempt`` numbers
    and the GET-style read returns them newest-first."""
    from app.services import webhook_service

    payload = {"event": "simulation.completed", "sim_id": "sim_a", "status": "completed"}
    for i in range(3):
        webhook_service._record_delivery(
            sim_dir=str(tmp_path),
            url="https://hooks.slack.com/services/T0/B0/abc",
            payload=payload,
            ok=(i % 2 == 0),
            message=("HTTP 200" if i % 2 == 0 else "HTTP 503"),
            latency_ms=120 + i,
            trigger="auto",
        )

    result = webhook_service.read_webhook_log(str(tmp_path))
    assert result["total_attempts"] == 3
    assert len(result["entries"]) == 3
    # newest-first
    assert [e["attempt"] for e in result["entries"]] == [3, 2, 1]
    # masking persists to disk
    assert all(e["url_masked"] == "https://hooks.slack.com/***" for e in result["entries"])
    assert "abc" not in (tmp_path / "webhook-log.jsonl").read_text()


def test_status_code_parsed_from_http_messages(tmp_path: Path):
    """``HTTP 503`` → ``status_code == 503``; network errors → null."""
    from app.services import webhook_service

    payload = {"event": "simulation.completed", "sim_id": "sim_x", "status": "completed"}
    webhook_service._record_delivery(
        sim_dir=str(tmp_path), url="https://example.com/hook",
        payload=payload, ok=True, message="HTTP 200", latency_ms=10, trigger="auto",
    )
    webhook_service._record_delivery(
        sim_dir=str(tmp_path), url="https://example.com/hook",
        payload=payload, ok=False, message="HTTP 503", latency_ms=20, trigger="auto",
    )
    webhook_service._record_delivery(
        sim_dir=str(tmp_path), url="https://example.com/hook",
        payload=payload, ok=False, message="URL error: timeout", latency_ms=5000, trigger="auto",
    )

    entries = _read_log(tmp_path)
    codes = {e["attempt"]: e["status_code"] for e in entries}
    assert codes[1] == 200
    assert codes[2] == 503
    assert codes[3] is None
    # Failure rows carry the upstream message; success rows have ``error: None``.
    err_by_attempt = {e["attempt"]: e["error"] for e in entries}
    assert err_by_attempt[1] is None
    assert err_by_attempt[2] == "HTTP 503"
    assert err_by_attempt[3] == "URL error: timeout"


def test_log_truncates_to_max_lines(tmp_path: Path):
    """Once the log hits ``WEBHOOK_LOG_MAX_LINES``, the oldest entry
    rolls off so the new attempt always lands."""
    from app.services import webhook_service
    from app.services.webhook_service import WEBHOOK_LOG_MAX_LINES

    payload = {"event": "simulation.completed", "sim_id": "sim_trunc", "status": "completed"}
    overshoot = WEBHOOK_LOG_MAX_LINES + 5
    for _ in range(overshoot):
        webhook_service._record_delivery(
            sim_dir=str(tmp_path), url="https://example.com/hook",
            payload=payload, ok=True, message="HTTP 204", latency_ms=15, trigger="auto",
        )

    log = tmp_path / "webhook-log.jsonl"
    line_count = sum(1 for line in log.read_text().splitlines() if line.strip())
    assert line_count == WEBHOOK_LOG_MAX_LINES

    # The all-time attempt counter keeps climbing even though older
    # rows have rolled off the disk file.
    result = webhook_service.read_webhook_log(str(tmp_path))
    assert result["total_attempts"] == overshoot
    # The slice is bounded by WEBHOOK_LOG_RETURN_LIMIT (default 10).
    assert len(result["entries"]) == 10
    # Newest first — the very first entry in the slice is the final
    # write (attempt = overshoot).
    assert result["entries"][0]["attempt"] == overshoot


def test_read_webhook_log_caps_slice_to_limit(tmp_path: Path):
    """The default GET slice is the last 10 entries even when more
    survived the truncation pass."""
    from app.services import webhook_service

    payload = {"event": "simulation.completed", "sim_id": "sim_cap", "status": "completed"}
    for _ in range(15):
        webhook_service._record_delivery(
            sim_dir=str(tmp_path), url="https://example.com/hook",
            payload=payload, ok=True, message="HTTP 200", latency_ms=8, trigger="auto",
        )

    result = webhook_service.read_webhook_log(str(tmp_path))
    assert len(result["entries"]) == 10
    assert result["total_attempts"] == 15
    # First entry of the slice is the most recent attempt (15th).
    assert result["entries"][0]["attempt"] == 15
    # Slice is contiguous: 15, 14, 13, ... 6.
    assert [e["attempt"] for e in result["entries"]] == list(range(15, 5, -1))


def test_append_skips_unwritable_sim_dir(tmp_path: Path):
    """Empty / falsy ``sim_dir`` must be a silent no-op — never raise."""
    from app.services import webhook_service

    # Should not raise.
    webhook_service._record_delivery(
        sim_dir="", url="https://example.com/hook",
        payload={"event": "x", "sim_id": "y", "status": "completed"},
        ok=True, message="HTTP 200", latency_ms=10, trigger="auto",
    )
    webhook_service._record_delivery(
        sim_dir=None, url="https://example.com/hook",
        payload={"event": "x", "sim_id": "y", "status": "completed"},
        ok=True, message="HTTP 200", latency_ms=10, trigger="auto",
    )


def test_corrupt_log_lines_are_skipped(tmp_path: Path):
    """A garbage line in the middle of the log must not blank the read."""
    from app.services import webhook_service

    log = tmp_path / "webhook-log.jsonl"
    log.write_text(
        json.dumps({"attempt": 1, "ok": True, "url_masked": "x"}) + "\n"
        + "this is not json\n"
        + json.dumps({"attempt": 2, "ok": False, "url_masked": "y"}) + "\n"
    )
    result = webhook_service.read_webhook_log(str(tmp_path))
    # Two valid, one skipped — total_attempts reflects the highest seen.
    assert result["total_attempts"] == 2
    assert len(result["entries"]) == 2
    assert {e["attempt"] for e in result["entries"]} == {1, 2}


# ── End-to-end dispatch + log integration ────────────────────────────────


def test_fire_webhook_appends_log_entry(tmp_path: Path):
    """A successful auto-fire writes a single ``trigger:"auto"`` row."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    finished = threading.Event()

    def fake_post(url, payload, timeout):
        # Tiny sleep so the elapsed time is measurable but bounded.
        time.sleep(0.01)
        finished.set()
        return True, "HTTP 200"

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://hooks.slack.com/services/T0/B0/abc'), \
         patch.object(webhook_service, '_post_json', side_effect=fake_post):
        webhook_service.fire_webhook_for_simulation(
            "sim_log_auto",
            "completed",
            sim_dir=str(tmp_path),
        )
        assert finished.wait(timeout=2.0)
        # Wait for the log write that happens after _post_json returns.
        assert _wait_for_log_lines(tmp_path, expected=1) == 1

    entries = _read_log(tmp_path)
    assert len(entries) == 1
    rec = entries[0]
    assert rec["attempt"] == 1
    assert rec["ok"] is True
    assert rec["status_code"] == 200
    assert rec["error"] is None
    assert rec["trigger"] == "auto"
    assert rec["url_masked"] == "https://hooks.slack.com/***"
    assert rec["event"] == "simulation.completed"
    assert rec["status"] == "completed"
    assert isinstance(rec["latency_ms"], int) and rec["latency_ms"] >= 0
    assert "T" in rec["timestamp"]  # ISO 8601


def test_fire_webhook_logs_failure_on_5xx(tmp_path: Path):
    """A 5xx from the downstream endpoint lands in the log as ok:false
    with a parsed status code and an upstream-error string."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    finished = threading.Event()

    def fake_post(url, payload, timeout):
        finished.set()
        return False, "HTTP 503"

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json', side_effect=fake_post):
        webhook_service.fire_webhook_for_simulation(
            "sim_log_5xx",
            "failed",
            sim_dir=str(tmp_path),
            error="exit code 1",
        )
        assert finished.wait(timeout=2.0)
        assert _wait_for_log_lines(tmp_path, expected=1) == 1

    entries = _read_log(tmp_path)
    rec = entries[0]
    assert rec["ok"] is False
    assert rec["status_code"] == 503
    assert rec["error"] == "HTTP 503"
    assert rec["status"] == "failed"
    assert rec["event"] == "simulation.failed"


def test_retry_bypasses_dedup_and_uses_retry_trigger(tmp_path: Path):
    """``retry_webhook_for_simulation`` must ignore the ``(sim_id, status)``
    dedup gate that ``fire_webhook_for_simulation`` honours, and tag the
    log entry with ``trigger:"retry"``."""
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    started = threading.Event()
    counter = {'n': 0}
    last_payload: dict = {}

    def fake_post(url, payload, timeout):
        counter['n'] += 1
        last_payload.clear()
        last_payload.update(payload)
        started.set()
        return True, "HTTP 200"

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service, '_post_json', side_effect=fake_post):
        # First, the auto-fire path: takes the (sim_id, "completed") slot.
        webhook_service.fire_webhook_for_simulation(
            "sim_replay", "completed", sim_dir=str(tmp_path),
        )
        assert _wait_for_log_lines(tmp_path, expected=1) == 1

        # A second auto-fire is deduped — never reaches _post_json.
        webhook_service.fire_webhook_for_simulation(
            "sim_replay", "completed", sim_dir=str(tmp_path),
        )
        # Operator-driven retry must NOT be deduped.
        result = webhook_service.retry_webhook_for_simulation(
            "sim_replay", "completed", sim_dir=str(tmp_path),
        )
        assert result["queued"] is True
        assert result["attempt_will_be"] == 2
        assert _wait_for_log_lines(tmp_path, expected=2) == 2

    entries = _read_log(tmp_path)
    triggers = {e["attempt"]: e["trigger"] for e in entries}
    assert triggers == {1: "auto", 2: "retry"}
    # Retry payload carries the explicit replay marker.
    assert last_payload.get("retry") is True


def test_retry_returns_error_when_no_url_configured(tmp_path: Path):
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    with patch.object(webhook_service, '_resolve_webhook_url', return_value=''):
        result = webhook_service.retry_webhook_for_simulation(
            "sim_no_url", "completed", sim_dir=str(tmp_path),
        )
    assert result["queued"] is False
    assert "no webhook URL" in (result.get("error") or "")
    # No log file should have been created — nothing was dispatched.
    assert not (tmp_path / "webhook-log.jsonl").exists()


def test_retry_rejects_unknown_status(tmp_path: Path):
    from app.services import webhook_service

    webhook_service.reset_dedup_for_tests()

    with patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'):
        result = webhook_service.retry_webhook_for_simulation(
            "sim_running", "running", sim_dir=str(tmp_path),
        )
    assert result["queued"] is False
    assert "unsupported status" in (result.get("error") or "")


def test_concurrent_appends_do_not_drop_entries(tmp_path: Path):
    """Two threads writing concurrently must both land in the log.

    Without the module-level write lock, both threads could read the
    same `existing` lines, both rename their tmp file over the target,
    and one entry would be silently lost — exactly the visibility gap
    this log is supposed to close.
    """
    from app.services import webhook_service

    N = 32
    barrier = threading.Barrier(N)
    errors: list[BaseException] = []

    def write(i: int) -> None:
        try:
            barrier.wait(timeout=2.0)
            webhook_service._append_log_entry(
                str(tmp_path),
                {"attempt": i, "trigger": "test", "status": "completed"},
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert not errors, f"thread errors: {errors!r}"
    log = tmp_path / "webhook-log.jsonl"
    assert log.exists()
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # All N writes must be persisted (or capped at WEBHOOK_LOG_MAX_LINES).
    expected = min(N, webhook_service.WEBHOOK_LOG_MAX_LINES)
    assert len(lines) == expected
    parsed = [json.loads(ln) for ln in lines]
    attempts = {e["attempt"] for e in parsed}
    assert len(attempts) == expected, f"duplicates / drops: {attempts}"


def test_retry_cooldown_rate_limits_per_simulation(tmp_path: Path):
    """`claim_retry_slot` rejects a second call inside the cooldown window
    for the same sim_id, but allows other sims through."""
    from app.services import webhook_service

    webhook_service.reset_retry_cooldown_for_tests()

    # First claim succeeds.
    assert webhook_service.claim_retry_slot("sim_a", now=100.0) is None
    # Same sim, half a second later → blocked, returns remaining seconds.
    remaining = webhook_service.claim_retry_slot("sim_a", now=100.5)
    assert remaining is not None
    assert 0.0 < remaining <= webhook_service.RETRY_COOLDOWN_SEC
    # Different sim is unaffected.
    assert webhook_service.claim_retry_slot("sim_b", now=100.5) is None
    # After cooldown elapses, the original sim is allowed again.
    assert webhook_service.claim_retry_slot(
        "sim_a", now=100.0 + webhook_service.RETRY_COOLDOWN_SEC + 0.01
    ) is None
