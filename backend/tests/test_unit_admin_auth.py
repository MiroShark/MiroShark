"""Unit tests for the admin-auth gate on mutation endpoints.

Issue #48 added a shared operator secret (``MIROSHARK_ADMIN_TOKEN``)
guarding ``POST /publish``, ``POST /resolve``, and ``POST /outcome``.
This file pins down the contract — if any of these properties drift,
the deploy goes from "auth-gated mutations" back to "any caller can
overwrite a verified prediction", which is the regression the issue
called out.

Tested directly against the helpers + decorator in
``app.api.simulation`` (no full Flask app boot, no Neo4j) by mounting
the decorator on a throwaway view inside a minimal Flask app. This
keeps the suite in the bare unit environment alongside the other
``test_unit_*.py`` files.

Coverage:

  1. ``_extract_bearer_token`` parses ``Authorization: Bearer <t>``
     and returns "" for missing / wrong-scheme / malformed headers.
  2. ``_load_admin_token`` reads from the env at call time and
     normalises whitespace.
  3. ``require_admin_token`` returns 503 when the env var is unset
     **even if the caller sent a token** — fail-closed is the whole
     point of issue #48 and a silent fallback would re-open the hole.
  4. ``require_admin_token`` returns 401 (generic message) for both
     "no header" and "wrong token" so a probe can't tell them apart.
  5. ``require_admin_token`` lets a matching bearer token through to
     the wrapped view.
  6. The error envelope on every failure path matches the
     ``{"success": false, "error": "..."}`` shape used elsewhere in
     the codebase — front-end clients branch on it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ──────────────────────────────────────────────────────────────────────────
# Header parsing
# ──────────────────────────────────────────────────────────────────────────


def _make_app():
    """Tiny Flask app with one view gated by ``require_admin_token``.

    We can't import the full ``create_app`` factory here because it
    boots Neo4j and the simulation runner — both unavailable in the
    unit environment. Mounting the decorator on a stub view exercises
    the same code path with zero infra.
    """
    from flask import Flask, jsonify

    from app.api.simulation import require_admin_token

    app = Flask(__name__)

    @app.route("/_test/protected", methods=["POST"])
    @require_admin_token
    def _protected():
        return jsonify({"success": True, "data": {"ok": True}}), 200

    return app


def test_extract_bearer_token_parses_valid_header():
    from flask import Flask
    from app.api.simulation import _extract_bearer_token

    app = Flask(__name__)
    with app.test_request_context(headers={"Authorization": "Bearer abc123"}):
        assert _extract_bearer_token() == "abc123"


@pytest.mark.parametrize(
    "header",
    [
        "",                      # absent
        "Basic abc123",          # wrong scheme
        "Bearer",                # no token portion
        "Bearer ",               # blank token
        "Token abc123",          # close but wrong scheme
    ],
)
def test_extract_bearer_token_rejects_bad_headers(header: str):
    from flask import Flask
    from app.api.simulation import _extract_bearer_token

    app = Flask(__name__)
    headers = {"Authorization": header} if header else {}
    with app.test_request_context(headers=headers):
        assert _extract_bearer_token() == ""


# ──────────────────────────────────────────────────────────────────────────
# Env var loading
# ──────────────────────────────────────────────────────────────────────────


def test_load_admin_token_reads_env(monkeypatch: pytest.MonkeyPatch):
    from app.api.simulation import _load_admin_token

    monkeypatch.setenv("MIROSHARK_ADMIN_TOKEN", "  s3cret  ")
    # Whitespace stripped — operators sometimes paste with stray spaces
    # and we don't want a constant-time compare to fail on that.
    assert _load_admin_token() == "s3cret"


def test_load_admin_token_unset_returns_empty(monkeypatch: pytest.MonkeyPatch):
    from app.api.simulation import _load_admin_token

    monkeypatch.delenv("MIROSHARK_ADMIN_TOKEN", raising=False)
    assert _load_admin_token() == ""


def test_load_admin_token_blank_returns_empty(monkeypatch: pytest.MonkeyPatch):
    """An explicit empty string in env counts as unset — same fail-closed
    posture as a missing var."""
    from app.api.simulation import _load_admin_token

    monkeypatch.setenv("MIROSHARK_ADMIN_TOKEN", "   ")
    assert _load_admin_token() == ""


# ──────────────────────────────────────────────────────────────────────────
# Decorator behaviour — the meat of the issue
# ──────────────────────────────────────────────────────────────────────────


def test_decorator_fails_closed_when_env_unset(monkeypatch: pytest.MonkeyPatch):
    """Issue #48's central invariant: with no ``MIROSHARK_ADMIN_TOKEN``
    in the environment the endpoint must return 503, **not** allow the
    request through. Even a caller presenting a token must be denied
    — the deploy is misconfigured and we refuse to play guess-the-secret.
    """
    monkeypatch.delenv("MIROSHARK_ADMIN_TOKEN", raising=False)

    app = _make_app()
    client = app.test_client()
    res = client.post(
        "/_test/protected",
        headers={"Authorization": "Bearer anything"},
    )
    assert res.status_code == 503
    body = res.get_json()
    assert body["success"] is False
    assert "not configured" in body["error"].lower()


def test_decorator_fails_closed_with_no_header(monkeypatch: pytest.MonkeyPatch):
    """Same invariant when the caller didn't send a header either —
    503 takes precedence over 401 because the deploy itself is broken."""
    monkeypatch.delenv("MIROSHARK_ADMIN_TOKEN", raising=False)

    app = _make_app()
    res = app.test_client().post("/_test/protected")
    assert res.status_code == 503


def test_decorator_returns_401_for_missing_header(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MIROSHARK_ADMIN_TOKEN", "right-token")

    app = _make_app()
    res = app.test_client().post("/_test/protected")
    assert res.status_code == 401
    body = res.get_json()
    assert body["success"] is False
    # Generic message — we deliberately do not say "missing".
    assert body["error"] == "Unauthorized"


def test_decorator_returns_401_for_wrong_token(monkeypatch: pytest.MonkeyPatch):
    """Same response shape as missing-header so a probe can't
    distinguish 'no token sent' from 'wrong token'."""
    monkeypatch.setenv("MIROSHARK_ADMIN_TOKEN", "right-token")

    app = _make_app()
    res = app.test_client().post(
        "/_test/protected",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert res.status_code == 401
    body = res.get_json()
    assert body["error"] == "Unauthorized"


def test_decorator_passes_through_with_matching_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MIROSHARK_ADMIN_TOKEN", "right-token")

    app = _make_app()
    res = app.test_client().post(
        "/_test/protected",
        headers={"Authorization": "Bearer right-token"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["ok"] is True


def test_decorator_uses_constant_time_compare(monkeypatch: pytest.MonkeyPatch):
    """Smoke test that the comparison goes through ``hmac.compare_digest``.

    We don't try to measure timing — that's flaky in CI — but we do
    confirm the function is *the* one being called by patching it and
    asserting it ran. If a future refactor swaps in ``==`` we want to
    know loudly.
    """
    import app.api.simulation as sim_mod

    monkeypatch.setenv("MIROSHARK_ADMIN_TOKEN", "tok")

    calls: list[tuple[bytes, bytes]] = []
    real = sim_mod.hmac.compare_digest

    def _spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(sim_mod.hmac, "compare_digest", _spy)

    app = _make_app()
    res = app.test_client().post(
        "/_test/protected",
        headers={"Authorization": "Bearer tok"},
    )
    assert res.status_code == 200
    assert calls, "compare_digest must be on the auth path"
    assert calls[0] == (b"tok", b"tok")


# ──────────────────────────────────────────────────────────────────────────
# Wiring check: every gated endpoint actually carries the gate
# ──────────────────────────────────────────────────────────────────────────


def test_publish_and_resolve_views_have_gate_applied():
    """Static check: the ``publish`` and ``resolve`` views are wrapped
    by ``require_admin_token``. The decorator stores the original
    function on ``__wrapped__`` (via ``functools.wraps``) so we can
    detect it without firing a request.
    """
    from app.api.simulation import publish_simulation, resolve_simulation

    for view in (publish_simulation, resolve_simulation):
        assert hasattr(view, "__wrapped__"), (
            f"{view.__name__} is not wrapped — admin auth gate missing"
        )


def test_outcome_post_is_gated_get_is_not(monkeypatch: pytest.MonkeyPatch):
    """``POST /outcome`` shares its view with ``GET /outcome`` so we
    can't use the decorator on the whole function. The view inlines
    the check on the POST branch only — verify that contract directly.
    """
    import inspect

    from app.api.simulation import simulation_outcome

    src = inspect.getsource(simulation_outcome)
    # POST gate: env load + bearer extraction + constant-time compare.
    assert "_load_admin_token()" in src
    assert "_extract_bearer_token()" in src
    assert "hmac.compare_digest" in src
    # And it has to be guarded by the method check or every GET would
    # fail with 503 too — which would break the gallery and embed.
    assert "request.method == 'POST'" in src or 'request.method == "POST"' in src
