"""Unit tests for the outbound webhook HMAC signature.

Covers the integrity layer that closes the "did this payload actually
come from my MiroShark instance?" question every webhook integration
(Slack, Discord, Zapier, Make, n8n, Revault, CancerHawk, custom) has
to answer once more than one tool is consuming the same stream.

Pure offline tests — no Flask app, no real HTTP. The integration tests
patch ``urllib.request.urlopen`` so the dispatch path runs end-to-end
through ``_post_json`` and the actual request headers can be
inspected, then assert on the bytes that would have left the box.

Same conventions as ``test_unit_webhook.py`` and
``test_unit_webhook_log.py`` — add the backend root to ``sys.path``,
reset the per-process dedup before every dispatch, and wait on the
daemon thread with a bounded ``Event``.
"""

from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Helpers ───────────────────────────────────────────────────────────


@contextmanager
def _set_webhook_secret(monkeypatch: pytest.MonkeyPatch, secret: Optional[str]):
    """Set / clear ``WEBHOOK_SECRET`` for the duration of the block."""
    if secret is None:
        monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    else:
        monkeypatch.setenv("WEBHOOK_SECRET", secret)
    yield


def _capture_request_via_urlopen(captured: dict):
    """Return a ``urlopen`` replacement that records the outgoing Request."""

    def fake_urlopen(req, timeout=None):
        captured["request"] = req
        captured["body"] = req.data
        # ``Request.headers`` keys are capitalized; mirror urllib's case.
        captured["headers"] = dict(req.header_items())
        captured["timeout"] = timeout

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(getcode=lambda: 200))
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    return fake_urlopen


def _wait_for_log_lines(sim_dir: Path, expected: int, timeout: float = 3.0) -> int:
    """Poll for the dispatcher to land ``expected`` rows in the log."""
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


# ── compute_signature / verify_signature ─────────────────────────────


def test_signature_format_is_sha256_prefixed_lowercase_hex(monkeypatch):
    """Format guard: ``sha256=`` prefix, 64-char lowercase hex digest."""
    from app.services.webhook_service import (
        compute_signature,
        SIGNATURE_PREFIX,
    )

    sig = compute_signature(b'{"event":"simulation.completed"}', secret="super-secret")
    assert sig is not None
    assert sig.startswith(SIGNATURE_PREFIX)
    digest = sig[len(SIGNATURE_PREFIX):]
    assert len(digest) == 64  # sha256 → 32 bytes → 64 hex chars
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_signature_round_trip(monkeypatch):
    """Sign-then-verify with the same secret succeeds; wrong secret fails."""
    from app.services.webhook_service import compute_signature, verify_signature

    body = b'{"event":"simulation.completed","sim_id":"sim_rt"}'
    secret = "32-char-random-hex-token-please"

    sig = compute_signature(body, secret=secret)
    assert sig is not None
    assert verify_signature(body, sig, secret) is True
    assert verify_signature(body, sig, "wrong-secret") is False


def test_signature_detects_tampered_body():
    """Flipping a single byte invalidates the signature — the whole point."""
    from app.services.webhook_service import compute_signature, verify_signature

    secret = "shared-secret"
    body = b'{"event":"simulation.completed","sim_id":"sim_a"}'
    sig = compute_signature(body, secret=secret)
    assert sig is not None

    tampered = body.replace(b'sim_a', b'sim_b')
    assert tampered != body
    assert verify_signature(tampered, sig, secret) is False


def test_signature_detects_tampered_header():
    """A bit-flipped signature header must be rejected."""
    from app.services.webhook_service import compute_signature, verify_signature

    secret = "shared-secret"
    body = b'{"event":"simulation.completed"}'
    sig = compute_signature(body, secret=secret)
    assert sig is not None

    # Flip one character of the hex digest.
    head, _, tail = sig.partition("=")
    flipped = tail[:-1] + ("0" if tail[-1] != "0" else "1")
    tampered_header = f"{head}={flipped}"
    assert tampered_header != sig
    assert verify_signature(body, tampered_header, secret) is False
    # Empty / missing header is also rejected.
    assert verify_signature(body, "", secret) is False
    assert verify_signature(body, None, secret) is False


def test_empty_secret_treats_payload_as_unsigned(monkeypatch):
    """Backward compat: empty / missing ``WEBHOOK_SECRET`` → no signature."""
    from app.services.webhook_service import compute_signature

    # Explicit empty string and whitespace-only both count as "unset".
    assert compute_signature(b'{"x":1}', secret="") is None
    assert compute_signature(b'{"x":1}', secret="   ".strip()) is None

    with _set_webhook_secret(monkeypatch, None):
        assert compute_signature(b'{"x":1}') is None
    with _set_webhook_secret(monkeypatch, ""):
        assert compute_signature(b'{"x":1}') is None
    with _set_webhook_secret(monkeypatch, "   "):
        # Surrounding whitespace is stripped by _resolve_webhook_secret.
        assert compute_signature(b'{"x":1}') is None


# ── Integration: signature lands on the actual outgoing request ──────


