"""Private share-link tokens — selective access without flipping is_public.

MiroShark's sharing model has been binary since day one: every simulation
is either ``is_public=true`` (anyone with the URL — and every crawler —
can read it) or private (only the operator with the admin token can see
it). There's no middle path. A researcher who wants to send a finished
sim to a co-author, an operator running a stakeholder preview before
going public, an AntFleet benchmark sharing a debug run with another
integrator — none of those workflows fit the binary gate. They want one
URL, given to one person, valid for a bounded window, revocable at any
time, and **not** indexed by search engines or the platform gallery.

This module fills that gap with one stdlib primitive:

  • ``generate_token(sim_id, sim_dir, expires_in_days)`` — mints a 32-char
    URL-safe token via :func:`secrets.token_urlsafe`, persists a tiny
    JSON record under ``<sim_dir>/share-tokens/<token>.json`` and returns
    the public envelope ``{token, expires_at_epoch, expires_at_iso,
    expires_in_days, created_at_epoch, created_at_iso}``.

  • ``resolve_token(token, sim_root)`` — walks the per-sim subdirectories
    under ``sim_root`` looking for that token. Returns the sim_id when
    the token file exists, isn't revoked, and isn't past its expiry.
    Returns ``None`` for every other case (unknown / revoked / expired /
    bad-shape on disk) — the route handler turns the same ``None`` into
    a single 404 so a probe can't distinguish "token doesn't exist" from
    "token was revoked last week".

  • ``revoke_token(sim_id, sim_dir, token)`` — flips ``revoked=true`` and
    stamps ``revoked_at_epoch``. Idempotent: a second revoke on the same
    token is a no-op.

  • ``list_tokens(sim_id, sim_dir)`` — returns the active tokens for one
    sim (non-revoked, non-expired) so the operator UI can render the
    "revoke" list without seeing already-revoked entries clutter the
    panel. Sorted newest-first so the most recently issued link is at the
    top of the list.

Design notes
------------

* **Co-located with the sim.** Token records live at
  ``<sim_dir>/share-tokens/<token>.json`` rather than a flat index file
  at the data root. The simulation directory is the canonical lifecycle
  unit — when an operator deletes a sim (``shutil.rmtree``), its tokens
  go with it. A separate flat index would dangle. The per-sim layout
  also keeps the writeable surface narrow: minting a token only touches
  one subdirectory, so two operators issuing links for two different
  sims can't race on a shared file.

* **Lookup cost.** ``resolve_token`` scans ``os.listdir(sim_root)`` and
  checks each entry for the token file. That's O(N) over sim count
  with one ``os.path.exists`` call per sim — a few hundred microseconds
  for a thousand sims on a warm filesystem. The preview endpoint is
  rate-limited by browser load, not internal latency, so this is the
  right tradeoff vs. a flat index that would need its own concurrency
  story.

* **Bypasses ``is_public`` deliberately.** A private share link is the
  whole point of this surface — if an operator wants the recipient to
  see a sim they explicitly chose not to publish, the token is the
  consent. The preview landing page in ``app.api.share`` injects a
  ``<meta name="robots" content="noindex,nofollow">`` so search engines
  and link-unfurlers don't accidentally index the preview URL.

* **No transitive reads.** The token grants access to the simulation's
  share-view (the same SPA the public ``/share/<sim_id>`` route serves)
  — it does **not** unlock the per-sim REST surfaces (signal.json,
  transcript.md, chart.svg, etc.). Those keep their existing
  ``is_public`` gate. This keeps the privacy boundary explicit: a token
  is a one-page preview, not an open key to the whole machine-readable
  surface set.

* **Expiry is required.** ``expires_in_days`` defaults to 30 and is
  clamped to ``[MIN_EXPIRES_IN_DAYS, MAX_EXPIRES_IN_DAYS]``. There's no
  "never expires" option — an unbounded token would defeat the
  selective-share contract the moment the recipient leaks the URL.

* **Pure stdlib.** ``secrets`` for token entropy, ``json`` + ``os`` for
  persistence, ``time`` for expiry arithmetic. Same module shape as
  ``signal_service``, ``clone_service``, ``volatility_service`` — no
  new dependencies. Pure functions; the module holds no global state.
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from typing import Any, Dict, List, Optional


SCHEMA_VERSION = "1"

# Subdirectory under each ``<sim_dir>`` that holds token records. The
# name matches the surface ("share-tokens", not the underscore-prefixed
# variant) so an operator inspecting an uploaded simulations folder can
# spot it without guessing.
SHARE_TOKENS_SUBDIR = "share-tokens"

# Token entropy: ``secrets.token_urlsafe(24)`` produces a 32-character
# URL-safe base64 string drawn from the system CSPRNG. 24 bytes ⇒ 192
# bits of entropy, which keeps a brute-force scan against a 1000-sim
# deployment intractable.
TOKEN_BYTES = 24

# Expiry bounds. The clamp lives at the service layer (not the route)
# so any caller — REST API, CLI, future MCP tool — gets the same
# guarantee without re-implementing the check.
MIN_EXPIRES_IN_DAYS = 1
MAX_EXPIRES_IN_DAYS = 365
DEFAULT_EXPIRES_IN_DAYS = 30

# One day in seconds. Pulled into a constant to keep the arithmetic in
# :func:`_expires_at_for` readable and to make the test suite's
# round-trip checks explicit about the units.
_SECONDS_PER_DAY = 86_400


def _share_tokens_dir(sim_dir: str) -> str:
    """Return the absolute path of the share-tokens subdirectory.

    Pure path join — never touches the filesystem. The caller decides
    whether to ``os.makedirs`` (mint path) or just probe for existence
    (resolve / list paths).
    """
    return os.path.join(sim_dir or "", SHARE_TOKENS_SUBDIR)


def _token_path(sim_dir: str, token: str) -> str:
    """Return the on-disk path of a single token record.

    The token has already been validated to URL-safe characters by the
    caller (either ``secrets.token_urlsafe`` on mint or the strict route
    validator on resolve). Constructing the path here without re-checking
    keeps the hot path tight.
    """
    return os.path.join(_share_tokens_dir(sim_dir), f"{token}.json")


def _now_epoch() -> int:
    """Integer Unix timestamp — single source for current-time arithmetic.

    Pulled into a helper so the test suite can monkey-patch one symbol
    rather than chasing ``time.time()`` calls scattered across the module.
    """
    return int(time.time())


def _epoch_to_iso(epoch_seconds: int) -> str:
    """Render a Unix timestamp as an ISO-8601 UTC string (``...Z``).

    Used purely for the operator-facing UI — the truth-of-record on disk
    is ``expires_at_epoch`` (integer seconds) so timezone interpretation
    drift can't desync resolve from list.
    """
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_seconds))


def _clamp_expires_in_days(value: Any) -> int:
    """Coerce ``value`` to an integer day count inside the policy bounds.

    Accepts any caller-shape: ``None`` → default, non-numeric → default,
    out-of-range numeric → clamped to the nearest bound. Returning a
    sane default rather than raising keeps the mint endpoint forgiving
    on a malformed body — the recipient still gets a usable token, just
    not the exact lifetime they asked for.
    """
    if value is None:
        return DEFAULT_EXPIRES_IN_DAYS
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_EXPIRES_IN_DAYS
    if days < MIN_EXPIRES_IN_DAYS:
        return MIN_EXPIRES_IN_DAYS
    if days > MAX_EXPIRES_IN_DAYS:
        return MAX_EXPIRES_IN_DAYS
    return days


def _expires_at_for(days: int, now_epoch: Optional[int] = None) -> int:
    """Compute the expiry epoch ``days`` whole days from ``now_epoch``.

    Pulling the ``now_epoch`` parameter out makes the test suite's
    expiry-arithmetic check explicit: ``_expires_at_for(7, now)`` is
    ``now + 7 * 86_400`` — no implicit clock read.
    """
    if now_epoch is None:
        now_epoch = _now_epoch()
    return now_epoch + days * _SECONDS_PER_DAY


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    """Write ``payload`` to ``path`` atomically.

    Uses the same staging-tempfile + ``os.replace`` posture
    ``surface_stats._atomic_write`` and the webhook log use, kept local
    so this module stays self-contained. A failed write leaves no
    half-written record on disk — either the token is fully usable or
    fully absent.
    """
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".share-token-", suffix=".tmp", dir=parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
        os.replace(tmp_path, path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise


def _load_record(path: str) -> Optional[Dict[str, Any]]:
    """Read a token file from disk; missing / corrupt → ``None``.

    Defensive on every branch — a corrupted token file should make
    ``resolve_token`` say "unknown token" (404), never crash the preview
    page. The same defensiveness covers an operator who hand-edits a
    token file to syntactically broken JSON.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _record_envelope(
    sim_id: str,
    token: str,
    expires_at_epoch: int,
    created_at_epoch: int,
    revoked: bool,
    revoked_at_epoch: Optional[int],
) -> Dict[str, Any]:
    """Build the canonical on-disk record shape.

    Centralised here so mint / revoke / public-list use the same key
    names and ordering — drift between writers and readers would surface
    as fields silently missing from the operator UI.
    """
    record: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "sim_id": sim_id,
        "token": token,
        "created_at_epoch": int(created_at_epoch),
        "expires_at_epoch": int(expires_at_epoch),
        "revoked": bool(revoked),
    }
    if revoked_at_epoch is not None:
        record["revoked_at_epoch"] = int(revoked_at_epoch)
    return record


