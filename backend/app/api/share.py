"""Public share landing route.

Serves an HTML page at ``/share/<simulation_id>`` with the right
Open Graph / Twitter card meta tags so links to a MiroShark simulation
unfurl as a rich preview on Twitter/X, Discord, Slack, LinkedIn, iMessage,
etc.

Bots that scrape the URL read the meta tags and render the share card.
Real browsers immediately bounce to the SPA — JS first (instant), with a
``<meta http-equiv="refresh">`` fallback for clients with JS disabled.

Mounted on a separate blueprint with no URL prefix so the URL stays clean
(``/share/sim_xxx`` rather than ``/api/share/sim_xxx``). Anyone with the
URL can hit the endpoint, but the underlying share-card.png and
embed-summary endpoints both enforce the ``is_public`` gate so a private
simulation just renders a generic preview.

Farcaster Frame v2
------------------

The same head also emits ``<meta property="fc:frame:*">`` tags for
published simulations, turning every cast that contains the share URL
into an interactive Frame card inside Warpcast / Supercast / any
Frame-aware Farcaster client. The Frame image is the chart SVG when
trajectory data is present, falling back to the share-card PNG for
mid-startup sims that haven't recorded any rounds yet. Private sims
suppress Frame tag injection so scenario titles don't leak through
the cast preview.
"""

from __future__ import annotations

import html
import os
from urllib.parse import quote, urlparse
from flask import Blueprint, Response, request

from ..config import Config
from ..services.simulation_manager import SimulationManager
from ..utils.base_url import resolve_public_base_url as _resolve_oembed_base_url
from ..utils.i18n import get_locale, t as _t
from ..utils.validation import validate_simulation_id


share_bp = Blueprint('share', __name__)


def _esc(value: str) -> str:
    """HTML attribute escape — quotes are critical here since values land
    inside ``content="..."``."""
    return html.escape(value or "", quote=True)


