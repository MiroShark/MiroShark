"""Platform health probe endpoint.

Sibling of ``app/api/stats.py`` and ``app/api/surfaces.py`` — all three
blueprints describe the platform itself rather than one simulation.
``stats.py`` aggregates analytics over the corpus; ``surfaces.py``
enumerates the surface area; this blueprint answers *"is the platform
up and making progress?"* for external status monitors.

One endpoint::

    GET /api/status.json

Returns the envelope described in
``services/platform_status.build_status``: queue depth, completions in
the last 24 hours, the last-completed timestamp, the total sim count
on disk, the catalog's surface count, the ISO check timestamp, and a
literal ``ok: true``. A consumer matching only on the body — the
default for many status-page templates — works on day one.

Sandbox note: stdlib + Flask only. Scans walk
``Config.WONDERWALL_SIMULATION_DATA_DIR`` directly through the service
module; no Neo4j, no LLM, no outbound network.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify

from ..config import Config
from ..services import platform_status as platform_status_service
from ..services import surfaces_catalog as surfaces_catalog_service
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.status")


status_bp = Blueprint("status", __name__)


def _cache_header() -> str:
    """``Cache-Control`` value for the status probe.

    30 seconds matches the cadence external status-page consumers
    (Upptime, BetterUptime, Statuspage.io) poll at. Short enough that
    a freshly-completed sim appears in ``last_completed_at`` within
    half a minute; long enough that a load-balanced fleet of monitors
    doesn't hammer the scan path on every tick.
    """
    return "public, max-age=30"


@status_bp.route("/status.json", methods=["GET"])
def get_platform_status() -> Response:
    """Return the platform health envelope.

    Response shape::

        {
          "success": true,
          "data": {
            "ok": true,
            "schema_version": "1",
            "queue_depth": <int>,
            "completed_24h": <int>,
            "last_completed_at": <ISO-8601 UTC str | null>,
            "total_sims": <int>,
            "surface_count": <int>,
            "check_at": <ISO-8601 UTC str>
          }
        }

    ``ok`` is a literal ``true`` so a status-page template that only
    matches on the body has a stable anchor. A future regression in
    the scan that materially degrades the probe should bubble up via
    the JSON envelope (or a 500) rather than flipping the boolean —
    that way a downstream alert keyed on ``ok`` doesn't silently
    decay into a no-op.

    ``Cache-Control: public, max-age=30`` so a fleet of monitors
    polling on the same minute doesn't multiply the scan cost. No
    in-process cache — the surface is meant to be live, and a 30s
    HTTP cache is enough smoothing on its own.

    Empty / missing ``WONDERWALL_SIMULATION_DATA_DIR`` returns a
    fully-zeroed envelope (still ``200``, still ``ok: true``) rather
    than a 404 — a fresh install probing itself should see a
    valid response, not an error.
    """
    try:
        surface_count = surfaces_catalog_service.catalog_count()
    except Exception as exc:  # noqa: BLE001 — defensive: never tank the probe
        logger.warning(
            f"platform-status: surface_count read failed, defaulting to 0: {exc}"
        )
        surface_count = 0

    try:
        payload = platform_status_service.build_status(
            Config.WONDERWALL_SIMULATION_DATA_DIR,
            surface_count=surface_count,
        )
    except Exception as exc:
        logger.error(f"Failed to build platform status: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500

    response = jsonify({"success": True, "data": payload})
    response.headers["Cache-Control"] = _cache_header()
    return response
