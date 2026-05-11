"""Outbound webhook for simulation completion.

Fires a one-shot ``POST {WEBHOOK_URL}`` with a JSON summary the moment a
simulation reaches a terminal state (``completed`` or ``failed``). The URL
is read from ``Config.WEBHOOK_URL`` so a single env var (or a Settings
modal save) wires up Zapier, Make, n8n, IFTTT, Slack via Incoming Webhooks,
Discord via Bot/Channel webhooks, custom dashboards, or a plain Cloud Run
listener — no bot, no OAuth, no hosted infrastructure.

Design notes
------------

* **Fire-and-forget.** Runs in a daemon thread so a slow webhook endpoint
  never delays the simulation runner.
* **Never raises.** Every failure is logged and swallowed. The webhook is
  a *notification*, not a critical path.
* **Idempotent.** Per-process dedup keyed on ``(sim_id, status)`` so the
  exit-code path and the ``simulation_end``-event path in the runner can
  both call this without firing twice.
* **Minimal disk reads.** Reuses the same artifact files the share card
  and gallery card already consume — no DB, no LLM.
* **Stdlib only.** ``urllib.request`` for the POST. No new dependencies.

Payload shape::

    {
      "event": "simulation.completed" | "simulation.failed",
      "sim_id": "sim_xxx",
      "scenario": "Will the SEC approve …",         # truncated to 280 chars
      "status": "completed" | "failed",
      "current_round": 20,
      "total_rounds": 20,
      "agent_count": 248,
      "quality_health": "Excellent" | null,
      "final_consensus": {                            # null if no trajectory
        "bullish": 62.0,
        "neutral": 13.0,
        "bearish": 25.0
      },
      "resolution_outcome": "YES" | null,
      "share_path": "/share/sim_xxx",
      "share_card_path": "/api/simulation/sim_xxx/share-card.png",
      "share_url": "https://host/share/sim_xxx",     # only if PUBLIC_BASE_URL set
      "share_card_url": "https://host/...png",       # only if PUBLIC_BASE_URL set
      "created_at": "2026-04-26T10:12:34",
      "completed_at": "2026-04-26T10:35:11",
      "fired_at": "2026-04-26T10:35:12.482912+00:00"
    }
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger('miroshark.webhook')


WEBHOOK_USER_AGENT = "MiroShark-Webhook/1.0"
WEBHOOK_TIMEOUT_SECONDS = 5.0
WEBHOOK_MAX_SCENARIO_CHARS = 280

# ---- HMAC signing -----------------------------------------------------
#
# When ``WEBHOOK_SECRET`` is set, every dispatched payload is signed with
# ``hmac-sha256(secret, body_bytes)`` and the signature is shipped as the
# ``X-MiroShark-Signature`` header so the recipient can prove the
# payload actually came from this MiroShark instance and wasn't spoofed
# en route. Same scheme Stripe and GitHub use — operators verify with
# three lines of stdlib ``hmac``.
#
# Backward compatible: when ``WEBHOOK_SECRET`` is unset or empty, the
# header is omitted and existing integrations keep working unchanged.
WEBHOOK_SECRET_ENV_VAR = "WEBHOOK_SECRET"
SIGNATURE_HEADER = "X-MiroShark-Signature"
SIGNATURE_PREFIX = "sha256="

# ---- Delivery log (per-simulation) -------------------------------------
#
# Every dispatch attempt — auto-fired from the runner OR manually
# replayed from the ``/webhook-retry`` endpoint — appends one JSON line
# to ``<sim_dir>/webhook-log.jsonl``. The log gives operators a feedback
# loop they didn't have before PR #46 shipped: "did the webhook fire?",
# "what status did the endpoint return?", "how long did it take?",
# "should I retry?". A 50-line cap with read-modify-write trim keeps
# disk usage bounded — operators can always retry past failures from a
# clean state.
WEBHOOK_LOG_FILENAME = "webhook-log.jsonl"
WEBHOOK_LOG_MAX_LINES = 50
WEBHOOK_LOG_RETURN_LIMIT = 10


# Per-process dedup. The runner's exit-code path and the ``simulation_end``
# event path can both fire for the same terminal status — keep only the
# first one per (sim_id, status). Bounded to avoid unbounded growth in
# very long-lived processes.
_FIRED: set[Tuple[str, str]] = set()
_FIRED_LOCK = threading.Lock()
_FIRED_MAX = 4096

# Serializes the read-modify-rename in `_append_log_entry`. Without it,
# two concurrent dispatches (auto-fire racing a manual retry, or two
# retries clicked back-to-back) both read `existing` and both
# `os.replace`, silently dropping the loser's entry — exactly the
# visibility failure this log is meant to surface.
_LOG_WRITE_LOCK = threading.Lock()

# Per-(sim_id) retry cooldown for the manual retry endpoint. Caps any
# single sim to one queued retry per ``RETRY_COOLDOWN_SEC`` window so a
# leaked admin token can't be weaponized as a low-volume amplifier
# against the configured Slack/Discord/n8n endpoint.
RETRY_COOLDOWN_SEC = 5.0
_LAST_RETRY_AT: Dict[str, float] = {}
_RETRY_LOCK = threading.Lock()


def claim_retry_slot(simulation_id: str, now: Optional[float] = None) -> Optional[float]:
    """Reserve a retry slot for ``simulation_id``.

    Returns ``None`` if the call is allowed (caller may proceed); returns
    the number of seconds remaining in the cooldown window if rate-limited.
    """
    import time
    ts = now if now is not None else time.monotonic()
    with _RETRY_LOCK:
        last = _LAST_RETRY_AT.get(simulation_id, 0.0)
        elapsed = ts - last
        if elapsed < RETRY_COOLDOWN_SEC:
            return RETRY_COOLDOWN_SEC - elapsed
        _LAST_RETRY_AT[simulation_id] = ts
        # Bound dict growth — drop one arbitrary expired entry per claim.
        if len(_LAST_RETRY_AT) > 4096:
            for sid, last_ts in list(_LAST_RETRY_AT.items()):
                if ts - last_ts >= RETRY_COOLDOWN_SEC:
                    _LAST_RETRY_AT.pop(sid, None)
                    break
        return None


def reset_retry_cooldown_for_tests() -> None:
    """Clear the per-sim retry cooldown table. Test-only convenience."""
    with _RETRY_LOCK:
        _LAST_RETRY_AT.clear()


def _mark_fired(sim_id: str, status: str) -> bool:
    """Record (sim_id, status) and return True if this is the first time."""
    key = (sim_id, status)
    with _FIRED_LOCK:
        if key in _FIRED:
            return False
        if len(_FIRED) >= _FIRED_MAX:
            # Drop one arbitrary entry to bound memory. Cheap; we don't
            # need LRU semantics for a notification dedup.
            _FIRED.pop()
        _FIRED.add(key)
        return True


def reset_dedup_for_tests() -> None:
    """Clear the in-process dedup set. Test-only convenience."""
    with _FIRED_LOCK:
        _FIRED.clear()


def mask_url(url: str) -> str:
    """Show only the scheme + host of a webhook URL.

    The full URL often carries an opaque secret in the path
    (``hooks.slack.com/services/T0…/B0…/abcXYZ``); never echo it back to
    the frontend. ``https://hooks.slack.com/services/T0…/***`` is enough
    for the user to recognize their own hook.
    """
    if not url:
        return ''
    try:
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return '***'
        return f"{parts.scheme}://{parts.netloc}/***"
    except Exception:
        return '***'


def webhook_log_path(sim_dir: str) -> str:
    """Absolute path to the per-sim webhook delivery log."""
    return os.path.join(sim_dir, WEBHOOK_LOG_FILENAME)


def _read_log_lines(sim_dir: str) -> List[str]:
    """Return the raw, non-empty lines of the log (preserving order).

    Never raises — a missing or unreadable log is treated as empty so
    the dispatch path stays fire-and-forget.
    """
    path = webhook_log_path(sim_dir)
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return [line for line in f.readlines() if line.strip()]
    except OSError:
        return []


def _parse_log_entries(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse JSONL lines, silently skipping anything malformed."""
    entries: List[Dict[str, Any]] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except Exception:
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _next_attempt_number(sim_dir: str) -> int:
    """1-based attempt counter — picks ``max(attempt) + 1`` from disk.

    Returns 1 when the log is missing or empty. Used so the GET endpoint
    can show ``attempt #N`` on each delivery without callers needing to
    pre-compute it.
    """
    entries = _parse_log_entries(_read_log_lines(sim_dir))
    last = 0
    for rec in entries:
        attempt = rec.get('attempt')
        if isinstance(attempt, int) and attempt > last:
            last = attempt
    return last + 1


