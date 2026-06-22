"""OriginTrail DKG publishing — citation surface for finished simulations.

Anchors a finished, published simulation's citation surface on the
OriginTrail DKG as a cryptographically verifiable Knowledge Asset. The
returned ``ual`` (Universal Asset Locator), ``merkleRoot``,
``transactionHash``, and ``blockNumber`` become a permanent,
blockchain-anchored citation key — the same provenance property Stripe
gives a charge or a DOI gives a paper, but for a MiroShark simulation
result. A researcher quoting Aaron's Aave risk sim can now point at the
UAL and anyone can verify the underlying claims have not been edited.

Design notes
------------

* **Optional + env-var-gated.** The four ``DKG_*`` vars empty → the
  module is a no-op. Same shape as ``WEBHOOK_URL`` / ``DISCORD_WEBHOOK_URL``
  / ``SLACK_WEBHOOK_URL``.
* **Manual trigger.** Operator clicks "Publish to DKG" in the EmbedDialog;
  the route handler calls :func:`publish_simulation`. There is no
  auto-publish on completion — anchoring on-chain costs TRAC + gas, and
  not every sim should hit the network.
* **Synchronous publish.** Uses ``POST /api/shared-memory/publish`` so
  the user clicking the button gets the citation back in the same
  request. The async ``/api/publisher/enqueue`` flow exists in DKG but
  adds polling complexity for v1.
* **Idempotent.** A successful publish persists ``dkg-citation.json`` to
  the sim dir; subsequent publishes return the existing citation without
  re-hitting the daemon (no double-spend of TRAC / gas).
* **Stdlib only.** ``urllib.request`` for HTTP, ``hashlib`` for the
  reproduce.json content hash, ``json`` for serialization. No new deps.
* **Never raises in the optional-noop path.** If the daemon is
  unreachable, :func:`publish_simulation` returns a structured error
  dict; the route handler maps that to a 502 / 504 / 503. Reading the
  citation when none exists yields ``None`` — safe to call during
  EmbedDialog mount.

The four-step DKG flow
----------------------

The OriginTrail DKG v9/v10 daemon HTTP API requires a three-tier write:

  1. ``POST /api/assertion/create``         — Working Memory (private draft)
  2. ``POST /api/assertion/{name}/write``   — append Turtle/n-quads
  3. ``POST /api/assertion/{name}/promote`` — WM → Shared Working Memory
  4. ``POST /api/shared-memory/publish``    — SWM → Verified Memory (on-chain)

Step 4 returns ``{ual, merkleRoot, transactionHash, blockNumber, finalized}``.

The Turtle payload
------------------

A minimal RDF representation of the simulation, citable from anywhere::

    @prefix mir: <https://miroshark.io/ns/sim#> .
    @prefix schema: <https://schema.org/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    <urn:miroshark:sim:sim_abc123> a mir:Simulation ;
      schema:identifier "sim_abc123" ;
      schema:name "Will the SEC approve …" ;
      mir:agentCount 248 ;
      mir:totalRounds 24 ;
      mir:bullishPercent "62.0"^^xsd:decimal ;
      …
      mir:reproduceConfigSha256 "sha256:abc…" ;
      mir:reproduceConfigUrl <https://host/api/simulation/sim_abc123/reproduce.json> .

The ``mir:reproduceConfigSha256`` literal is the actual citation key — a
verifier fetches the URL, hashes the bytes, and compares to the on-chain
Merkle root. The reproduce.json blob is already bytewise-stable per the
existing repro_export module, so this hash is durable.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from ..utils.logger import get_logger
from ..utils.timeutils import utc_iso8601 as _now_iso

logger = get_logger("miroshark.dkg")


# ---- HTTP defaults ---------------------------------------------------------

DKG_USER_AGENT = "MiroShark-DKG/1.0"

# Sub-step timeouts for the publish pipeline. The assertion writes are
# essentially local disk + RocksDB writes; the final publish waits for
# blockchain finality on the chosen chain and can be slow on testnet
# under load. Tune conservatively — the EmbedDialog shows a spinner and
# users will tolerate ~60s for a one-time citation anchor.
DKG_WRITE_TIMEOUT_SECONDS = 15.0
DKG_PUBLISH_TIMEOUT_SECONDS = 120.0


# ---- Citation persistence --------------------------------------------------

DKG_CITATION_FILENAME = "dkg-citation.json"


# ---- Turtle namespaces -----------------------------------------------------

MIROSHARK_NS = "https://miroshark.io/ns/sim#"
SCHEMA_NS = "https://schema.org/"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"

# Lock the assertion name shape: ``miroshark-sim-<id>``. The DKG
# ``/api/assertion/create`` endpoint returns 409 on name collision —
# turning a re-click into a duplicate publish — which is exactly the
# behaviour we want as a backstop to the on-disk citation check.
def _assertion_name(simulation_id: str) -> str:
    return f"miroshark-sim-{simulation_id}"


def _subject_uri(simulation_id: str) -> str:
    return f"urn:miroshark:sim:{simulation_id}"


# ---- Explorer URL templates (per chain) -----------------------------------
#
# Per the user's "configurable, default testnet" choice: ``DKG_NETWORK``
# picks the explorer template, not the daemon's chain — the daemon was
# already pointed at a chain when the operator ran ``dkg init``. This is
# pure metadata: it labels the citation with the chain the operator
# anchored against so a recipient knows which explorer to open.

_EXPLORER_TEMPLATES: Dict[str, str] = {
    "testnet": "https://dkg-testnet.origintrail.io/explore?ual={ual}",
    "mainnet": "https://dkg.origintrail.io/explore?ual={ual}",
}


def _explorer_url_for(ual: str, network: str) -> str:
    template = _EXPLORER_TEMPLATES.get(network, _EXPLORER_TEMPLATES["testnet"])
    return template.format(ual=ual)


# ---- Config helpers (late-binding so Settings modal changes take effect) --


def _resolve_config() -> Dict[str, str]:
    """Read DKG_* env vars at call time via the ``Config`` class.

    Late-binding mirrors webhook_service / discord_notify so an operator
    pasting values into a future Settings modal sees them take effect
    immediately without a server restart.
    """
    try:
        from ..config import Config
        return {
            "api_url": (getattr(Config, "DKG_API_URL", "") or "").strip().rstrip("/"),
            "auth_token": (getattr(Config, "DKG_AUTH_TOKEN", "") or "").strip(),
            "context_graph_id": (getattr(Config, "DKG_CONTEXT_GRAPH_ID", "") or "").strip(),
            "network": (getattr(Config, "DKG_NETWORK", "testnet") or "testnet").strip().lower(),
        }
    except Exception:
        return {"api_url": "", "auth_token": "", "context_graph_id": "", "network": "testnet"}


def is_configured() -> bool:
    """True iff the three required DKG_* vars are non-empty.

    ``DKG_NETWORK`` defaults to "testnet" and is never required — it's
    explorer-URL metadata, not a connectivity prerequisite.
    """
    cfg = _resolve_config()
    return bool(cfg["api_url"] and cfg["auth_token"] and cfg["context_graph_id"])


def mask_token(token: str) -> str:
    """Show the first 6 chars of an auth token for log lines / UI.

    Mirrors :func:`webhook_service.mask_url`: never echo the full secret
    back to logs or the frontend. ``abc123def456`` → ``abc123***``.
    """
    if not token:
        return ""
    stripped = token.strip()
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
    auth_token: str,
    api_url: str,
) -> Tuple[bool, int, Any]:
    """Issue one DKG daemon HTTP call.

    Returns ``(ok, status_code, payload)``:
      * ``ok`` — True for 2xx, False otherwise.
      * ``status_code`` — 0 if the request never reached the daemon
        (DNS / connection refused / timeout).
      * ``payload`` — parsed JSON response when possible, otherwise the
        raw body text as a string, or an error message on transport
        failure.

    Never raises — DKG calls happen inside a user-facing request handler
    and must surface the failure as data so the frontend can render a
    sensible error message instead of a generic 500.
    """
    url = f"{api_url}{path}"
    headers: Dict[str, str] = {
        "User-Agent": DKG_USER_AGENT,
        "Authorization": f"Bearer {auth_token}",
        "Accept": "application/json",
    }
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
        # Daemon returned a 4xx/5xx — read the body so the route can
        # bubble up the structured error.
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


# ---- Turtle generation ----------------------------------------------------


def _escape_literal(value: str) -> str:
    """Escape a Turtle string literal.

    Turtle backslash + quote escaping per
    https://www.w3.org/TR/turtle/#sec-escapes. We use the
    triple-double-quote long-form variant to allow embedded newlines
    cleanly.
    """
    if value is None:
        return ""
    s = str(value)
    # Escape backslash first, then triple-quotes (rare but possible) so
    # the long-form literal terminator can't be smuggled in.
    s = s.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return s


def _ttl_long_literal(value: str) -> str:
    """Render ``value`` as a Turtle triple-quoted string literal.

    Returns ``\"\"\"escaped\"\"\"``. Empty / None becomes ``\"\"`` so the
    caller can still emit a triple without conditional logic.
    """
    if value is None or value == "":
        return '""'
    return f'"""{_escape_literal(value)}"""'


def _ttl_decimal(value: float) -> str:
    """Render a decimal as Turtle ``"NN.N"^^xsd:decimal``."""
    return f'"{value:.1f}"^^xsd:decimal'


def _ttl_int(value: int) -> str:
    """Render an integer as a Turtle integer literal (xsd:integer implied)."""
    return str(int(value))


def _ttl_bool(value: bool) -> str:
    return "true" if value else "false"


def _ttl_datetime(value: Optional[str]) -> Optional[str]:
    """Render an ISO-8601 datetime as ``"…"^^xsd:dateTime``.

    Returns ``None`` for missing / unparseable input so the caller can
    omit the predicate rather than emit an invalid literal.
    """
    if not value:
        return None
    return f'"{_escape_literal(value)}"^^xsd:dateTime'


def _sha256_hex(payload_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload_bytes).hexdigest()


def build_turtle(
    *,
    simulation_id: str,
    repro_blob: Dict[str, Any],
    reproduce_json_bytes: bytes,
    webhook_payload: Dict[str, Any],
    base_url: str,
) -> Tuple[str, str]:
    """Compose the Turtle RDF for one simulation's Knowledge Asset.

    Returns ``(turtle_text, reproduce_sha256)``. The hash is the
    citation key — a verifier fetches ``mir:reproduceConfigUrl``,
    SHA-256s the bytes, and compares against the literal stored on-chain.

    ``webhook_payload`` is reused as the source of the consensus +
    quality + scenario summary so the on-chain claim matches the
    notification claim byte-for-byte.
    """
    subject = _subject_uri(simulation_id)
    repro_sha = _sha256_hex(reproduce_json_bytes)

    scenario = _ttl_long_literal(webhook_payload.get("scenario") or repro_blob.get("scenario") or "")

    lines = [
        f"@prefix mir: <{MIROSHARK_NS}> .",
        f"@prefix schema: <{SCHEMA_NS}> .",
        f"@prefix xsd: <{XSD_NS}> .",
        "",
        f"<{subject}> a mir:Simulation ;",
        f'  schema:identifier "{_escape_literal(simulation_id)}" ;',
        f"  schema:name {scenario} ;",
    ]

    agent_count = int(repro_blob.get("agent_count") or webhook_payload.get("agent_count") or 0)
    total_rounds = int(repro_blob.get("total_rounds") or webhook_payload.get("total_rounds") or 0)
    lines.append(f"  mir:agentCount {_ttl_int(agent_count)} ;")
    lines.append(f"  mir:totalRounds {_ttl_int(total_rounds)} ;")

    platforms = repro_blob.get("platforms") or {}
    if isinstance(platforms, dict):
        lines.append(f"  mir:twitterEnabled {_ttl_bool(bool(platforms.get('twitter', False)))} ;")
        lines.append(f"  mir:redditEnabled {_ttl_bool(bool(platforms.get('reddit', False)))} ;")
        lines.append(f"  mir:polymarketEnabled {_ttl_bool(bool(platforms.get('polymarket', False)))} ;")

    consensus = webhook_payload.get("final_consensus")
    if isinstance(consensus, dict):
        if "bullish" in consensus:
            lines.append(f"  mir:bullishPercent {_ttl_decimal(float(consensus.get('bullish') or 0.0))} ;")
        if "neutral" in consensus:
            lines.append(f"  mir:neutralPercent {_ttl_decimal(float(consensus.get('neutral') or 0.0))} ;")
        if "bearish" in consensus:
            lines.append(f"  mir:bearishPercent {_ttl_decimal(float(consensus.get('bearish') or 0.0))} ;")

    quality_health = webhook_payload.get("quality_health")
    if quality_health:
        lines.append(f'  mir:qualityHealth "{_escape_literal(quality_health)}" ;')

    resolution_outcome = webhook_payload.get("resolution_outcome")
    if resolution_outcome:
        lines.append(f'  mir:resolutionOutcome "{_escape_literal(resolution_outcome)}" ;')

    created_at = _ttl_datetime(webhook_payload.get("created_at"))
    if created_at:
        lines.append(f"  mir:createdAt {created_at} ;")
    completed_at = _ttl_datetime(webhook_payload.get("completed_at"))
    if completed_at:
        lines.append(f"  mir:completedAt {completed_at} ;")

    # Lineage: original / fork / counterfactual + parent UAL pointer
    lineage = repro_blob.get("lineage") or {}
    if isinstance(lineage, dict):
        kind = lineage.get("kind") or "original"
        lines.append(f'  mir:lineageKind "{_escape_literal(kind)}" ;')
        parent_id = lineage.get("parent_simulation_id")
        if parent_id:
            lines.append(f'  mir:parentSimulationId "{_escape_literal(parent_id)}" ;')
            lines.append(f"  mir:parentSimulation <{_subject_uri(parent_id)}> ;")
        cf = lineage.get("counterfactual") or {}
        if isinstance(cf, dict) and cf.get("trigger_round"):
            lines.append(f"  mir:counterfactualTriggerRound {_ttl_int(cf.get('trigger_round') or 0)} ;")
            if cf.get("label"):
                lines.append(f'  mir:counterfactualLabel "{_escape_literal(cf.get("label"))}" ;')

    # Citation primitive: the SHA-256 of the reproduce.json bytes plus
    # the canonical fetch URL. The Merkle root the DKG returns is a
    # cryptographic commitment over this Turtle blob; the literal here
    # makes the binding to the *reproduce.json* content explicit.
    lines.append(f'  mir:reproduceConfigSha256 "{_escape_literal(repro_sha)}" ;')
    if base_url:
        base = base_url.rstrip("/")
        lines.append(f"  mir:reproduceConfigUrl <{base}/api/simulation/{simulation_id}/reproduce.json> ;")
        lines.append(f"  mir:shareUrl <{base}/share/{simulation_id}> ;")
        lines.append(f"  mir:shareCardUrl <{base}/api/simulation/{simulation_id}/share-card.png> ;")

    lines.append(f'  mir:publishedAt "{_now_iso()}"^^xsd:dateTime .')

    return "\n".join(lines) + "\n", repro_sha


# ---- Citation file --------------------------------------------------------


def citation_path(sim_dir: str) -> str:
    return os.path.join(sim_dir or "", DKG_CITATION_FILENAME)


def read_citation(sim_dir: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the persisted citation dict, or ``None`` if absent.

    Cheap read used by the EmbedDialog to render the existing citation
    badge without forcing another publish. Never raises.
    """
    if not sim_dir:
        return None
    path = citation_path(sim_dir)
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


