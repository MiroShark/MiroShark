"""Discord rich-embed notification on simulation completion.

Companion to :mod:`webhook_service`. The generic webhook posts a raw
JSON blob — Discord renders nothing from it (no embed, no card, no
unfurl). When ``DISCORD_WEBHOOK_URL`` is set, this module POSTs a
proper Discord *embed object* alongside the generic dispatch so a
Discord channel receives a coloured, titled, button-linked card on
every ``simulation.completed`` / ``simulation.failed`` event.

The first third-party MiroShark integration (``@revaultdrops``,
2026-05-13 — "ReVault intelligence layer powered by @miroshark_") runs
its operator chatter in a Discord server. This module turns that
server into a live MiroShark distribution channel without requiring
the operator to write any integration glue.

Design notes
------------

* **Fire-and-forget.** Runs in a daemon thread so a slow Discord
  endpoint never delays the simulation runner. Never raises.
* **Opt-in.** No env var ⇒ no-op. A misconfigured URL (HTTP 4xx)
  logs a warning and continues. Existing deployments unaware of the
  feature are unaffected.
* **Per-process dedup.** ``(sim_id, status)`` keyed; the runner's
  exit-code path and the ``simulation_end`` event path both fire,
  but Discord only sees one card per terminal state.
* **Reuses ``build_payload``.** The on-disk artifact reads
  (``simulation_config.json``, ``quality.json``, ``trajectory.json``,
  ``state.json``, …) live in :mod:`webhook_service` and are not
  duplicated here. The embed builder is a pure projection over the
  same payload the generic webhook ships.
* **Stdlib only.** ``urllib.request`` for the POST, ``json`` for the
  body, ``os`` for the env var. No new dependencies.

Embed shape (Discord ``embeds[0]``)::

    {
      "type": "rich",
      "title": "<scenario, ≤100 chars>",
      "url":   "<share_url or share_path>",
      "color": <int — green/grey/red/orange by consensus direction>,
      "fields": [
        {"name": "Bullish",  "value": "62.0%", "inline": true},
        {"name": "Neutral",  "value": "13.0%", "inline": true},
        {"name": "Bearish",  "value": "25.0%", "inline": true},
        {"name": "Quality",  "value": "Excellent", "inline": true},
        {"name": "Rounds",   "value": "20", "inline": true},
        {"name": "Agents",   "value": "248", "inline": true}
      ],
      "thumbnail": {"url": "<share_card_url>"},
      "footer":    {"text": "MiroShark"},
      "timestamp": "<fired_at>"
    }
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, Optional, Tuple

from ..utils.logger import get_logger
from .simulation_run_state import SimulationRunState
from ._notify_base import Dedup, post_json

logger = get_logger('miroshark.discord_notify')


DISCORD_WEBHOOK_URL_ENV_VAR = "DISCORD_WEBHOOK_URL"
DISCORD_USER_AGENT = "MiroShark-DiscordNotify/1.0"
DISCORD_TIMEOUT_SECONDS = 5.0

# Discord field values are capped server-side; titles are clamped here so
# a long scenario doesn't break the embed.
DISCORD_TITLE_MAX_CHARS = 100

# Discord embed-colour integers. Picked to match the rest of the SPA so
# the in-app consensus chip and the Discord card read as the same colour
# system.
COLOR_BULLISH = 0x22C55E   # green-500   — bullish-led consensus
COLOR_NEUTRAL = 0x6B7280   # grey-500    — no dominant direction
COLOR_BEARISH = 0xEF4444   # red-500     — bearish-led consensus
COLOR_FAILED  = 0xF59E0B   # amber-500   — sim failed (no consensus)

# Per-process dedup. Mirrors the same idea as `webhook_service._FIRED`:
# the runner has two terminal code paths (exit-code monitor + the
# `simulation_end` event in the action log) and both call into the
# notifier — keep only the first per (sim_id, status).
_dedup = Dedup()


def reset_dedup_for_tests() -> None:
    """Clear the in-process dedup set. Test-only convenience."""
    _dedup.reset()


def _resolve_webhook_url() -> str:
    """Read ``DISCORD_WEBHOOK_URL`` at call time.

    Late binding so a runtime env mutation (or a test ``monkeypatch``)
    takes effect without re-importing the module.
    """
    return (os.environ.get(DISCORD_WEBHOOK_URL_ENV_VAR, "") or "").strip()


def is_configured() -> bool:
    """``True`` iff ``DISCORD_WEBHOOK_URL`` is set to a non-empty value."""
    return bool(_resolve_webhook_url())


def _consensus_color(payload: Dict[str, Any]) -> int:
    """Pick the embed colour for ``payload``.

    A failed sim is always amber regardless of the (often empty)
    trajectory. A completed sim with no trajectory falls back to
    neutral grey. Otherwise the colour follows the dominant stance
    bucket (bullish/neutral/bearish) using the same ±0.2 threshold
    every other surface uses.
    """
    if (payload.get("status") or "") == "failed":
        return COLOR_FAILED

    consensus = payload.get("final_consensus") or {}
    if not isinstance(consensus, dict):
        return COLOR_NEUTRAL

    try:
        bullish = float(consensus.get("bullish") or 0.0)
        neutral = float(consensus.get("neutral") or 0.0)
        bearish = float(consensus.get("bearish") or 0.0)
    except (TypeError, ValueError):
        return COLOR_NEUTRAL

    if bullish == 0.0 and neutral == 0.0 and bearish == 0.0:
        return COLOR_NEUTRAL

    if bullish >= bearish and bullish >= neutral:
        return COLOR_BULLISH
    if bearish >= bullish and bearish >= neutral:
        return COLOR_BEARISH
    return COLOR_NEUTRAL


def _truncate(value: str, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)].rstrip() + "…"


def _resolve_share_url(payload: Dict[str, Any]) -> Optional[str]:
    """Prefer the absolute ``share_url`` when ``PUBLIC_BASE_URL`` was set.

    Falls back to the relative ``share_path`` so the embed always
    carries some link — but Discord renders a clickable button only
    when the URL is absolute, which is why the generic webhook layer
    surfaces ``share_url`` separately.
    """
    abs_url = payload.get("share_url")
    if isinstance(abs_url, str) and abs_url.strip():
        return abs_url.strip()
    rel = payload.get("share_path")
    if isinstance(rel, str) and rel.strip():
        return rel.strip()
    return None


def _format_pct(value: Any) -> str:
    """Render a percentage field the way the SPA renders it ("62.0%")."""
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def build_discord_embed(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble the Discord embed object for ``payload``.

    ``payload`` is the same dict :func:`webhook_service.build_payload`
    produces. The embed surfaces the four numbers a casual reader
    cares about (bullish / neutral / bearish / quality) plus the
    rounds + agent count, and links the share page so a single tap
    opens the simulation.
    """
    status = str(payload.get("status") or "")
    sim_id = str(payload.get("sim_id") or "")

    scenario = _truncate(
        str(payload.get("scenario") or ""),
        DISCORD_TITLE_MAX_CHARS,
    )
    if not scenario:
        # Avoid an empty Discord title — Discord renders it as a tiny
        # gap and the card looks broken. Fall back to a stable label.
        scenario = (
            f"Simulation {sim_id}".strip()
            if sim_id
            else "MiroShark simulation"
        )

    consensus = payload.get("final_consensus") or {}
    fields: list[Dict[str, Any]] = []
    if isinstance(consensus, dict) and consensus:
        fields.extend([
            {"name": "Bullish", "value": _format_pct(consensus.get("bullish")), "inline": True},
            {"name": "Neutral", "value": _format_pct(consensus.get("neutral")), "inline": True},
            {"name": "Bearish", "value": _format_pct(consensus.get("bearish")), "inline": True},
        ])

    quality_health = payload.get("quality_health")
    if isinstance(quality_health, str) and quality_health:
        fields.append({"name": "Quality", "value": quality_health, "inline": True})

    total_rounds = payload.get("total_rounds")
    if isinstance(total_rounds, int) and total_rounds > 0:
        fields.append({"name": "Rounds", "value": str(total_rounds), "inline": True})

    agent_count = payload.get("agent_count")
    if isinstance(agent_count, int) and agent_count > 0:
        fields.append({"name": "Agents", "value": str(agent_count), "inline": True})

    resolution_outcome = payload.get("resolution_outcome")
    if isinstance(resolution_outcome, str) and resolution_outcome:
        fields.append({
            "name": "Resolution",
            "value": resolution_outcome,
            "inline": True,
        })

    if status == "failed":
        err_text = str(payload.get("error") or "").strip()
        if err_text:
            # Discord field values cap at 1024 chars — be defensive.
            fields.append({
                "name": "Error",
                "value": _truncate(err_text, 1000),
                "inline": False,
            })

    embed: Dict[str, Any] = {
        "type": "rich",
        "title": scenario,
        "color": _consensus_color(payload),
        "fields": fields,
        "footer": {"text": "MiroShark"},
    }

    url = _resolve_share_url(payload)
    if url and (url.startswith("http://") or url.startswith("https://")):
        embed["url"] = url

    thumb = payload.get("share_card_url")
    if isinstance(thumb, str) and (
        thumb.startswith("http://") or thumb.startswith("https://")
    ):
        embed["thumbnail"] = {"url": thumb}

    fired_at = payload.get("fired_at")
    if isinstance(fired_at, str) and fired_at:
        embed["timestamp"] = fired_at

    # Description carries the status verb so the card reads cleanly
    # even when the dashboard rolls up several cards in a row.
    if status == "completed":
        embed["description"] = "Simulation reached its terminal round."
    elif status == "failed":
        embed["description"] = "Simulation ended in a failure state."
    elif status == "test":
        embed["description"] = "Test event — your Discord webhook is configured correctly."

    return embed