def _append_log_entry(sim_dir: str, entry: Dict[str, Any]) -> None:
    """Append ``entry`` as a JSON line; trim to ``WEBHOOK_LOG_MAX_LINES``.

    Never raises — log writes are best-effort. If the log already has
    ``WEBHOOK_LOG_MAX_LINES`` rows, the oldest get dropped via a
    read-modify-rename so the new entry always lands.
    """
    if not sim_dir:
        return
    try:
        os.makedirs(sim_dir, exist_ok=True)
    except OSError as exc:
        logger.warning(f"webhook-log: could not ensure sim_dir for {sim_dir}: {exc}")
        return

    path = webhook_log_path(sim_dir)
    try:
        serialized = json.dumps(entry, ensure_ascii=False) + "\n"
    except Exception as exc:
        logger.warning(f"webhook-log: refusing unserializable entry for {sim_dir}: {exc}")
        return

    # Lock the read-modify-rename window so concurrent dispatches don't
    # both read the same `existing` and clobber each other's entries.
    with _LOG_WRITE_LOCK:
        try:
            existing = _read_log_lines(sim_dir)
            if len(existing) >= WEBHOOK_LOG_MAX_LINES:
                keep = existing[-(WEBHOOK_LOG_MAX_LINES - 1):]
                tmp_path = path + ".tmp"
                try:
                    with open(tmp_path, 'w', encoding='utf-8') as f:
                        f.writelines(keep)
                        f.write(serialized)
                    os.replace(tmp_path, path)
                finally:
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
            else:
                with open(path, 'a', encoding='utf-8') as f:
                    f.write(serialized)
        except OSError as exc:
            logger.warning(f"webhook-log: write failed for {sim_dir}: {exc}")