def _render_landing_html(
    simulation_id: str,
    scenario: str,
    is_public: bool,
    spa_url: str,
    card_url: str,
    frame_meta: dict | None = None,
    oembed_block: str = "",
) -> str:
    """Build the static HTML returned to scrapers + browsers.

    Keep this small and dependency-free — the page exists purely to expose
    Open Graph tags. The body is a minimal "redirecting" splash so users
    who somehow see it briefly know what's happening.

    When ``frame_meta`` is supplied AND the sim is public, a block of
    Farcaster Frame v2 ``<meta property="fc:frame:*">`` tags is emitted
    alongside the existing Open Graph / Twitter tags. Non-Farcaster
    scrapers silently ignore the Frame tags. For private sims the
    Frame block is suppressed — same posture as the OG description
    falling back to a generic string.
    """
    if scenario:
        scenario_clean = scenario.strip()
        if len(scenario_clean) > 200:
            scenario_clean = scenario_clean[:197].rstrip() + "…"
        title = f"MiroShark · {scenario_clean}"
    else:
        title = "MiroShark Simulation"

    description = (
        scenario.strip() if scenario else
        "An autonomous social-simulation result on MiroShark — view the full belief drift, agent network, and prediction outcome."
    )
    if len(description) > 280:
        description = description[:277].rstrip() + "…"

    import json as _json

    title_e = _esc(title)
    desc_e = _esc(description)
    card_e = _esc(card_url)
    spa_e = _esc(spa_url)
    spa_js = _json.dumps(spa_url)  # safe for inline <script> string literal

    # Farcaster Frame v2 meta-tag block. Emitted only for published
    # sims — private sims fall through to the generic OG preview so
    # the scenario title never leaks into a Farcaster cast for a sim
    # the operator hasn't explicitly published.
    frame_block = ""
    if is_public and frame_meta:
        frame_image = _esc(frame_meta.get("image_url") or "")
        frame_aspect = _esc(frame_meta.get("image_aspect_ratio") or "1.91:1")
        frame_version = _esc(frame_meta.get("frame_version") or "next")
        buttons = frame_meta.get("buttons") or []
        if frame_image:
            parts = [
                "\n",
                f"<meta property=\"fc:frame\" content=\"{frame_version}\">\n",
                f"<meta property=\"fc:frame:image\" content=\"{frame_image}\">\n",
                f"<meta property=\"fc:frame:image:aspect_ratio\" content=\"{frame_aspect}\">\n",
            ]
            # Frame spec caps buttons at 4; we only ever emit one, but
            # iterate so the helper can grow without touching this
            # branch. ``idx`` is 1-indexed per the spec.
            for idx, button in enumerate(buttons[:4], start=1):
                label = _esc((button or {}).get("label") or "")
                action = _esc((button or {}).get("action") or "link")
                target = _esc((button or {}).get("target") or spa_url)
                if not label:
                    continue
                parts.append(
                    f"<meta property=\"fc:frame:button:{idx}\" content=\"{label}\">\n"
                )
                parts.append(
                    f"<meta property=\"fc:frame:button:{idx}:action\" content=\"{action}\">\n"
                )
                parts.append(
                    f"<meta property=\"fc:frame:button:{idx}:target\" content=\"{target}\">\n"
                )
            frame_block = "".join(parts)

    # Note the dual redirect: <meta refresh> handles JS-off; the inline
    # script handles JS-on (instant). Bots ignore both.
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        f"<title>{title_e}</title>\n"
        f"<meta name=\"description\" content=\"{desc_e}\">\n"
        "\n"
        "<meta property=\"og:type\" content=\"website\">\n"
        f"<meta property=\"og:title\" content=\"{title_e}\">\n"
        f"<meta property=\"og:description\" content=\"{desc_e}\">\n"
        f"<meta property=\"og:image\" content=\"{card_e}\">\n"
        "<meta property=\"og:image:width\" content=\"1200\">\n"
        "<meta property=\"og:image:height\" content=\"630\">\n"
        f"<meta property=\"og:url\" content=\"{spa_e}\">\n"
        "<meta property=\"og:site_name\" content=\"MiroShark\">\n"
        "\n"
        "<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
        f"<meta name=\"twitter:title\" content=\"{title_e}\">\n"
        f"<meta name=\"twitter:description\" content=\"{desc_e}\">\n"
        f"<meta name=\"twitter:image\" content=\"{card_e}\">\n"
        f"{frame_block}"
        f"{oembed_block}"
        "\n"
        f"<meta http-equiv=\"refresh\" content=\"0; url={spa_e}\">\n"
        f"<link rel=\"canonical\" href=\"{spa_e}\">\n"
        "<style>\n"
        "  body { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;\n"
        "         background: #0a0a0a; color: #fafafa; margin: 0;\n"
        "         display: flex; align-items: center; justify-content: center;\n"
        "         min-height: 100vh; text-align: center; padding: 24px; }\n"
        "  a { color: #ea580c; }\n"
        "  .wrap { max-width: 480px; }\n"
        "  h1 { font-size: 16px; letter-spacing: 0.18em; margin: 0 0 8px; opacity: 0.5;\n"
        "       text-transform: uppercase; font-weight: 700; }\n"
        "  p { font-size: 18px; line-height: 1.5; margin: 0 0 24px; }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<div class=\"wrap\">\n"
        "  <h1>MiroShark</h1>\n"
        "  <p>Opening simulation…</p>\n"
        f"  <p><a href=\"{spa_e}\">Continue →</a></p>\n"
        "</div>\n"
        "<script>\n"
        f"  window.location.replace({spa_js});\n"
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )


