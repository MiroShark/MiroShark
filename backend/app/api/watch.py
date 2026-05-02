"""Public spectator-watch route.

Serves an HTML page at ``/watch/<simulation_id>`` purpose-built for
broadcasting an in-progress simulation: a minimal full-viewport view
with a live belief bar, round counter, progress bar, and Open Graph /
Twitter card meta tags so the URL unfurls as a 1200×630 image when
pasted into Twitter/X, Discord, Slack, LinkedIn, iMessage, etc.

The watch page is the **seventh** thin renderer over the same on-disk
``sim_dir/`` folder that powers the share card (PNG), replay GIF
(motion), transcript (Markdown + JSON), public-gallery feeds
(Atom + RSS), and trajectory export (CSV + JSONL). The previous six
surface a *finished* simulation; the watch page surfaces a *live* one
— the format the project was missing for "tweet a sim mid-run" sharing.

Mounted on its own blueprint with no URL prefix so the URL stays clean
(``/watch/sim_xxx`` rather than ``/api/watch/sim_xxx``). Anyone with
the URL can hit the endpoint, but the underlying live data
(``/api/simulation/<id>/embed-summary``) enforces the ``is_public``
gate, so a private simulation just renders a generic broadcast page
(no scenario, no live numbers) to anyone but the operator.
"""

from __future__ import annotations

from flask import Blueprint, Response, request

from ..services.simulation_manager import SimulationManager
from ..services.simulation_runner import SimulationRunner
from ..services import watch_renderer
from ..utils.i18n import get_locale, t as _t
from ..utils.validation import validate_simulation_id


watch_bp = Blueprint('watch', __name__)


def _build_summary_for_watch(simulation_id: str) -> dict | None:
    """Pull just enough state to seed the watch page bootstrap blob.

    Returns ``None`` when the simulation isn't found OR when it isn't
    public — both cases land on the same generic broadcast page so the
    fact a private sim *exists* with that id never leaks through the
    page chrome.

    Mirrors the field shape of ``api/simulation._build_embed_summary_payload``
    but without that helper's broader dependencies (config-generator,
    profile-generator imports) — keeps the watch path independent of
    the simulation-API module so a regression on one side doesn't break
    the other.
    """
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state is None:
            return None
        if not bool(getattr(state, "is_public", False)):
            return None

        config = manager.get_simulation_config(simulation_id)
        scenario = ""
        if config:
            scenario = (config.get("simulation_requirement") or "").strip()

        run_state = SimulationRunner.get_run_state(simulation_id)
        if run_state is not None:
            current_round = int(getattr(run_state, "current_round", 0) or 0)
            total_rounds = int(getattr(run_state, "total_rounds", 0) or 0)
            runner_status_attr = getattr(run_state, "runner_status", None)
            runner_status = (
                runner_status_attr.value
                if hasattr(runner_status_attr, "value")
                else (str(runner_status_attr) if runner_status_attr else "idle")
            )
        else:
            current_round = 0
            total_rounds = 0
            runner_status = "idle"

        # Belief bootstrap reads the same trajectory.json the embed
        # endpoint reads. Best-effort — never raise here.
        belief = _load_belief_bootstrap(simulation_id)
        quality_health = _load_quality_health(simulation_id)

        status_attr = getattr(state, "status", None)
        status_value = (
            status_attr.value if hasattr(status_attr, "value")
            else (str(status_attr) if status_attr else "idle")
        )

        return {
            "simulation_id": simulation_id,
            "scenario": scenario,
            "is_public": True,
            "status": status_value,
            "runner_status": runner_status,
            "current_round": current_round,
            "total_rounds": total_rounds,
            "profiles_count": int(getattr(state, "profiles_count", 0) or 0),
            "belief": belief,
            "quality": ({"health": quality_health} if quality_health else None),
        }
    except Exception:
        # The page must never 500 just because a peripheral lookup
        # failed — a generic broadcast page is preferable.
        return None


