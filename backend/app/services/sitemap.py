"""Search-engine sitemap renderer for the public simulation gallery.

Every published MiroShark simulation already has a public landing page
(``/share/<id>``) and a live spectator-watch page (``/watch/<id>``) — the
share card carries Open Graph tags so a tweeted link unfurls with a
1200×630 image, the watch page broadcasts a live belief bar. What was
missing was a *crawlable index* a search engine could discover. Without
one, Googlebot / Bingbot / DuckDuckBot have no entry point into the
simulation corpus other than whatever an external site happens to link
to. The "Aave reserve-factor scenario from 2026-05-08" Aaron tweeted
will not surface on Google when someone searches the scenario keywords.

``GET /sitemap.xml`` closes that gap: an XML sitemap document
(``http://www.sitemaps.org/schemas/sitemap/0.9``) auto-generated from
the public sim corpus, with one ``<url>`` entry per published simulation
pointing at ``/share/<id>``, plus a parallel entry for ``/watch/<id>``.
``<lastmod>`` reflects the simulation's most recent state write so
crawlers re-fetch a still-running sim's pages without waiting on the
default re-crawl cadence; ``<changefreq>`` is ``always`` for in-progress
sims and ``weekly`` for completed ones.

A companion ``GET /robots.txt`` advertises the sitemap location via the
standard ``Sitemap:`` directive so any compliant crawler discovers it
without manual registration. Operators submitting the sitemap manually
to Google Search Console get the same payload either way — the
discovery benefit compounds on every future publish.

Design notes
------------

* **Pure stdlib.** ``xml.etree.ElementTree`` + ``os`` + ``datetime``;
  zero new dependencies. Same posture every share / feed / lineage /
  reproduce surface keeps.

* **Read-only.** The renderer never writes — it walks ``sim_data_dir``
  for state.json files, projects each into a ``<url>`` block, and
  serializes. Corrupt state files degrade to "skipped"; never raises.

* **Public-only.** Only sims with ``is_public=true`` appear. A private
  fork or in-progress operator-only run never surfaces in search.

* **Bounded.** Capped at ``MAX_SITEMAP_URLS`` total ``<url>`` entries
  (50,000 — the spec ceiling per file). MiroShark won't approach this
  soon, but the guard is defense-in-depth against a (future) bulk-fork
  operator pattern blowing up the document.

* **Stable byte output.** Sims are sorted by ``simulation_id`` ascending
  before serialization, so two consecutive renders against the same
  on-disk corpus produce byte-identical output. Lets the route layer
  set a meaningful ``ETag`` if it ever wants to.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional, Tuple
from xml.etree import ElementTree as ET


# Sitemap protocol version 0.9 — the only version major search engines
# read. The namespace string is part of the spec; renderers that omit
# it produce a document Googlebot / Bingbot / DuckDuckBot ignore.
SITEMAP_NAMESPACE: str = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Spec hard cap is 50,000 ``<url>`` entries per sitemap file; documents
# that exceed it must be split into a sitemap index. We pin to the spec
# ceiling here — MiroShark's public corpus is currently three-figure
# small, so the cap is purely defense-in-depth against pathological
# bulk-fork operators rather than a normal truncation case. When the
# corpus realistically approaches this, the right move is a sitemap
# index (``sitemap_index.xml``) rather than bumping this number.
MAX_SITEMAP_URLS: int = 50_000

# Per-sim entry order: share landing first, then the live watch page.
# Both are public-discovery surfaces; ``/share`` is the canonical
# unfurl destination and the citation-friendly URL, ``/watch`` carries
# the live belief bars so its priority is one notch lower.
SHARE_PRIORITY: str = "0.8"
WATCH_PRIORITY: str = "0.7"

# Change-frequency hints. The spec calls these advisory ("crawlers may
# use this information"); we still emit them because Googlebot's
# scheduler does honour them for fresh sites, and an in-progress sim's
# belief bars genuinely change every round. Completed sims become
# stable artifacts so ``weekly`` matches their actual change rate.
RUNNING_CHANGEFREQ: str = "always"
COMPLETED_CHANGEFREQ: str = "weekly"


def _safe_str(value: Any) -> str:
    """Coerce ``value`` to a stripped string; ``None`` ⇒ empty.

    Mirrors the same helper ``lineage_service`` keeps so the two
    renderers share a posture: trust nothing on disk, never raise.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value).strip()
    except Exception:
        return ""


