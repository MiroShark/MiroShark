"""Public-gallery syndication feeds — Atom 1.0 + RSS 2.0.

Serves the same cards ``GET /api/simulation/public`` returns, but as
syndication XML so research-and-tooling readers can subscribe in
Feedly / Readwise / Inoreader / Obsidian RSS / NetNewsWire — every newly
published MiroShark simulation lands in a follower's reader the same way
an AI newsletter or Substack post does.

Mounted on a dedicated blueprint at ``/api`` so the URLs stay short
(``/api/feed.atom``, ``/api/feed.rss``) and don't bury under the
``/api/simulation/...`` namespace where they'd be missed by feed
auto-discovery scripts.

Same publish gate as the gallery itself: only simulations toggled
``is_public=true`` appear, exactly the set already on /explore.

Sandbox note: pure stdlib (``xml.etree.ElementTree`` + the existing
``SimulationManager``). No outbound network — the route never raises and
never blocks on Neo4j / LLM calls.
"""

from __future__ import annotations

import os

from flask import Response, request

from . import feed_bp
from ..config import Config
from ..services.simulation_manager import SimulationManager
from ..services.feed import (
    DEFAULT_FEED_LIMIT,
    render_feed,
    select_public_cards,
)
from ..utils.i18n import get_locale
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.feed")


def _resolve_base_url() -> str:
    """Build the absolute URL prefix used inside the feed XML.

    Prefers ``Config.PUBLIC_BASE_URL`` (the operator-supplied canonical
    deployment URL — same field the webhook payload + share-card use)
    so a feed served from ``localhost`` but configured for a public host
    still points at the public host. Falls back to the request's host
    URL with X-Forwarded-Proto/Host honored when behind a reverse proxy.
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


def _is_truthy(value: str) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _serve_feed(fmt: str) -> Response:
    """Shared body for the Atom + RSS endpoints.

    ``fmt`` is ``"atom"`` or ``"rss"``; the renderer handles the per-
    format differences and the MIME type.
    """
    # Local imports keep the module-load graph small — feed.py is
    # cheap to import on its own, but the gallery helper pulls in the
    # full simulation API surface, so we defer until the request
    # actually fires.
    from .simulation import _build_gallery_card_payload, _read_outcome_file

    verified_only = _is_truthy(request.args.get("verified") or "")

    try:
        manager = SimulationManager()
        all_sims = manager.list_simulations()
    except Exception as exc:
        # Never 500 the feed surface — readers will retry on the next
        # poll, an empty feed is the right interim state.
        logger.warning("feed: failed to list simulations (%s) — serving empty feed", exc)
        all_sims = []

    cards = select_public_cards(
        all_sims,
        sim_data_dir=Config.WONDERWALL_SIMULATION_DATA_DIR,
        card_builder=_build_gallery_card_payload,
        outcome_reader=_read_outcome_file,
        limit=DEFAULT_FEED_LIMIT,
        verified_only=verified_only,
    )

    base_url = _resolve_base_url()
    feed_path = request.full_path.rstrip("?") or request.path
    locale = get_locale(request)

    body, mime = render_feed(
        fmt,
        cards,
        base_url=base_url,
        feed_path=feed_path,
        verified_only=verified_only,
        locale=locale,
    )

    response = Response(body, mimetype=mime)
    # 5-minute CDN-friendly cache. Short enough that a freshly published
    # simulation appears in subscribers' next poll without requiring a
    # cache bust, long enough to absorb aggressive aggregator polling.
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@feed_bp.route("/feed.atom", methods=["GET"])
def feed_atom():
    """Atom 1.0 representation of the public simulation gallery.

    Query parameters:

      * ``verified`` — when truthy (``1``, ``true``, ``yes``, ``on``)
        restricts the feed to simulations with a recorded outcome
        annotation (the ``/verified`` curated hall).

    Cap of 20 entries per the repo-actions specification — keeps the
    rendered XML small enough that aggressive aggregator polling stays
    cheap.
    """
    return _serve_feed("atom")


@feed_bp.route("/feed.rss", methods=["GET"])
def feed_rss():
    """RSS 2.0 representation of the public simulation gallery.

    Same content + selection as ``/api/feed.atom`` — older readers /
    self-hosted aggregators that haven't moved off RSS get this surface
    so the discovery channel doesn't fragment on format.
    """
    return _serve_feed("rss")