def _public_view(record: Dict[str, Any]) -> Dict[str, Any]:
    """Public envelope for an operator-facing list / mint response.

    Adds the ISO-formatted timestamps the on-disk record stores only as
    epoch seconds. ``expires_in_days_remaining`` is computed at read
    time so the UI doesn't have to do timezone arithmetic.
    """
    expires_at_epoch = int(record.get("expires_at_epoch") or 0)
    created_at_epoch = int(record.get("created_at_epoch") or 0)
    now = _now_epoch()
    remaining_seconds = max(0, expires_at_epoch - now)
    return {
        "token": record.get("token"),
        "sim_id": record.get("sim_id"),
        "created_at_epoch": created_at_epoch,
        "created_at_iso": _epoch_to_iso(created_at_epoch) if created_at_epoch else "",
        "expires_at_epoch": expires_at_epoch,
        "expires_at_iso": _epoch_to_iso(expires_at_epoch) if expires_at_epoch else "",
        "expires_in_days_remaining": remaining_seconds // _SECONDS_PER_DAY,
        "expires_in_seconds_remaining": remaining_seconds,
    }


def generate_token(
    sim_id: str,
    sim_dir: str,
    expires_in_days: Any = DEFAULT_EXPIRES_IN_DAYS,
) -> Dict[str, Any]:
    """Mint a fresh share-link token for ``sim_id`` and persist it.

    The caller is responsible for verifying the simulation exists before
    minting (the route handler does this via :class:`SimulationManager`).
    ``sim_dir`` is the absolute path of the sim's data directory
    (``Config.WONDERWALL_SIMULATION_DATA_DIR / sim_id``).

    Returns the public envelope — same shape as one entry of
    :func:`list_tokens`. Never raises on a clamp-able ``expires_in_days``
    value; will raise if the underlying filesystem write fails (atomic
    write surfaces an OSError to the caller).
    """
    if not sim_id:
        raise ValueError("sim_id must not be empty")
    if not sim_dir:
        raise ValueError("sim_dir must not be empty")

    clamped_days = _clamp_expires_in_days(expires_in_days)
    now = _now_epoch()
    token = secrets.token_urlsafe(TOKEN_BYTES)
    expires_at_epoch = _expires_at_for(clamped_days, now_epoch=now)

    record = _record_envelope(
        sim_id=sim_id,
        token=token,
        expires_at_epoch=expires_at_epoch,
        created_at_epoch=now,
        revoked=False,
        revoked_at_epoch=None,
    )

    _atomic_write_json(_token_path(sim_dir, token), record)

    public = _public_view(record)
    # Echo the clamped value so the caller knows what lifetime the
    # token actually got (vs. what they asked for).
    public["expires_in_days"] = clamped_days
    return public


