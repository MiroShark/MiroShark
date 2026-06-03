"""Machine-readable surface catalog endpoints.

Sibling of ``app/api/stats.py`` — both blueprints describe the
platform itself rather than one simulation. ``stats.py`` aggregates
runtime metrics over the corpus; ``surfaces.py`` describes the
discoverable surface area an integrator can call into and the
ecosystem of integrators already building on it.

Two endpoints::

    GET /api/surfaces.json
    GET /api/ecosystem.json

``surfaces.json`` returns the full catalog of every share / platform
surface this deployment exposes — each entry carries the surface key,
endpoint path (with ``<simulation_id>`` placeholder where relevant),
HTTP method, type category, one-line description, originating PR, and
a copy-pasteable ``curl`` example.

``ecosystem.json`` returns the machine-readable counterpart of
``ECOSYSTEM.md`` — every public project, agent, and product
identified as built on MiroShark, with a stable category, primary
URL, X handle, and repo link per entry. An integrator iterating the
catalog never has to parse Markdown to discover what else is built
on the platform.

Sandbox note: stdlib + Flask only. Both catalogues are literal lists
at module scope (``services/surfaces_catalog.py`` and
``services/ecosystem_catalog.py``); no disk scan, no Neo4j, no
outbound network.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ..services import ecosystem_catalog as ecosystem_catalog_service
from ..services import surfaces_catalog as surfaces_catalog_service
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.surfaces")


surfaces_bp = Blueprint("surfaces", __name__)


def _cache_header() -> str:
    """``Cache-Control`` value for both catalog endpoints.

    One hour matches the underlying catalog cadence — both catalogues
    only change when a new surface or integrator ships, which is
    bounded to a few PRs per week at most. A consumer polling every
    minute pays for one full body per hour and 304s for every
    subsequent request inside the window.
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


@surfaces_bp.route("/ecosystem.json", methods=["GET"])
def get_ecosystem_catalog() -> Response:
    """Return the full ecosystem catalog as JSON.

    Machine-readable counterpart of ``ECOSYSTEM.md`` — every external
    project, agent, and product publicly identified as built on
    MiroShark. An integrator iterating the catalog never has to parse
    the Markdown table.

    Response shape::

        {
          "success": true,
          "data": {
            "schema_version": "1",
            "count": <int>,
            "ecosystem": [
              { "name": <str>,
                "url": <str>,
                "description": <str, <=160 chars>,
                "category": "product"|"tool"|"integration"
                           |"agent"|"benchmark",
                "x_handle": <str|null>,
                "repo": <str|null> },
              ...
            ]
          }
        }

    ``ETag`` derives from the catalog length — bumps when a new
    integrator is appended. A conditional ``If-None-Match`` GET
    short-circuits to ``304 Not Modified`` so a polling consumer
    doesn't pay for the JSON body on every request.

    ``Cache-Control: public, max-age=3600`` — the catalog only
    changes when a new PR adds an integrator; one hour is a tight
    bound on the lag between a ship and the catalog reflecting it.

    Always returns ``200`` (or ``304``) — there is no input the
    caller can supply that would produce a ``404``. The catalog is
    intentionally static so the endpoint is itself idempotent across
    every deployment of the same code revision.
    """
    etag = ecosystem_catalog_service.catalog_etag()
    if_none_match = (request.headers.get("If-None-Match") or "").strip()
    if if_none_match and if_none_match == etag:
        resp = Response(status=304)
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = _cache_header()
        return resp

    payload = ecosystem_catalog_service.build_response_payload()
    response = jsonify({"success": True, "data": payload})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = _cache_header()
    return response