@share_bp.route('/share/<simulation_id>', methods=['GET'])
def share_landing(simulation_id: str):
    """Server-rendered HTML with OG meta tags pointing to the share-card
    PNG endpoint. Browsers JS-redirect to the SPA simulation view.

    No auth — but the underlying ``/share-card.png`` honors ``is_public``,
    so private sims fall back to a generic preview rather than leaking
    scenario detail through the meta tags.
    """
    locale = get_locale(request)
    try:
        validate_simulation_id(simulation_id)
    except ValueError as exc:
        return Response(
            _t(f"Invalid simulation id: {exc}", f"无效的模拟 ID:{exc}", locale),
            status=400,
            mimetype="text/plain",
        )

    # Pull just enough to populate OG tags — never raise on missing data.
    scenario = ""
    is_public = False
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            is_public = bool(getattr(state, "is_public", False))
            if is_public:
                config = manager.get_simulation_config(simulation_id)
                if config:
                    scenario = (config.get("simulation_requirement") or "").strip()
    except Exception:
        # Don't 500 the page just because a peripheral lookup failed —
        # the worst case is a generic preview.
        pass

    # Prefer the proxied ``Host`` header so links work behind a reverse
    # proxy. Falls back to ``request.host_url`` (which uses the WSGI
    # SERVER_NAME).
    base = request.host_url.rstrip("/")
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    forwarded_host = request.headers.get("X-Forwarded-Host")
    if forwarded_host:
        proto = forwarded_proto or ("https" if request.is_secure else "http")
        base = f"{proto}://{forwarded_host}"

    spa_url = f"{base}/simulation/{simulation_id}/start"
    card_url = f"{base}/api/simulation/{simulation_id}/share-card.png"

    # Build Farcaster Frame v2 metadata for published sims. The
    # frame_metadata service reuses the chart-SVG trajectory loader to
    # decide whether to point Farcaster at the chart (preferred) or
    # the share-card PNG (fallback for mid-startup sims). Failures
    # here must never crash the share page — we swallow exceptions
    # and let the OG/Twitter preview stand alone.
    frame_meta = None
    if is_public:
        try:
            from ..services import frame_metadata as frame_metadata_service
            sim_dir = os.path.join(
                Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id
            )
            frame_meta = frame_metadata_service.build_frame_metadata(
                sim_id=simulation_id,
                scenario=scenario,
                sim_dir=sim_dir,
                base_url=base,
                is_public=True,
            )
        except Exception:
            frame_meta = None

    # oEmbed discovery links. Emitted only for published sims — same
    # gating posture as the OG / Frame tags so a private sim's scenario
    # never leaks. Writing platforms (Notion, Ghost, Substack, WordPress)
    # read these <link> tags and call back to /oembed for a rich card.
    # Both the JSON and XML format variants are advertised; the endpoint
    # honours ?format= and the consumer picks whichever it prefers.
    oembed_block = ""
    if is_public:
        share_self_url = f"{base}/share/{simulation_id}"
        encoded = quote(share_self_url, safe="")
        oembed_title = _esc((scenario or "MiroShark Simulation")[:60])
        json_href = _esc(f"{base}/oembed?url={encoded}&format=json")
        xml_href = _esc(f"{base}/oembed?url={encoded}&format=xml")
        oembed_block = (
            f"<link rel=\"alternate\" type=\"application/json+oembed\" "
            f"href=\"{json_href}\" title=\"{oembed_title}\">\n"
            f"<link rel=\"alternate\" type=\"text/xml+oembed\" "
            f"href=\"{xml_href}\" title=\"{oembed_title}\">\n"
        )

    body = _render_landing_html(
        simulation_id=simulation_id,
        scenario=scenario if is_public else "",
        is_public=is_public,
        spa_url=spa_url,
        card_url=card_url,
        frame_meta=frame_meta,
        oembed_block=oembed_block,
    )

    response = Response(body, mimetype="text/html; charset=utf-8")
    # OG scrapers cache aggressively — keep the cache short so newly
    # published sims show their card without long delays.
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


def _oembed_allowed_hosts(base_url: str) -> set:
    """Hosts an inbound oEmbed ``url`` is allowed to belong to.

    A consumer hands us the canonical share URL it scraped the discovery
    tag from; we only describe sims hosted on *this* deployment. The set
    is the union of the resolved canonical host, the raw request host, and
    any ``X-Forwarded-Host`` — so the gate passes behind a proxy and on a
    bare ``PUBLIC_BASE_URL``-less dev server alike, but a foreign domain
    is rejected (the endpoint can't be aimed at another site).
    """
    hosts: set = set()
    for candidate in (base_url, request.host_url):
        if candidate:
            netloc = urlparse(candidate).netloc.lower()
            if netloc:
                hosts.add(netloc)
    forwarded_host = request.headers.get("X-Forwarded-Host")
    if forwarded_host:
        hosts.add(forwarded_host.strip().lower())
    return hosts