def _load_belief_bootstrap(simulation_id: str) -> dict | None:
    """Read the latest belief snapshot from ``trajectory.json``.

    Returns the same shape the embed-summary endpoint uses — a dict with
    ``rounds``, ``bullish``, ``neutral``, ``bearish``, ``final``, and
    consensus markers — or ``None`` when the file is absent or
    malformed.
    """
    import json
    import os
    from ..config import Config

    sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
    trajectory_path = os.path.join(sim_dir, "trajectory.json")
    if not os.path.exists(trajectory_path):
        return None
    try:
        with open(trajectory_path, "r", encoding="utf-8") as f:
            traj = json.load(f) or {}
    except Exception:
        return None

    rounds: list[int] = []
    bullish: list[float] = []
    neutral: list[float] = []
    bearish: list[float] = []
    threshold = watch_renderer.STANCE_THRESHOLD
    for snap in traj.get("snapshots", []) or []:
        positions = snap.get("belief_positions") or {}
        if not positions:
            continue
        stances: list[float] = []
        for p in positions.values():
            if isinstance(p, dict) and p:
                stances.append(sum(p.values()) / len(p))
        if not stances:
            continue
        total = len(stances)
        nb = sum(1 for s in stances if s > threshold)
        nbe = sum(1 for s in stances if s < -threshold)
        nn = total - nb - nbe
        rounds.append(int(snap.get("round_num") or len(rounds)))
        bullish.append(round(nb / total * 100, 1))
        neutral.append(round(nn / total * 100, 1))
        bearish.append(round(nbe / total * 100, 1))

    if not rounds:
        return None

    consensus_round = None
    consensus_stance = None
    for i, _ in enumerate(rounds):
        if bullish[i] > 50:
            consensus_round = rounds[i]
            consensus_stance = "bullish"
            break
        if bearish[i] > 50:
            consensus_round = rounds[i]
            consensus_stance = "bearish"
            break

    return {
        "rounds": rounds,
        "bullish": bullish,
        "neutral": neutral,
        "bearish": bearish,
        "final": {
            "bullish": bullish[-1],
            "neutral": neutral[-1],
            "bearish": bearish[-1],
        },
        "consensus_round": consensus_round,
        "consensus_stance": consensus_stance,
    }


def _load_quality_health(simulation_id: str) -> str | None:
    """Read ``quality.json`` health label if present. Never raises."""
    import json
    import os
    from ..config import Config

    quality_path = os.path.join(
        Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id, "quality.json",
    )
    if not os.path.exists(quality_path):
        return None
    try:
        with open(quality_path, "r", encoding="utf-8") as f:
            return (json.load(f) or {}).get("health")
    except Exception:
        return None


def _resolve_base_url() -> str:
    """Same proxy-aware base URL resolution the share-landing route
    uses — ``X-Forwarded-Proto`` + ``X-Forwarded-Host`` first, then
    ``request.host_url``."""
    forwarded_host = request.headers.get("X-Forwarded-Host")
    if forwarded_host:
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        proto = forwarded_proto or ("https" if request.is_secure else "http")
        return f"{proto}://{forwarded_host}"
    return request.host_url.rstrip("/")


@watch_bp.route('/watch/<simulation_id>', methods=['GET'])
def watch_landing(simulation_id: str):
    """Server-rendered spectator-watch page.

    Body carries OG / Twitter meta tags + a self-contained vanilla-JS
    poller that updates the belief bar / round counter / progress bar
    every 15s by hitting the existing ``/api/simulation/<id>/embed-summary``
    and ``/api/simulation/<id>/run-status`` REST endpoints. Once the
    runner reaches a terminal state, polling stops and the "View full"
    + "Fork this scenario" CTAs fade in.

    No auth — but the underlying live endpoints honour ``is_public``,
    so a private simulation only renders the bare broadcast frame.
    """
    locale = get_locale(request)
    try:
        validate_simulation_id(simulation_id)
    except ValueError as exc:
        return Response(
            _t(f"Invalid simulation id: {exc}", f"无效的模拟 ID:{exc}", locale),
            status=400,
            mimetype="text/plain",
        )

    summary = _build_summary_for_watch(simulation_id)

    base = _resolve_base_url()
    spa_url = f"{base}/simulation/{simulation_id}/start"
    fork_url = f"{base}/simulation/{simulation_id}/start?fork=1"
    card_url = f"{base}/api/simulation/{simulation_id}/share-card.png"
    explore_url = f"{base}/explore"

    body = watch_renderer.render_watch_html(
        simulation_id=simulation_id,
        summary=summary,
        spa_url=spa_url,
        fork_url=fork_url,
        card_url=card_url,
        explore_url=explore_url,
    )

    response = Response(body, mimetype="text/html; charset=utf-8")
    # OG scrapers cache aggressively — keep the cache short so the
    # initial unfurl reflects the running state shortly after publish,
    # while keeping crawler load bounded.
    response.headers["Cache-Control"] = "public, max-age=60"
    return response
