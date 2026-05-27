"""Telegram Bot completion-notification channel.

Companion to :mod:`discord_notify`, :mod:`slack_notify`, and
:mod:`email_notify` — same contract, different transport. Where the
Discord and Slack channels target Discord/Slack workspaces and SMTP
fans out to any mailbox, Telegram covers the messaging surface most
of MiroShark's crypto-launch / political-debate audience already
lives in. Two env vars (``TELEGRAM_BOT_TOKEN`` + ``TELEGRAM_CHAT_ID``)
turn any private chat, group, or channel into a live
simulation-completion firehose.

Message shape — Bot API ``sendMessage`` with ``parse_mode=HTML``,
``disable_web_page_preview=true``, and a single-button
``inline_keyboard`` linking the share page when an absolute URL is
available.

Design notes
------------

* **Fire-and-forget.** Daemon-thread dispatch, never raises. The
  simulation runner is unaffected by a slow Telegram edge or a
  rate-limited bot.
* **Opt-in.** Either env var unset ⇒ no-op. Existing deployments
  are unaffected.
* **Per-process dedup.** ``(sim_id, status)`` keyed; the runner's
  two terminal code paths both call into us but the chat only sees
  one message per terminal state.
* **Reuses ``build_payload``.** Same artifact reads as the other
  channels live in :mod:`webhook_service`. The HTML builder is a
  pure projection over the dict the generic webhook ships.
* **Stdlib only.** ``urllib.request`` + ``json`` + ``html`` + ``os``.
  No new dependencies (zero-dep streak preserved).
* **Unicode block-bars, no images.** Telegram renders the same
  ``█████░░░░░`` glyphs Slack uses, so a recipient comparing
  channels sees identical bars.

Telegram HTML caveats
---------------------

The Bot API accepts a narrow HTML subset (``<b>``, ``<i>``,
``<u>``, ``<s>``, ``<code>``, ``<pre>``, ``<a>``). Every piece of
user-supplied text is funnelled through :func:`_escape` so a
scenario containing ``<`` / ``>`` / ``&`` doesn't break the parser
(Telegram rejects the whole message with HTTP 400 on a tag-parse
failure — silent loss, not a partial render).
"""

from __future__ import annotations

import html
import json
import os
import threading
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .simulation_runner import SimulationRunState


logger = get_logger("miroshark.telegram_notify")


# Env-var names — pinned as module constants so tests catch
# accidental renames the same way ``DISCORD_WEBHOOK_URL_ENV_VAR`` does.
TELEGRAM_BOT_TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV_VAR = "TELEGRAM_CHAT_ID"

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_USER_AGENT = "MiroShark-TelegramNotify/1.0"
TELEGRAM_TIMEOUT_SECONDS = 5.0

# Telegram caps text messages at 4096 chars. The scenario itself is
# clamped much earlier so the assembled body never approaches the
# limit, but pin a generous safety bound so a future format expansion
# can't silently overflow.
TELEGRAM_TEXT_MAX_CHARS = 4000
TELEGRAM_SCENARIO_MAX_CHARS = 200
TELEGRAM_ERROR_MAX_CHARS = 1500

# Same Unicode block-bar constants the Slack + email notifiers use so
# a recipient comparing channels sees identical bars.
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


# ── env-var resolution ────────────────────────────────────────────────


def _env(name: str) -> str:
    return (os.environ.get(name, "") or "").strip()


def _resolve_bot_token() -> str:
    return _env(TELEGRAM_BOT_TOKEN_ENV_VAR)


def _resolve_chat_id() -> str:
    return _env(TELEGRAM_CHAT_ID_ENV_VAR)


def is_configured() -> bool:
    """``True`` iff both ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID``
    are set to non-empty values.

    Both are required for a valid dispatch — a token without a chat id
    has nowhere to send, a chat id without a token has no transport.
    """
    return bool(_resolve_bot_token()) and bool(_resolve_chat_id())


# ── payload → HTML builder ────────────────────────────────────────────


