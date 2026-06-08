"""HMAC-signed trading-signal payload — offline-verifiable provenance for
a finished, published simulation.

The signal returned by ``GET /api/simulation/<id>/signal.json`` is the
canonical machine-readable view of the final-round belief split + quality
tier. HTTPS covers in-transit authenticity — but once a caller stores the
payload (Capacitr's settlement ledger, a research archive, an ML pipeline's
provenance table) there is no way to prove the stored bytes match what
MiroShark actually emitted without making a live API call back to the
deployment.

``build_signed_result`` returns the same signal fields wrapped in a
canonical envelope plus an HMAC-SHA256 signature over the deterministic
JSON encoding of the inner ``result`` block. The signing key is the same
``WEBHOOK_SECRET`` the outbound delivery service reads — zero new config,
zero new secrets, identical algorithm + prefix as the
``X-MiroShark-Signature`` webhook header.

Two consequences of that choice:

* **Anyone who can already verify a webhook can verify a stored signal.**
  The recipient-side ``hmac.compare_digest`` / ``crypto.timingSafeEqual``
  logic an integrator wrote for the webhook handler is the same logic
  they re-use here.
* **Deterministic canonical JSON.** ``json.dumps(result, sort_keys=True,
  separators=(",", ":"))`` produces a byte string a recipient can
  reconstruct exactly from the parsed ``result`` dict — no whitespace
  drift, no key reordering, no trailing newline ambiguity. The signature
  is computed over that canonical encoding, not over the response body
  the route handler emits (which carries the envelope's ``signed_at``,
  ``algorithm``, ``signing_key_hint`` + the signature itself).

Design notes
------------

* **Pure stdlib.** ``hmac`` + ``hashlib`` + ``json``. Zero new
  dependencies — same posture as ``signal_service`` /
  ``surfaces_catalog`` / every pure-data module in this tree.
* **Never raises on the missing-secret path.** If ``WEBHOOK_SECRET`` is
  empty or unset, the function returns the inner ``result`` block plus
  ``signed=false`` + a human-readable error string. Callers translate
  this into a 200 with an explicit ``signed=false`` flag, not a 500 —
  the un-signed payload is still useful (it carries the same fields as
  ``signal.json``); the absence of a signature is the missing feature,
  not an API failure.
* **Same publish gate as signal.json.** The route handler short-circuits
  to 403 for private sims and 404 for not-yet-ready sims *before* this
  service is called. This module does not enforce the gate — it derives
  the signature over whatever signal it's given.
* **Algorithm identifier locked.** The ``algorithm`` envelope field is
  the literal string ``"hmac-sha256"`` — a future migration to a different
  primitive (HS256 → Ed25519, say) would bump the field and add a
  ``schema_version`` boundary; today, v1 is the only published version.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


SCHEMA_VERSION = "1"
ALGORITHM = "hmac-sha256"

# Webhook delivery prefixes the digest with ``sha256=`` in the
# ``X-MiroShark-Signature`` header. For the signed-result body we publish
# the bare hex digest — the envelope's ``algorithm`` field already says
# ``hmac-sha256``, so prefixing the hex with ``sha256=`` would be
# redundant + would diverge from the canonical hex convention every
# JSON-Web-Signature-ish primitive uses. Recipients verify by recomputing
# the hex digest and ``hmac.compare_digest``-ing against this field.
_KEY_HINT_LENGTH = 8


def _iso_utc_now() -> str:
    """ISO-8601 UTC ``"YYYY-MM-DDTHH:MM:SSZ"`` for the envelope timestamp.

    Same shape every other export surface uses (signal_service,
    webhook_service log, reproduce.json's ``exported_at``).
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json(payload: Dict[str, Any]) -> bytes:
    """Return the canonical JSON encoding of ``payload`` as UTF-8 bytes.

    Locked encoding:

      - ``sort_keys=True`` so two identical dicts produce identical bytes
        regardless of insertion order
      - ``separators=(",", ":")`` so whitespace can never drift
      - ``ensure_ascii=True`` (the JSON-module default) so the output
        carries only ASCII bytes — a non-ASCII string in the input is
        emitted as ``\\uXXXX``, the form every JSON parser reproduces
        byte-for-byte from a string round-trip
      - no trailing newline

    A recipient reconstructs the bytes by passing the parsed ``result``
    dict back through this exact function (or equivalent) before
    verifying the HMAC.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _key_hint(secret: str) -> Optional[str]:
    """Return the first ``_KEY_HINT_LENGTH`` characters of the secret
    followed by ``"..."`` so a caller can confirm both ends are using the
    same key without exposing the rest. Returns ``None`` when the
    secret is empty (caller has already signalled ``signed=false``)."""
    if not secret:
        return None
    if len(secret) <= _KEY_HINT_LENGTH:
        # Pathologically short secret — show the whole thing rather than
        # an empty prefix; the operator who configured a one-char
        # ``WEBHOOK_SECRET`` has a bigger problem than the hint leaking.
        return secret + "..."
    return secret[:_KEY_HINT_LENGTH] + "..."


def compute_signature(canonical: bytes, secret: str) -> str:
    """Return the HMAC-SHA256 hex digest of ``canonical`` under ``secret``.

    Symmetric with ``webhook_service.compute_signature`` (which prefixes
    ``sha256=``); here we publish the bare hex digest because the
    envelope's ``algorithm`` field is the authoritative algorithm
    identifier. Recipients use ``hmac.compare_digest`` to guard against
    timing-based key extraction.
    """
    return hmac.new(
        secret.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()


def build_signed_result(
    signal: Dict[str, Any],
    simulation_id: str,
    secret: Optional[str],
) -> Dict[str, Any]:
    """Build the full signed-result envelope.

    Parameters
    ----------
    signal:
        The dict returned by ``signal_service.compute_signal`` — every
        field present in the ``signal.json`` payload (``schema_version``,
        ``direction``, ``confidence_pct``, ``risk_tier``, the three
        percentages, ``quality_health``, ``signal_generated_at``).
    simulation_id:
        Echoed simulation id; lands on the envelope's top level so a
        consumer doesn't have to look inside ``result`` to identify which
        sim this signature covers.
    secret:
        The HMAC secret. ``None``, empty string, or whitespace-only →
        ``signed=false`` envelope (still 200, ``signature=null``,
        ``signing_key_hint=null``, plus a human-readable ``error``).

    Returns
    -------
    A dict ready for ``jsonify`` / canonical JSON serialisation. Two
    consecutive calls with the same ``signal``, ``simulation_id``, and
    ``secret`` produce signatures that match each other byte-for-byte —
    determinism over the ``result`` block, not over the envelope
    (``signed_at`` is wall-clock).
    """
    # The signal already carries ``simulation_id`` (the route handler
    # injects it before calling us), but the envelope re-emits it at top
    # level so a consumer doesn't have to crack open the inner block.
    result_block = dict(signal)
    # Belt-and-braces: drop any envelope-level fields that might have
    # accidentally been written into ``signal`` (the signal_service
    # currently emits none, but a future contributor adding one shouldn't
    # be able to silently shadow the envelope).
    result_block["simulation_id"] = simulation_id

    canonical = canonical_json(result_block)

    secret_clean = (secret or "").strip()
    if not secret_clean:
        return {
            "schema_version": SCHEMA_VERSION,
            "simulation_id": simulation_id,
            "signed": False,
            "signed_at": _iso_utc_now(),
            "algorithm": ALGORITHM,
            "result": result_block,
            "signature": None,
            "signing_key_hint": None,
            "error": (
                "signing_unavailable: WEBHOOK_SECRET is not configured. "
                "Set WEBHOOK_SECRET on the deployment to receive a signed "
                "payload; the unsigned result fields above are still valid."
            ),
        }

    signature = compute_signature(canonical, secret_clean)
    return {
        "schema_version": SCHEMA_VERSION,
        "simulation_id": simulation_id,
        "signed": True,
        "signed_at": _iso_utc_now(),
        "algorithm": ALGORITHM,
        "result": result_block,
        "signature": signature,
        "signing_key_hint": _key_hint(secret_clean),
    }