def _parse_status_code_from_message(msg: Optional[str]) -> Optional[int]:
    """Extract the integer HTTP status from an ``HTTP <N>`` message.

    Returns ``None`` for network errors / serialization failures /
    anything that isn't a numeric HTTP response — those cases land in
    the log with ``status_code: null`` so consumers can distinguish
    them from a real 5xx.
    """
    if not isinstance(msg, str):
        return None
    if msg.startswith("HTTP "):
        try:
            return int(msg.split(" ", 1)[1].strip())
        except (ValueError, IndexError):
            return None
    return None


def read_webhook_log(
    sim_dir: str,
    *,
    limit: int = WEBHOOK_LOG_RETURN_LIMIT,
) -> Dict[str, Any]:
    """Public read API for ``GET /webhook-log``.

    Returns the most recent ``limit`` entries newest-first plus the
    total attempt count. ``max_retained`` is exposed so the EmbedDialog
    can show "showing last N of M (max retained K)".
    """
    entries = _parse_log_entries(_read_log_lines(sim_dir))
    total_attempts = 0
    for rec in entries:
        attempt = rec.get('attempt')
        if isinstance(attempt, int) and attempt > total_attempts:
            total_attempts = attempt
    sliced = entries[-max(limit, 0):] if limit > 0 else entries
    sliced.reverse()  # newest first
    return {
        "entries": sliced,
        "total_attempts": total_attempts,
        "max_retained": WEBHOOK_LOG_MAX_LINES,
    }


