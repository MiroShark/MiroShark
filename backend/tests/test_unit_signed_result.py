"""Unit tests for the HMAC-signed-result service.

Pure offline — no Flask, no network, no on-disk state. Covers the
properties the ``/<id>/signed-result.json`` endpoint depends on:

  1. ``build_signed_result`` produces the documented envelope shape.
  2. ``signed=true`` path: the signature verifies under the same secret
     using ``hmac.compare_digest`` (the exact recipient-side primitive).
  3. ``signed=false`` path: empty / missing / whitespace secret returns
     an envelope with ``signed=false`` + ``signature=null`` + a human-
     readable ``error`` — never raises, never 500s.
  4. Canonical JSON encoding is deterministic and ``sort_keys``-stable —
     two consecutive calls produce identical signature bytes for the
     same input.
  5. The signature changes when the result body changes (a tampered
     ``confidence_pct`` produces a different digest).
  6. The ``result`` block field set matches ``signal.json`` exactly (no
     leaked envelope fields, no missing signal fields).
  7. ``signing_key_hint`` is the first 8 chars + ``"..."``.
  8. The route handler decorator + handler function exist in
     ``app/api/simulation.py``.
  9. ``signed_result`` is registered in ``surface_stats.SURFACE_KEYS``.
 10. The OpenAPI spec declares the path with the expected response shape
     (drift guard).
 11. ``signed_result`` is in ``surfaces_catalog`` and tracked in the
     per-sim subset.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── Fixtures ──────────────────────────────────────────────────────────────


_TEST_SECRET = "miroshark-test-secret-very-long-do-not-use-in-prod"
_TEST_SIM_ID = "sim-test-abc12345"


def _signal(
    *,
    direction: str = "Bullish",
    confidence_pct: float = 56.7,
    risk_tier: str = "low-risk",
    bullish_pct: float = 62.0,
    neutral_pct: float = 18.0,
    bearish_pct: float = 20.0,
    quality_health: str = "excellent",
) -> dict:
    """A signal-shaped dict — matches the keys ``signal_service`` emits."""
    return {
        "schema_version": "1",
        "direction": direction,
        "confidence_pct": confidence_pct,
        "risk_tier": risk_tier,
        "bullish_pct": bullish_pct,
        "neutral_pct": neutral_pct,
        "bearish_pct": bearish_pct,
        "quality_health": quality_health,
        "signal_generated_at": "2026-06-08T12:00:00Z",
    }


# ── Property 1 — documented envelope shape ────────────────────────────────


def test_signed_envelope_has_documented_keys_when_signed():
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    expected = {
        "schema_version",
        "simulation_id",
        "signed",
        "signed_at",
        "algorithm",
        "result",
        "signature",
        "signing_key_hint",
    }
    assert set(envelope.keys()) == expected
    assert envelope["schema_version"] == "1"
    assert envelope["algorithm"] == "hmac-sha256"
    assert envelope["signed"] is True
    assert envelope["simulation_id"] == _TEST_SIM_ID


def test_envelope_is_json_serializable():
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    blob = json.dumps(envelope, sort_keys=True)
    parsed = json.loads(blob)
    assert parsed["signature"] == envelope["signature"]
    assert parsed["result"]["direction"] == envelope["result"]["direction"]


# ── Property 2 — signature verifies with hmac.compare_digest ─────────────


def test_signature_verifies_under_same_secret():
    """The exact symmetry every recipient relies on:
    ``hmac.compare_digest(recomputed_hex, envelope.signature)`` is True."""
    from app.services.signed_result import build_signed_result, canonical_json

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    recomputed = hmac.new(
        _TEST_SECRET.encode("utf-8"),
        canonical_json(envelope["result"]),
        hashlib.sha256,
    ).hexdigest()
    assert hmac.compare_digest(recomputed, envelope["signature"])


def test_signature_fails_under_wrong_secret():
    from app.services.signed_result import build_signed_result, canonical_json

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    wrong_secret = "different-secret-not-the-one-that-signed-this-payload"
    recomputed = hmac.new(
        wrong_secret.encode("utf-8"),
        canonical_json(envelope["result"]),
        hashlib.sha256,
    ).hexdigest()
    assert not hmac.compare_digest(recomputed, envelope["signature"])


# ── Property 3 — unsigned path never raises, returns signed=false ────────


def test_unsigned_envelope_when_secret_is_none():
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=None,
    )
    assert envelope["signed"] is False
    assert envelope["signature"] is None
    assert envelope["signing_key_hint"] is None
    assert envelope["algorithm"] == "hmac-sha256"
    assert "signing_unavailable" in envelope["error"]
    # The unsigned result block is still complete — the unsigned payload
    # carries the same fields as signal.json, just without a signature.
    assert envelope["result"]["direction"] == "Bullish"
    assert envelope["result"]["confidence_pct"] == 56.7


def test_unsigned_envelope_when_secret_is_empty_string():
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret="",
    )
    assert envelope["signed"] is False
    assert envelope["signature"] is None
    assert envelope["error"].startswith("signing_unavailable")


def test_unsigned_envelope_when_secret_is_whitespace_only():
    """A WEBHOOK_SECRET configured as ``"   "`` is a deployment error,
    not a valid signing key — treat it the same as missing."""
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret="   \t\n  ",
    )
    assert envelope["signed"] is False
    assert envelope["signature"] is None


# ── Property 4 — canonical JSON is deterministic ──────────────────────────


def test_canonical_json_sorts_keys():
    from app.services.signed_result import canonical_json

    a = canonical_json({"b": 2, "a": 1, "c": 3})
    b = canonical_json({"c": 3, "a": 1, "b": 2})
    assert a == b
    # Whitespace-stripped + sorted keys.
    assert a == b'{"a":1,"b":2,"c":3}'


def test_canonical_json_emits_ascii_unicode_escapes():
    """Non-ASCII strings round-trip as ``\\uXXXX`` so two implementations
    on different stdlibs reproduce identical bytes."""
    from app.services.signed_result import canonical_json

    encoded = canonical_json({"label": "café"})
    # ``é`` is the JSON escape for ``é``.
    assert encoded == b'{"label":"caf\\u00e9"}'


def test_two_calls_produce_identical_signature():
    """Determinism on the inner ``result`` block — same signal in,
    same signature out (envelope ``signed_at`` is wall-clock and will
    differ, but the signature is what recipients verify)."""
    from app.services.signed_result import build_signed_result

    a = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    b = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    assert a["signature"] == b["signature"]


# ── Property 5 — tampering the result changes the signature ──────────────


def test_signature_changes_when_confidence_changes():
    from app.services.signed_result import build_signed_result

    honest = build_signed_result(
        signal=_signal(confidence_pct=56.7),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    tampered = build_signed_result(
        signal=_signal(confidence_pct=72.3),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    assert honest["signature"] != tampered["signature"]


def test_signature_changes_when_direction_changes():
    from app.services.signed_result import build_signed_result

    bullish = build_signed_result(
        signal=_signal(direction="Bullish"),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    bearish = build_signed_result(
        signal=_signal(direction="Bearish"),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    assert bullish["signature"] != bearish["signature"]


def test_signature_changes_when_sim_id_changes():
    """The ``simulation_id`` is part of the inner result block — a
    forwarded signature for ``sim_A`` must not validate for ``sim_B``."""
    from app.services.signed_result import build_signed_result

    a = build_signed_result(
        signal=_signal(),
        simulation_id="sim-AAAA",
        secret=_TEST_SECRET,
    )
    b = build_signed_result(
        signal=_signal(),
        simulation_id="sim-BBBB",
        secret=_TEST_SECRET,
    )
    assert a["signature"] != b["signature"]


# ── Property 6 — result block mirrors signal.json field set ──────────────


def test_result_block_field_set_matches_signal_json():
    """The fields under ``envelope["result"]`` must match every key
    ``signal.json`` returns, plus ``simulation_id`` which the route
    handler injects. No leaked envelope fields ('signature', 'signed_at',
    etc.) should appear inside the inner result block."""
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    result_keys = set(envelope["result"].keys())
    expected = {
        "schema_version",
        "simulation_id",
        "direction",
        "confidence_pct",
        "risk_tier",
        "bullish_pct",
        "neutral_pct",
        "bearish_pct",
        "quality_health",
        "signal_generated_at",
    }
    assert result_keys == expected
    # None of the envelope-level fields leak into the inner block.
    leakage = {"signature", "signed", "signed_at", "algorithm", "signing_key_hint", "error"}
    assert not (result_keys & leakage)


# ── Property 7 — signing_key_hint is the documented prefix shape ─────────


def test_signing_key_hint_is_first_eight_chars_plus_ellipsis():
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    hint = envelope["signing_key_hint"]
    assert hint == _TEST_SECRET[:8] + "..."


def test_signing_key_hint_handles_short_secret():
    """A pathologically short secret returns the whole thing + ``...``
    rather than an empty prefix that wouldn't help diagnose a mismatch."""
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret="abc",
    )
    assert envelope["signing_key_hint"] == "abc..."


