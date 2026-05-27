"""SMTP completion-notification channel.

Companion to :mod:`discord_notify` and :mod:`slack_notify` — same
contract, different transport. Where Discord and Slack require their
respective platform accounts + webhook URLs, email is the one
notification channel that requires *neither*: every operator already
has a mailbox, every research team already has a mailing list, every
analyst already has an inbox. ``SMTP_HOST`` + ``SMTP_TO`` are enough
to start fanning sim-completion summaries out to whoever needs them.

The body mirrors the Slack Block Kit structure (scenario header,
belief percentages with visual cue, quality badge, scale, share URL)
in a ``multipart/alternative`` envelope — a plain-text part for
terminal-grade clients and an HTML part for richer ones. Both parts
carry the same payload so a recipient on either side gets the same
information.

Design notes
------------

* **Fire-and-forget.** Daemon-thread dispatch. A slow MX or a TLS
  handshake stall never blocks the simulation runner; the notifier
  never raises.
* **Opt-in.** ``SMTP_HOST`` unset ⇒ no-op. Existing deployments are
  unaffected.
* **Per-process dedup.** ``(sim_id, status)`` keyed; the runner's
  two terminal code paths both call into us but the inbox only sees
  one message per terminal state.
* **Reuses ``build_payload``.** Same artifact reads as the other
  channels live in :mod:`webhook_service`. The MIME builder is a
  pure projection over the dict the generic webhook ships.
* **Stdlib only.** ``smtplib`` + ``email.mime.*`` + ``ssl`` + ``os``.
  No new dependencies (zero-dep streak preserved).
* **Auth-optional.** ``SMTP_USER`` / ``SMTP_PASSWORD`` are optional so
  unauthenticated relays (self-hosted Postfix, ``localhost:25``) are
  supported alongside the common Gmail / SendGrid / Mailgun /
  authenticated-MX path. STARTTLS is attempted opportunistically;
  servers that refuse it (a bare port-25 relay) continue plaintext.

Message shape (``multipart/alternative``)::

    Subject: [MiroShark] Bullish: Will the SEC approve XYZ?
    From:    miroshark-notify@miroshark.example
    To:      research-team@example.com, alerts@example.com

    [plain text]
      Will the SEC approve XYZ?
      ─────────────────────────
      Status:   Completed
      Bullish:  62.0%  ██████░░░░
      Neutral:  13.0%  █░░░░░░░░░
      Bearish:  25.0%  ██░░░░░░░░
      Quality:  Excellent
      Scale:    248 agents · 20 rounds
      View:     https://miroshark.app/share/sim_x

    [html]
      <h2>Will the SEC approve XYZ?</h2>
      <p><strong>Bullish:</strong> 62.0% (green span)</p>
      …
      <a href="https://miroshark.app/share/sim_x">View simulation →</a>
"""

from __future__ import annotations

import os
import smtplib
import ssl
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .simulation_runner import SimulationRunState


logger = get_logger("miroshark.email_notify")


# Env-var names — pinned as module constants so tests catch
# accidental renames the same way ``DISCORD_WEBHOOK_URL_ENV_VAR`` does.
SMTP_HOST_ENV_VAR = "SMTP_HOST"
SMTP_PORT_ENV_VAR = "SMTP_PORT"
SMTP_USER_ENV_VAR = "SMTP_USER"
SMTP_PASSWORD_ENV_VAR = "SMTP_PASSWORD"
SMTP_FROM_ENV_VAR = "SMTP_FROM"
SMTP_TO_ENV_VAR = "SMTP_TO"
SMTP_USE_TLS_ENV_VAR = "SMTP_USE_TLS"

# ``465`` is the canonical SMTPS port (implicit TLS via ``SMTP_SSL``).
# ``587`` is the canonical submission port (STARTTLS via ``starttls()``).
# ``25`` is the canonical relay port (usually plaintext on internal
# networks). ``587`` is the safest default for hosted operators; the
# code falls back to ``SMTP`` (plaintext) for ``25`` and ``SMTP_SSL``
# for ``465`` so all three common shapes work without an env knob.
SMTP_DEFAULT_PORT = 587
SMTP_TIMEOUT_SECONDS = 10.0