def _record_delivery(
    *,
    sim_dir: Optional[str],
    url: str,
    payload: Dict[str, Any],
    ok: bool,
    message: str,
    latency_ms: int,
    trigger: str,
) -> None:
    """Persist a single delivery attempt to ``webhook-log.jsonl``.

    ``trigger`` is ``"auto"`` for the runner-fired path and ``"retry"``
    for the manual replay endpoint — useful when an operator scans the
    log to tell automatic vs manual deliveries apart.
    """
    if not sim_dir:
        return
    status_code = _parse_status_code_from_message(message)
    error = None if ok else message
    entry: Dict[str, Any] = {
        "attempt": _next_attempt_number(sim_dir),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url_masked": mask_url(url),
        "event": payload.get("event"),
        "status": payload.get("status"),
        "status_code": status_code,
        "ok": bool(ok),
        "latency_ms": int(latency_ms) if latency_ms is not None else None,
        "error": error,
        "trigger": trigger,
    }
    _append_log_entry(sim_dir, entry)


def _resolve_webhook_secret() -> str:
    """Read ``WEBHOOK_SECRET`` at call time.

    Late binding mirrors :func:`_resolve_webhook_url` so a Settings change
    or an ``os.environ`` mutation takes effect immediately without
    re-importing the module.
    """
    return (os.environ.get(WEBHOOK_SECRET_ENV_VAR, "") or "").strip()


def compute_signature(
    payload_bytes: bytes,
    secret: Optional[str] = None,
) -> Optional[str]:
    """Return ``sha256=<hex>`` for ``payload_bytes`` under ``secret``.

    ``secret`` defaults to the ``WEBHOOK_SECRET`` env var. A blank /
    missing secret returns ``None`` — the dispatcher then omits the
    signature header entirely so existing integrations stay
    backward-compatible.
    """
    if secret is None:
        secret = _resolve_webhook_secret()
    if not secret:
        return None
    digest = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def verify_signature(
    payload_bytes: bytes,
    header_value: Optional[str],
    secret: str,
) -> bool:
    """Constant-time verification helper for recipients.

    Returns ``True`` iff ``header_value`` is the signature this
    MiroShark instance would emit for ``payload_bytes`` under ``secret``.
    Uses :func:`hmac.compare_digest` so a network attacker can't time-
    trial the comparison.

    This function is published so the docs can point operators at one
    canonical implementation — the recipient-side check is symmetric
    with :func:`compute_signature` and never needs to diverge.
    """
    if not header_value or not secret:
        return False
    expected = compute_signature(payload_bytes, secret)
    if expected is None:
        return False
    return hmac.compare_digest(expected, header_value)