@share_bp.route('/oembed', methods=['GET'])
def oembed_provider():
    """oEmbed 1.0 provider — auto-unfurl for MiroShark share URLs.

    Mounted at the **root** (no ``/api`` prefix) so the discovery tag in
    the share page points at a clean ``/oembed?url=`` endpoint. A consumer
    (Notion, Ghost, Substack, WordPress, …) that finds the
    ``<link rel="alternate" type="application/json+oembed">`` tag on a
    ``/share/<id>`` page calls back here with the share URL and renders
    the returned ``rich`` embed inline.

    Query params:

      * ``url`` (required) — the MiroShark share URL the consumer scraped.
        Must resolve to a sim hosted on this deployment; a foreign domain
        or a URL with no recognisable sim path returns ``404``.
      * ``format`` (optional, ``json`` default) — ``json`` or ``xml``. Any
        other value returns ``501`` per the oEmbed spec.

    Same publish gate as the share landing tags: a private or missing sim
    is answered with ``404`` (indistinguishable from a non-existent one)
    so the endpoint never confirms a private sim exists.
    """
    from ..services import oembed_service
    from ..services import surface_stats

    locale = get_locale(request)

    fmt = (request.args.get("format") or "json").strip().lower()
    if fmt not in ("json", "xml"):
        # oEmbed spec: a requested format the provider can't supply is a
        # 501 Not Implemented, not a 400.
        return Response(
            _t(
                "Unsupported oEmbed format — use 'json' or 'xml'.",
                "不支持的 oEmbed 格式 — 请使用 'json' 或 'xml'。",
                locale,
            ),
            status=501,
            mimetype="text/plain; charset=utf-8",
        )

    url = (request.args.get("url") or "").strip()
    if not url:
        return Response(
            _t(
                "Missing required 'url' query parameter.",
                "缺少必需的 'url' 查询参数。",
                locale,
            ),
            status=400,
            mimetype="text/plain; charset=utf-8",
        )

    base = _resolve_oembed_base_url()
    allowed_hosts = _oembed_allowed_hosts(base)

    not_found = Response(
        _t(
            "No published MiroShark simulation found for that URL.",
            "未找到与该 URL 对应的已发布 MiroShark 模拟。",
            locale,
        ),
        status=404,
        mimetype="text/plain; charset=utf-8",
    )

    sim_id = oembed_service.parse_sim_id_from_url(url, allowed_hosts=allowed_hosts)
    if not sim_id:
        return not_found

    try:
        validate_simulation_id(sim_id)
    except ValueError:
        return not_found

    # Publish gate — never raise on a peripheral lookup; an unpublished or
    # missing sim falls through to the shared 404.
    scenario = ""
    is_public = False
    try:
        manager = SimulationManager()
        state = manager.get_simulation(sim_id)
        if state:
            is_public = bool(getattr(state, "is_public", False))
            if is_public:
                config = manager.get_simulation_config(sim_id)
                if config:
                    scenario = (config.get("simulation_requirement") or "").strip()
    except Exception:
        is_public = False

    if not is_public:
        return not_found

    payload = oembed_service.build_oembed_payload(scenario, sim_id, base)

    sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, sim_id)
    surface_stats.increment_surface_stat(sim_dir, "oembed")

    if fmt == "xml":
        body = oembed_service.oembed_to_xml(payload)
        response = Response(body, mimetype="text/xml; charset=utf-8")
    else:
        import json as _json

        body = _json.dumps(payload, indent=2, ensure_ascii=False)
        response = Response(body, mimetype="application/json; charset=utf-8")

    response.headers["Cache-Control"] = "public, max-age=300"
    return response