def resolve_token(token: str, sim_root: str) -> Optional[str]:
    """Look up ``token`` across every sim dir under ``sim_root``.

    Returns the owning ``sim_id`` for a valid, non-revoked, non-expired
    token. Returns ``None`` for anything else — unknown token, revoked
    token, past-expiry token, malformed token file. The caller (route
    handler) maps all four cases to a single 404 so a probe can't tell
    them apart.

    Scans ``os.listdir(sim_root)`` once. With a few hundred sims and a
    warm filesystem, that's well under a millisecond on a single SSD.
    A larger deployment may want to layer a flat index on top, but the
    write-once / read-occasionally access pattern doesn't justify the
    complexity yet.
    """
    if not token or not sim_root:
        return None

    # Token character set is constrained at mint time, but a hostile
    # ``token`` arriving via URL might contain path separators or
    # parent-directory references that ``os.path.join`` would happily
    # collapse. Reject anything outside the URL-safe base64 alphabet
    # before touching the filesystem.
    if not _is_safe_token(token):
        return None

    if not os.path.isdir(sim_root):
        return None

    try:
        candidates = os.listdir(sim_root)
    except OSError:
        return None

    now = _now_epoch()
    for entry in candidates:
        sim_dir = os.path.join(sim_root, entry)
        if not os.path.isdir(sim_dir):
            continue
        token_path = _token_path(sim_dir, token)
        if not os.path.exists(token_path):
            continue
        record = _load_record(token_path)
        if not _record_is_active(record, now):
            return None
        # The record's ``sim_id`` is the truth (the filesystem entry
        # name should match, but if an operator renamed the directory
        # we still want to return what the record claims).
        recorded_sim_id = (record or {}).get("sim_id")
        if isinstance(recorded_sim_id, str) and recorded_sim_id:
            return recorded_sim_id
        return entry

    return None