# ── Property 8 — route + handler exist in simulation.py ──────────────────


def test_signed_result_route_decorator_exists():
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    assert "/<simulation_id>/signed-result.json" in text
    assert "def get_signed_result_json" in text


def test_signed_result_handler_increments_surface_stat():
    """The serve handler must increment the signed_result surface counter
    so the inbound analytics layer sees the request."""
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    assert '"signed_result"' in text


def test_signed_result_handler_has_auth_posture_comment():
    """Step 7 of skills/feature/SKILL.md requires an explicit auth-posture
    comment near the route handler so reviewers see the decision was
    deliberate. We require the literal ``Auth posture:`` phrase."""
    api_file = _BACKEND / "app" / "api" / "simulation.py"
    text = api_file.read_text(encoding="utf-8")
    # The phrase appears in the handler's docstring.
    assert "Auth posture: private" in text


# ── Property 9 — surface_stats registers the key ─────────────────────────


def test_signed_result_is_registered_in_surface_stats():
    from app.services.surface_stats import SURFACE_KEYS, read_surface_stats

    assert "signed_result" in SURFACE_KEYS
    stats = read_surface_stats(None)
    assert stats["signed_result"] == 0
    assert "total" in stats


# ── Property 10 — openapi drift guard ────────────────────────────────────