# Subject capping — RFC 2822 has no formal limit but most clients
# truncate around 78 chars in the list view, so 80 keeps the prefix +
# verb readable without overflowing.
SUBJECT_SCENARIO_MAX_CHARS = 60
PLAIN_SCENARIO_MAX_CHARS = 160

# Unicode block-bar glyphs — same constants the Slack notifier uses
# so a recipient comparing the two channels sees identical bars.
BAR_FILLED = "█"
BAR_EMPTY = "░"
BAR_WIDTH = 10

# Inline-CSS colour swatches — identical to the Discord embed border
# colours so a recipient who saw one channel reads the same colour
# language on the other.
COLOR_BULLISH = "#22c55e"
COLOR_NEUTRAL = "#6b7280"
COLOR_BEARISH = "#ef4444"
COLOR_FAILED = "#f59e0b"


# Per-process dedup — same shape as the Discord / Slack notifiers.
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


def _resolve_host() -> str:
    return _env(SMTP_HOST_ENV_VAR)


def _resolve_port() -> int:
    raw = _env(SMTP_PORT_ENV_VAR)
    if not raw:
        return SMTP_DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError:
        return SMTP_DEFAULT_PORT
    if port <= 0 or port > 65535:
        return SMTP_DEFAULT_PORT
    return port


def _resolve_recipients() -> List[str]:
    """Parse the comma-separated ``SMTP_TO`` env var into addresses."""
    raw = _env(SMTP_TO_ENV_VAR)
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def _resolve_from(host: str) -> str:
    """Default the sender to a deployment-derived noreply when unset."""
    explicit = _env(SMTP_FROM_ENV_VAR)
    if explicit:
        return explicit
    # Mirror the convention most transactional senders use — easier to
    # filter in an inbox than a random user account.
    safe_host = (host or "localhost").lower()
    return f"miroshark-notify@{safe_host}"


def _resolve_use_tls() -> bool:
    """Whether to attempt STARTTLS on a port-587/25 SMTP connection.

    Defaults to ``True`` because every modern submission-port relay
    supports it. An operator routing through a plain port-25 LAN relay
    that rejects STARTTLS can set ``SMTP_USE_TLS=false`` to suppress
    the upgrade attempt.
    """
    raw = _env(SMTP_USE_TLS_ENV_VAR).lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no", "off"}


def is_configured() -> bool:
    """``True`` iff ``SMTP_HOST`` *and* at least one recipient are set.

    Both are required for a valid dispatch — a host without recipients
    has nowhere to send, recipients without a host have no transport.
    Returning ``False`` for either case keeps the SPA chip honest and
    prevents the runner from spinning up dispatch threads with nothing
    to do.
    """
    return bool(_resolve_host()) and bool(_resolve_recipients())


# ── payload → MIME builders ───────────────────────────────────────────


def _truncate(value: str, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)].rstrip() + "…"