def _safe_iso_date(value: Any) -> Optional[str]:
    """Coerce a datetime-ish value to ``YYYY-MM-DD`` (W3C date format).

    The sitemap spec accepts the full W3C datetime profile (any of
    ``YYYY``, ``YYYY-MM``, ``YYYY-MM-DD``, ``YYYY-MM-DDThh:mm:ss+TZ``),
    but day-precision is the practical norm — Googlebot ignores
    sub-second precision and sub-day timestamps, and a slimmer date
    keeps the rendered XML small for large corpora.

    Returns ``None`` when no usable date can be extracted; the
    caller then omits ``<lastmod>`` for that entry, which is also
    spec-compliant.
    """
    text = _safe_str(value)
    if not text:
        return None
    # Already day-or-finer ISO; take the first 10 chars when they look
    # like a date. Cheap path that avoids the full ``fromisoformat``
    # parse for the overwhelmingly common case where state.json wrote
    # ``2026-05-14T10:00:00`` and we want ``2026-05-14``.
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        head = text[:10]
        try:
            datetime.strptime(head, "%Y-%m-%d")
            return head
        except ValueError:
            pass
    # Fall back to ISO parsing for anything else operators wrote into
    # state.json over the years. Failing both yields ``None`` so the
    # ``<lastmod>`` element is omitted entirely.
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _is_running(state: Any) -> bool:
    """Return True when the simulation hasn't reached a terminal status.

    A terminal state ⇒ ``<changefreq>weekly</changefreq>`` because the
    artifact is stable; anything else (running, paused, ready) gets
    ``always`` so a crawler that finds the page mid-run will re-fetch
    instead of caching the partial render.
    """
    if state is None:
        return False
    status = getattr(state, "status", None)
    raw = getattr(status, "value", None) or status
    text = _safe_str(raw).lower()
    if not text:
        return True
    return text not in ("completed", "failed", "cancelled", "canceled")


def _candidate_sims(sims: Iterable[Any]) -> List[Tuple[str, Any]]:
    """Filter to public sims with a usable id; sort for stable output.

    Sorting by ``simulation_id`` ascending (rather than ``created_at``
    descending) means the rendered bytes are deterministic given the
    same on-disk corpus — two consecutive ``GET /sitemap.xml`` calls
    that hit different gunicorn workers produce identical XML, which
    lets the route layer set a meaningful ``ETag`` if it wants to and
    keeps integration-test goldens stable.
    """
    rows: List[Tuple[str, Any]] = []
    for state in sims or []:
        if state is None:
            continue
        if not bool(getattr(state, "is_public", False)):
            continue
        sim_id = _safe_str(getattr(state, "simulation_id", None))
        if not sim_id:
            continue
        rows.append((sim_id, state))
    rows.sort(key=lambda row: row[0])
    return rows


def _last_modified_for(state: Any, sim_dir: str) -> Optional[str]:
    """Best-effort ``lastmod`` date for a single sim.

    Prefers a state-side timestamp (``updated_at`` ⇒ ``created_at``),
    then falls back to the on-disk ``state.json`` mtime so a long-lived
    in-progress sim whose ``created_at`` is days old still tells the
    crawler "the artifact changed today". Returns ``None`` when no
    usable signal exists; the caller omits the element rather than
    inventing a value.
    """
    candidate = (
        _safe_iso_date(getattr(state, "updated_at", None))
        or _safe_iso_date(getattr(state, "created_at", None))
    )
    if candidate:
        return candidate

    state_json = os.path.join(sim_dir or "", "state.json")
    try:
        if state_json and os.path.exists(state_json):
            mtime = os.path.getmtime(state_json)
            return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        pass
    return None


def _append_url_block(
    parent: ET.Element,
    *,
    loc: str,
    lastmod: Optional[str],
    changefreq: str,
    priority: str,
) -> None:
    """Append one ``<url>`` block to the sitemap document.

    Element order — ``<loc>``, ``<lastmod>``, ``<changefreq>``,
    ``<priority>`` — matches the order the spec example shows; some
    older crawlers parse positionally rather than by tag name.
    """
    url_el = ET.SubElement(parent, "url")
    ET.SubElement(url_el, "loc").text = loc
    if lastmod:
        ET.SubElement(url_el, "lastmod").text = lastmod
    ET.SubElement(url_el, "changefreq").text = changefreq
    ET.SubElement(url_el, "priority").text = priority