def _escape(value: Any) -> str:
    """Escape ``<`` / ``>`` / ``&`` for Telegram HTML parse mode.

    Telegram rejects the whole message with HTTP 400 if any HTML tag
    fails to parse — a scenario containing a stray ``<`` (e.g.
    ``"Will TVL <$1B by EOY?"``) would silently kill the notification.
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def _truncate(value: str, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)].rstrip() + "…"


def belief_bar(pct: Any, width: int = BAR_WIDTH) -> str:
    """Render a horizontal block-bar for ``pct`` (a value in [0, 100])."""
    try:
        value = float(pct)
    except (TypeError, ValueError):
        value = 0.0
    if value < 0.0:
        value = 0.0
    if value > 100.0:
        value = 100.0

    filled = int(round((value / 100.0) * max(int(width), 1)))
    if filled < 0:
        filled = 0
    if filled > width:
        filled = width
    bar = (BAR_FILLED * filled) + (BAR_EMPTY * (width - filled))
    return f"{bar} {value:.1f}%"


def _format_pct(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _consensus_direction(payload: Dict[str, Any]) -> str:
    """Return ``"Bullish"`` / ``"Neutral"`` / ``"Bearish"`` / ``"Failed"``.

    Same bucket logic as :func:`email_notify._consensus_direction` so
    the channels stay aligned on "what just happened."
    """
    if (payload.get("status") or "") == "failed":
        return "Failed"

    consensus = payload.get("final_consensus") or {}
    if not isinstance(consensus, dict):
        return "Neutral"

    try:
        b = float(consensus.get("bullish") or 0.0)
        n = float(consensus.get("neutral") or 0.0)
        r = float(consensus.get("bearish") or 0.0)
    except (TypeError, ValueError):
        return "Neutral"

    if b == 0.0 and n == 0.0 and r == 0.0:
        return "Neutral"

    if b >= r and b >= n:
        return "Bullish"
    if r >= b and r >= n:
        return "Bearish"
    return "Neutral"


def _status_verb(status: str) -> str:
    if status == "completed":
        return "Completed"
    if status == "failed":
        return "Failed"
    if status == "test":
        return "Test event"
    return status.title() or "Unknown"


def _resolve_share_url(payload: Dict[str, Any]) -> Optional[str]:
    """Prefer the absolute ``share_url`` — Telegram inline-keyboard
    buttons require an absolute ``http(s)://`` URL."""
    abs_url = payload.get("share_url")
    if isinstance(abs_url, str) and abs_url.strip():
        s = abs_url.strip()
        if s.startswith("http://") or s.startswith("https://"):
            return s
    return None