def _post_json(url: str, body: Dict[str, Any], timeout: float) -> Tuple[bool, str]:
    """Issue the POST. Returns ``(ok, message)`` — never raises."""
    return post_json(url, body, timeout, user_agent=DISCORD_USER_AGENT, label="Discord")


def send_discord_payload(url: str, embed: Dict[str, Any]) -> Tuple[bool, str]:
    """Synchronously POST one embed to ``url``. Returns ``(ok, message)``.

    Exposed so the "Send test event" path can surface the result
    immediately without going through the daemon-thread dispatch.
    """
    if not url:
        return False, "Discord webhook URL is empty"
    body = {"embeds": [embed]}
    return _post_json(url, body, DISCORD_TIMEOUT_SECONDS)


def _start_dispatch_thread(url: str, embed: Dict[str, Any], thread_name: str) -> None:
    """Launch the daemon thread that POSTs the embed and logs the result."""
    def _send() -> None:
        ok, msg = send_discord_payload(url, embed)
        sim_id = embed.get("title") or ""
        if ok:
            logger.info(f"Discord notify ok ({msg}) — {sim_id}")
        else:
            logger.warning(f"Discord notify failed ({msg}) — {sim_id}")

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
    """Fire-and-forget Discord embed dispatch for a finished simulation.

    Safe to call from the simulation monitor thread — the POST runs
    in its own daemon thread. No-op when ``DISCORD_WEBHOOK_URL`` is
    not set or when this ``(sim_id, status)`` already fired in this
    process.
    """
    if status not in {"completed", "failed"}:
        return

    url = _resolve_webhook_url()
    if not url:
        return

    if not _dedup.mark(simulation_id, status):
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
        logger.warning(f"Discord notify: build_payload failed for {simulation_id}: {exc}")
        return

    try:
        embed = build_discord_embed(payload)
    except Exception as exc:
        logger.warning(f"Discord notify: embed build failed for {simulation_id}: {exc}")
        return

    _start_dispatch_thread(
        url=url,
        embed=embed,
        thread_name=f"discord-notify-{simulation_id}",
    )


def send_test_notification(url: Optional[str] = None) -> Dict[str, Any]:
    """Synchronously POST a sample embed.

    Used by the Settings ``Send test event`` flow so an operator gets
    immediate feedback that their Discord webhook URL works.
    """
    target = (url or _resolve_webhook_url()).strip()
    if not target:
        return {"ok": False, "message": "Discord webhook URL is empty"}

    from . import webhook_service
    sample_payload = webhook_service.build_test_payload(
        "Test event from MiroShark — your Discord webhook is configured."
    )
    embed = build_discord_embed(sample_payload)
    ok, msg = send_discord_payload(target, embed)
    return {"ok": ok, "message": msg}