def _consensus_direction(payload: Dict[str, Any]) -> str:
    """Return ``"Bullish"`` / ``"Neutral"`` / ``"Bearish"`` / ``"Failed"``.

    Used for the subject-line prefix and the email body header — same
    bucket logic as :func:`discord_notify._consensus_color` so the
    three notification channels stay aligned on "what just happened."
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


def _belief_bar(pct: Any) -> str:
    """Same renderer as :func:`slack_notify.belief_bar`.

    Re-implemented here rather than imported so a future change to the
    Slack bar width / glyphs doesn't silently re-flow every queued
    plain-text email.
    """
    try:
        value = float(pct)
    except (TypeError, ValueError):
        value = 0.0
    if value < 0.0:
        value = 0.0
    if value > 100.0:
        value = 100.0
    filled = int(round((value / 100.0) * BAR_WIDTH))
    if filled < 0:
        filled = 0
    if filled > BAR_WIDTH:
        filled = BAR_WIDTH
    return (BAR_FILLED * filled) + (BAR_EMPTY * (BAR_WIDTH - filled))


def _format_pct(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _resolve_share_url(payload: Dict[str, Any]) -> Optional[str]:
    """Prefer an absolute URL so the email body links cleanly."""
    abs_url = payload.get("share_url")
    if isinstance(abs_url, str) and abs_url.strip():
        s = abs_url.strip()
        if s.startswith("http://") or s.startswith("https://"):
            return s
    rel = payload.get("share_path")
    if isinstance(rel, str) and rel.strip():
        return rel.strip()
    return None


def build_subject(payload: Dict[str, Any]) -> str:
    """Subject line: ``[MiroShark] <Direction>: <Scenario>``.

    Direction is one of ``Bullish`` / ``Neutral`` / ``Bearish`` /
    ``Failed`` so a recipient scanning their inbox can triage by
    direction alone — same bucket the Discord embed colour conveys.
    """
    direction = _consensus_direction(payload)
    scenario = str(payload.get("scenario") or "").strip()
    if not scenario:
        sim_id = str(payload.get("sim_id") or "").strip()
        scenario = f"Simulation {sim_id}" if sim_id else "MiroShark simulation"
    return f"[MiroShark] {direction}: {_truncate(scenario, SUBJECT_SCENARIO_MAX_CHARS)}"


def _status_verb(status: str) -> str:
    if status == "completed":
        return "Completed"
    if status == "failed":
        return "Failed"
    if status == "test":
        return "Test event"
    return status.title() or "Unknown"


def build_plain_body(payload: Dict[str, Any]) -> str:
    """Render the ``text/plain`` part.

    Designed to read cleanly in mutt / Apple Mail / Outlook list-view
    previews — the leading lines carry the highest-signal fields so
    even a notification-banner glance tells the operator what
    happened.
    """
    sim_id = str(payload.get("sim_id") or "")
    status = str(payload.get("status") or "")
    scenario = _truncate(
        str(payload.get("scenario") or "").strip(),
        PLAIN_SCENARIO_MAX_CHARS,
    )
    if not scenario:
        scenario = f"Simulation {sim_id}" if sim_id else "MiroShark simulation"

    lines: List[str] = []
    lines.append(scenario)
    lines.append("─" * min(len(scenario), 60))
    lines.append(f"Status:   {_status_verb(status)}")

    consensus = payload.get("final_consensus") or {}
    if isinstance(consensus, dict) and consensus:
        try:
            b = float(consensus.get("bullish") or 0.0)
            n = float(consensus.get("neutral") or 0.0)
            r = float(consensus.get("bearish") or 0.0)
            has_any = b > 0.0 or n > 0.0 or r > 0.0
        except (TypeError, ValueError):
            has_any = False
        if has_any:
            lines.append(
                f"Bullish:  {_format_pct(consensus.get('bullish')):>6}  {_belief_bar(consensus.get('bullish'))}"
            )
            lines.append(
                f"Neutral:  {_format_pct(consensus.get('neutral')):>6}  {_belief_bar(consensus.get('neutral'))}"
            )
            lines.append(
                f"Bearish:  {_format_pct(consensus.get('bearish')):>6}  {_belief_bar(consensus.get('bearish'))}"
            )

    quality_health = payload.get("quality_health")
    if isinstance(quality_health, str) and quality_health:
        lines.append(f"Quality:  {quality_health}")

    total_rounds = payload.get("total_rounds")
    agent_count = payload.get("agent_count")
    scale_parts: List[str] = []
    if isinstance(agent_count, int) and agent_count > 0:
        scale_parts.append(f"{agent_count} agents")
    if isinstance(total_rounds, int) and total_rounds > 0:
        scale_parts.append(f"{total_rounds} rounds")
    if scale_parts:
        lines.append(f"Scale:    {' · '.join(scale_parts)}")

    resolution_outcome = payload.get("resolution_outcome")
    if isinstance(resolution_outcome, str) and resolution_outcome:
        lines.append(f"Outcome:  {resolution_outcome}")

    if status == "failed":
        err_text = str(payload.get("error") or "").strip()
        if err_text:
            lines.append("")
            lines.append("Error:")
            # Cap the error so a 50KB stderr dump doesn't fill the inbox.
            lines.append(_truncate(err_text, 1500))

    share_url = _resolve_share_url(payload)
    if share_url:
        lines.append("")
        lines.append(f"View:     {share_url}")

    lines.append("")
    lines.append("— MiroShark")
    return "\n".join(lines) + "\n"


def _html_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _consensus_swatch(direction: str) -> str:
    if direction == "Bullish":
        return COLOR_BULLISH
    if direction == "Bearish":
        return COLOR_BEARISH
    if direction == "Failed":
        return COLOR_FAILED
    return COLOR_NEUTRAL


def build_html_body(payload: Dict[str, Any]) -> str:
    """Render the ``text/html`` part.

    Single ``<table>`` layout so Outlook / Gmail / Apple Mail render
    it consistently — modern email clients still treat divs with
    ``flex``/``grid`` as freshly-discovered alien lifeforms.
    """
    sim_id = str(payload.get("sim_id") or "")
    status = str(payload.get("status") or "")
    direction = _consensus_direction(payload)
    swatch = _consensus_swatch(direction)
    scenario = _truncate(
        str(payload.get("scenario") or "").strip(),
        PLAIN_SCENARIO_MAX_CHARS,
    )
    if not scenario:
        scenario = f"Simulation {sim_id}" if sim_id else "MiroShark simulation"

    rows: List[str] = []
    rows.append(
        f'<tr><td style="padding:6px 12px;color:#6b7280;width:90px;">Status</td>'
        f'<td style="padding:6px 12px;font-weight:600;">{_html_escape(_status_verb(status))}</td></tr>'
    )

    consensus = payload.get("final_consensus") or {}
    if isinstance(consensus, dict) and consensus:
        try:
            b = float(consensus.get("bullish") or 0.0)
            n = float(consensus.get("neutral") or 0.0)
            r = float(consensus.get("bearish") or 0.0)
            has_any = b > 0.0 or n > 0.0 or r > 0.0
        except (TypeError, ValueError):
            has_any = False
        if has_any:
            for label, key, color in (
                ("Bullish", "bullish", COLOR_BULLISH),
                ("Neutral", "neutral", COLOR_NEUTRAL),
                ("Bearish", "bearish", COLOR_BEARISH),
            ):
                rows.append(
                    f'<tr><td style="padding:6px 12px;color:#6b7280;">{label}</td>'
                    f'<td style="padding:6px 12px;">'
                    f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
                    f'border-radius:2px;margin-right:8px;vertical-align:middle;"></span>'
                    f'<strong>{_html_escape(_format_pct(consensus.get(key)))}</strong>'
                    f'</td></tr>'
                )

    quality_health = payload.get("quality_health")
    if isinstance(quality_health, str) and quality_health:
        rows.append(
            f'<tr><td style="padding:6px 12px;color:#6b7280;">Quality</td>'
            f'<td style="padding:6px 12px;">{_html_escape(quality_health)}</td></tr>'
        )

    total_rounds = payload.get("total_rounds")
    agent_count = payload.get("agent_count")
    scale_parts: List[str] = []
    if isinstance(agent_count, int) and agent_count > 0:
        scale_parts.append(f"{agent_count} agents")
    if isinstance(total_rounds, int) and total_rounds > 0:
        scale_parts.append(f"{total_rounds} rounds")
    if scale_parts:
        rows.append(
            f'<tr><td style="padding:6px 12px;color:#6b7280;">Scale</td>'
            f'<td style="padding:6px 12px;">{_html_escape(" · ".join(scale_parts))}</td></tr>'
        )

    resolution_outcome = payload.get("resolution_outcome")
    if isinstance(resolution_outcome, str) and resolution_outcome:
        rows.append(
            f'<tr><td style="padding:6px 12px;color:#6b7280;">Outcome</td>'
            f'<td style="padding:6px 12px;">{_html_escape(resolution_outcome)}</td></tr>'
        )

    error_block = ""
    if status == "failed":
        err_text = str(payload.get("error") or "").strip()
        if err_text:
            error_block = (
                '<div style="margin-top:18px;padding:12px 16px;'
                'background:#fef3c7;border-left:4px solid #f59e0b;'
                'font-family:Menlo,Consolas,monospace;font-size:12px;'
                'color:#78350f;white-space:pre-wrap;overflow-wrap:break-word;">'
                f'{_html_escape(_truncate(err_text, 1500))}'
                "</div>"
            )

    share_url = _resolve_share_url(payload)
    cta_block = ""
    if share_url and (share_url.startswith("http://") or share_url.startswith("https://")):
        cta_block = (
            f'<p style="margin:24px 0 0 0;">'
            f'<a href="{_html_escape(share_url)}" '
            f'style="display:inline-block;padding:10px 18px;'
            f'background:{swatch};color:#ffffff;text-decoration:none;'
            f'border-radius:6px;font-weight:600;">'
            "View simulation →</a></p>"
        )

    html = (
        '<html><body style="margin:0;padding:24px;'
        'font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        'background:#f9fafb;color:#111827;">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;'
        'border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">'
        f'<div style="padding:18px 22px;border-top:4px solid {swatch};">'
        f'<h2 style="margin:0 0 16px 0;font-size:18px;line-height:1.4;color:#111827;">'
        f'{_html_escape(scenario)}</h2>'
        '<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f'{"".join(rows)}'
        '</table>'
        f'{error_block}'
        f'{cta_block}'
        '<p style="margin:24px 0 0 0;color:#9ca3af;font-size:12px;">— MiroShark</p>'
        '</div></div></body></html>'
    )
    return html


def build_email_message(
    payload: Dict[str, Any],
    *,
    from_addr: str,
    to_addrs: List[str],
) -> MIMEMultipart:
    """Assemble the full ``multipart/alternative`` MIME envelope."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = build_subject(payload)
    msg["From"] = formataddr(("MiroShark", from_addr))
    msg["To"] = ", ".join(to_addrs)

    # Stamp the sim id into a custom header so operators can filter on
    # it server-side (Sieve / Gmail filter / Outlook rule) without
    # parsing the subject line.
    sim_id = str(payload.get("sim_id") or "")
    if sim_id:
        msg["X-MiroShark-Sim-Id"] = sim_id
    status = str(payload.get("status") or "")
    if status:
        msg["X-MiroShark-Event"] = f"simulation.{status}"

    msg.attach(MIMEText(build_plain_body(payload), "plain", "utf-8"))
    msg.attach(MIMEText(build_html_body(payload), "html", "utf-8"))
    return msg