def build_telegram_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble the Telegram ``sendMessage`` body for ``payload``.

    Returns the kwargs dict ready to JSON-serialize as the POST body;
    ``chat_id`` is added by :func:`_post_send_message` at dispatch
    time so the builder stays a pure projection of the payload.
    """
    sim_id = str(payload.get("sim_id") or "")
    status = str(payload.get("status") or "")

    raw_scenario = str(payload.get("scenario") or "").strip()
    scenario = _truncate(raw_scenario, TELEGRAM_SCENARIO_MAX_CHARS)
    if not scenario:
        scenario = f"Simulation {sim_id}" if sim_id else "MiroShark simulation"

    direction = _consensus_direction(payload)
    verb = _status_verb(status)

    lines: list[str] = []
    # 1. Header — scenario in bold, then a status line.
    lines.append(f"<b>{_escape(scenario)}</b>")
    if sim_id:
        lines.append(f"<i>{_escape(verb)}</i> · <code>{_escape(sim_id)}</code>")
    else:
        lines.append(f"<i>{_escape(verb)}</i>")

    # 2. Belief bars — only when a trajectory was available.
    consensus = payload.get("final_consensus") or {}
    if isinstance(consensus, dict):
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
            lines.append("")
            lines.append(f"<b>Bullish</b> <code>{_escape(belief_bar(bullish))}</code>")
            lines.append(f"<b>Neutral</b> <code>{_escape(belief_bar(neutral))}</code>")
            lines.append(f"<b>Bearish</b> <code>{_escape(belief_bar(bearish))}</code>")

    # 3. Quality / Scale / Outcome key-value lines.
    kv: list[str] = []
    quality_health = payload.get("quality_health")
    if isinstance(quality_health, str) and quality_health:
        kv.append(f"<b>Quality:</b> {_escape(quality_health)}")

    total_rounds = payload.get("total_rounds")
    agent_count = payload.get("agent_count")
    scale_parts: list[str] = []
    if isinstance(agent_count, int) and agent_count > 0:
        scale_parts.append(f"{agent_count} agents")
    if isinstance(total_rounds, int) and total_rounds > 0:
        scale_parts.append(f"{total_rounds} rounds")
    if scale_parts:
        kv.append(f"<b>Scale:</b> {_escape(' · '.join(scale_parts))}")

    resolution_outcome = payload.get("resolution_outcome")
    if isinstance(resolution_outcome, str) and resolution_outcome:
        kv.append(f"<b>Outcome:</b> {_escape(resolution_outcome)}")

    if kv:
        lines.append("")
        lines.extend(kv)

    # 4. Direction tag — gives an inbox-glance read even on a phone
    # notification that only previews the first line.
    if direction and direction != "Neutral" or status == "failed":
        lines.append("")
        lines.append(f"<b>Direction:</b> {_escape(direction)}")

    # 5. Failure error — fenced as a <pre> block so multiline stack
    # traces render cleanly on every Telegram client.
    if status == "failed":
        err_text = str(payload.get("error") or "").strip()
        if err_text:
            lines.append("")
            lines.append(
                f"<b>Error</b>\n<pre>{_escape(_truncate(err_text, TELEGRAM_ERROR_MAX_CHARS))}</pre>"
            )

    text = "\n".join(lines)
    # Final defensive clamp — should never trigger with the scenario /
    # error caps above, but guarantees the assembled body is always
    # under Telegram's 4096-char hard limit.
    text = _truncate(text, TELEGRAM_TEXT_MAX_CHARS)

    body: Dict[str, Any] = {
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    # 6. "View simulation" inline-keyboard button — only when we have
    # an absolute URL. Telegram rejects buttons whose ``url`` isn't
    # ``http(s)://``.
    share_url = _resolve_share_url(payload)
    if share_url:
        body["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "View simulation", "url": share_url},
            ]],
        }

    return body


# ── HTTP + dispatch ───────────────────────────────────────────────────


def _send_message_url(token: str) -> str:
    """Telegram Bot API ``sendMessage`` URL for ``token``."""
    # Telegram requires the literal ``bot`` prefix in the path.
    return f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"


def _post_json(url: str, body: Dict[str, Any], timeout: float) -> Tuple[bool, str]:
    """Issue the POST. Returns ``(ok, message)`` — never raises."""
    try:
        encoded = json.dumps(body).encode("utf-8")
    except Exception as exc:
        return False, f"Could not serialize Telegram payload: {exc}"

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": TELEGRAM_USER_AGENT,
    }
    req = urllib.request.Request(url, data=encoded, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            if 200 <= code < 300:
                return True, f"HTTP {code}"
            return False, f"HTTP {code}"
    except urllib.error.HTTPError as exc:
        # Telegram returns the error description in the response body —
        # surface it so a malformed HTML payload is debuggable from logs.
        detail = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw else {}
            if isinstance(parsed, dict):
                desc = parsed.get("description")
                if isinstance(desc, str) and desc:
                    detail = f" {desc}"
        except Exception:
            pass
        return False, f"HTTP {exc.code}{detail}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"URL error: {reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _post_send_message(
    token: str,
    chat_id: str,
    body: Dict[str, Any],
    timeout: float = TELEGRAM_TIMEOUT_SECONDS,
) -> Tuple[bool, str]:
    """Synchronously POST one Bot API ``sendMessage`` call."""
    if not token:
        return False, "Telegram bot token is empty"
    if not chat_id:
        return False, "Telegram chat id is empty"
    payload = dict(body)
    payload["chat_id"] = chat_id
    return _post_json(_send_message_url(token), payload, timeout)


def send_telegram_message(
    token: str,
    chat_id: str,
    body: Dict[str, Any],
) -> Tuple[bool, str]:
    """Synchronously POST one ``sendMessage`` body. Never raises.

    Exposed so the "Send test event" path can surface the result
    immediately without going through the daemon-thread dispatch.
    """
    return _post_send_message(token, chat_id, body)


def _start_dispatch_thread(
    *,
    token: str,
    chat_id: str,
    body: Dict[str, Any],
    thread_name: str,
) -> None:
    """Launch the daemon thread that POSTs the message and logs."""
    def _send() -> None:
        ok, msg = _post_send_message(token, chat_id, body)
        text = body.get("text") or ""
        # The header line ends at the first newline; log it so a
        # multi-simulation deployment can attribute log lines.
        first_line = text.split("\n", 1)[0] if isinstance(text, str) else ""
        if ok:
            logger.info(f"Telegram notify ok ({msg}) — {first_line}")
        else:
            logger.warning(f"Telegram notify failed ({msg}) — {first_line}")

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
    """Fire-and-forget Telegram dispatch for a finished simulation.

    Same contract as :func:`discord_notify.notify_if_configured` and
    :func:`slack_notify.notify_if_configured`. No-op when either
    ``TELEGRAM_BOT_TOKEN`` or ``TELEGRAM_CHAT_ID`` is unset, or when
    this ``(sim_id, status)`` already fired in this process.
    """
    if status not in {"completed", "failed"}:
        return

    token = _resolve_bot_token()
    chat_id = _resolve_chat_id()
    if not token or not chat_id:
        return

    if not _mark_fired(simulation_id, status):
        return

    # Defer the import so the package-level wiring stays cycle-free
    # (webhook_service does not import this module).
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
        logger.warning(
            f"Telegram notify: build_payload failed for {simulation_id}: {exc}"
        )
        return

    try:
        body = build_telegram_message(payload)
    except Exception as exc:
        logger.warning(
            f"Telegram notify: message build failed for {simulation_id}: {exc}"
        )
        return

    _start_dispatch_thread(
        token=token,
        chat_id=chat_id,
        body=body,
        thread_name=f"telegram-notify-{simulation_id}",
    )


def send_test_notification(
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Synchronously POST a sample message.

    Used by the Settings ``Send test event`` flow so an operator gets
    immediate feedback that their Telegram bot token + chat id work.
    """
    use_token = (token or _resolve_bot_token()).strip()
    use_chat = (chat_id or _resolve_chat_id()).strip()
    if not use_token:
        return {"ok": False, "message": "Telegram bot token is empty"}
    if not use_chat:
        return {"ok": False, "message": "Telegram chat id is empty"}

    sample_payload = {
        "event": "simulation.test",
        "sim_id": "sim_test_event",
        "scenario": "Test event from MiroShark — your Telegram bot is configured.",
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
    body = build_telegram_message(sample_payload)
    ok, msg = _post_send_message(use_token, use_chat, body)
    return {"ok": ok, "message": msg}
