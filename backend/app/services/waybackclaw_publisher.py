"""WaybackClaw archive publishing — agent snapshot surface for finished simulations.

Submits a finished, published simulation as a **snapshot** to the
WaybackClaw AI Agent Archive (``api.waybackclaw.space``). Each
snapshot captures the scenario, agent count, total rounds, platforms,
final consensus, quality health, lineage, and the SHA-256 of the
canonical ``reproduce.json`` blob — packaged as a versioned record
under the deployment's registered MiroShark agent identity.

A successful submission returns a ``{id, ipfsCid, nostrEventId, …}``
envelope that becomes the sibling of the OriginTrail DKG citation:
the DKG anchor provides on-chain provenance, WaybackClaw provides
content-addressed IPFS storage + Nostr broadcast on the agent-archive
side, and ``reproduce.json`` is the bytes both layers commit to.

Design notes
------------

* **Optional + env-var-gated.** ``WAYBACKCLAW_AGENT_TOKEN`` empty →
  the module is a no-op. ``WAYBACKCLAW_API_URL`` defaults to the
  hosted endpoint, ``WAYBACKCLAW_AGENT_CATEGORY`` defaults to
  ``prediction`` (MiroShark sims are prediction-market-style runs).
* **One HTTP call.** WaybackClaw exposes a single
  ``POST /api/archive/submit`` for snapshots — no multi-step
  WM→SWM→VM pipeline like the DKG daemon. Auth is a long-lived
  bearer token issued via ``POST /api/archive/register``.
* **Free for agents.** Submission carries no payment requirement
  beyond the token. No ``X-PAYMENT`` header is sent; we let the
  server's free-tier write path handle the request.
* **Idempotent on disk.** A successful submission persists
  ``<sim_dir>/waybackclaw-record.json`` and the route handler
  returns the cached envelope without re-hitting the API on
  subsequent clicks (matches the DKG flow). ``force=True`` is
  plumbed through for re-submission after a sim correction.
* **Stdlib only.** ``urllib.request`` for HTTP, ``hashlib`` for
  the ``reproduce.json`` SHA-256, ``json`` for serialization.
* **Never raises.** Failures surface as structured dicts so the
  route handler can map them to sensible HTTP semantics
  (502 / 504 / 503 / 429) instead of a generic 500.

The submit payload
------------------

A minimal but complete snapshot describing the simulation, with a
metadata blob carrying the reproducible citation primitives::

    {
      "version": "<simulation_id>",
      "capabilities": ["swarm-simulation", "twitter", "reddit", "polymarket"],
      "category": "prediction",
      "modelFamily": "MiroShark",
      "description": "<scenario>",
      "metadata": {
        "agentCount": 248,
        "totalRounds": 24,
        "bullishPercent": 62.0,
        "neutralPercent": 13.0,
        "bearishPercent": 25.0,
        "qualityHealth": "Excellent",
        "lineageKind": "original",
        "reproduceConfigSha256": "sha256:7c9f…",
        "reproduceConfigUrl": "https://host/api/simulation/<id>/reproduce.json",
        "shareUrl": "https://host/share/<id>",
        "shareCardUrl": "https://host/api/simulation/<id>/share-card.png",
        "platform": "MiroShark",
        "chain": "off-chain",
        "publishedAt": "2026-05-22T12:00:00Z"
      }
    }

The ``metadata.reproduceConfigSha256`` literal is the citation key —
a verifier fetches the ``reproduceConfigUrl`` bytes, re-hashes them,
and compares to the stored hash. WaybackClaw also pins the JSON
record itself to IPFS (returning ``ipfsCid``), so the snapshot is
content-addressed end-to-end without the operator running any
infrastructure.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger
from ..utils.timeutils import utc_iso8601 as _now_iso

logger = get_logger("miroshark.waybackclaw")


# ---- HTTP defaults ---------------------------------------------------------

WAYBACKCLAW_USER_AGENT = "MiroShark-WaybackClaw/1.0"

# Snapshot submissions land on the SQLite write path immediately, but
# the API spawns async daemon threads for IPFS pinning + Nostr
# publishing before returning the envelope with ``ipfsCid`` /
# ``nostrEventId`` populated. 30s is conservative; under load the
# IPFS pin can stretch past the default 10s urlopen timeout.
WAYBACKCLAW_SUBMIT_TIMEOUT_SECONDS = 30.0


# ---- Persistence -----------------------------------------------------------

WAYBACKCLAW_RECORD_FILENAME = "waybackclaw-record.json"


# ---- Config (late-binding so Settings modal changes take effect) ----------

# WaybackClaw's hosted production endpoint. Operators can override via
# ``WAYBACKCLAW_API_URL`` (private deployment, staging, self-hosted
# fork) — same shape as the DKG_API_URL knob.
WAYBACKCLAW_DEFAULT_API_URL = "https://api.waybackclaw.space"

# Sensible default category for MiroShark snapshots. The WaybackClaw
# taxonomy includes ``prediction`` (oracle / prediction-market style),
# which is the right home for a multi-agent swarm sim with a final
# consensus distribution. Operators can override per deployment.
WAYBACKCLAW_DEFAULT_CATEGORY = "prediction"


def _resolve_config() -> Dict[str, str]:
    """Read WAYBACKCLAW_* env vars at call time via the ``Config`` class.

    Late-binding mirrors webhook_service / dkg_publisher so an operator
    pasting values into a future Settings modal sees them take effect
    immediately without a server restart.
    """
    try:
        from ..config import Config
        return {
            "api_url": (
                (getattr(Config, "WAYBACKCLAW_API_URL", "") or WAYBACKCLAW_DEFAULT_API_URL)
                .strip()
                .rstrip("/")
            ),
            "agent_token": (getattr(Config, "WAYBACKCLAW_AGENT_TOKEN", "") or "").strip(),
            "category": (
                (getattr(Config, "WAYBACKCLAW_AGENT_CATEGORY", "") or WAYBACKCLAW_DEFAULT_CATEGORY)
                .strip()
                .lower()
            ),
        }
    except Exception:
        return {
            "api_url": WAYBACKCLAW_DEFAULT_API_URL,
            "agent_token": "",
            "category": WAYBACKCLAW_DEFAULT_CATEGORY,
        }


def is_configured() -> bool:
    """True iff ``WAYBACKCLAW_AGENT_TOKEN`` is set.

    ``WAYBACKCLAW_API_URL`` has a sensible production default and is
    never required. ``WAYBACKCLAW_AGENT_CATEGORY`` is metadata only.
    The agent token is the single required secret — it carries both
    identity and authorization in the
    ``Bearer <agentId>:<secret>`` format the WaybackClaw API expects.
    """
    cfg = _resolve_config()
    return bool(cfg["agent_token"])


def mask_token(token: str) -> str:
    """Show the leading agent id prefix of a token for log lines / UI.

    Tokens look like ``agent_abc123:long-secret``. We surface the
    agent-id half (safe, semi-public — it's effectively a username)
    and mask the secret half completely. Mirrors
    :func:`dkg_publisher.mask_token`.
    """
    if not token:
        return ""
    stripped = token.strip()
    if ":" in stripped:
        agent_part, _, _ = stripped.partition(":")
        return f"{agent_part}:***"
    if len(stripped) <= 6:
        return "***"
    return f"{stripped[:6]}***"


# ---- HTTP transport --------------------------------------------------------


def _request(
    method: str,
    path: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    timeout: float,
    agent_token: str,
    api_url: str,
) -> Tuple[bool, int, Any]:
    """Issue one WaybackClaw API HTTP call.

    Returns ``(ok, status_code, payload)``:
      * ``ok`` — True for 2xx, False otherwise.
      * ``status_code`` — 0 if the request never reached the server
        (DNS / connection refused / timeout).
      * ``payload`` — parsed JSON response when possible, otherwise
        the raw body text or an error message on transport failure.

    Never raises — submission happens inside a user-facing request
    handler and must surface the failure as data so the frontend can
    render a sensible error message instead of a generic 500.
    """
    url = f"{api_url}{path}"
    headers: Dict[str, str] = {
        "User-Agent": WAYBACKCLAW_USER_AGENT,
        "Accept": "application/json",
    }
    if agent_token:
        # The API accepts ``X-Agent-Token: Bearer <agentId>:<secret>``
        # per the WaybackClaw docs. We also forward the same token via
        # ``Authorization`` for clients / proxies that strip the
        # custom header. Belt-and-suspenders, no behavioural change.
        bearer = agent_token if agent_token.lower().startswith("bearer ") else f"Bearer {agent_token}"
        headers["X-Agent-Token"] = bearer
        headers["Authorization"] = bearer

    data: Optional[bytes] = None
    if body is not None:
        try:
            data = json.dumps(body).encode("utf-8")
        except Exception as exc:
            return False, 0, f"could not serialize request body: {exc}"
        headers["Content-Type"] = "application/json; charset=utf-8"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode() or 0
            raw = resp.read()
            payload = _parse_body(raw)
            ok = 200 <= status < 300
            return ok, status, payload
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read() or b""
        except Exception:
            raw = b""
        payload = _parse_body(raw)
        return False, exc.code or 0, payload
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, 0, f"URL error: {reason}"
    except Exception as exc:
        return False, 0, f"{type(exc).__name__}: {exc}"


def _parse_body(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None


# ---- Record file ----------------------------------------------------------


def record_path(sim_dir: str) -> str:
    return os.path.join(sim_dir or "", WAYBACKCLAW_RECORD_FILENAME)


def read_record(sim_dir: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the persisted submission record, or ``None`` if absent.

    Cheap read used by the EmbedDialog to render the existing
    snapshot badge without forcing another submission. Never raises.
    """
    if not sim_dir:
        return None
    path = record_path(sim_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


_RECORD_WRITE_LOCK = threading.Lock()


def _write_record(sim_dir: str, payload: Dict[str, Any]) -> None:
    """Persist the submission record atomically via tempfile + os.replace.

    Mirrors the dkg-citation on-disk atomic-write pattern.
    """
    if not sim_dir:
        return
    try:
        os.makedirs(sim_dir, exist_ok=True)
    except OSError as exc:
        logger.warning(f"waybackclaw-record: could not ensure sim_dir for {sim_dir}: {exc}")
        return
    path = record_path(sim_dir)
    tmp_path = path + ".tmp"
    with _RECORD_WRITE_LOCK:
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp_path, path)
        except OSError as exc:
            logger.warning(f"waybackclaw-record: write failed for {sim_dir}: {exc}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass


# ---- Snapshot payload assembly --------------------------------------------


def _sha256_hex(payload_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload_bytes).hexdigest()


def _derive_capabilities(repro_blob: Dict[str, Any]) -> List[str]:
    """Translate enabled platforms into WaybackClaw capability tags.

    Capabilities are free-form short strings on the WaybackClaw API;
    we pick a stable set of MiroShark-flavoured ones so the archive's
    capability index has useful aggregates for searches like "find
    every prediction agent that simulates a Polymarket-style market".
    """
    caps: List[str] = ["swarm-simulation", "multi-agent", "consensus-tracking"]
    platforms = repro_blob.get("platforms") or {}
    if isinstance(platforms, dict):
        if platforms.get("twitter"):
            caps.append("twitter")
        if platforms.get("reddit"):
            caps.append("reddit")
        if platforms.get("polymarket"):
            caps.append("polymarket")
    return caps


def build_submission(
    *,
    simulation_id: str,
    repro_blob: Dict[str, Any],
    reproduce_json_bytes: bytes,
    webhook_payload: Dict[str, Any],
    base_url: str,
    category: str,
) -> Tuple[Dict[str, Any], str]:
    """Compose the WaybackClaw snapshot submission body.

    Returns ``(body, reproduce_sha256)``. The hash is the citation
    key — a verifier fetches ``metadata.reproduceConfigUrl``, SHA-256s
    the bytes, and compares against the literal stored in the
    snapshot's metadata (and pinned content-addressed via IPFS).

    ``webhook_payload`` is reused as the source of the consensus +
    quality + scenario summary so the on-archive claim matches the
    notification claim byte-for-byte.
    """
    repro_sha = _sha256_hex(reproduce_json_bytes)

    scenario = (
        webhook_payload.get("scenario")
        or repro_blob.get("scenario")
        or f"MiroShark simulation {simulation_id}"
    )

    agent_count = int(repro_blob.get("agent_count") or webhook_payload.get("agent_count") or 0)
    total_rounds = int(repro_blob.get("total_rounds") or webhook_payload.get("total_rounds") or 0)

    metadata: Dict[str, Any] = {
        "simulationId": simulation_id,
        "agentCount": agent_count,
        "totalRounds": total_rounds,
        "reproduceConfigSha256": repro_sha,
        "platform": "MiroShark",
        # MiroShark sims aren't on-chain — the metadata layer's
        # ``chain`` field maps to the consensus venue for tokenized
        # agents in the WaybackClaw taxonomy, so labelling the runs
        # ``off-chain`` is accurate and avoids implying a chain
        # affinity the runner doesn't have.
        "chain": "off-chain",
        "framework": "MiroShark",
        "publishedAt": _now_iso(),
    }

    consensus = webhook_payload.get("final_consensus")
    if isinstance(consensus, dict):
        if "bullish" in consensus:
            metadata["bullishPercent"] = round(float(consensus.get("bullish") or 0.0), 1)
        if "neutral" in consensus:
            metadata["neutralPercent"] = round(float(consensus.get("neutral") or 0.0), 1)
        if "bearish" in consensus:
            metadata["bearishPercent"] = round(float(consensus.get("bearish") or 0.0), 1)

    quality_health = webhook_payload.get("quality_health")
    if quality_health:
        metadata["qualityHealth"] = quality_health

    resolution_outcome = webhook_payload.get("resolution_outcome")
    if resolution_outcome:
        metadata["resolutionOutcome"] = resolution_outcome

    created_at = webhook_payload.get("created_at")
    if created_at:
        metadata["createdAt"] = created_at
    completed_at = webhook_payload.get("completed_at")
    if completed_at:
        metadata["completedAt"] = completed_at

    lineage = repro_blob.get("lineage") or {}
    if isinstance(lineage, dict):
        kind = lineage.get("kind") or "original"
        metadata["lineageKind"] = kind
        parent_id = lineage.get("parent_simulation_id")
        if parent_id:
            metadata["parentSimulationId"] = parent_id
        cf = lineage.get("counterfactual") or {}
        if isinstance(cf, dict):
            if cf.get("trigger_round"):
                metadata["counterfactualTriggerRound"] = int(cf.get("trigger_round") or 0)
            if cf.get("label"):
                metadata["counterfactualLabel"] = cf.get("label")

    platforms = repro_blob.get("platforms") or {}
    if isinstance(platforms, dict):
        metadata["twitterEnabled"] = bool(platforms.get("twitter", False))
        metadata["redditEnabled"] = bool(platforms.get("reddit", False))
        metadata["polymarketEnabled"] = bool(platforms.get("polymarket", False))

    if base_url:
        base = base_url.rstrip("/")
        metadata["reproduceConfigUrl"] = f"{base}/api/simulation/{simulation_id}/reproduce.json"
        metadata["shareUrl"] = f"{base}/share/{simulation_id}"
        metadata["shareCardUrl"] = f"{base}/api/simulation/{simulation_id}/share-card.png"

    body: Dict[str, Any] = {
        # The snapshot ``version`` field is free-form; using the
        # simulation id keeps the archive's per-agent version history
        # 1:1 with MiroShark's own sim ids so a viewer can match
        # archive entries back to ``/share/<id>`` URLs without
        # cross-referencing.
        "version": simulation_id,
        "capabilities": _derive_capabilities(repro_blob),
        "category": category,
        "modelFamily": "MiroShark",
        "description": scenario,
        "metadata": metadata,
    }
    return body, repro_sha


# ---- Submission flow ------------------------------------------------------


def submit_snapshot(
    *,
    simulation_id: str,
    sim_dir: str,
    repro_blob: Dict[str, Any],
    reproduce_json_bytes: bytes,
    webhook_payload: Dict[str, Any],
    base_url: str,
    force: bool = False,
) -> Dict[str, Any]:
    """Submit a simulation snapshot to the WaybackClaw archive.

    Idempotent: a successful submission persists the response envelope
    to ``<sim_dir>/waybackclaw-record.json`` and is returned directly
    on subsequent calls unless ``force=True``.

    Returns one of these shapes:

      * ``{ok: True, record: {…}, cached: True}`` — record already on
        disk, no API call made.
      * ``{ok: True, record: {…}, cached: False}`` — fresh submission.
      * ``{ok: False, status_code: int, stage: str, error: str}`` —
        submission failed. Stage values: ``"not_configured"``,
        ``"submit"``.

    Never raises.
    """
    if not is_configured():
        return {
            "ok": False,
            "status_code": 0,
            "stage": "not_configured",
            "error": "WAYBACKCLAW_AGENT_TOKEN not set",
        }

    if not force:
        existing = read_record(sim_dir)
        if existing and existing.get("id"):
            return {"ok": True, "record": existing, "cached": True}

    cfg = _resolve_config()
    body, repro_sha = build_submission(
        simulation_id=simulation_id,
        repro_blob=repro_blob,
        reproduce_json_bytes=reproduce_json_bytes,
        webhook_payload=webhook_payload,
        base_url=base_url,
        category=cfg["category"],
    )

    masked = mask_token(cfg["agent_token"])
    logger.info(
        f"waybackclaw-submit: starting {simulation_id} → {cfg['api_url']} "
        f"category={cfg['category']} token={masked}"
    )

    ok, status, payload = _request(
        "POST",
        "/api/archive/submit",
        body=body,
        timeout=WAYBACKCLAW_SUBMIT_TIMEOUT_SECONDS,
        agent_token=cfg["agent_token"],
        api_url=cfg["api_url"],
    )
    if not ok:
        return _fail("submit", status, payload)

    if not isinstance(payload, dict):
        return _fail("submit", status, f"unexpected response shape: {payload!r}")

    # The WaybackClaw API wraps everything in ``{success, data, timestamp}``.
    # Unwrap when present, fall back to the raw payload for resilience
    # against a future shape change.
    envelope = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    snapshot_id = envelope.get("id") or ""
    if not snapshot_id:
        return _fail("submit", status, f"API returned no snapshot id: {payload!r}")

    record: Dict[str, Any] = {
        "id": snapshot_id,
        "agent_id": envelope.get("agentId") or "",
        "agent_name": envelope.get("agentName") or "",
        "version": envelope.get("version") or simulation_id,
        "category": envelope.get("category") or cfg["category"],
        "captured_at": envelope.get("capturedAt") or "",
        "ipfs_cid": envelope.get("ipfsCid") or "",
        "nostr_event_id": envelope.get("nostrEventId") or "",
        "access_level": envelope.get("accessLevel") or "",
        "reproduce_config_sha256": repro_sha,
        "archive_url": f"{cfg['api_url']}/api/archive/retrieve?agentId={envelope.get('agentId') or ''}".rstrip(),
        "ipfs_gateway_url": (
            f"https://gateway.pinata.cloud/ipfs/{envelope.get('ipfsCid')}"
            if envelope.get("ipfsCid") else ""
        ),
        "submitted_at": _now_iso(),
        "schema_version": "1",
    }

    _write_record(sim_dir, record)
    logger.info(
        f"waybackclaw-submit: ok {simulation_id} → {snapshot_id} "
        f"(ipfs={record['ipfs_cid'][:10] if record['ipfs_cid'] else 'n/a'}…, "
        f"nostr={record['nostr_event_id'][:10] if record['nostr_event_id'] else 'n/a'}…)"
    )
    return {"ok": True, "record": record, "cached": False}


def _fail(stage: str, status: int, payload: Any) -> Dict[str, Any]:
    """Shape a submission failure into the structured response."""
    if isinstance(payload, dict):
        try:
            err_text = json.dumps(payload, ensure_ascii=False)
        except Exception:
            err_text = str(payload)
    else:
        err_text = str(payload) if payload is not None else ""
    if len(err_text) > 800:
        err_text = err_text[:797].rstrip() + "…"
    logger.warning(f"waybackclaw-submit: stage={stage} status={status} error={err_text}")
    return {
        "ok": False,
        "status_code": status,
        "stage": stage,
        "error": err_text or f"WaybackClaw API returned status {status}",
    }