def test_openapi_declares_signed_result_path():
    """Strict drift guard — the path entry, schema reference, and shape
    must all be present so a route addition can't silently desync the
    spec."""
    import yaml  # type: ignore[import-untyped]

    spec_path = _BACKEND / "openapi.yaml"
    with spec_path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    assert (
        "/api/simulation/{simulation_id}/signed-result.json" in spec["paths"]
    ), "signed-result.json path missing from openapi.yaml"
    schemas = spec.get("components", {}).get("schemas", {})
    assert "SignedSimulationResult" in schemas, (
        "SignedSimulationResult schema missing from openapi.yaml"
    )
    schema = schemas["SignedSimulationResult"]
    required = set(schema.get("required") or [])
    # Every envelope field is required — the only nullable fields are
    # ``signature`` and ``signing_key_hint`` which are still listed.
    for field in (
        "schema_version",
        "simulation_id",
        "signed",
        "signed_at",
        "algorithm",
        "result",
        "signature",
    ):
        assert field in required, (
            f"SignedSimulationResult.required is missing {field!r}"
        )


# ── Property 11 — surfaces_catalog entry + tracked-keys subset ───────────


def test_signed_result_in_surfaces_catalog():
    from app.services.surfaces_catalog import (
        get_surfaces_catalog,
        _PER_SIM_TRACKED_KEYS,
    )

    keys = {entry["key"] for entry in get_surfaces_catalog()}
    assert "signed_result" in keys
    assert "signed_result" in _PER_SIM_TRACKED_KEYS


def test_signed_result_catalog_entry_has_documented_fields():
    from app.services.surfaces_catalog import get_surfaces_catalog

    entry = next(
        e for e in get_surfaces_catalog() if e["key"] == "signed_result"
    )
    assert entry["endpoint"] == "/api/simulation/<simulation_id>/signed-result.json"
    assert entry["method"] == "GET"
    assert entry["type"] == "integration"
    # Descriptions are capped at 120 chars per the surface_catalog
    # docstring contract.
    assert len(entry["description"]) <= 120


# ── Signature is lower-case hex of the documented length ─────────────────


def test_signature_is_64_char_lower_hex():
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    sig = envelope["signature"]
    # SHA-256 hex digest is 64 lower-case hex chars — verifiable by
    # both ``hmac.compare_digest`` and ``crypto.timingSafeEqual``.
    assert re.fullmatch(r"[0-9a-f]{64}", sig), (
        f"signature must be 64 lower-case hex chars; got {sig!r}"
    )


# ── ``signed_at`` is ISO-8601 UTC with trailing Z ────────────────────────


def test_signed_at_is_iso_utc_z():
    from app.services.signed_result import build_signed_result

    envelope = build_signed_result(
        signal=_signal(),
        simulation_id=_TEST_SIM_ID,
        secret=_TEST_SECRET,
    )
    ts = envelope["signed_at"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts), (
        f"signed_at must be ISO-8601 UTC with trailing Z; got {ts!r}"
    )
