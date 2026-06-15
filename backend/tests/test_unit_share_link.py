"""Unit tests for the private share-link service.

Pure offline tests — no Flask app, no Neo4j, no network. Drive the
service module directly against a ``tmp_path`` sim-root so the
filesystem layout is explicit and the time arithmetic is testable.

Coverage targets:

  1. ``generate_token`` writes a record under
     ``<sim_dir>/share-tokens/<token>.json`` whose token is a 32+ char
     URL-safe string.
  2. ``resolve_token`` returns the right ``sim_id`` for a valid token,
     ``None`` for unknown / revoked / expired / malformed tokens, and
     ``None`` for path-traversal-shaped strings.
  3. ``revoke_token`` flips ``revoked=true`` and is idempotent.
  4. ``list_tokens`` excludes revoked + expired entries and sorts
     newest-first by ``created_at_epoch``.
  5. Expiry arithmetic — ``_expires_at_for(days)`` is ``now + days * 86400``
     to the second.
  6. ``_clamp_expires_in_days`` clamps below MIN / above MAX and falls
     through to the default for ``None`` / non-numeric input.
  7. Two tokens minted for the same sim both resolve.
  8. Resolving a token after the sim dir is removed yields ``None``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict



_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _make_sim_dir(sim_root: Path, sim_id: str) -> Path:
    """Create a sim subdir with a minimal ``state.json`` so the layout
    matches what the route handler would have produced."""
    sim_dir = sim_root / sim_id
    sim_dir.mkdir(parents=True, exist_ok=True)
    # Empty state.json — the service module doesn't read it, but the
    # presence of a non-empty subdirectory matches how a real deployment
    # looks on disk and exercises the ``isdir`` branch in resolve.
    (sim_dir / "state.json").write_text("{}", encoding="utf-8")
    return sim_dir


# ── generate_token ─────────────────────────────────────────────────────────


def test_generate_token_writes_record_file(tmp_path):
    from app.services import share_link_service

    sim_id = "sim_alpha"
    sim_dir = _make_sim_dir(tmp_path, sim_id)

    record = share_link_service.generate_token(sim_id=sim_id, sim_dir=str(sim_dir))

    token = record["token"]
    assert isinstance(token, str)
    # ``secrets.token_urlsafe(24)`` returns 32 chars; the URL-safe
    # alphabet is [A-Za-z0-9_-].
    assert len(token) >= 30
    assert all(c.isalnum() or c in "_-" for c in token)

    token_file = sim_dir / "share-tokens" / f"{token}.json"
    assert token_file.exists()


def test_generate_token_defaults_to_30_days(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_beta")
    record = share_link_service.generate_token(
        sim_id="sim_beta", sim_dir=str(sim_dir)
    )

    assert record["expires_in_days"] == 30


def test_generate_token_clamps_above_max(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_gamma")
    record = share_link_service.generate_token(
        sim_id="sim_gamma",
        sim_dir=str(sim_dir),
        expires_in_days=10_000,
    )

    assert record["expires_in_days"] == share_link_service.MAX_EXPIRES_IN_DAYS


def test_generate_token_clamps_below_min(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_delta")
    record = share_link_service.generate_token(
        sim_id="sim_delta",
        sim_dir=str(sim_dir),
        expires_in_days=0,
    )

    assert record["expires_in_days"] == share_link_service.MIN_EXPIRES_IN_DAYS


def test_generate_token_envelope_has_iso_timestamps(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_epsilon")
    record = share_link_service.generate_token(
        sim_id="sim_epsilon", sim_dir=str(sim_dir)
    )

    assert record["created_at_iso"].endswith("Z")
    assert record["expires_at_iso"].endswith("Z")
    assert record["expires_at_epoch"] > record["created_at_epoch"]


# ── resolve_token ──────────────────────────────────────────────────────────


def test_resolve_token_returns_sim_id_for_valid_token(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_aaa")
    record = share_link_service.generate_token(
        sim_id="sim_aaa", sim_dir=str(sim_dir)
    )

    resolved = share_link_service.resolve_token(
        token=record["token"], sim_root=str(tmp_path)
    )
    assert resolved == "sim_aaa"


def test_resolve_token_returns_none_for_unknown_token(tmp_path):
    from app.services import share_link_service

    _make_sim_dir(tmp_path, "sim_bbb")
    assert (
        share_link_service.resolve_token(
            token="not-a-real-token-zzzz", sim_root=str(tmp_path)
        )
        is None
    )


def test_resolve_token_returns_none_for_revoked_token(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_ccc")
    record = share_link_service.generate_token(
        sim_id="sim_ccc", sim_dir=str(sim_dir)
    )
    token = record["token"]

    share_link_service.revoke_token(
        sim_id="sim_ccc", sim_dir=str(sim_dir), token=token
    )

    assert (
        share_link_service.resolve_token(token=token, sim_root=str(tmp_path))
        is None
    )


def test_resolve_token_returns_none_for_expired_token(tmp_path, monkeypatch):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_ddd")

    # Mint at t=0, then read the clock forward past the 1-day expiry.
    monkeypatch.setattr(share_link_service, "_now_epoch", lambda: 1_000_000)
    record = share_link_service.generate_token(
        sim_id="sim_ddd", sim_dir=str(sim_dir), expires_in_days=1
    )
    token = record["token"]

    # Resolve at a later time — past expiry should yield None.
    monkeypatch.setattr(
        share_link_service, "_now_epoch", lambda: 1_000_000 + 2 * 86_400
    )
    assert (
        share_link_service.resolve_token(token=token, sim_root=str(tmp_path))
        is None
    )


def test_resolve_token_rejects_path_traversal(tmp_path):
    from app.services import share_link_service

    _make_sim_dir(tmp_path, "sim_eee")
    for hostile in ("../etc/passwd", "..", "/tmp/x", "tok/with/slashes"):
        assert (
            share_link_service.resolve_token(
                token=hostile, sim_root=str(tmp_path)
            )
            is None
        )


def test_resolve_token_handles_missing_sim_root(tmp_path):
    from app.services import share_link_service

    missing = tmp_path / "does-not-exist"
    assert (
        share_link_service.resolve_token(
            token="anything", sim_root=str(missing)
        )
        is None
    )


# ── revoke_token ───────────────────────────────────────────────────────────


def test_revoke_token_is_idempotent(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_fff")
    record = share_link_service.generate_token(
        sim_id="sim_fff", sim_dir=str(sim_dir)
    )
    token = record["token"]

    assert share_link_service.revoke_token(
        sim_id="sim_fff", sim_dir=str(sim_dir), token=token
    ) is True
    # Second revoke still reports success — the operator's intent ("be
    # gone") is satisfied either way.
    assert share_link_service.revoke_token(
        sim_id="sim_fff", sim_dir=str(sim_dir), token=token
    ) is True


def test_revoke_token_returns_false_for_unknown(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_ggg")
    assert share_link_service.revoke_token(
        sim_id="sim_ggg", sim_dir=str(sim_dir), token="never-existed-token"
    ) is False


# ── list_tokens ────────────────────────────────────────────────────────────


def test_list_tokens_excludes_revoked_and_expired(tmp_path, monkeypatch):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_hhh")

    monkeypatch.setattr(share_link_service, "_now_epoch", lambda: 1_000_000)
    active = share_link_service.generate_token(
        sim_id="sim_hhh", sim_dir=str(sim_dir), expires_in_days=10
    )
    soon_revoked = share_link_service.generate_token(
        sim_id="sim_hhh", sim_dir=str(sim_dir), expires_in_days=10
    )
    soon_expired = share_link_service.generate_token(
        sim_id="sim_hhh", sim_dir=str(sim_dir), expires_in_days=1
    )

    share_link_service.revoke_token(
        sim_id="sim_hhh", sim_dir=str(sim_dir), token=soon_revoked["token"]
    )

    # Advance the clock past the 1-day token's expiry but keep the
    # 10-day token alive.
    monkeypatch.setattr(
        share_link_service, "_now_epoch", lambda: 1_000_000 + 2 * 86_400
    )

    tokens = share_link_service.list_tokens(
        sim_id="sim_hhh", sim_dir=str(sim_dir)
    )

    listed = {entry["token"] for entry in tokens}
    assert active["token"] in listed
    assert soon_revoked["token"] not in listed
    assert soon_expired["token"] not in listed


def test_list_tokens_sorts_newest_first(tmp_path, monkeypatch):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_iii")

    monkeypatch.setattr(share_link_service, "_now_epoch", lambda: 1_000_000)
    first = share_link_service.generate_token(
        sim_id="sim_iii", sim_dir=str(sim_dir)
    )
    monkeypatch.setattr(share_link_service, "_now_epoch", lambda: 1_000_005)
    second = share_link_service.generate_token(
        sim_id="sim_iii", sim_dir=str(sim_dir)
    )

    tokens = share_link_service.list_tokens(
        sim_id="sim_iii", sim_dir=str(sim_dir)
    )

    assert tokens[0]["token"] == second["token"]
    assert tokens[1]["token"] == first["token"]


def test_list_tokens_returns_empty_for_no_tokens_dir(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_jjj")
    # No share-tokens subdir created.
    assert share_link_service.list_tokens(
        sim_id="sim_jjj", sim_dir=str(sim_dir)
    ) == []


# ── expiry arithmetic + clamps ────────────────────────────────────────────


def test_expires_at_for_is_exact_days_after_now():
    from app.services import share_link_service

    now = 1_700_000_000
    assert (
        share_link_service._expires_at_for(7, now_epoch=now)
        == now + 7 * 86_400
    )


def test_clamp_expires_in_days_handles_garbage_input():
    from app.services import share_link_service

    cases: Dict[Any, int] = {
        None: share_link_service.DEFAULT_EXPIRES_IN_DAYS,
        "not-a-number": share_link_service.DEFAULT_EXPIRES_IN_DAYS,
        -5: share_link_service.MIN_EXPIRES_IN_DAYS,
        0: share_link_service.MIN_EXPIRES_IN_DAYS,
        1: 1,
        45: 45,
        500: share_link_service.MAX_EXPIRES_IN_DAYS,
    }
    for raw, expected in cases.items():
        assert share_link_service._clamp_expires_in_days(raw) == expected, raw


# ── multi-token + cleanup ──────────────────────────────────────────────────


def test_two_tokens_for_same_sim_both_resolve(tmp_path):
    from app.services import share_link_service

    sim_dir = _make_sim_dir(tmp_path, "sim_kkk")
    one = share_link_service.generate_token(
        sim_id="sim_kkk", sim_dir=str(sim_dir)
    )
    two = share_link_service.generate_token(
        sim_id="sim_kkk", sim_dir=str(sim_dir)
    )

    assert one["token"] != two["token"]
    assert (
        share_link_service.resolve_token(
            token=one["token"], sim_root=str(tmp_path)
        )
        == "sim_kkk"
    )
    assert (
        share_link_service.resolve_token(
            token=two["token"], sim_root=str(tmp_path)
        )
        == "sim_kkk"
    )


def test_resolve_after_sim_dir_removed_yields_none(tmp_path):
    from app.services import share_link_service
    import shutil

    sim_dir = _make_sim_dir(tmp_path, "sim_lll")
    record = share_link_service.generate_token(
        sim_id="sim_lll", sim_dir=str(sim_dir)
    )

    shutil.rmtree(sim_dir)

    assert (
        share_link_service.resolve_token(
            token=record["token"], sim_root=str(tmp_path)
        )
        is None
    )
