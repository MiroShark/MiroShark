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
"""

from __future__ import annotations

import html
from flask import Blueprint, Response, request

from ..services.simulation_manager import SimulationManager
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
) -> str:
    """Build the static HTML returned to scrapers + browsers.

    Keep this small and dependency-free — the page exists purely to expose
    Open Graph tags. The body is a minimal "redirecting" splash so users
    who somehow see it briefly know what's happening.
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

    body = _render_landing_html(
        simulation_id=simulation_id,
        scenario=scenario if is_public else "",
        is_public=is_public,
        spa_url=spa_url,
        card_url=card_url,
    )

    response = Response(body, mimetype="text/html; charset=utf-8")
    # OG scrapers cache aggressively — keep the cache short so newly
    # published sims show their card without long delays.
    response.headers["Cache-Control"] = "public, max-age=300"
    return response
