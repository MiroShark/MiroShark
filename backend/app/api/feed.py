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
from ..services import gallery_filters
from ..services.simulation_manager import SimulationManager
from ..services.feed import (
    DEFAULT_FEED_LIMIT,
    MAX_FEED_LIMIT,
    render_feed,
    select_public_cards,
)
from ..services import surface_stats
from ..utils.base_url import resolve_public_base_url as _resolve_base_url
from ..utils.i18n import get_locale
from ..utils.logger import get_logger


logger = get_logger("miroshark.api.feed")


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

    # Same filter knobs the gallery exposes — composing them here turns
    # the feed into a structured signal source (Feedly / n8n / Zapier
    # consumers can subscribe to "bullish + excellent" without scraping
    # the gallery API). Validation mirrors gallery_filters exactly so a
    # bookmarked URL produces the same selection on both surfaces.
    q = gallery_filters.normalise_query(request.args.get("q"))
    consensus = gallery_filters.normalise_consensus(request.args.get("consensus"))
    quality = gallery_filters.normalise_quality(request.args.get("quality"))
    outcome = gallery_filters.normalise_outcome(request.args.get("outcome"))
    sort_key = gallery_filters.normalise_sort(request.args.get("sort"))

    # ``limit`` honours its own cap (50 — feed-specific, smaller than the
    # gallery's 100) since aggressive aggregators re-fetch the feed every
    # few minutes and a 100-entry XML doc costs them too much per poll.
    raw_limit = request.args.get("limit")
    limit = DEFAULT_FEED_LIMIT
    if raw_limit is not None and str(raw_limit).strip() != "":
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = DEFAULT_FEED_LIMIT
        limit = max(1, min(limit, MAX_FEED_LIMIT))

    try:
        manager = SimulationManager()
        all_sims = manager.list_simulations()
    except Exception as exc:
        # Never 500 the feed surface — readers will retry on the next
        # poll, an empty feed is the right interim state.
        logger.warning("feed: failed to list simulations (%s) — serving empty feed", exc)
        all_sims = []

    def _read_serves_total(sim_dir: str) -> int:
        try:
            stats = surface_stats.read_surface_stats(sim_dir)
            return int(stats.get("total", 0) or 0)
        except Exception:
            return 0

    cards = select_public_cards(
        all_sims,
        sim_data_dir=Config.WONDERWALL_SIMULATION_DATA_DIR,
        card_builder=_build_gallery_card_payload,
        outcome_reader=_read_outcome_file,
        limit=limit,
        verified_only=verified_only,
        q=q,
        consensus=consensus,
        quality=quality,
        outcome=outcome,
        sort=sort_key,
        surface_stats_reader=_read_serves_total if sort_key == "trending" else None,
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
        q=q,
        consensus=consensus,
        quality=quality,
        outcome=outcome,
        sort=sort_key,
    )

    response = Response(body, mimetype=mime)
    # 5-minute CDN-friendly cache. Short enough that a freshly published
    # simulation appears in subscribers' next poll without requiring a
    # cache bust, long enough to absorb aggressive aggregator polling.
    response.headers["Cache-Control"] = "public, max-age=300"

    # Each sim that appears in this feed render gets +1 on its own
    # ``feed_atom`` / ``feed_rss`` counter. The operator-facing question
    # this answers is: "was my sim syndicated to RSS subscribers in the
    # last poll cycle?" — which is the distribution signal that
    # matters, not the global feed-fetch count.
    surface_key = "feed_atom" if fmt == "atom" else "feed_rss"
    for card in cards:
        if not isinstance(card, dict):
            continue
        sim_id = card.get("simulation_id") or card.get("id")
        if not sim_id:
            continue
        surface_stats.increment_surface_stat(
            os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, str(sim_id)),
            surface_key,
        )
    return response


@feed_bp.route("/feed.atom", methods=["GET"])
def feed_atom():
    """Atom 1.0 representation of the public simulation gallery.

    Query parameters mirror the gallery API so a bookmarked feed URL
    answers the same question as ``GET /api/simulation/public``:

      * ``verified`` — truthy values (``1`` / ``true`` / ``yes`` / ``on``)
        restrict the feed to simulations with a recorded outcome
        annotation (the ``/verified`` curated hall).
      * ``q`` — case-insensitive substring search over each simulation's
        scenario text.
      * ``consensus`` — ``bullish`` / ``neutral`` / ``bearish``; uses
        the same ±0.2 stance dominance threshold as the gallery.
      * ``quality`` — ``excellent`` / ``good`` / ``fair`` / ``poor``.
      * ``outcome`` — ``correct`` / ``incorrect`` / ``partial`` (subset
        of ``verified=1`` that further narrows on the outcome label).
      * ``sort`` — ``date`` (default, newest first) / ``rounds`` /
        ``agents`` / ``trending`` (cumulative share-surface serves).
      * ``limit`` — 1..50; default 20.

    Unknown / invalid values fall back to the default for that knob — a
    typo'd ``?consensus=bullsih`` returns the full feed rather than an
    empty one, matching the gallery's "graceful degradation" contract.

    Default cap of 20 entries per the repo-actions specification — keeps
    the rendered XML small enough that aggressive aggregator polling
    stays cheap.
    """
    return _serve_feed("atom")


@feed_bp.route("/feed.rss", methods=["GET"])
def feed_rss():
    """RSS 2.0 representation of the public simulation gallery.

    Same content + selection + query parameter set as
    ``/api/feed.atom`` — older readers / self-hosted aggregators that
    haven't moved off RSS get the same filtered streams Atom subscribers
    do (``?consensus=`` / ``?quality=`` / ``?sort=`` / ``?q=`` /
    ``?outcome=`` / ``?verified=`` / ``?limit=``), so the discovery
    channel doesn't fragment on format.
    """
    return _serve_feed("rss")