def validate_url(url: str) -> Optional[str]:
    """Return ``None`` if the URL is acceptable, else an error message.

    Empty string is valid (treated as "disable webhook").
    """
    if not url:
        return None
    if not isinstance(url, str):
        return "Webhook URL must be a string"
    stripped = url.strip()
    if not stripped:
        return None
    if len(stripped) > 2048:
        return "Webhook URL is too long (max 2048 chars)"
    lowered = stripped.lower()
    if not (lowered.startswith('http://') or lowered.startswith('https://')):
        return "Webhook URL must start with http:// or https://"
    return None


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON load — returns ``None`` on any failure."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _final_consensus_from_trajectory(trajectory: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """Walk the trajectory snapshots in reverse and pick the last one with
    computable belief positions, then bucket stances into bullish / neutral
    / bearish percentages.

    Mirrors the same threshold (±0.2) used by the gallery / share-card
    helpers so the consensus the webhook reports matches what users see
    in the share card image.
    """
    if not trajectory:
        return None
    snapshots = trajectory.get("snapshots") or []
    if not isinstance(snapshots, list):
        return None
    for snap in reversed(snapshots):
        positions = (snap or {}).get("belief_positions") or {}
        if not positions:
            continue
        stances = []
        for p in positions.values():
            if p:
                stances.append(sum(p.values()) / len(p))
        if not stances:
            continue
        total = len(stances)
        nb = sum(1 for s in stances if s > 0.2)
        nbe = sum(1 for s in stances if s < -0.2)
        nn = total - nb - nbe
        return {
            "bullish": round(nb / total * 100, 1),
            "neutral": round(nn / total * 100, 1),
            "bearish": round(nbe / total * 100, 1),
        }
    return None


def build_payload(
    simulation_id: str,
    status: str,
    sim_dir: str,
    *,
    state: Optional[Any] = None,
    base_url: Optional[str] = None,
    completed_at: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the webhook JSON payload for one simulation.

    Reads ``simulation_config.json``, ``quality.json``, ``trajectory.json``,
    ``resolution.json``, ``state.json`` from ``sim_dir`` — every artifact
    is optional. Missing files degrade gracefully into ``None`` /
    sensible defaults; the webhook always fires with at least the
    identifier and status.

    ``state`` is the optional in-memory ``SimulationState``-like object
    the runner already has — when provided, ``agent_count``,
    ``created_at``, and ``parent_simulation_id`` come from there;
    otherwise they're loaded from ``state.json``.
    """
    config = _read_json(os.path.join(sim_dir, "simulation_config.json"))
    quality = _read_json(os.path.join(sim_dir, "quality.json"))
    trajectory = _read_json(os.path.join(sim_dir, "trajectory.json"))
    resolution = _read_json(os.path.join(sim_dir, "resolution.json"))
    on_disk_state = _read_json(os.path.join(sim_dir, "state.json"))

    scenario = ""
    total_rounds = 0
    if config:
        scenario = (config.get("simulation_requirement") or "").strip()
        time_config = config.get("time_config") or {}
        try:
            mpr = max(int(time_config.get("minutes_per_round", 60) or 60), 1)
            hours = int(time_config.get("total_simulation_hours", 0) or 0)
            total_rounds = int(hours * 60 / mpr)
        except Exception:
            total_rounds = 0
    if scenario and len(scenario) > WEBHOOK_MAX_SCENARIO_CHARS:
        scenario = scenario[:WEBHOOK_MAX_SCENARIO_CHARS - 1].rstrip() + "…"

    # Prefer the live in-memory state object when the caller has one —
    # it's freshly written, no race with disk flushes.
    agent_count = 0
    created_at = None
    parent_simulation_id = None
    current_round = 0
    if state is not None:
        agent_count = getattr(state, "profiles_count", 0) or 0
        created_at = getattr(state, "created_at", None)
        parent_simulation_id = getattr(state, "parent_simulation_id", None)
        current_round = getattr(state, "current_round", 0) or 0
        runner_total = getattr(state, "total_rounds", 0) or 0
        if runner_total:
            total_rounds = runner_total
    if (agent_count == 0 or created_at is None) and on_disk_state:
        if not agent_count:
            agent_count = on_disk_state.get("profiles_count") or 0
        if created_at is None:
            created_at = on_disk_state.get("created_at")
        if parent_simulation_id is None:
            parent_simulation_id = on_disk_state.get("parent_simulation_id")

    quality_health = (quality or {}).get("health")
    resolution_outcome = (resolution or {}).get("actual_outcome")
    final_consensus = _final_consensus_from_trajectory(trajectory)

    share_path = f"/share/{simulation_id}"
    share_card_path = f"/api/simulation/{simulation_id}/share-card.png"

    payload: Dict[str, Any] = {
        "event": f"simulation.{status}",
        "sim_id": simulation_id,
        "scenario": scenario,
        "status": status,
        "current_round": current_round,
        "total_rounds": total_rounds,
        "agent_count": agent_count,
        "quality_health": quality_health,
        "final_consensus": final_consensus,
        "resolution_outcome": resolution_outcome,
        "share_path": share_path,
        "share_card_path": share_card_path,
        "created_at": created_at,
        "completed_at": completed_at,
        "parent_simulation_id": parent_simulation_id,
        "fired_at": datetime.now(timezone.utc).isoformat(),
    }

    if error:
        # Trim long stack traces — the webhook payload is meant for a
        # notification body, not full debug output.
        err_text = str(error)
        if len(err_text) > 1000:
            err_text = err_text[:997].rstrip() + "…"
        payload["error"] = err_text

    if base_url:
        base = base_url.rstrip('/')
        payload["share_url"] = f"{base}{share_path}"
        payload["share_card_url"] = f"{base}{share_card_path}"

    return payload


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> Tuple[bool, str]:
    """Issue the POST. Returns ``(ok, message)`` — never raises."""
    try:
        body = json.dumps(payload).encode('utf-8')
    except Exception as exc:
        return False, f"Could not serialize payload: {exc}"

    headers: Dict[str, str] = {
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': WEBHOOK_USER_AGENT,
        'X-MiroShark-Event': payload.get('event', 'simulation.unknown'),
        'X-MiroShark-Sim-Id': payload.get('sim_id', ''),
    }
    signature = compute_signature(body)
    if signature is not None:
        headers[SIGNATURE_HEADER] = signature

    req = urllib.request.Request(
        url,
        data=body,
        method='POST',
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            if 200 <= status_code < 300:
                return True, f"HTTP {status_code}"
            return False, f"HTTP {status_code}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, 'reason', exc)
        return False, f"URL error: {reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _resolve_webhook_url() -> str:
    """Read the configured webhook URL — late-binding so runtime Settings
    updates take effect immediately without needing to re-import."""
    try:
        from ..config import Config
        return (getattr(Config, 'WEBHOOK_URL', '') or '').strip()
    except Exception:
        return ''


def _resolve_base_url() -> str:
    """Read PUBLIC_BASE_URL — used to build absolute ``share_url`` /
    ``share_card_url`` fields when no Flask request context is available
    (the runner fires from a background thread)."""
    try:
        from ..config import Config
        return (getattr(Config, 'PUBLIC_BASE_URL', '') or '').strip()
    except Exception:
        return ''


def fire_webhook_for_simulation(
    simulation_id: str,
    status: str,
    *,
    sim_dir: Optional[str] = None,
    state: Optional[Any] = None,
    completed_at: Optional[str] = None,
    error: Optional[str] = None,
    base_url: Optional[str] = None,
) -> None:
    """Fire-and-forget webhook for a simulation that just reached a
    terminal state.

    Safe to call from inside the simulation monitor thread — work happens
    in its own daemon thread. No-op if no webhook URL is configured or if
    this (sim_id, status) pair has already fired in this process.
    """
    if status not in {"completed", "failed"}:
        logger.warning(f"Webhook ignored — unsupported status: {status}")
        return

    url = _resolve_webhook_url()
    if not url:
        return

    if not _mark_fired(simulation_id, status):
        return

    if sim_dir is None:
        # Mirror the path SimulationRunner.RUN_STATE_DIR uses.
        try:
            from ..config import Config
            sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        except Exception:
            sim_dir = simulation_id

    if base_url is None:
        base_url = _resolve_base_url()

    payload = build_payload(
        simulation_id,
        status,
        sim_dir,
        state=state,
        base_url=base_url,
        completed_at=completed_at,
        error=error,
    )

    _start_dispatch_thread(
        url=url,
        payload=payload,
        sim_dir=sim_dir,
        trigger="auto",
        thread_name=f'webhook-{simulation_id}',
    )


def _start_dispatch_thread(
    *,
    url: str,
    payload: Dict[str, Any],
    sim_dir: Optional[str],
    trigger: str,
    thread_name: str,
) -> None:
    """Launch the daemon thread that POSTs ``payload`` and records a log
    entry on the way out.

    Shared between the automatic ``fire_webhook_for_simulation`` path
    and the manual ``retry_webhook_for_simulation`` path so the timing,
    masking, and log shape stay identical.
    """
    sim_id = payload.get("sim_id", "")
    status = payload.get("status", "")

    def _send() -> None:
        started = time.monotonic()
        ok, msg = _post_json(url, payload, WEBHOOK_TIMEOUT_SECONDS)
        latency_ms = int((time.monotonic() - started) * 1000)

        masked = mask_url(url)
        if ok:
            logger.info(
                f"Webhook fired for {sim_id} ({status}) → {masked} "
                f"[{msg} · {latency_ms}ms · {trigger}]"
            )
        else:
            logger.warning(
                f"Webhook delivery failed for {sim_id} ({status}) → {masked}: "
                f"{msg} ({latency_ms}ms · {trigger})"
            )

        try:
            _record_delivery(
                sim_dir=sim_dir,
                url=url,
                payload=payload,
                ok=ok,
                message=msg,
                latency_ms=latency_ms,
                trigger=trigger,
            )
        except Exception as exc:
            # Never let a logging failure take the dispatch thread down.
            logger.warning(f"webhook-log: record_delivery failed for {sim_id}: {exc}")

    threading.Thread(
        target=_send,
        daemon=True,
        name=thread_name,
    ).start()


def retry_webhook_for_simulation(
    simulation_id: str,
    status: str,
    *,
    sim_dir: Optional[str] = None,
    state: Optional[Any] = None,
    completed_at: Optional[str] = None,
    error: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Manually re-dispatch the completion webhook for a finished sim.

    Mirrors :func:`fire_webhook_for_simulation` but **bypasses the
    per-process ``(sim_id, status)`` dedup set** — operators retry
    precisely when the original auto-fire failed (or hit the wrong
    endpoint), so blocking the second attempt would defeat the
    purpose. Dedup exists only to prevent the runner's two terminal
    code paths from double-firing automatically.

    Returns ``{queued, attempt_will_be, sim_id, status, url_masked,
    error?}``. Returns ``{queued: False}`` when no webhook URL is
    configured — the caller should surface a clear "configure your
    webhook URL first" error.
    """
    if status not in {"completed", "failed"}:
        return {"queued": False, "error": f"unsupported status: {status}"}

    url = _resolve_webhook_url()
    if not url:
        return {"queued": False, "error": "no webhook URL configured"}

    if sim_dir is None:
        try:
            from ..config import Config
            sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        except Exception:
            sim_dir = simulation_id

    if base_url is None:
        base_url = _resolve_base_url()

    payload = build_payload(
        simulation_id,
        status,
        sim_dir,
        state=state,
        base_url=base_url,
        completed_at=completed_at,
        error=error,
    )
    payload["retry"] = True

    attempt_will_be = _next_attempt_number(sim_dir)

    _start_dispatch_thread(
        url=url,
        payload=payload,
        sim_dir=sim_dir,
        trigger="retry",
        thread_name=f'webhook-retry-{simulation_id}',
    )

    return {
        "queued": True,
        "attempt_will_be": attempt_will_be,
        "sim_id": simulation_id,
        "status": status,
        "url_masked": mask_url(url),
    }


def send_test_webhook(url: str, base_url: Optional[str] = None) -> Dict[str, Any]:
    """Synchronously POST a sample payload to ``url`` and return the
    result. Used by the Settings ``Send test event`` button so the user
    gets immediate feedback on whether their endpoint is reachable.

    Returns ``{ok, message, status_code, latency_ms}``.
    """
    err = validate_url(url)
    if err:
        return {"ok": False, "message": err}
    if not url.strip():
        return {"ok": False, "message": "Webhook URL is empty"}

    payload = {
        "event": "simulation.test",
        "sim_id": "sim_test_event",
        "scenario": "Test event from MiroShark — your webhook is configured correctly.",
        "status": "test",
        "current_round": 0,
        "total_rounds": 0,
        "agent_count": 0,
        "quality_health": None,
        "final_consensus": None,
        "resolution_outcome": None,
        "share_path": "/share/sim_test_event",
        "share_card_path": "/api/simulation/sim_test_event/share-card.png",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "parent_simulation_id": None,
        "fired_at": datetime.now(timezone.utc).isoformat(),
        "test": True,
    }
    if base_url:
        base = base_url.rstrip('/')
        payload["share_url"] = f"{base}/share/sim_test_event"
        payload["share_card_url"] = f"{base}/api/simulation/sim_test_event/share-card.png"

    started = datetime.now()
    ok, msg = _post_json(url.strip(), payload, WEBHOOK_TIMEOUT_SECONDS)
    latency_ms = int((datetime.now() - started).total_seconds() * 1000)

    return {
        "ok": ok,
        "message": msg,
        "latency_ms": latency_ms,
    }
