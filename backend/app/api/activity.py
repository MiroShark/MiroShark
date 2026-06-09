"""Lightweight activity-feed endpoint.

Sibling of ``app/api/stats.py`` / ``app/api/status.py`` /
``app/api/surfaces.py`` — every blueprint in this small family
describes the platform itself rather than one simulation. The other
three answer *what the corpus looks like*, *whether the deployment is
working*, and *what surfaces exist*. This one answers *"what just
finished?"* — the polling-loop question integrators ask between gallery
refreshes and a per-sim webhook subscription.

One endpoint::

    GET /api/activity.json[?limit=N]

Returns the envelope described in
``services/activity_feed.build_activity_feed``: the ``limit`` most
recently completed public simulations in reverse-chronological order,
each carrying the small payload a polling loop or status dashboard
needs (sim_id, scenario title, direction + confidence + quality, total
rounds, completion timestamp, project id).

**Auth posture: public — built for keyless integrator polling
(Aeon push-recap, social bots, status dashboards). The publish gate is
applied per sim inside the service module so an anonymous caller can
only see sims the operator explicitly toggled public; no private or
in-flight sim appears regardless of request shape.**

The route is added to the auth-exemption allow-list in
``app/__init__.py`` alongside ``/api/status.json`` and
``/api/simulation/batch-status`` for the same reason: the value of the
surface is its keyless poll-ability for third-party consumers.

Sandbox note: stdlib + Flask only. Scans walk
``Config.WONDERWALL_SIMULATION_DATA_DIR`` directly through the service
module; no Neo4j, no LLM, no outbound network.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ..config import Config
from ..services import activity_feed as activity_feed_service
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.activity")


activity_bp = Blueprint("activity", __name__)


def _cache_header() -> str:
    """``Cache-Control`` value for the activity feed.

    30 seconds matches the cadence external polling loops (Aeon's
    push-recap skill, integrator status dashboards, social bots) tick
    at. Short enough that a freshly-completed sim appears within half
    a minute; long enough that a load-balanced fleet of pollers
    doesn't multiply the scan cost. Same cadence the platform-status
    probe uses — a consumer polling both surfaces sees consistent
    freshness.
    """
    return "public, max-age=30"


@activity_bp.route("/activity.json", methods=["GET"])
def get_activity_feed() -> Response:
    """Return the activity-feed envelope.

    Query params:

    * ``limit`` (optional, int, 1–50, default 20) — number of entries.
      Values outside the range are clamped (not rejected) so a typo'd
      param doesn't break a polling loop. Non-numeric or absent → 20.

    Response shape::

        {
          "success": true,
          "data": {
            "schema_version": "1",
            "count": <int>,
            "results": [
              {
                "sim_id": <str>,
                "scenario_title": <str>,
                "direction": <"Bullish" | "Neutral" | "Bearish" | null>,
                "confidence_pct": <float | null>,
                "quality_health": <str | null>,
                "total_rounds": <int>,
                "completed_at": <ISO-8601 str>,
                "project_id": <str | null>
              },
              ...
            ]
          }
        }

    ``results`` is ordered by ``completed_at`` descending. Only
    ``is_public == true`` AND ``status == "completed"`` sims appear,
    same publish gate as ``/api/feed.rss`` and ``/api/stats``.

    Auth posture: public / keyless — added to the
    ``internal_auth_guard`` allow-list alongside ``/api/status.json``
    and ``/api/simulation/batch-status``. Built for third-party
    polling consumers; the per-sim publish gate inside the service
    module is the only privacy boundary the endpoint needs.

    ``Cache-Control: public, max-age=30`` so a fleet of pollers
    doesn't multiply the scan cost. An ``ETag`` is also set —
    derived from ``count`` + the newest entry's ``completed_at`` —
    so a conditional ``If-None-Match`` GET short-circuits to ``304``
    without re-serialising the body.

    Empty / missing ``WONDERWALL_SIMULATION_DATA_DIR`` returns a
    fully-zeroed envelope (still ``200``, ``count: 0``, ``results:
    []``) rather than a 404 — a fresh install polling itself sees a
    valid response.
    """
    raw_limit = request.args.get("limit")
    limit = activity_feed_service.clamp_limit(raw_limit)

    try:
        payload = activity_feed_service.build_activity_feed(
            Config.WONDERWALL_SIMULATION_DATA_DIR,
            limit=limit,
        )
    except Exception as exc:
        logger.error(f"Failed to build activity feed: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500

    etag = activity_feed_service.feed_etag(payload)
    if_none_match = (request.headers.get("If-None-Match") or "").strip()
    if if_none_match and if_none_match == etag:
        resp = Response(status=304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = _cache_header()
        return resp

    response = jsonify({"success": True, "data": payload})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = _cache_header()
    return response
