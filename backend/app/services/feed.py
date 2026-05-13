"""Atom 1.0 / RSS 2.0 feed renderer for the public simulation gallery.

Converts the same on-disk gallery cards that back ``GET /api/simulation/public``
into a syndication feed so researchers / DeFi analysts / AI tooling
operators can subscribe in Feedly, Readwise, Inoreader, Obsidian RSS,
NetNewsWire, etc. — every newly published MiroShark simulation lands in
their reader the same way an AI newsletter or a Substack post does.

Pure stdlib (``xml.etree.ElementTree`` + ``html``). Zero new dependencies.
Same ±0.2 stance threshold the gallery / share card / replay GIF / webhook
all share, so a sim's "62% bullish / 13% neutral / 25% bearish" string
matches the gallery card on every surface.

Two output formats:

  * **Atom 1.0** (``application/atom+xml``) — preferred by modern readers
    and the format browsers auto-discover via ``<link rel="alternate">``.
  * **RSS 2.0** (``application/rss+xml``) — kept for parity with older
    readers that haven't moved off RSS yet.

Both render from the same ``feed_payload(...)`` shape — the route layer
supplies the cards, this module supplies the bytes.

The feed is intentionally **read-only** and **publish-gated**: only
simulations toggled `is_public=true` appear, the same gate the share
card and transcript exports honor.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional
from xml.etree import ElementTree as ET

from . import gallery_filters


# Atom requires a stable feed id even when the underlying paths change —
# anchor it on the host so a deployment behind a different base URL
# keeps a distinct feed identity.
FEED_GENERATOR_NAME = "MiroShark"

# How many entries a feed tops out at. Mirrors the repo-actions
# specification (20) — keeps the rendered XML small enough that bots
# polling on a tight cadence don't pull megabytes per fetch.
DEFAULT_FEED_LIMIT = 20

# Hard ceiling for ``?limit=`` on the feed surface — readers + bots that
# poll aggressively don't get to extract the whole gallery in one fetch.
# Matches the gallery API cap.
MAX_FEED_LIMIT = 50

# Atom + RSS title cap. Most readers truncate around 100 chars when
# laying out the river view, so trim there with an ellipsis to keep
# tooltips clean.
TITLE_CHARS = 100


# ── Helpers ────────────────────────────────────────────────────────────────


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def _isoformat_z(value: Optional[str]) -> str:
    """Coerce a datetime-ish value to RFC3339 / ISO8601 ``Z`` form.

    Atom requires ``updated`` and ``published`` in RFC3339; RSS 2.0
    requires RFC822 (rendered separately). Both readers accept ``Z`` for
    UTC; we treat naive ISO strings as UTC since that's what the
    simulation manager writes.
    """
    if not value:
        return _now_z()
    try:
        s = str(value).strip()
        if s.endswith("Z"):
            return s
        # ``datetime.fromisoformat`` accepts naive and offset-aware
        # strings on 3.11+ — what fails is microsecond + timezone-naïve
        # mixed with the "Z" suffix some upstreams emit.
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return _now_z()


def _now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_rfc822(value: Optional[str]) -> str:
    """RFC822 date — RSS 2.0 ``<pubDate>`` requires it."""
    if not value:
        dt = datetime.now(timezone.utc)
    else:
        try:
            s = str(value).strip()
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            dt = datetime.now(timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _consensus_blurb(consensus: Optional[dict]) -> str:
    """One-line stance split — appears in every feed entry's summary so
    the river view in a reader telegraphs the simulation's outcome
    without opening it."""
    if not consensus:
        return "Belief consensus not yet available."
    bull = float(consensus.get("bullish") or 0)
    neut = float(consensus.get("neutral") or 0)
    bear = float(consensus.get("bearish") or 0)
    return (
        f"🔵 {bull:.1f}% Bullish · "
        f"⚪ {neut:.1f}% Neutral · "
        f"🔴 {bear:.1f}% Bearish"
    )


def _entry_summary(card: dict) -> str:
    """Plain-text summary line per entry — bullish/neutral/bearish split,
    quality, agent count. Readers index this for search and show it in
    list views."""
    parts: list[str] = [_consensus_blurb(card.get("final_consensus"))]

    quality = (card.get("quality_health") or "").strip()
    if quality:
        parts.append(f"Quality: {quality}")

    agents = card.get("agent_count")
    if isinstance(agents, int) and agents > 0:
        parts.append(f"Agents: {agents}")

    rounds_now = card.get("current_round") or 0
    rounds_total = card.get("total_rounds") or 0
    if rounds_total:
        parts.append(f"Rounds: {rounds_now}/{rounds_total}")
    elif rounds_now:
        parts.append(f"Rounds: {rounds_now}")

    outcome = card.get("outcome") or {}
    if outcome:
        label = (outcome.get("label") or "").strip()
        if label == "correct":
            parts.append("📍 Verified — called it")
        elif label == "incorrect":
            parts.append("⚠ Called wrong")
        elif label == "partial":
            parts.append("◑ Partial outcome")

    resolution = (card.get("resolution_outcome") or "").strip()
    if resolution:
        parts.append(f"Resolved: {resolution}")

    return " · ".join(parts)


def _entry_html_summary(card: dict, share_url: str, replay_gif_url: Optional[str]) -> str:
    """Rich HTML summary for ``content type='html'`` — readers that
    render HTML (Feedly, Inoreader, NetNewsWire) get a clickable preview;
    text-only readers fall back to the plain ``summary`` element."""
    scenario = html.escape(card.get("scenario") or "(untitled scenario)", quote=False)
    line = html.escape(_entry_summary(card), quote=False)
    safe_share = html.escape(share_url, quote=True)
    blocks: list[str] = [
        f'<p><strong>{scenario}</strong></p>',
        f'<p>{line}</p>',
    ]
    if replay_gif_url:
        safe_gif = html.escape(replay_gif_url, quote=True)
        blocks.append(
            f'<p><img src="{safe_gif}" alt="Belief replay" '
            'style="max-width:100%;height:auto;" /></p>'
        )
    blocks.append(
        f'<p><a href="{safe_share}">View on MiroShark →</a></p>'
    )
    return "".join(blocks)


def _absolute(base_url: str, relative: Optional[str]) -> Optional[str]:
    """Resolve a relative path (``/api/simulation/sim_x/share-card.png``)
    against the deployment base URL. Returns ``None`` when the input is
    falsy so callers can omit the field cleanly."""
    if not relative:
        return None
    if relative.startswith("http://") or relative.startswith("https://"):
        return relative
    if not base_url:
        return relative
    if relative.startswith("/"):
        return f"{base_url.rstrip('/')}{relative}"
    return f"{base_url.rstrip('/')}/{relative}"


def _entry_id(base_url: str, sim_id: str) -> str:
    """Stable Atom entry id — must not change across feed fetches.

    Anchoring on the share landing URL gives us a globally unique URI per
    simulation that survives backend redeploys (the share URL is the
    canonical permalink anyway).
    """
    base = (base_url or "").rstrip("/")
    if base:
        return f"{base}/share/{sim_id}"
    return f"urn:miroshark:simulation:{sim_id}"


# ── Atom 1.0 ───────────────────────────────────────────────────────────────


_ATOM_NS = "http://www.w3.org/2005/Atom"
_MEDIA_NS = "http://search.yahoo.com/mrss/"


def render_atom(
    cards: Iterable[dict],
    *,
    base_url: str,
    feed_path: str,
    title: str,
    subtitle: str,
    verified_only: bool = False,
) -> bytes:
    """Render the public-gallery cards as an Atom 1.0 XML feed.

    ``feed_path`` is the request path that produced this feed (e.g.
    ``/api/feed.atom?verified=1``) — used as the ``rel="self"`` link so
    readers can re-fetch from the canonical URL even if they discovered
    the feed at a different path.
    """
    ET.register_namespace("", _ATOM_NS)
    ET.register_namespace("media", _MEDIA_NS)

    feed = ET.Element(f"{{{_ATOM_NS}}}feed")

    feed_id = _absolute(base_url, feed_path) or f"urn:miroshark:feed:{feed_path}"
    ET.SubElement(feed, f"{{{_ATOM_NS}}}id").text = feed_id
    ET.SubElement(feed, f"{{{_ATOM_NS}}}title").text = title
    ET.SubElement(feed, f"{{{_ATOM_NS}}}subtitle").text = subtitle

    # rel="self" — canonical URL of this feed.
    self_href = _absolute(base_url, feed_path) or feed_path
    ET.SubElement(
        feed,
        f"{{{_ATOM_NS}}}link",
        attrib={"rel": "self", "type": "application/atom+xml", "href": self_href},
    )

    # rel="alternate" — the human-readable gallery the feed mirrors.
    alternate_path = "/verified" if verified_only else "/explore"
    alternate_href = _absolute(base_url, alternate_path) or alternate_path
    ET.SubElement(
        feed,
        f"{{{_ATOM_NS}}}link",
        attrib={"rel": "alternate", "type": "text/html", "href": alternate_href},
    )

    cards_list = list(cards)
    most_recent = ""
    for c in cards_list:
        ts = _isoformat_z(c.get("created_at"))
        if ts > most_recent:
            most_recent = ts
    ET.SubElement(feed, f"{{{_ATOM_NS}}}updated").text = most_recent or _now_z()

    generator = ET.SubElement(feed, f"{{{_ATOM_NS}}}generator")
    generator.set("uri", "https://github.com/aaronjmars/MiroShark")
    generator.text = FEED_GENERATOR_NAME

    author = ET.SubElement(feed, f"{{{_ATOM_NS}}}author")
    ET.SubElement(author, f"{{{_ATOM_NS}}}name").text = "MiroShark Operators"

    for card in cards_list:
        sim_id = card.get("simulation_id") or ""
        if not sim_id:
            continue

        share_url = _absolute(base_url, card.get("share_landing_url")) or _entry_id(
            base_url, sim_id
        )
        share_card_url = _absolute(base_url, card.get("share_card_url"))
        replay_gif_url = _absolute(
            base_url, f"/api/simulation/{sim_id}/replay.gif"
        )

        scenario = card.get("scenario") or "(untitled scenario)"
        entry = ET.SubElement(feed, f"{{{_ATOM_NS}}}entry")
        ET.SubElement(entry, f"{{{_ATOM_NS}}}id").text = _entry_id(base_url, sim_id)
        ET.SubElement(entry, f"{{{_ATOM_NS}}}title").text = _truncate(
            scenario, TITLE_CHARS
        )
        ET.SubElement(
            entry,
            f"{{{_ATOM_NS}}}link",
            attrib={"rel": "alternate", "type": "text/html", "href": share_url},
        )
        ET.SubElement(entry, f"{{{_ATOM_NS}}}updated").text = _isoformat_z(
            card.get("created_at")
        )
        ET.SubElement(entry, f"{{{_ATOM_NS}}}published").text = _isoformat_z(
            card.get("created_at")
        )

        ET.SubElement(entry, f"{{{_ATOM_NS}}}summary").text = _entry_summary(card)

        content = ET.SubElement(
            entry,
            f"{{{_ATOM_NS}}}content",
            attrib={"type": "html"},
        )
        content.text = _entry_html_summary(card, share_url, replay_gif_url)

        # MediaRSS-style enclosures for readers that surface previews
        # (Feedly's River view, Inoreader's magazine layout). Each card
        # has a static share card PNG; published runs also have an
        # animated belief-replay GIF.
        if share_card_url:
            ET.SubElement(
                entry,
                f"{{{_MEDIA_NS}}}thumbnail",
                attrib={"url": share_card_url, "width": "1200", "height": "630"},
            )
            ET.SubElement(
                entry,
                f"{{{_MEDIA_NS}}}content",
                attrib={
                    "url": share_card_url,
                    "type": "image/png",
                    "medium": "image",
                    "width": "1200",
                    "height": "630",
                },
            )
        if replay_gif_url:
            ET.SubElement(
                entry,
                f"{{{_MEDIA_NS}}}content",
                attrib={
                    "url": replay_gif_url,
                    "type": "image/gif",
                    "medium": "image",
                },
            )

        # Outcome / quality categories make a feed filterable on the
        # reader side — Feedly lets users save category-keyed searches.
        outcome = card.get("outcome") or {}
        outcome_label = (outcome.get("label") or "").strip()
        if outcome_label:
            ET.SubElement(
                entry,
                f"{{{_ATOM_NS}}}category",
                attrib={"term": f"verified-{outcome_label}", "label": "Verified"},
            )
        quality = (card.get("quality_health") or "").strip()
        if quality:
            ET.SubElement(
                entry,
                f"{{{_ATOM_NS}}}category",
                attrib={"term": f"quality-{quality.lower()}", "label": quality},
            )

    body = ET.tostring(feed, encoding="utf-8", xml_declaration=True)
    return body


# ── RSS 2.0 ────────────────────────────────────────────────────────────────


def render_rss(
    cards: Iterable[dict],
    *,
    base_url: str,
    feed_path: str,
    title: str,
    subtitle: str,
    verified_only: bool = False,
    locale: str = "en",
) -> bytes:
    """Render the public-gallery cards as an RSS 2.0 XML feed.

    Mirrors :func:`render_atom` but emits the older format for readers
    that haven't moved to Atom (still common in self-hosted aggregators
    and academic RSS pipelines).
    """
    ET.register_namespace("media", _MEDIA_NS)
    ET.register_namespace("atom", _ATOM_NS)

    rss = ET.Element("rss", attrib={"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "description").text = subtitle

    alternate_path = "/verified" if verified_only else "/explore"
    alternate_href = _absolute(base_url, alternate_path) or alternate_path
    ET.SubElement(channel, "link").text = alternate_href

    self_href = _absolute(base_url, feed_path) or feed_path
    ET.SubElement(
        channel,
        f"{{{_ATOM_NS}}}link",
        attrib={"rel": "self", "type": "application/rss+xml", "href": self_href},
    )

    ET.SubElement(channel, "generator").text = (
        f"{FEED_GENERATOR_NAME} (https://github.com/aaronjmars/MiroShark)"
    )
    ET.SubElement(channel, "language").text = "zh-CN" if locale == "zh-CN" else "en"

    cards_list = list(cards)
    most_recent_iso = ""
    for c in cards_list:
        ts = _isoformat_z(c.get("created_at"))
        if ts > most_recent_iso:
            most_recent_iso = ts
    ET.SubElement(channel, "lastBuildDate").text = _to_rfc822(most_recent_iso)
    ET.SubElement(channel, "pubDate").text = _to_rfc822(most_recent_iso)

    for card in cards_list:
        sim_id = card.get("simulation_id") or ""
        if not sim_id:
            continue

        share_url = _absolute(base_url, card.get("share_landing_url")) or _entry_id(
            base_url, sim_id
        )
        share_card_url = _absolute(base_url, card.get("share_card_url"))
        replay_gif_url = _absolute(
            base_url, f"/api/simulation/{sim_id}/replay.gif"
        )

        scenario = card.get("scenario") or "(untitled scenario)"
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = _truncate(scenario, TITLE_CHARS)
        ET.SubElement(item, "link").text = share_url

        # ``isPermaLink="false"`` — the share landing URL is already
        # ``<link>``; ``<guid>`` carries our stable identifier.
        guid = ET.SubElement(item, "guid", attrib={"isPermaLink": "false"})
        guid.text = _entry_id(base_url, sim_id)

        ET.SubElement(item, "pubDate").text = _to_rfc822(card.get("created_at"))
        ET.SubElement(item, "description").text = _entry_html_summary(
            card, share_url, replay_gif_url
        )

        if share_card_url:
            ET.SubElement(
                item,
                "enclosure",
                attrib={
                    "url": share_card_url,
                    "type": "image/png",
                    "length": "0",
                },
            )
            ET.SubElement(
                item,
                f"{{{_MEDIA_NS}}}thumbnail",
                attrib={"url": share_card_url, "width": "1200", "height": "630"},
            )
        if replay_gif_url:
            ET.SubElement(
                item,
                f"{{{_MEDIA_NS}}}content",
                attrib={
                    "url": replay_gif_url,
                    "type": "image/gif",
                    "medium": "image",
                },
            )

        outcome = card.get("outcome") or {}
        outcome_label = (outcome.get("label") or "").strip()
        if outcome_label:
            ET.SubElement(item, "category").text = f"verified-{outcome_label}"
        quality = (card.get("quality_health") or "").strip()
        if quality:
            ET.SubElement(item, "category").text = f"quality-{quality.lower()}"

    body = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    return body


# ── Public-facing render dispatcher ───────────────────────────────────────


def _filter_chip(
    *,
    consensus: Optional[str],
    quality: Optional[str],
    outcome: Optional[str],
    q: str,
    sort: str,
    is_zh: bool,
) -> str:
    """One-line summary of the active filters for the feed title/subtitle.

    Returns an empty string when no filter is active so the unfiltered
    feed renders its original title. Sort is only echoed when the caller
    opted out of the default (``date``) — readers expect "latest" by
    default, so naming it explicitly would be noise.
    """
    parts: list[str] = []
    if consensus:
        parts.append(
            {
                "bullish": ("Bullish", "看涨"),
                "neutral": ("Neutral", "中性"),
                "bearish": ("Bearish", "看跌"),
            }[consensus][1 if is_zh else 0]
        )
    if quality:
        label_en = quality.capitalize()
        label_zh = {
            "excellent": "优",
            "good": "良",
            "fair": "中",
            "poor": "差",
        }.get(quality, quality)
        parts.append(label_zh if is_zh else label_en)
    if outcome:
        label_zh, label_en = {
            "correct": ("已验证", "Verified"),
            "incorrect": ("误判", "Incorrect"),
            "partial": ("部分应验", "Partial"),
        }.get(outcome, (outcome, outcome.capitalize()))
        parts.append(label_zh if is_zh else label_en)
    if q:
        # Trim to keep the title row narrow in River-view UIs; readers
        # see the full query if they expand the entry.
        snippet = q.strip()
        if len(snippet) > 30:
            snippet = snippet[:29].rstrip() + "…"
        parts.append(f'"{snippet}"')
    sort_norm = (sort or "").strip().lower()
    if sort_norm in {"trending", "rounds", "agents"}:
        sort_label_zh = {
            "trending": "热度",
            "rounds": "轮次",
            "agents": "智能体",
        }[sort_norm]
        sort_label_en = sort_norm.capitalize()
        parts.append(
            ("按" + sort_label_zh) if is_zh else f"sorted by {sort_label_en}"
        )
    if not parts:
        return ""
    sep = " · " if is_zh else " · "
    return sep.join(parts)


def render_feed(
    fmt: str,
    cards: Iterable[dict],
    *,
    base_url: str,
    feed_path: str,
    verified_only: bool = False,
    locale: str = "en",
    q: str = "",
    consensus: Optional[str] = None,
    quality: Optional[str] = None,
    outcome: Optional[str] = None,
    sort: str = "date",
) -> tuple[bytes, str]:
    """Render the feed in the requested format.

    Returns ``(body_bytes, mime_type)``. ``fmt`` accepts ``"atom"`` (the
    default) or ``"rss"`` — anything else falls back to Atom so a
    misrouted call still returns a valid feed.

    ``locale`` switches the channel title + description between English
    (default) and ``zh-CN``. Per-entry scenario text and the bracketed
    feature names (Feedly / Readwise / Inoreader / NetNewsWire) stay in
    their source language so reader auto-discovery still matches.

    Active filters (``consensus``, ``quality``, ``outcome``, ``q``, non-
    default ``sort``) are appended to the channel title + subtitle so a
    subscriber whose feed is "MiroShark · Bullish + Excellent" can tell
    at a glance which slice of the gallery they signed up for. Empty
    filters fall through to the original title.
    """
    is_zh = locale == "zh-CN"
    chip = _filter_chip(
        consensus=consensus,
        quality=quality,
        outcome=outcome,
        q=q,
        sort=sort,
        is_zh=is_zh,
    )
    if verified_only:
        if is_zh:
            title = "MiroShark · 已验证预言"
            subtitle = (
                "已被运营者标注真实世界结果的 MiroShark 公开模拟——"
                "应验的预言(以及未应验的)。"
            )
        else:
            title = "MiroShark · Verified Predictions"
            subtitle = (
                "Public MiroShark simulations whose operators marked a "
                "real-world outcome — calls that landed (and those that didn't)."
            )
    else:
        if is_zh:
            title = "MiroShark · 公开模拟"
            subtitle = (
                "最新发布的 MiroShark 模拟——智能体群体、信念漂移与预测结果,"
                "可分叉到你自己的场景中。"
            )
        else:
            title = "MiroShark · Public Simulations"
            subtitle = (
                "Newest published MiroShark simulations — agent populations, "
                "belief drift, and prediction outcomes you can fork into your "
                "own scenarios."
            )

    if chip:
        title = f"{title} · {chip}"
        suffix = (
            f"已应用筛选: {chip}." if is_zh
            else f"Filtered: {chip}."
        )
        subtitle = f"{subtitle} {suffix}"

    fmt_norm = (fmt or "").strip().lower()
    if fmt_norm == "rss":
        body = render_rss(
            cards,
            base_url=base_url,
            feed_path=feed_path,
            title=title,
            subtitle=subtitle,
            verified_only=verified_only,
            locale=locale,
        )
        mime = "application/rss+xml; charset=utf-8"
    else:
        body = render_atom(
            cards,
            base_url=base_url,
            feed_path=feed_path,
            title=title,
            subtitle=subtitle,
            verified_only=verified_only,
        )
        mime = "application/atom+xml; charset=utf-8"
    return body, mime


def select_public_cards(
    sims: Iterable[Any],
    *,
    sim_data_dir: str,
    card_builder,
    outcome_reader,
    limit: int = DEFAULT_FEED_LIMIT,
    verified_only: bool = False,
    q: str = "",
    consensus: Optional[str] = None,
    quality: Optional[str] = None,
    outcome: Optional[str] = None,
    sort: str = "date",
    surface_stats_reader: Optional[Callable[[str], int]] = None,
) -> list[dict]:
    """Filter + sort + truncate the gallery cards used to render a feed.

    Mirrors the exact selection ``GET /api/simulation/public`` performs so
    a subscription stays in lockstep with what shows up on /explore — and
    extends that parity to the gallery's filter knobs (``q``, ``consensus``,
    ``quality``, ``outcome``, ``sort``). An operator who scoped their
    /explore view to "bullish + excellent" gets the same selection in
    RSS by appending ``?consensus=bullish&quality=excellent`` to their
    feed URL.

    ``sort="trending"`` ranks by the cumulative share-surface serve count
    that the gallery surfaces — pass a ``surface_stats_reader`` callback
    that takes a ``sim_dir`` and returns the integer total. The reader is
    only invoked when ``sort == "trending"`` so the default ``date`` path
    stays read-free.

    Pulled out into a helper so the feed module can be unit-tested
    without booting Flask: the route layer plugs in the real
    ``_build_gallery_card_payload`` and ``_read_outcome_file``.
    """
    import os

    sort_key = gallery_filters.normalise_sort(sort)

    # Build cards for every public sim, then let ``gallery_filters`` do
    # the filter / sort / limit dance the gallery API already uses. Going
    # through the same helper guarantees the feed and ``GET
    # /api/simulation/public`` answer the same question identically — a
    # 33.4 / 33.3 / 33.3 split never leaks into ``consensus=bullish`` on
    # either surface, ``quality_health="Good with caveats"`` matches
    # ``quality=good`` on both, etc.
    public_sims = [s for s in sims if bool(getattr(s, "is_public", False))]

    cards: list[dict] = []
    for state in public_sims:
        sim_dir = os.path.join(sim_data_dir, state.simulation_id)
        try:
            cards.append(card_builder(state, sim_dir))
        except Exception:
            # One bad sim should not blank out the whole feed.
            continue

    if sort_key == "trending" and surface_stats_reader is not None:
        for card in cards:
            sim_id = card.get("simulation_id") or card.get("id") or ""
            sim_dir = os.path.join(sim_data_dir, sim_id)
            try:
                card[gallery_filters.TRENDING_FIELD] = int(
                    surface_stats_reader(sim_dir) or 0
                )
            except Exception:
                card[gallery_filters.TRENDING_FIELD] = 0

    # Clamp ``limit`` into the feed envelope first so a caller passing
    # ``limit=10_000`` can't bypass our 50-entry cap by going through this
    # helper — the gallery's MAX_LIMIT (100) is too generous for an XML
    # surface that aggressive aggregators re-fetch every few minutes.
    try:
        effective_limit = int(limit) if limit is not None else DEFAULT_FEED_LIMIT
    except (TypeError, ValueError):
        effective_limit = DEFAULT_FEED_LIMIT
    effective_limit = max(1, min(effective_limit, MAX_FEED_LIMIT))

    # ``verified_only`` is enforced via the on-disk ``outcome_reader``
    # rather than gallery_filters' embedded-outcome gate: the live card
    # builder (``_build_gallery_card_payload``) doesn't always inline the
    # outcome record, so trusting the card field alone would silently
    # drop legit verified sims. Run the on-disk gate BEFORE the rest of
    # the filter stack so the trending / pagination math operates on the
    # right corpus.
    if verified_only and outcome_reader is not None:
        cards = [
            c for c in cards
            if _has_outcome_record(c, sim_data_dir, outcome_reader)
        ]
    elif verified_only:
        cards = [c for c in cards if (c.get("outcome") or {}).get("label")]

    page, _total = gallery_filters.select_filtered_cards(
        cards,
        q=q or "",
        consensus=consensus,
        quality=quality,
        outcome=outcome,
        verified_only=False,
        sort=sort_key,
        limit=effective_limit,
        offset=0,
    )

    # Drop the transient trending field — it's an implementation detail of
    # the sort, not part of the per-card payload feed renderers consume.
    if sort_key == "trending":
        for card in page:
            card.pop(gallery_filters.TRENDING_FIELD, None)

    return page


def _has_outcome_record(
    card: dict,
    sim_data_dir: str,
    outcome_reader: Callable[[str], Any],
) -> bool:
    """Return True iff the card already carries an outcome OR the
    on-disk reader confirms one for the sim. Belt-and-suspenders so the
    verified gate matches the pre-filter behaviour even when the card
    builder skipped reading ``outcome.json``.
    """
    import os

    if isinstance(card.get("outcome"), dict) and card["outcome"].get("label"):
        return True
    sim_id = card.get("simulation_id") or card.get("id") or ""
    if not sim_id:
        return False
    sim_dir = os.path.join(sim_data_dir, sim_id)
    try:
        return outcome_reader(sim_dir) is not None
    except Exception:
        return False