def test_signature_header_present_when_secret_set(tmp_path, monkeypatch):
    """End-to-end: dispatch a webhook with ``WEBHOOK_SECRET`` set, then
    verify the captured Request carries a valid ``X-MiroShark-Signature``
    that matches the body."""
    from app.services import webhook_service
    from app.services.webhook_service import (
        SIGNATURE_HEADER,
        SIGNATURE_PREFIX,
        verify_signature,
    )

    webhook_service.reset_dedup_for_tests()

    captured: dict = {}
    secret = "deadbeefcafefacefeedfacecafef00d"

    with _set_webhook_secret(monkeypatch, secret), \
         patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://hooks.slack.com/services/T/B/abc'), \
         patch.object(webhook_service.urllib.request, 'urlopen',
                      side_effect=_capture_request_via_urlopen(captured)):
        webhook_service.fire_webhook_for_simulation(
            "sim_signed",
            "completed",
            sim_dir=str(tmp_path),
        )
        # Wait for the daemon thread to finish writing the log row.
        assert _wait_for_log_lines(tmp_path, expected=1) == 1

    # ``Request.header_items`` returns capitalized header names.
    assert "x-miroshark-signature" in {k.lower() for k in captured["headers"]}
    sig = None
    for k, v in captured["headers"].items():
        if k.lower() == SIGNATURE_HEADER.lower():
            sig = v
            break
    assert sig is not None
    assert sig.startswith(SIGNATURE_PREFIX)
    # The signature must verify against the actual body that was sent.
    assert verify_signature(captured["body"], sig, secret) is True


def test_no_signature_header_when_secret_unset(tmp_path, monkeypatch):
    """Backward compat: no ``WEBHOOK_SECRET`` → no header on the wire."""
    from app.services import webhook_service
    from app.services.webhook_service import SIGNATURE_HEADER

    webhook_service.reset_dedup_for_tests()

    captured: dict = {}

    with _set_webhook_secret(monkeypatch, None), \
         patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service.urllib.request, 'urlopen',
                      side_effect=_capture_request_via_urlopen(captured)):
        webhook_service.fire_webhook_for_simulation(
            "sim_unsigned",
            "completed",
            sim_dir=str(tmp_path),
        )
        assert _wait_for_log_lines(tmp_path, expected=1) == 1

    lower_keys = {k.lower() for k in captured["headers"]}
    assert SIGNATURE_HEADER.lower() not in lower_keys
    # The other identification headers are still there — only the
    # signature is conditional.
    assert "x-miroshark-event" in lower_keys
    assert "x-miroshark-sim-id" in lower_keys


def test_retry_dispatch_carries_signature(tmp_path, monkeypatch):
    """An operator-driven retry must sign its payload the same way an
    auto-fire does — the recipient runs one verification path, not two."""
    from app.services import webhook_service
    from app.services.webhook_service import (
        SIGNATURE_HEADER,
        SIGNATURE_PREFIX,
        verify_signature,
    )

    webhook_service.reset_dedup_for_tests()

    secret = "another-32+-char-random-secret-token"
    captured_auto: dict = {}
    captured_retry: dict = {}
    call_count = {"n": 0}

    def fake_urlopen(req, timeout=None):
        call_count["n"] += 1
        target = captured_auto if call_count["n"] == 1 else captured_retry
        target["request"] = req
        target["body"] = req.data
        target["headers"] = dict(req.header_items())
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(getcode=lambda: 200))
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    with _set_webhook_secret(monkeypatch, secret), \
         patch.object(webhook_service, '_resolve_webhook_url',
                      return_value='https://example.com/hook'), \
         patch.object(webhook_service.urllib.request, 'urlopen',
                      side_effect=fake_urlopen):
        webhook_service.fire_webhook_for_simulation(
            "sim_retry_signed",
            "completed",
            sim_dir=str(tmp_path),
        )
        assert _wait_for_log_lines(tmp_path, expected=1) == 1

        result = webhook_service.retry_webhook_for_simulation(
            "sim_retry_signed",
            "completed",
            sim_dir=str(tmp_path),
        )
        assert result["queued"] is True
        assert _wait_for_log_lines(tmp_path, expected=2) == 2

    def _signature(headers: dict) -> str:
        for k, v in headers.items():
            if k.lower() == SIGNATURE_HEADER.lower():
                return v
        return ""

    auto_sig = _signature(captured_auto["headers"])
    retry_sig = _signature(captured_retry["headers"])

    assert auto_sig.startswith(SIGNATURE_PREFIX)
    assert retry_sig.startswith(SIGNATURE_PREFIX)
    # Each signature must verify against its OWN body — the retry payload
    # adds ``retry: true``, so the two bodies (and therefore the two
    # signatures) differ. Both must be individually valid.
    assert verify_signature(captured_auto["body"], auto_sig, secret) is True
    assert verify_signature(captured_retry["body"], retry_sig, secret) is True
    # And the retry payload carries the explicit replay marker that the
    # docs promise downstream consumers can use to dedupe.
    retry_payload = json.loads(captured_retry["body"].decode("utf-8"))
    assert retry_payload.get("retry") is True