def build_sitemap(
    sims: Iterable[Any],
    base_url: str,
    *,
    sim_data_dir: str = "",
    max_urls: int = MAX_SITEMAP_URLS,
) -> bytes:
    """Render the sitemap XML document for the public simulation corpus.

    Each public sim contributes two ``<url>`` blocks: the canonical
    ``/share/<id>`` landing page and the live ``/watch/<id>`` view.
    The two surfaces serve different intent (citation vs. broadcast)
    so they get distinct priorities; both are crawler-discoverable
    entry points into the simulation.

    ``base_url`` is the absolute URL prefix (``https://miroshark.app``).
    Falls back to a relative ``/share/<id>`` ``<loc>`` only if the
    caller supplies ``""`` — the spec requires absolute URLs in
    production but tests don't have a public host, and a relative
    ``<loc>`` is the cheapest way to keep the renderer testable
    without monkeypatching every call site. Production callers should
    always pass an absolute base.

    ``max_urls`` caps total ``<url>`` blocks (not sims). Two blocks
    per sim, so the effective sim cap is ``max_urls // 2``.

    Returns UTF-8 encoded bytes with the XML declaration and a
    trailing newline so a ``curl > sitemap.xml`` produces a clean
    file.
    """
    base = (base_url or "").rstrip("/")
    cap = max(0, int(max_urls or 0))

    root = ET.Element("urlset", attrib={"xmlns": SITEMAP_NAMESPACE})

    written = 0
    for sim_id, state in _candidate_sims(sims):
        if written >= cap:
            break

        sim_dir = os.path.join(sim_data_dir or "", sim_id) if sim_data_dir else ""
        lastmod = _last_modified_for(state, sim_dir)
        running = _is_running(state)
        changefreq = RUNNING_CHANGEFREQ if running else COMPLETED_CHANGEFREQ

        share_loc = f"{base}/share/{sim_id}" if base else f"/share/{sim_id}"
        _append_url_block(
            root,
            loc=share_loc,
            lastmod=lastmod,
            changefreq=changefreq,
            priority=SHARE_PRIORITY,
        )
        written += 1

        if written >= cap:
            break

        watch_loc = f"{base}/watch/{sim_id}" if base else f"/watch/{sim_id}"
        # The watch page is the same artifact whether the sim is
        # mid-run or done; for completed sims it still polls the
        # status endpoint once before settling, which is a one-time
        # render — ``daily`` reflects "occasionally re-rendered" for
        # done sims while ``always`` matches the live case.
        watch_changefreq = RUNNING_CHANGEFREQ if running else "daily"
        _append_url_block(
            root,
            loc=watch_loc,
            lastmod=lastmod,
            changefreq=watch_changefreq,
            priority=WATCH_PRIORITY,
        )
        written += 1

    # ``ET.tostring`` with ``xml_declaration`` writes the standard
    # ``<?xml version='1.0' encoding='utf-8'?>`` prologue; some older
    # validators reject documents that omit it. The trailing newline
    # keeps shell-redirected output (``curl > sitemap.xml``) tidy.
    body = ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=False,
    )
    if not body.endswith(b"\n"):
        body = body + b"\n"
    return body


def build_robots_txt(
    base_url: str,
    *,
    enabled: bool = True,
) -> bytes:
    """Render the ``robots.txt`` document for the public deployment.

    Always allows crawlers on the public discovery surfaces
    (``/share/``, ``/watch/``, ``/explore``, ``/verified``); when
    ``enabled`` is true, advertises ``Sitemap:`` so any compliant
    crawler discovers ``/sitemap.xml`` automatically — operators
    don't need to submit it manually.

    The ``Disallow:`` block protects the API namespace and the SPA
    routes that aren't meant for indexing (settings, dashboards). A
    crawler still *can* follow those URLs, but the directive tells
    well-behaved bots to skip them so they don't pollute search
    results with debugging surfaces.

    Returns UTF-8 bytes terminated with a newline.
    """
    base = (base_url or "").rstrip("/")

    lines: List[str] = [
        "User-agent: *",
        "Allow: /share/",
        "Allow: /watch/",
        "Allow: /explore",
        "Allow: /verified",
        "Allow: /embed/",
        "Disallow: /api/",
        "Disallow: /settings",
        "Disallow: /dashboard",
        "",
    ]
    if enabled and base:
        lines.append(f"Sitemap: {base}/sitemap.xml")
        lines.append("")
    return "\n".join(lines).encode("utf-8")
