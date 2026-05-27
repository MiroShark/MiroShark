"""Slack Block Kit notification on simulation completion.

Companion to :mod:`webhook_service` — same shape as
:mod:`discord_notify` but emits a Slack-native Block Kit message
instead of a Discord embed. Operators wiring MiroShark into a Slack
workspace set ``SLACK_WEBHOOK_URL`` and start receiving formatted
cards (scenario header, belief block-bars, quality + agent fields,
"View simulation" link button) in the configured channel.

The generic webhook (PR #46) already accepts a Slack Incoming Webhook
URL, but Slack renders a raw JSON post as a code-block dump — fine
for debugging, useless as a real notification. This module emits the
Block Kit JSON Slack expects so the message renders as a proper
channel card.

Design notes
------------

* **Fire-and-forget.** Daemon-thread dispatch, never raises. The
  simulation runner is unaffected by a slow or broken Slack endpoint.
* **Opt-in.** ``SLACK_WEBHOOK_URL`` unset ⇒ no-op. Existing
  deployments are unchanged.
* **Per-process dedup.** ``(sim_id, status)`` keyed; the runner's
  two terminal code paths both call into us but Slack only sees one
  message per terminal state.
* **Reuses ``build_payload``.** All artifact reads live in
  :mod:`webhook_service`. The Block Kit builder is a pure
  projection over the same dict the generic webhook ships.
* **Unicode block-bars, no images.** Slack renders block characters
  in ``mrkdwn`` natively — no image-host round-trip, no thumbnail
  fetch latency. The bars degrade cleanly into plain text in mobile
  notifications.
* **Stdlib only.** ``urllib.request`` + ``json`` + ``os``. No new
  dependencies.

Message shape (Block Kit ``blocks``)::

    [
      {"type": "header", "text": {...scenario...}},
      {"type": "context", "elements": [{"type": "mrkdwn", "text": "*Status:* …"}]},
      {"type": "section", "fields": [
        {"type": "mrkdwn", "text": "*Bullish*\\n█████░░░░░ 52.0%"},
        ...
      ]},
      {"type": "actions", "elements": [{"type": "button", ...}]}
    ]
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .simulation_runner import SimulationRunState

logger = get_logger('miroshark.slack_notify')


SLACK_WEBHOOK_URL_ENV_VAR = "SLACK_WEBHOOK_URL"
SLACK_USER_AGENT = "MiroShark-SlackNotify/1.0"
SLACK_TIMEOUT_SECONDS = 5.0

# Slack header blocks cap at 150 chars; the SPA truncates scenario
# previews to 120 in most surfaces, so 120 is the safer match.
SLACK_HEADER_MAX_CHARS = 120

# Unicode full-/empty-block characters. ``mrkdwn`` renders both
# faithfully across desktop + mobile clients.
BAR_FILLED = "█"
BAR_EMPTY = "░"
BAR_WIDTH = 10


_FIRED: set[Tuple[str, str]] = set()
_FIRED_LOCK = threading.Lock()
_FIRED_MAX = 4096


def _mark_fired(sim_id: str, status: str) -> bool:
    key = (sim_id, status)
    with _FIRED_LOCK:
        if key in _FIRED:
            return False
        if len(_FIRED) >= _FIRED_MAX:
            _FIRED.pop()
        _FIRED.add(key)
        return True


def reset_dedup_for_tests() -> None:
    """Clear the in-process dedup set. Test-only convenience."""
    with _FIRED_LOCK:
        _FIRED.clear()


def _resolve_webhook_url() -> str:
    return (os.environ.get(SLACK_WEBHOOK_URL_ENV_VAR, "") or "").strip()


def is_configured() -> bool:
    """``True`` iff ``SLACK_WEBHOOK_URL`` is set to a non-empty value."""
    return bool(_resolve_webhook_url())


def belief_bar(pct: float, width: int = BAR_WIDTH) -> str:
    """Render a horizontal block-bar for ``pct`` (a value in [0, 100]).

    Width is the number of glyphs, not characters of label. The
    trailing label always shows the rounded percentage with one
    decimal place, matching how the SPA renders the same number.
    """
    try:
        value = float(pct)
    except (TypeError, ValueError):
        value = 0.0
    if value < 0.0:
        value = 0.0
    if value > 100.0:
        value = 100.0

    filled_count = int(round((value / 100.0) * max(int(width), 1)))
    if filled_count < 0:
        filled_count = 0
    if filled_count > width:
        filled_count = width
    empty_count = width - filled_count
    bar = (BAR_FILLED * filled_count) + (BAR_EMPTY * empty_count)
    return f"{bar} {value:.1f}%"


def _truncate(value: str, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)].rstrip() + "…"


def _resolve_share_url(payload: Dict[str, Any]) -> Optional[str]:
    """Prefer the absolute ``share_url`` — Slack only renders button URLs
    for absolute ``http(s)://`` values.
    """
    abs_url = payload.get("share_url")
    if isinstance(abs_url, str) and abs_url.strip():
        s = abs_url.strip()
        if s.startswith("http://") or s.startswith("https://"):
            return s
    return None


def _status_verb(status: str) -> str:
    if status == "completed":
        return "Completed"
    if status == "failed":
        return "Failed"
    if status == "test":
        return "Test event"
    return status.title() or "Unknown"


def build_slack_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble the Block Kit ``{blocks: [...]}`` body for ``payload``."""
    sim_id = str(payload.get("sim_id") or "")
    status = str(payload.get("status") or "")

    scenario = _truncate(
        str(payload.get("scenario") or "").strip(),
        SLACK_HEADER_MAX_CHARS,
    )
    if not scenario:
        scenario = f"Simulation {sim_id}" if sim_id else "MiroShark simulation"

    blocks: list[Dict[str, Any]] = []

    # 1. Header — the scenario, rendered large.
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": scenario,
            "emoji": True,
        },
    })

    # 2. Context — status verb + sim id (small grey text).
    verb = _status_verb(status)
    ctx_text = f"*{verb}*  ·  `{sim_id}`" if sim_id else f"*{verb}*"
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": ctx_text},
        ],
    })

    # 3. Belief bars — only when a trajectory was available.
    consensus = payload.get("final_consensus") or {}
    fields: list[Dict[str, Any]] = []
    if isinstance(consensus, dict) and consensus:
        bullish = consensus.get("bullish")
        neutral = consensus.get("neutral")
        bearish = consensus.get("bearish")
        try:
            b = float(bullish) if bullish is not None else 0.0
            n = float(neutral) if neutral is not None else 0.0
            r = float(bearish) if bearish is not None else 0.0
            has_any = b > 0.0 or n > 0.0 or r > 0.0
        except (TypeError, ValueError):
            has_any = False
        if has_any:
            fields.extend([
                {"type": "mrkdwn", "text": f"*Bullish*\n`{belief_bar(bullish)}`"},
                {"type": "mrkdwn", "text": f"*Neutral*\n`{belief_bar(neutral)}`"},
                {"type": "mrkdwn", "text": f"*Bearish*\n`{belief_bar(bearish)}`"},
            ])

    quality_health = payload.get("quality_health")
    if isinstance(quality_health, str) and quality_health:
        fields.append({"type": "mrkdwn", "text": f"*Quality*\n{quality_health}"})

    total_rounds = payload.get("total_rounds")
    agent_count = payload.get("agent_count")
    rounds_text_parts: list[str] = []
    if isinstance(agent_count, int) and agent_count > 0:
        rounds_text_parts.append(f"{agent_count} agents")
    if isinstance(total_rounds, int) and total_rounds > 0:
        rounds_text_parts.append(f"{total_rounds} rounds")
    if rounds_text_parts:
        fields.append({
            "type": "mrkdwn",
            "text": "*Scale*\n" + " · ".join(rounds_text_parts),
        })

    resolution_outcome = payload.get("resolution_outcome")
    if isinstance(resolution_outcome, str) and resolution_outcome:
        fields.append({
            "type": "mrkdwn",
            "text": f"*Resolution*\n{resolution_outcome}",
        })

    if fields:
        # Slack section blocks cap fields at 10 entries. Belief +
        # quality + scale + resolution is at most 6, so we're always
        # safely under, but be defensive against future drift.
        blocks.append({
            "type": "section",
            "fields": fields[:10],
        })

    if status == "failed":
        err_text = str(payload.get("error") or "").strip()
        if err_text:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error*\n```{_truncate(err_text, 800)}```",
                },
            })

    # 4. "View simulation" action button — only when we have an
    # absolute URL. Slack rejects buttons whose URL isn't http(s)://.
    share_url = _resolve_share_url(payload)
    if share_url:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View simulation",
                        "emoji": True,
                    },
                    "url": share_url,
                    "action_id": "view_simulation",
                },
            ],
        })

    return {"blocks": blocks}