_CITATION_WRITE_LOCK = threading.Lock()


def _write_citation(sim_dir: str, payload: Dict[str, Any]) -> None:
    """Persist the citation atomically via tempfile + os.replace.

    Mirrors surface_stats / webhook_log on-disk atomic-write pattern.
    Never raises — a missed write is logged but doesn't break the
    user-facing publish response (the response already carries the UAL).
    """
    if not sim_dir:
        return
    try:
        os.makedirs(sim_dir, exist_ok=True)
    except OSError as exc:
        logger.warning(f"dkg-citation: could not ensure sim_dir for {sim_dir}: {exc}")
        return
    path = citation_path(sim_dir)
    tmp_path = path + ".tmp"
    with _CITATION_WRITE_LOCK:
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp_path, path)
        except OSError as exc:
            logger.warning(f"dkg-citation: write failed for {sim_dir}: {exc}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass


# ---- Publish flow ---------------------------------------------------------


def publish_simulation(
    *,
    simulation_id: str,
    sim_dir: str,
    repro_blob: Dict[str, Any],
    reproduce_json_bytes: bytes,
    webhook_payload: Dict[str, Any],
    base_url: str,
    force: bool = False,
) -> Dict[str, Any]:
    """Anchor a simulation's citation surface on the OriginTrail DKG.

    Idempotent: a successful citation is persisted to
    ``<sim_dir>/dkg-citation.json`` and returned directly on subsequent
    calls unless ``force=True``. Force is plumbed through so a future
    "re-publish after correction" button can re-anchor without an
    operator deleting the file by hand; the UI does not expose it in v1.

    Returns one of these shapes:

      * ``{ok: True, citation: {…}, cached: True}`` — citation already
        on disk, no daemon call made.
      * ``{ok: True, citation: {…}, cached: False}`` — fresh anchor.
      * ``{ok: False, status_code: int, stage: str, error: str}`` —
        anchor failed at ``stage``. Stage values: ``"not_configured"``,
        ``"create"``, ``"write"``, ``"promote"``, ``"publish"``.

    Never raises.
    """
    if not is_configured():
        return {
            "ok": False,
            "status_code": 0,
            "stage": "not_configured",
            "error": "DKG_API_URL / DKG_AUTH_TOKEN / DKG_CONTEXT_GRAPH_ID not set",
        }

    if not force:
        existing = read_citation(sim_dir)
        if existing and existing.get("ual"):
            return {"ok": True, "citation": existing, "cached": True}

    cfg = _resolve_config()
    name = _assertion_name(simulation_id)

    turtle, repro_sha = build_turtle(
        simulation_id=simulation_id,
        repro_blob=repro_blob,
        reproduce_json_bytes=reproduce_json_bytes,
        webhook_payload=webhook_payload,
        base_url=base_url,
    )

    masked = mask_token(cfg["auth_token"])
    logger.info(
        f"dkg-publish: starting {simulation_id} → CG={cfg['context_graph_id']} "
        f"network={cfg['network']} token={masked}"
    )

    # Step 1: create the assertion in Working Memory. Idempotent re-runs
    # after a previous mid-pipeline failure will 409 here — surface that
    # as a clean error rather than masking it as success, since the
    # operator needs to either ``dkg assertion discard`` or pass force.
    ok, status, payload = _request(
        "POST",
        "/api/assertion/create",
        body={"contextGraphId": cfg["context_graph_id"], "name": name},
        timeout=DKG_WRITE_TIMEOUT_SECONDS,
        auth_token=cfg["auth_token"],
        api_url=cfg["api_url"],
    )
    if not ok:
        return _fail("create", status, payload)

    # Step 2: write the Turtle as quads. DKG accepts either Turtle
    # serialization or n-quads on this endpoint; we send Turtle text in
    # the ``quads`` field, which the daemon parses into named-graph
    # quads on the way in.
    ok, status, payload = _request(
        "POST",
        f"/api/assertion/{name}/write",
        body={
            "contextGraphId": cfg["context_graph_id"],
            "quads": turtle,
        },
        timeout=DKG_WRITE_TIMEOUT_SECONDS,
        auth_token=cfg["auth_token"],
        api_url=cfg["api_url"],
    )
    if not ok:
        return _fail("write", status, payload)

    # Step 3: WM → SWM. ``entities: "all"`` promotes everything we just
    # wrote — the simpler default. Per-entity selection exists for
    # cases where an assertion holds drafts plus committed facts; ours
    # is a fresh assertion per publish so all-or-nothing is correct.
    ok, status, payload = _request(
        "POST",
        f"/api/assertion/{name}/promote",
        body={
            "contextGraphId": cfg["context_graph_id"],
            "entities": "all",
        },
        timeout=DKG_WRITE_TIMEOUT_SECONDS,
        auth_token=cfg["auth_token"],
        api_url=cfg["api_url"],
    )
    if not ok:
        return _fail("promote", status, payload)

    # Step 4: SWM → VM. This is the slow path that waits for blockchain
    # finality; bump the timeout. The response carries the citation
    # primitives we hand back to the caller.
    ok, status, payload = _request(
        "POST",
        "/api/shared-memory/publish",
        body={"contextGraphId": cfg["context_graph_id"]},
        timeout=DKG_PUBLISH_TIMEOUT_SECONDS,
        auth_token=cfg["auth_token"],
        api_url=cfg["api_url"],
    )
    if not ok:
        return _fail("publish", status, payload)

    if not isinstance(payload, dict):
        return _fail("publish", status, f"unexpected response shape: {payload!r}")

    ual = payload.get("ual") or ""
    merkle_root = payload.get("merkleRoot") or payload.get("merkle_root") or ""
    tx_hash = payload.get("transactionHash") or payload.get("transaction_hash") or ""
    block_number = payload.get("blockNumber") or payload.get("block_number")
    finalized = bool(payload.get("finalized", False))

    if not ual:
        return _fail("publish", status, f"daemon returned no ual: {payload!r}")

    citation: Dict[str, Any] = {
        "ual": ual,
        "merkle_root": merkle_root,
        "transaction_hash": tx_hash,
        "block_number": block_number if isinstance(block_number, int) else None,
        "finalized": finalized,
        "network": cfg["network"],
        "context_graph_id": cfg["context_graph_id"],
        "assertion_name": name,
        "reproduce_config_sha256": repro_sha,
        "explorer_url": _explorer_url_for(ual, cfg["network"]),
        "published_at": _now_iso(),
        "schema_version": "1",
    }

    _write_citation(sim_dir, citation)
    logger.info(
        f"dkg-publish: ok {simulation_id} → {ual} "
        f"(merkle={merkle_root[:10] if merkle_root else 'n/a'}…, "
        f"tx={tx_hash[:10] if tx_hash else 'n/a'}…)"
    )
    return {"ok": True, "citation": citation, "cached": False}


def _fail(stage: str, status: int, payload: Any) -> Dict[str, Any]:
    """Shape a daemon failure into the structured response.

    ``payload`` is whatever the daemon (or transport) returned. Trim long
    bodies so the response stays a notification-sized blob.
    """
    if isinstance(payload, dict):
        try:
            err_text = json.dumps(payload, ensure_ascii=False)
        except Exception:
            err_text = str(payload)
    else:
        err_text = str(payload) if payload is not None else ""
    if len(err_text) > 800:
        err_text = err_text[:797].rstrip() + "…"
    logger.warning(f"dkg-publish: stage={stage} status={status} error={err_text}")
    return {
        "ok": False,
        "status_code": status,
        "stage": stage,
        "error": err_text or f"DKG daemon returned status {status}",
    }
