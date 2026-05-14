"""Public ``GET /sitemap.xml`` + ``GET /robots.txt`` endpoints.

Search engines need a structured entry point into MiroShark's growing
public-simulation corpus before they can return individual sims as
results. The sitemap is auto-generated from the same ``is_public=true``
filter the gallery / feed / lineage surfaces share, so every newly
published sim is crawlable on the next sitemap fetch — no operator
intervention required after the initial Search-Console submission.

Mounted on a dedicated blueprint with **no URL prefix** so the URLs
match what crawlers expect (``/sitemap.xml`` and ``/robots.txt`` at
the root, not ``/api/sitemap.xml``). Registration mirrors the existing
``share_bp`` / ``watch_bp`` posture for the same reason — those keep
the public unfurl URL clean; this keeps the crawler-discovery URLs
clean.

Both endpoints opt in via ``ENABLE_SITEMAP=true`` (default ``true``).
Operators running a private MiroShark instance — or one indexing
sensitive scenarios — set ``ENABLE_SITEMAP=false`` to make
``/sitemap.xml`` return ``404`` and the ``robots.txt`` to drop the
``Sitemap:`` advertisement. The companion ``GET /api/config/sitemap``
endpoint exposes the flag to the SPA so ``EmbedDialog`` can render the
right hint.

Sandbox note: pure stdlib (``xml.etree.ElementTree`` from the
``sitemap`` service module + the existing ``SimulationManager``). No
outbound network — the routes never raise and never block on
Neo4j / LLM calls.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ..config import Config
from ..services.simulation_manager import SimulationManager
from ..services import sitemap as sitemap_service
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.sitemap")

sitemap_bp = Blueprint("sitemap", __name__)


def _resolve_base_url() -> str:
    """Build the absolute URL prefix used inside the sitemap document.

    Identical strategy to the feed module — prefer ``Config.PUBLIC_BASE_URL``
    when the operator has set it (single source of truth across the
    feed / webhook / share-card / sitemap surfaces) and fall back to
    the request's host with ``X-Forwarded-Proto`` / ``X-Forwarded-Host``
    honored for reverse-proxy deployments.
    """
    explicit = (Config.PUBLIC_BASE_URL or "").strip()
    if explicit:
        return explicit.rstrip("/")

    base = (request.host_url or "").rstrip("/")
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    forwarded_host = request.headers.get("X-Forwarded-Host")
    if forwarded_host:
        proto = forwarded_proto or ("https" if request.is_secure else "http")
        base = f"{proto}://{forwarded_host}"
    return base


@sitemap_bp.route("/sitemap.xml", methods=["GET"])
def sitemap_xml() -> Response:
    """Render the auto-generated public-simulation sitemap.

    Walks ``SimulationManager.list_simulations()`` for sims toggled
    ``is_public=true``, projects each into a ``<url>`` block (one for
    ``/share/<id>``, one for ``/watch/<id>``), and serializes per the
    sitemaps.org 0.9 spec. Returns ``application/xml`` so a browser
    rendering the URL shows the source rather than a hex dump.

    ``Cache-Control: public, max-age=3600`` — the sitemap is stable
    enough for an hourly cache; a freshly published simulation will
    appear within an hour at the latest, which matches the cadence
    Googlebot's scheduler uses for dynamic sites anyway.

    Returns ``404`` when ``ENABLE_SITEMAP=false`` so a private
    deployment's URL doesn't even hint that the sitemap surface
    exists.
    """
    if not Config.ENABLE_SITEMAP:
        return Response(
            "Sitemap disabled. Set ENABLE_SITEMAP=true to enable.",
            status=404,
            mimetype="text/plain; charset=utf-8",
        )

    try:
        manager = SimulationManager()
        all_sims = manager.list_simulations()
    except Exception as exc:
        # Never 500 the sitemap surface — crawlers retry, an empty
        # sitemap is the right interim state if the manager fails.
        logger.warning("sitemap: failed to list simulations (%s) — serving empty sitemap", exc)
        all_sims = []

    base_url = _resolve_base_url()
    body = sitemap_service.build_sitemap(
        all_sims,
        base_url,
        sim_data_dir=Config.WONDERWALL_SIMULATION_DATA_DIR,
    )

    response = Response(body, mimetype="application/xml; charset=utf-8")
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@sitemap_bp.route("/robots.txt", methods=["GET"])
def robots_txt() -> Response:
    """Render the public ``robots.txt`` for the deployment.

    Always served (even when ``ENABLE_SITEMAP=false``) so well-behaved
    crawlers see the ``Disallow: /api/`` directive — without a
    ``robots.txt`` they'll attempt to crawl the API namespace and
    pollute the index with JSON 404s. When the sitemap is enabled,
    a trailing ``Sitemap:`` line points crawlers at it for automatic
    discovery; when disabled, the line is omitted.

    ``Cache-Control: public, max-age=3600`` mirrors the sitemap cadence
    so a single CDN purge refreshes both surfaces together.
    """
    base_url = _resolve_base_url()
    body = sitemap_service.build_robots_txt(
        base_url,
        enabled=bool(Config.ENABLE_SITEMAP),
    )

    response = Response(body, mimetype="text/plain; charset=utf-8")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@sitemap_bp.route("/api/config/sitemap", methods=["GET"])
def sitemap_config() -> Response:
    """Expose the ``ENABLE_SITEMAP`` flag to the SPA.

    Lets the EmbedDialog render the right hint without leaking any
    secret config. Returns ``{success, data: {enabled, sitemap_url}}``
    where ``sitemap_url`` is the absolute public URL when enabled and
    ``None`` otherwise. Public — the flag is not sensitive and the
    URL is the same one any crawler would discover via robots.txt.
    """
    enabled = bool(Config.ENABLE_SITEMAP)
    sitemap_url = None
    if enabled:
        base = _resolve_base_url()
        if base:
            sitemap_url = f"{base}/sitemap.xml"
    response = jsonify({
        "success": True,
        "data": {
            "enabled": enabled,
            "sitemap_url": sitemap_url,
        },
    })
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response
