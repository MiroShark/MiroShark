"""Platform-level + per-project aggregate stats endpoints.

Three surfaces on one blueprint:

* ``GET /api/stats`` — JSON envelope describing every public,
  completed simulation on disk (total count, consensus distribution,
  average confidence, total surface views, unique projects, newest sim
  metadata). The first endpoint that describes the platform itself
  rather than one simulation; press kits, external dashboards, and
  LLM-agent health checks all consume the same payload.

* ``GET /api/stats/badge.svg`` — A flat 20-pixel Shields.io-compatible
  pill (``MiroShark | N simulations``) that any README, Substack, or
  portfolio can embed in one line of Markdown. The platform-level
  sibling of the per-sim ``/badge.svg`` introduced in PR #94.

* ``GET /api/project/<project_id>/stats`` — Per-project sibling of
  ``/api/stats``: the same envelope shape filtered to a single
  ``project_id``, plus a quality distribution. Lets an operator
  managing several published projects pull aggregate numbers for one
  workspace in a single call.

All three endpoints are public (no auth), cache for 60 seconds, and
reuse the same scan helpers. Each JSON endpoint emits a short ETag
so a conditional ``If-None-Match`` GET short-circuits to ``304``
without serialising the body.

Sandbox note: stdlib + Flask only. Scans walk
``Config.WONDERWALL_SIMULATION_DATA_DIR`` directly; no Neo4j, no LLM,
no outbound network.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ..config import Config
from ..services import platform_stats as platform_stats_service
from ..services import project_stats as project_stats_service
from ..services.badge_service import render_platform_badge_svg_bytes
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.stats")


stats_bp = Blueprint("stats", __name__)


def _cache_header() -> str:
    """Cache-Control value shared by both endpoints.

    60 seconds matches the cache TTL on ``compute_platform_stats`` and
    the per-sim ``/badge.svg`` route's cache header — a polling
    consumer sees consistent freshness across the platform-stats and
    per-sim badge surfaces.
    """
    return "public, max-age=60"


@stats_bp.route("", methods=["GET"])
def get_platform_stats() -> Response:
    """Return platform-level aggregate statistics as JSON.

    Response shape::

        {
          "success": true,
          "data": {
            "schema_version": "1",
            "total_sims": <int>,
            "consensus_distribution": {
              "bullish": <int>, "neutral": <int>, "bearish": <int>,
              "bullish_pct": <float>, "neutral_pct": <float>,
              "bearish_pct": <float>
            },
            "avg_confidence_pct": <float>,
            "total_surface_views": <int>,
            "unique_projects": <int>,
            "newest_sim_id": <str | null>,
            "newest_sim_created_at": <ISO-8601 str | null>
          }
        }

    ETag header is set; a matching ``If-None-Match`` short-circuits to
    ``304 Not Modified`` so polling consumers (READMEs that embed the
    badge, dashboards refreshing every minute) don't pay the JSON
    serialisation cost on every request.

    Cache-Control: ``public, max-age=60`` to absorb bursty press
    unfurls. The 60-second cache window matches the
    ``compute_platform_stats`` module-level cache exactly — every call
    after the first inside the window is a dict copy, not a disk scan.
    """
    try:
        payload = platform_stats_service.compute_platform_stats(
            Config.WONDERWALL_SIMULATION_DATA_DIR
        )
    except Exception as exc:
        logger.error(f"Failed to compute platform stats: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500

    etag = platform_stats_service.stats_etag(payload)
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


@stats_bp.route("/badge.svg", methods=["GET"])
def get_platform_stats_badge() -> Response:
    """Render the platform-stats badge as an SVG.

    A flat 20-pixel Shields.io-style pill: ``MiroShark`` (grey) +
    ``N simulations`` (platform-blue). Count is the same
    ``total_sims`` value the JSON endpoint reports. Always returns
    ``200`` with a renderable badge — a zero-sim instance still
    produces a valid ``MiroShark | 0 simulations`` pill rather than
    a 404, so a README embed never breaks on a fresh deployment.

    Cache-Control: ``public, max-age=60``; Content-Type:
    ``image/svg+xml``.
    """
    try:
        payload = platform_stats_service.compute_platform_stats(
            Config.WONDERWALL_SIMULATION_DATA_DIR
        )
        count = int(payload.get("total_sims", 0) or 0)
    except Exception as exc:
        logger.warning(
            f"platform-stats badge: stats computation failed, rendering 0-sim badge: {exc}"
        )
        count = 0

    body = render_platform_badge_svg_bytes(count)
    response = Response(body, mimetype="image/svg+xml")
    response.headers["Cache-Control"] = _cache_header()
    return response


# ── Per-project stats ─────────────────────────────────────────────────────
#
# Mounted on a second blueprint that pins itself to ``/api/project`` so
# the URL ``/api/project/<project_id>/stats`` stays the canonical place
# a per-project surface lives even as the platform-stats namespace
# grows. Two blueprints, one file — both surfaces are conceptually the
# "stats" family and share helpers.


project_stats_bp = Blueprint("project_stats", __name__)


@project_stats_bp.route("/<project_id>/stats", methods=["GET"])
def get_project_stats(project_id: str) -> Response:
    """Return per-project aggregate statistics as JSON.

    Response shape::

        {
          "success": true,
          "data": {
            "schema_version": "1",
            "project_id": <str>,
            "total_sims": <int>,
            "published_sims": <int>,
            "consensus_distribution": {
              "bullish": <int>, "neutral": <int>, "bearish": <int>,
              "bullish_pct": <float>, "neutral_pct": <float>,
              "bearish_pct": <float>
            },
            "avg_confidence_pct": <float>,
            "quality_distribution": {
              "excellent": <int>, "good": <int>, "fair": <int>,
              "poor": <int>
            },
            "total_surface_views": <int>,
            "newest_sim_id": <str | null>,
            "newest_sim_created_at": <ISO-8601 str | null>
          }
        }

    Unknown ``project_id`` (no matching sims) returns an all-zero
    envelope rather than ``404`` — absence of a project is a valid
    state for an operator iterating projects in a dashboard, not an
    error.

    Malformed ``project_id`` (does not match ``[A-Za-z0-9_.\\-]{1,120}``)
    returns ``400`` before the scan runs. Caps the URL parameter at
    120 chars and excludes characters that would break path joins or
    URL parsing downstream.

    ETag is set to ``"project-<total>-<newest_id_prefix>"``; a matching
    ``If-None-Match`` short-circuits to ``304`` so a polling consumer
    doesn't pay the JSON body cost on every request.

    Cache-Control: ``public, max-age=60`` — matches ``/api/stats`` so
    a dashboard polling both surfaces sees consistent freshness.
    """
    if not project_stats_service.is_valid_project_id(project_id):
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Invalid project_id — must be 1–120 characters of "
                        "[A-Za-z0-9_.-]."
                    ),
                }
            ),
            400,
        )

    try:
        payload = project_stats_service.compute_project_stats(
            Config.WONDERWALL_SIMULATION_DATA_DIR,
            project_id,
        )
    except Exception as exc:
        logger.error(f"Failed to compute project stats for {project_id!r}: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500

    etag = project_stats_service.stats_etag(payload)
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