# ── SMTP dispatch ─────────────────────────────────────────────────────


def send_email(
    message: MIMEMultipart,
    *,
    host: str,
    port: int,
    from_addr: str,
    to_addrs: List[str],
    user: str = "",
    password: str = "",
    use_tls: bool = True,
    timeout: float = SMTP_TIMEOUT_SECONDS,
) -> Tuple[bool, str]:
    """Synchronously POST one message via SMTP. Never raises.

    Picks transport by port: ``465`` ⇒ ``SMTP_SSL`` (implicit TLS),
    anything else ⇒ ``SMTP`` with optional STARTTLS upgrade. Auth is
    attempted only when both ``user`` and ``password`` are non-empty —
    a deployment routing through ``localhost:25`` runs unauthenticated.
    """
    if not host:
        return False, "SMTP_HOST is empty"
    if not to_addrs:
        return False, "SMTP_TO is empty"

    try:
        body = message.as_string()
    except Exception as exc:
        return False, f"Could not serialize email payload: {exc}"

    try:
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as conn:
                if user and password:
                    conn.login(user, password)
                conn.sendmail(from_addr, to_addrs, body)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as conn:
                conn.ehlo_or_helo_if_needed()
                if use_tls:
                    try:
                        conn.starttls(context=context)
                        conn.ehlo()
                    except smtplib.SMTPException:
                        # Relay refused the upgrade — keep going in
                        # plaintext if the operator explicitly allowed
                        # ``SMTP_USE_TLS=false``, otherwise bail rather
                        # than send credentials in the clear.
                        if user and password:
                            return False, "STARTTLS refused; refusing to send credentials in clear"
                if user and password:
                    conn.login(user, password)
                conn.sendmail(from_addr, to_addrs, body)
    except smtplib.SMTPException as exc:
        return False, f"SMTP error: {exc}"
    except (OSError, ssl.SSLError) as exc:
        return False, f"Connection error: {exc}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    return True, f"sent to {len(to_addrs)} recipient(s)"