def _post_json(url: str, body: Dict[str, Any], timeout: float) -> Tuple[bool, str]:
    """Issue the POST. Returns ``(ok, message)`` — never raises."""
    try:
        encoded = json.dumps(body).encode("utf-8")
    except Exception as exc:
        return False, f"Could not serialize Slack payload: {exc}"

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": SLACK_USER_AGENT,
    }
    req = urllib.request.Request(url, data=encoded, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            if 200 <= code < 300:
                return True, f"HTTP {code}"
            return False, f"HTTP {code}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"URL error: {reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def send_slack_payload(url: str, message: Dict[str, Any]) -> Tuple[bool, str]:
    """Synchronously POST one Block Kit message. Never raises."""
    if not url:
        return False, "Slack webhook URL is empty"
    return _post_json(url, message, SLACK_TIMEOUT_SECONDS)


def _start_dispatch_thread(url: str, message: Dict[str, Any], thread_name: str) -> None:
    def _send() -> None:
        ok, msg = send_slack_payload(url, message)
        # Pull the scenario out of the header block for the log line.
        header_text = ""
        for blk in message.get("blocks", []):
            if blk.get("type") == "header":
                header_text = blk.get("text", {}).get("text", "") or ""
                break
        if ok:
            logger.info(f"Slack notify ok ({msg}) — {header_text}")
        else:
            logger.warning(f"Slack notify failed ({msg}) — {header_text}")

    threading.Thread(target=_send, daemon=True, name=thread_name).start()


def notify_if_configured(
    simulation_id: str,
    status: str,
    *,
    sim_dir: Optional[str] = None,
    state: Optional[SimulationRunState] = None,
    completed_at: Optional[str] = None,
    error: Optional[str] = None,
    base_url: Optional[str] = None,
) -> None:
    """Fire-and-forget Slack Block Kit dispatch for a finished sim.

    Same contract as :func:`discord_notify.notify_if_configured`. No-op
    when ``SLACK_WEBHOOK_URL`` is unset or when this
    ``(sim_id, status)`` already fired in this process.
    """
    if status not in {"completed", "failed"}:
        return

    url = _resolve_webhook_url()
    if not url:
        return

    if not _mark_fired(simulation_id, status):
        return

    from . import webhook_service

    if sim_dir is None:
        try:
            from ..config import Config
            sim_dir = os.path.join(
                Config.WONDERWALL_SIMULATION_DATA_DIR,
                simulation_id,
            )
        except Exception:
            sim_dir = simulation_id

    if base_url is None:
        base_url = webhook_service._resolve_base_url()

    try:
        payload = webhook_service.build_payload(
            simulation_id,
            status,
            sim_dir,
            state=state,
            base_url=base_url,
            completed_at=completed_at,
            error=error,
        )
    except Exception as exc:
        logger.warning(f"Slack notify: build_payload failed for {simulation_id}: {exc}")
        return

    try:
        message = build_slack_message(payload)
    except Exception as exc:
        logger.warning(f"Slack notify: message build failed for {simulation_id}: {exc}")
        return

    _start_dispatch_thread(
        url=url,
        message=message,
        thread_name=f"slack-notify-{simulation_id}",
    )


def send_test_notification(url: Optional[str] = None) -> Dict[str, Any]:
    """Synchronously POST a sample Block Kit message.

    Used by the Settings ``Send test event`` flow.
    """
    target = (url or _resolve_webhook_url()).strip()
    if not target:
        return {"ok": False, "message": "Slack webhook URL is empty"}

    sample_payload = {
        "event": "simulation.test",
        "sim_id": "sim_test_event",
        "scenario": "Test event from MiroShark — your Slack webhook is configured.",
        "status": "test",
        "current_round": 0,
        "total_rounds": 0,
        "agent_count": 0,
        "quality_health": None,
        "final_consensus": None,
        "resolution_outcome": None,
        "share_path": "/share/sim_test_event",
        "share_card_path": "/api/simulation/sim_test_event/share-card.png",
        "fired_at": None,
    }
    message = build_slack_message(sample_payload)
    ok, msg = send_slack_payload(target, message)
    return {"ok": ok, "message": msg}
