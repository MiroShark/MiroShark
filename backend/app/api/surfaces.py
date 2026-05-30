"""Machine-readable surface catalog endpoint.

Sibling of ``app/api/stats.py`` — both blueprints describe the
platform itself rather than one simulation. ``stats.py`` aggregates
runtime metrics over the corpus; ``surfaces.py`` describes the
capability surface area an integrator can call into.

One endpoint::

    GET /api/surfaces.json

Returns the full catalog of every share / platform surface this
deployment exposes — each entry carries the surface key, endpoint
path (with ``<simulation_id>`` placeholder where relevant), HTTP
method, type category, one-line description, originating PR, and a
copy-pasteable ``curl`` example.

Sandbox note: stdlib + Flask only. The catalog itself is a literal
list at module scope in ``services/surfaces_catalog.py``; no disk
scan, no Neo4j, no outbound network.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ..services import surfaces_catalog as surfaces_catalog_service
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.surfaces")


surfaces_bp = Blueprint("surfaces", __name__)


def _cache_header() -> str:
    """``Cache-Control`` value for the catalog endpoint.

    One hour matches the underlying catalog cadence — the catalog
    only changes when a new surface ships, which is bounded to a few
    PRs per week at most. A consumer polling every minute pays for one
    full body per hour and 304s for every subsequent request inside
    the window.
    """
    return "public, max-age=3600"


@surfaces_bp.route("/surfaces.json", methods=["GET"])
def get_surfaces_catalog() -> Response:
    """Return the full surface catalog as JSON.

    Response shape::

        {
          "success": true,
          "data": {
            "schema_version": "1",
            "count": <int>,
            "surfaces": [
              { "key": ..., "endpoint": ..., "method": "GET"|"POST",
                "type": "analytics"|"visualization"|"export"|"embed"
                       |"integration"|"platform"|"discovery",
                "description": <str, <=120 chars>,
                "added_in_pr": <int|null>,
                "example_curl": <str> },
              ...
            ]
          }
        }

    ``ETag`` derives from the catalog length — bumps when a new
    surface is appended. A conditional ``If-None-Match`` GET
    short-circuits to ``304 Not Modified`` so a polling consumer
    doesn't pay for the JSON body on every request.

    ``Cache-Control: public, max-age=3600`` — the catalog only
    changes when a new PR ships a new surface; one hour is a tight
    bound on the lag between a ship and the catalog reflecting it.

    Always returns ``200`` (or ``304``) — there is no input the
    caller can supply that would produce a ``404``. The catalog is
    intentionally static so the endpoint is itself idempotent across
    every deployment of the same code revision.
    """
    etag = surfaces_catalog_service.catalog_etag()
    if_none_match = (request.headers.get("If-None-Match") or "").strip()
    if if_none_match and if_none_match == etag:
        resp = Response(status=304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = _cache_header()
        return resp

    payload = surfaces_catalog_service.build_response_payload()
    response = jsonify({"success": True, "data": payload})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = _cache_header()
    return response
