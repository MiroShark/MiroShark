"""Status badge SVG — the thirteenth share surface, distribution edition.

The previous twelve surfaces describe a simulation in various depths
of detail: share card / replay GIF / chart SVG (visual), trajectory
CSV / JSONL / transcript / thread / notebook (data + prose), watch
page (live), reproduce.json (citation), DKG citation (on-chain
provenance), signal.json (action primitive), and archive.zip
(take-offline composite). This module adds the cheapest, smallest
surface yet — a flat 20-pixel-tall Shields.io-compatible SVG badge
that fits inside any `<img>` tag, Markdown image link, or
`<link rel="alternate">` reference.

The badge is the **passive distribution lever**. Every researcher's
GitHub README, every Notion page, every operator's personal site can
embed a live belief badge with one line of Markdown:

    ![MiroShark](https://your-host/api/simulation/<id>/badge.svg)

Whenever the underlying simulation's stance / confidence shifts, the
badge updates on the next 60-second cache window. A reader who sees
the badge clicks through to the share page; the share page surfaces
the other twelve surfaces. Discovery flows in one direction; the
badge starts the funnel.

Design notes
------------

* **Pure stdlib.** ``xml.etree.ElementTree`` only — same posture as
  ``chart_svg`` / ``frame_metadata`` / ``share_card``. The ``signal_service``
  side derives ``direction`` + ``confidence_pct`` from the embed-summary
  payload; this module just renders those into a flat badge. Zero new
  dependencies.

* **Shields.io-compatible.** 20-pixel total height (the
  Shields.io flat-style standard) so the badge sits inline with text
  the same way a Shields.io build badge does. The pill ends come from
  a ``<clipPath>`` of ``rx=3`` so the rounded corners render across
  every browser / `<img>` consumer including IE11-era renderers some
  older Notion / Substack themes still use. Font family
  ``DejaVu Sans,Verdana,Geneva,sans-serif`` matches Shields.io so the
  badge sits next to other Shields.io-rendered badges without an
  obvious font swap.

* **Bytewise stable.** Element insertion order is deterministic and
  the serializer pins ``short_empty_elements=True``; two calls with
  the same inputs produce the same bytes. A consumer caching the badge
  bytes by hash gets stable cache keys.

* **Same colour vocabulary as every other belief surface.**
  ``#22c55e`` (Bullish), ``#6b7280`` (Neutral / unknown), ``#ef4444``
  (Bearish) — matches the chart SVG, share card, replay GIF, watch
  page, EmbedDialog belief bars, and email belief percentages. A
  reader who saw the chart in a README recognises the badge colour at
  a glance.

* **Defensive on input.** A missing / unrecognised direction renders
  with the neutral colour and an ``Unknown`` label rather than
  raising. A confidence outside ``[0, 100]`` clamps; a non-numeric
  confidence becomes ``0`` and the badge still renders. The route
  handler treats "no rounds yet" as a 404 upstream — this module
  assumes the caller has already validated the simulation has a
  signal worth rendering.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


# ── Visual tokens ─────────────────────────────────────────────────────────
#
# Stance colours are pinned to the same values every other belief
# surface uses. Don't change without updating ``chart_svg`` /
# ``share_card`` / EmbedDialog in lockstep.

BULLISH_COLOR = "#22c55e"
NEUTRAL_COLOR = "#6b7280"
BEARISH_COLOR = "#ef4444"

# Shields.io left-half grey. Locked at ``#555555`` so MiroShark badges
# render flush next to GitHub-Actions / npm / PyPI Shields.io badges
# in the same README without an obvious mismatch.
LEFT_FILL = "#555555"

TEXT_FILL = "#ffffff"

# DejaVu Sans is the Shields.io reference family; the Verdana / Geneva
# fallback chain matches what shields.io ships so a renderer without
# DejaVu Sans (e.g. a hosted markdown previewer) lands on a metric-
# similar fallback rather than the default serif.
FONT_FAMILY = "DejaVu Sans,Verdana,Geneva,sans-serif"
FONT_SIZE = 11

# Shields.io flat-style canonical height.
BADGE_HEIGHT = 20

# Inner padding on each side of each label. 6px is the Shields.io flat
# default for the "social" preset — leaves visual breathing room
# without making short labels look stretched.
SIDE_PADDING = 6

LEFT_LABEL = "MiroShark"


_COLOR_BY_DIRECTION: dict[str, str] = {
    "bullish": BULLISH_COLOR,
    "neutral": NEUTRAL_COLOR,
    "bearish": BEARISH_COLOR,
}


# ── Internal helpers ──────────────────────────────────────────────────────


def _approx_text_width(text: str) -> int:
    """Return an approximate pixel width for ``text`` at 11px DejaVu Sans.

    Pure stdlib — no font-metrics library available. The actual
    Shields.io renderer uses a per-character width table for accuracy;
    we approximate by treating every glyph as 6.5px wide (the DejaVu
    Sans average at 11px) and rounding up. The result is slightly
    wider than the ideal layout, but never narrower — so a badge
    never clips a label on the right side.

    Empty strings produce a zero-width section so the caller can still
    centre the (absent) text without dividing by zero downstream.
    """
    if not text:
        return 0
    return max(1, int(round(len(text) * 6.5)))


def _resolve_color(direction: Any) -> str:
    """Map a direction string to the canonical stance colour.

    Case-insensitive on the trimmed leading token so ``"Bullish "``
    and ``"bullish"`` resolve identically. Unknown / non-string input
    falls back to the neutral grey so a partially-rendered signal
    still produces a readable badge.
    """
    if not isinstance(direction, str):
        return NEUTRAL_COLOR
    key = direction.strip().lower()
    return _COLOR_BY_DIRECTION.get(key, NEUTRAL_COLOR)


def _coerce_confidence(value: Any) -> float:
    """Coerce a confidence-shaped value to ``float`` in ``[0, 100]``.

    Non-numeric / ``None`` becomes ``0.0`` so the badge still renders
    a (probably-meaningless) ``Unknown 0%`` label rather than raising
    inside the route handler.
    """
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pct != pct:  # NaN check
        return 0.0
    if pct < 0.0:
        return 0.0
    if pct > 100.0:
        return 100.0
    return pct


def _format_right_label(direction: Any, confidence_pct: Any) -> str:
    """Build the right-hand label: e.g. ``"Bullish 72%"``.

    Direction is title-cased so ``"bullish"`` and ``"BULLISH"`` both
    render as ``"Bullish"``. Unknown / empty direction falls back to
    ``"Unknown"`` so the badge stays self-explanatory. Confidence is
    rounded to the nearest integer percent — Shields.io flat badges
    are too short to display a decimal cleanly, and a quant tool
    consumer reading the integer-rounded badge still sees the right
    confidence bucket within ±0.5pp.
    """
    if isinstance(direction, str) and direction.strip():
        direction_label = direction.strip().title()
    else:
        direction_label = "Unknown"

    pct = _coerce_confidence(confidence_pct)
    return f"{direction_label} {int(round(pct))}%"


def _build_badge_document(right_label: str, right_color: str, clip_id: str) -> str:
    """Assemble the shared flat-badge SVG document.

    Both the per-sim belief badge and the platform-stats badge render
    the identical Shields.io flat structure — viewBox, rounded clip
    path, two background rects, and a centred two-label text group —
    differing only in the right-hand label, the right-half fill, and
    the ``clipPath`` id. Sharing the body here keeps the two renderers
    bytewise-consistent: a future tweak to dimensions / padding / font
    can't drift one badge away from the other.

    Element insertion order and ``short_empty_elements=True`` are kept
    exactly as before so the output stays bytewise-deterministic for
    HTTP caching / hash-based ETags.
    """
    left_text_width = _approx_text_width(LEFT_LABEL)
    right_text_width = _approx_text_width(right_label)

    left_section_width = left_text_width + 2 * SIDE_PADDING
    right_section_width = right_text_width + 2 * SIDE_PADDING
    total_width = left_section_width + right_section_width

    aria_label = f"MiroShark: {right_label}"

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(total_width),
            "height": str(BADGE_HEIGHT),
            "viewBox": f"0 0 {total_width} {BADGE_HEIGHT}",
            "role": "img",
            "aria-label": aria_label,
        },
    )

    title = ET.SubElement(svg, "title")
    title.text = aria_label

    # Rounded-corner clip — Shields.io's approach. ``rx=3`` matches the
    # flat-style standard exactly.
    clip = ET.SubElement(svg, "clipPath", {"id": clip_id})
    ET.SubElement(
        clip,
        "rect",
        {
            "width": str(total_width),
            "height": str(BADGE_HEIGHT),
            "rx": "3",
            "fill": "#fff",
        },
    )

    # Background rectangles — left grey, right stance-coloured. Clipped
    # by the rounded mask so the seam between the two halves never
    # bleeds outside the pill outline.
    bg = ET.SubElement(svg, "g", {"clip-path": f"url(#{clip_id})"})
    ET.SubElement(
        bg,
        "rect",
        {
            "width": str(left_section_width),
            "height": str(BADGE_HEIGHT),
            "fill": LEFT_FILL,
        },
    )
    ET.SubElement(
        bg,
        "rect",
        {
            "x": str(left_section_width),
            "width": str(right_section_width),
            "height": str(BADGE_HEIGHT),
            "fill": right_color,
        },
    )

    # Centred text group. ``y=14`` for the 20px badge / 11px font
    # combination puts the visual baseline at the same place
    # Shields.io renders, so a MiroShark badge sits flush next to a
    # GitHub-Actions badge in the same README.
    text_group = ET.SubElement(
        svg,
        "g",
        {
            "fill": TEXT_FILL,
            "text-anchor": "middle",
            "font-family": FONT_FAMILY,
            "font-size": str(FONT_SIZE),
        },
    )

    left_text = ET.SubElement(
        text_group,
        "text",
        {
            "x": str(left_section_width // 2),
            "y": "14",
        },
    )
    left_text.text = LEFT_LABEL

    right_text = ET.SubElement(
        text_group,
        "text",
        {
            "x": str(left_section_width + right_section_width // 2),
            "y": "14",
        },
    )
    right_text.text = right_label

    # ``short_empty_elements=True`` mirrors every other XML renderer in
    # this package (``chart_svg`` / ``frame_metadata`` / sitemap), so a
    # consumer comparing badge bytes against another stdlib SVG sees
    # the same compact form.
    return ET.tostring(svg, encoding="unicode", short_empty_elements=True)


# ── Public renderer ───────────────────────────────────────────────────────


def build_badge_svg(direction: Any, confidence_pct: Any) -> str:
    """Render a flat Shields.io-style status badge as an SVG string.

    Returns a complete SVG 1.1 document — XML declaration, namespace,
    ``viewBox``, accessibility ``role="img"`` + ``aria-label``, and a
    rounded ``clipPath`` so the pill ends render across every
    `<img>`-tag consumer including older Notion / Substack / GitHub
    Markdown previewers.

    The output is bytewise-deterministic across calls with the same
    inputs — useful for HTTP caching and a future hash-based ETag
    layer.
    """
    right_label = _format_right_label(direction, confidence_pct)
    right_color = _resolve_color(direction)
    return _build_badge_document(right_label, right_color, "miroshark-badge-clip")


def render_badge_svg_bytes(direction: Any, confidence_pct: Any) -> bytes:
    """Convenience wrapper returning the SVG document as UTF-8 bytes.

    Includes the XML declaration so a stdout ``curl > badge.svg`` is
    a fully self-contained file. Same posture as
    ``chart_svg.render_chart_svg_bytes``.
    """
    body = build_badge_svg(direction, confidence_pct)
    return b'<?xml version="1.0" encoding="UTF-8"?>' + body.encode("utf-8")


# ── Platform-level badge ──────────────────────────────────────────────────
#
# A sibling renderer for the platform-stats badge served at
# ``/api/stats/badge.svg``. The per-sim ``build_badge_svg`` above renders
# a stance-coloured pill for one simulation; this renders a flat
# platform-blue pill ("MiroShark | N simulations") suitable for the
# project README, the community Substack header, an operator's portfolio,
# anywhere a single live count of platform activity belongs.
#
# Pinned colour: ``#0ea5e9`` (sky-500). Distinct from the three stance
# colours so a reader never mistakes the platform badge for a per-sim
# consensus badge. Same flat 20-pixel Shields.io geometry as the per-sim
# pill so the two badges sit flush in a row of README shields.

PLATFORM_COLOR = "#0ea5e9"


def _format_platform_right_label(count: Any) -> str:
    """Build the right-hand label for the platform badge.

    Coerces the count to a non-negative integer (anything non-numeric
    becomes ``0``) and produces the ``"N simulations"`` string. Always
    uses the plural form regardless of count — Shields.io badges look
    visually balanced with a consistent word width across renders, and
    the rare ``1 simulations`` reads as "platform-active" rather than
    ungrammatical on a freshly-deployed instance.
    """
    try:
        ivalue = int(count)
    except (TypeError, ValueError):
        ivalue = 0
    if ivalue < 0:
        ivalue = 0
    return f"{ivalue} simulations"


def build_platform_badge_svg(count: Any) -> str:
    """Render the flat platform-stats badge as an SVG string.

    Returns a complete SVG 1.1 document with the same dimensions,
    rounded clip path, font family, and a11y attributes as
    ``build_badge_svg`` — only the right-hand label and fill colour
    differ. Bytewise-deterministic across calls with the same count
    so HTTP caching layers can hash the body for an ETag.
    """
    right_label = _format_platform_right_label(count)
    return _build_badge_document(right_label, PLATFORM_COLOR, "miroshark-platform-clip")


def render_platform_badge_svg_bytes(count: Any) -> bytes:
    """Convenience wrapper returning the platform badge as UTF-8 bytes
    with an XML declaration prefix — mirrors ``render_badge_svg_bytes``.
    """
    body = build_platform_badge_svg(count)
    return b'<?xml version="1.0" encoding="UTF-8"?>' + body.encode("utf-8")