def _render_private_preview_html(
    simulation_id: str,
    scenario: str,
    spa_url: str,
    expires_at_iso: str,
) -> str:
    """Build the private-preview HTML returned for a valid share token.

    Differences from the public landing page in :func:`_render_landing_html`:

    * ``<meta name="robots" content="noindex,nofollow">`` — the whole
      point of a private link is that search engines and link unfurlers
      don't index it. The recipient sees the page; Googlebot doesn't.
    * No Open Graph / Twitter card / Farcaster Frame tags. A leaked
      preview URL pasted into a Discord channel renders as a bare link
      rather than auto-unfurling the scenario text into the channel.
    * No oEmbed discovery links. Same reason — a content provider that
      crawls oEmbed shouldn't auto-render the preview.
    * A "Private Preview" banner so a recipient who lands on the page
      knows this is a pre-publication share and not the public surface.
    * The same SPA redirect (JS + ``<meta refresh>`` fallback) so the
      recipient gets the live simulation view without an extra click.
    """
    title_e = _esc(f"MiroShark — Private Preview · {simulation_id}")
    spa_e = _esc(spa_url)
    import json as _json
    spa_js = _json.dumps(spa_url)

    if scenario:
        scenario_clean = scenario.strip()
        if len(scenario_clean) > 200:
            scenario_clean = scenario_clean[:197].rstrip() + "…"
        scenario_e = _esc(scenario_clean)
        scenario_block = f"<p class=\"scenario\">{scenario_e}</p>\n"
    else:
        scenario_block = ""

    expires_block = ""
    if expires_at_iso:
        expires_block = (
            f"<p class=\"expires\">Link expires {_esc(expires_at_iso)}</p>\n"
        )

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        f"<title>{title_e}</title>\n"
        "<meta name=\"robots\" content=\"noindex,nofollow\">\n"
        "<meta name=\"referrer\" content=\"no-referrer\">\n"
        f"<link rel=\"canonical\" href=\"{spa_e}\">\n"
        f"<meta http-equiv=\"refresh\" content=\"0; url={spa_e}\">\n"
        "<style>\n"
        "  body { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;\n"
        "         background: #0a0a0a; color: #fafafa; margin: 0;\n"
        "         display: flex; align-items: center; justify-content: center;\n"
        "         min-height: 100vh; text-align: center; padding: 24px; }\n"
        "  a { color: #ea580c; }\n"
        "  .wrap { max-width: 540px; }\n"
        "  .badge { display: inline-block; padding: 4px 10px; font-size: 11px;\n"
        "           letter-spacing: 0.18em; text-transform: uppercase;\n"
        "           border: 1px solid #ea580c; color: #ea580c; border-radius: 999px;\n"
        "           margin-bottom: 16px; font-weight: 700; }\n"
        "  h1 { font-size: 16px; letter-spacing: 0.18em; margin: 0 0 8px; opacity: 0.5;\n"
        "       text-transform: uppercase; font-weight: 700; }\n"
        "  p { font-size: 18px; line-height: 1.5; margin: 0 0 16px; }\n"
        "  .scenario { font-size: 16px; opacity: 0.85; margin-bottom: 24px; }\n"
        "  .expires { font-size: 12px; opacity: 0.55; margin-top: 24px;\n"
        "             letter-spacing: 0.06em; }\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<div class=\"wrap\">\n"
        "  <div class=\"badge\">Private Preview</div>\n"
        "  <h1>MiroShark</h1>\n"
        "  <p>Opening simulation…</p>\n"
        f"{scenario_block}"
        f"  <p><a href=\"{spa_e}\">Continue →</a></p>\n"
        f"{expires_block}"
        "</div>\n"
        "<script>\n"
        f"  window.location.replace({spa_js});\n"
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def _private_preview_not_found(locale: str) -> Response:
    """Single 404 for every preview-resolution miss.

    Unknown token / revoked token / expired token / malformed token all
    return the same response so an attacker probing the surface can't
    distinguish "token never existed" from "token was revoked yesterday"
    — both are equally not-allowed-in.
    """
    body = _t(
        "This preview link is no longer valid.",
        "此预览链接已失效。",
        locale,
    )
    response = Response(body, status=404, mimetype="text/plain; charset=utf-8")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex,nofollow"
    return response


@share_bp.route('/preview/<token>', methods=['GET'])
def private_preview_landing(token: str):
    """Resolve a private share-link token to a noindex preview page.

    A token bypasses the ``is_public`` gate for one page — the same SPA
    share view ``/share/<sim_id>`` serves — without flipping the sim's
    public flag or adding it to the gallery. Search-engine indexing and
    link-unfurl previews are suppressed via ``<meta robots>`` and the
    absence of Open Graph tags.

    Returns 404 for unknown / revoked / expired tokens — single response
    so a probe can't tell the cases apart.
    """
    from ..services import share_link_service

    locale = get_locale(request)

    sim_id = share_link_service.resolve_token(
        token=token,
        sim_root=Config.WONDERWALL_SIMULATION_DATA_DIR,
    )
    if not sim_id:
        return _private_preview_not_found(locale)

    try:
        validate_simulation_id(sim_id)
    except ValueError:
        return _private_preview_not_found(locale)

    scenario = ""
    try:
        manager = SimulationManager()
        state = manager.get_simulation(sim_id)
        if not state:
            return _private_preview_not_found(locale)
        config = manager.get_simulation_config(sim_id)
        if config:
            scenario = (config.get("simulation_requirement") or "").strip()
    except Exception:
        return _private_preview_not_found(locale)

    base = request.host_url.rstrip("/")
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    forwarded_host = request.headers.get("X-Forwarded-Host")
    if forwarded_host:
        proto = forwarded_proto or ("https" if request.is_secure else "http")
        base = f"{proto}://{forwarded_host}"

    spa_url = f"{base}/simulation/{sim_id}/start"

    expires_at_iso = ""
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, sim_id)
        tokens = share_link_service.list_tokens(sim_id=sim_id, sim_dir=sim_dir)
        for entry in tokens:
            if entry.get("token") == token:
                expires_at_iso = entry.get("expires_at_iso") or ""
                break
    except Exception:
        expires_at_iso = ""

    body = _render_private_preview_html(
        simulation_id=sim_id,
        scenario=scenario,
        spa_url=spa_url,
        expires_at_iso=expires_at_iso,
    )

    response = Response(body, mimetype="text/html; charset=utf-8")
    # Never cache the preview page — a freshly revoked token must stop
    # serving immediately, and an intermediate proxy holding the body
    # would defeat that.
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex,nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