def revoke_token(sim_id: str, sim_dir: str, token: str) -> bool:
    """Mark ``token`` as revoked for ``sim_id``.

    Idempotent — returns ``True`` when the token existed (whether or not
    it was already revoked), ``False`` when there's no such token on
    disk. The route handler returns ``204`` on either branch so the
    caller (UI) can't distinguish "already gone" from "I just deleted
    it" — the user-facing outcome is the same and the UI re-fetches the
    list either way.
    """
    if not sim_dir or not token:
        return False
    if not _is_safe_token(token):
        return False

    path = _token_path(sim_dir, token)
    record = _load_record(path)
    if not record:
        return False

    if record.get("revoked"):
        # Already revoked — no-op write, but report True so the caller
        # treats the user's revoke action as a success.
        return True

    updated = _record_envelope(
        sim_id=record.get("sim_id") or sim_id,
        token=record.get("token") or token,
        expires_at_epoch=int(record.get("expires_at_epoch") or 0),
        created_at_epoch=int(record.get("created_at_epoch") or 0),
        revoked=True,
        revoked_at_epoch=_now_epoch(),
    )
    _atomic_write_json(path, updated)
    return True


def list_tokens(sim_id: str, sim_dir: str) -> List[Dict[str, Any]]:
    """Return active share-link tokens for ``sim_id`` (revoked + expired excluded).

    Sorted newest-first by ``created_at_epoch`` so the operator UI shows
    the most recently issued token at the top of the panel. Returns an
    empty list for a sim with no tokens (or no share-tokens directory),
    never raises.
    """
    if not sim_dir:
        return []

    tokens_dir = _share_tokens_dir(sim_dir)
    if not os.path.isdir(tokens_dir):
        return []

    try:
        entries = os.listdir(tokens_dir)
    except OSError:
        return []

    now = _now_epoch()
    active: List[Dict[str, Any]] = []
    for entry in entries:
        if not entry.endswith(".json"):
            continue
        path = os.path.join(tokens_dir, entry)
        record = _load_record(path)
        if not _record_is_active(record, now):
            continue
        public = _public_view(record or {})
        # Force the sim_id to the requested one — the caller asked for
        # tokens belonging to this sim, and we don't want a hand-edited
        # record claiming a different sim_id to leak through.
        public["sim_id"] = sim_id
        active.append(public)

    active.sort(key=lambda t: int(t.get("created_at_epoch") or 0), reverse=True)
    return active


def _record_is_active(record: Optional[Dict[str, Any]], now_epoch: int) -> bool:
    """Return True when a record exists, isn't revoked, and isn't expired.

    Returns False for ``None`` (missing record) and for records with the
    wrong shape — a corrupted or schema-drifted file is treated as
    inactive rather than crashing the preview page.
    """
    if not isinstance(record, dict):
        return False
    if record.get("revoked"):
        return False
    try:
        expires_at = int(record.get("expires_at_epoch") or 0)
    except (TypeError, ValueError):
        return False
    if expires_at <= 0:
        return False
    if expires_at <= now_epoch:
        return False
    return True


def _is_safe_token(token: str) -> bool:
    """Reject anything outside the URL-safe base64 alphabet.

    ``secrets.token_urlsafe`` only emits ``[A-Za-z0-9_-]``. A token
    arriving via the URL that contains a slash, dot, or anything else
    can't have come from ``generate_token`` — it's either a probe or a
    truncated copy-paste. We bail before touching the filesystem so a
    crafted ``../../etc/passwd`` payload can't traverse out of the
    token directory via ``os.path.join``.
    """
    if not token or not isinstance(token, str):
        return False
    if len(token) > 128:
        # ``secrets.token_urlsafe(24)`` returns 32 chars; cap at 128 to
        # leave headroom for a future increase without accepting
        # pathologically large probe strings.
        return False
    for ch in token:
        if not (ch.isalnum() or ch == "_" or ch == "-"):
            return False
    return True