def _start_dispatch_thread(
    *,
    message: MIMEMultipart,
    host: str,
    port: int,
    from_addr: str,
    to_addrs: List[str],
    user: str,
    password: str,
    use_tls: bool,
    thread_name: str,
) -> None:
    def _send() -> None:
        ok, msg = send_email(
            message,
            host=host,
            port=port,
            from_addr=from_addr,
            to_addrs=to_addrs,
            user=user,
            password=password,
            use_tls=use_tls,
        )
        subject = message.get("Subject", "") or ""
        if ok:
            logger.info(f"Email notify ok ({msg}) — {subject}")
        else:
            logger.warning(f"Email notify failed ({msg}) — {subject}")

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
    """Fire-and-forget email dispatch for a finished simulation.

    Same contract as :func:`discord_notify.notify_if_configured` and
    :func:`slack_notify.notify_if_configured`. No-op when ``SMTP_HOST``
    or ``SMTP_TO`` is unset, or when this ``(sim_id, status)`` already
    fired in this process.
    """
    if status not in {"completed", "failed"}:
        return

    host = _resolve_host()
    if not host:
        return
    to_addrs = _resolve_recipients()
    if not to_addrs:
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
        logger.warning(f"Email notify: build_payload failed for {simulation_id}: {exc}")
        return

    from_addr = _resolve_from(host)
    try:
        message = build_email_message(
            payload, from_addr=from_addr, to_addrs=to_addrs,
        )
    except Exception as exc:
        logger.warning(f"Email notify: message build failed for {simulation_id}: {exc}")
        return

    _start_dispatch_thread(
        message=message,
        host=host,
        port=_resolve_port(),
        from_addr=from_addr,
        to_addrs=to_addrs,
        user=_env(SMTP_USER_ENV_VAR),
        password=_env(SMTP_PASSWORD_ENV_VAR),
        use_tls=_resolve_use_tls(),
        thread_name=f"email-notify-{simulation_id}",
    )


def send_test_notification(
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    to: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Synchronously dispatch a sample email so an operator can verify config.

    Mirrors the test-event flows in ``discord_notify`` and ``slack_notify``
    so the Settings → Integrations panel can wire a single "Send test
    event" button per channel.
    """
    target_host = (host or _resolve_host()).strip()
    target_port = port if port is not None else _resolve_port()
    target_to = to if to is not None else _resolve_recipients()
    if not target_host:
        return {"ok": False, "message": "SMTP_HOST is empty"}
    if not target_to:
        return {"ok": False, "message": "SMTP_TO is empty"}

    sample_payload = {
        "event": "simulation.test",
        "sim_id": "sim_test_event",
        "scenario": "Test event from MiroShark — your SMTP relay is configured.",
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
    from_addr = _resolve_from(target_host)
    message = build_email_message(
        sample_payload, from_addr=from_addr, to_addrs=target_to,
    )
    ok, msg = send_email(
        message,
        host=target_host,
        port=target_port,
        from_addr=from_addr,
        to_addrs=target_to,
        user=_env(SMTP_USER_ENV_VAR),
        password=_env(SMTP_PASSWORD_ENV_VAR),
        use_tls=_resolve_use_tls(),
    )
    return {"ok": ok, "message": msg}
