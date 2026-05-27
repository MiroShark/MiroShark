"""Per-round belief trajectory rendered as a pure-stdlib SVG.

The eighth share surface alongside the share card (PNG, final-state
verdict), replay GIF (motion), transcript (prose), trajectory CSV /
JSONL (raw data), thread (text), watch page (live), and notebook
(analysis). The previous seven cover *what happened* in a finished or
live simulation; this one is the **scalable visual of the journey** —
the bullish / neutral / bearish curves across all recorded rounds, as
an `<img>`-embeddable vector image.

Same approach as the sitemap renderer (PR #82): pure stdlib
`xml.etree.ElementTree` — no Cairo, no matplotlib, no Pillow, no new
dependencies. The output is a complete SVG 1.1 document that Notion,
Substack, Ghost, GitHub READMEs, and LaTeX `\\includesvg{}` consume as
a single `<img src="…/chart.svg">` tag.

Design notes
------------

* **Zero deps.** ``xml.etree.ElementTree`` + ``json`` + ``os`` + ``math``
  — every renderer module in this package follows the same rule.
* **Bytewise stable.** Element insertion order is deterministic and the
  serializer pins ``short_empty_elements=True`` so two identical inputs
  produce identical bytes. The byte hash is suitable as a cache key.
* **Robust to partial data.** A trajectory with a single recorded round
  still renders. ``render_chart_svg_bytes`` returns ``None`` only when
  the trajectory is *empty* (no rows at all) so the route handler can
  emit a 404 rather than a blank canvas.
* **Same colors as every other surface.** ``#22c55e`` bullish,
  ``#6b7280`` neutral, ``#ef4444`` bearish — matches the share card,
  replay GIF, watch page, and EmbedDialog belief bars. A reader who
  saw the share card embed recognises the colours immediately.
"""

from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET
from typing import Optional


# ── Canvas geometry ───────────────────────────────────────────────────────

SVG_WIDTH = 800
SVG_HEIGHT = 400
PAD_TOP = 56
PAD_RIGHT = 24
PAD_BOTTOM = 56
PAD_LEFT = 56

PLOT_W = SVG_WIDTH - PAD_LEFT - PAD_RIGHT
PLOT_H = SVG_HEIGHT - PAD_TOP - PAD_BOTTOM


# ── Stance colors ─────────────────────────────────────────────────────────
#
# These match the share card / replay GIF / watch page colours so the
# chart SVG reads as the same visual language. Don't change without
# updating those surfaces in lockstep.

BULLISH_COLOR = "#22c55e"
NEUTRAL_COLOR = "#6b7280"
BEARISH_COLOR = "#ef4444"

AXIS_COLOR = "#9ca3af"
GRID_COLOR = "#e5e7eb"
LABEL_COLOR = "#374151"
TITLE_COLOR = "#111827"
BG_COLOR = "#ffffff"


# ── Title geometry ────────────────────────────────────────────────────────
#
# The title sits in the top padding band; ``80`` is the soft truncation
# point — anything longer gets an ellipsis. ``120`` is a hard ceiling
# that lets a slightly-longer scenario render without losing meaning
# (long titles wrap onto the chart area would look worse than truncating).

TITLE_MAX_CHARS = 80


# ── Internal helpers ──────────────────────────────────────────────────────


def _scale_x(round_num: int, max_round: int) -> float:
    """Map a round number into a pixel x-coordinate inside the plot area.

    ``max_round`` is the largest round in the trajectory (not the count
    of rounds — round numbers can be 1-indexed). When there is only one
    round, the single point sits centred on the y-axis edge — the line
    would otherwise have nowhere to go.
    """
    if max_round <= 0:
        return PAD_LEFT
    # Anchor round 0 (or round 1 for 1-indexed runs) at the left edge,
    # the final round at the right edge. Round 0 + max_round = full
    # span; intermediate rounds scale linearly.
    span = max(1, max_round)
    fraction = round_num / span
    return PAD_LEFT + fraction * PLOT_W


def _scale_y(pct: float) -> float:
    """Map a percentage (0–100) into a pixel y-coordinate.

    SVG y-axis is inverted — 0 is at the top. We invert the percentage
    so 100% maps to ``PAD_TOP`` (top of the plot) and 0% to
    ``PAD_TOP + PLOT_H`` (bottom).
    """
    clamped = max(0.0, min(100.0, float(pct)))
    return PAD_TOP + PLOT_H * (1.0 - clamped / 100.0)


def _format_float(value: float) -> str:
    """Trim trailing zeros so ``120.0`` serialises as ``120`` — keeps the
    SVG body small and bytewise stable across float repr quirks."""
    if value == int(value):
        return str(int(value))
    # One decimal is enough — the percentages on disk are already
    # rounded to one place by ``trajectory_export``.
    formatted = f"{value:.1f}"
    if formatted.endswith(".0"):
        formatted = formatted[:-2]
    return formatted


def _polyline_points(rows: list[dict], pct_key: str, max_round: int) -> str:
    """Build an SVG ``points`` attribute string for one stance series.

    Each row contributes ``x,y`` where x comes from the round number
    and y from the per-round percentage for ``pct_key``. Skips rows
    where the percentage is missing or non-numeric.
    """
    parts: list[str] = []
    for row in rows:
        try:
            r = int(row.get("round") or 0)
        except (TypeError, ValueError):
            continue
        raw = row.get(pct_key)
        if not isinstance(raw, (int, float)):
            continue
        x = _scale_x(r, max_round)
        y = _scale_y(float(raw))
        parts.append(f"{_format_float(x)},{_format_float(y)}")
    return " ".join(parts)


def _truncate_title(text: str) -> str:
    """Trim the chart title to ``TITLE_MAX_CHARS`` with an ellipsis."""
    text = (text or "").strip()
    if len(text) <= TITLE_MAX_CHARS:
        return text
    return text[: TITLE_MAX_CHARS - 1].rstrip() + "…"


# ── On-disk reader ────────────────────────────────────────────────────────


def load_trajectory_for_chart(sim_dir: str) -> list[dict]:
    """Read the trajectory rows the chart needs.

    Reuses ``trajectory_export.build_rows`` so a single change to the
    underlying ``trajectory.json`` schema flows through both surfaces.
    The chart only consumes ``round``, ``bullish_pct``, ``neutral_pct``,
    and ``bearish_pct`` — the other columns are ignored. Returns an
    empty list when ``sim_dir`` is missing or the trajectory is empty.
    """
    if not sim_dir or not os.path.isdir(sim_dir):
        return []
    # Local import — keeps the module free of a circular import at
    # package init time and mirrors the pattern other renderers use.
    from . import trajectory_export

    try:
        rows = trajectory_export.build_rows(sim_dir)
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    return rows


# ── SVG builder ───────────────────────────────────────────────────────────


def _add_axes_and_grid(svg: ET.Element, max_round: int) -> None:
    """Draw the y-axis grid (0/25/50/75/100), the x-axis baseline, and
    the y-axis tick labels.

    The x-axis ticks (round numbers) are added by the caller after the
    grid so the round labels paint on top of the grid lines.
    """
    # Y-axis grid lines + labels at 0, 25, 50, 75, 100 percent.
    for pct in (0, 25, 50, 75, 100):
        y = _scale_y(pct)
        ET.SubElement(svg, "line", {
            "x1": _format_float(PAD_LEFT),
            "y1": _format_float(y),
            "x2": _format_float(PAD_LEFT + PLOT_W),
            "y2": _format_float(y),
            "stroke": GRID_COLOR,
            "stroke-width": "1",
        })
        label = ET.SubElement(svg, "text", {
            "x": _format_float(PAD_LEFT - 8),
            "y": _format_float(y + 4),
            "fill": LABEL_COLOR,
            "font-family": "Inter, system-ui, -apple-system, sans-serif",
            "font-size": "11",
            "text-anchor": "end",
        })
        label.text = f"{pct}%"

    # X-axis baseline along y=0 (bottom of the plot).
    ET.SubElement(svg, "line", {
        "x1": _format_float(PAD_LEFT),
        "y1": _format_float(PAD_TOP + PLOT_H),
        "x2": _format_float(PAD_LEFT + PLOT_W),
        "y2": _format_float(PAD_TOP + PLOT_H),
        "stroke": AXIS_COLOR,
        "stroke-width": "1",
    })

    # Y-axis vertical line.
    ET.SubElement(svg, "line", {
        "x1": _format_float(PAD_LEFT),
        "y1": _format_float(PAD_TOP),
        "x2": _format_float(PAD_LEFT),
        "y2": _format_float(PAD_TOP + PLOT_H),
        "stroke": AXIS_COLOR,
        "stroke-width": "1",
    })

    # X-axis tick labels — round numbers. Pick a step so we end up with
    # ~5-8 labels across the plot regardless of total round count; a
    # 30-round sim shows every 5 rounds, a 100-round sim every 20.
    if max_round <= 0:
        return
    if max_round <= 10:
        step = 1
    elif max_round <= 25:
        step = 5
    elif max_round <= 60:
        step = 10
    else:
        step = max(10, int(math.ceil(max_round / 8 / 10) * 10))

    r = 0
    while r <= max_round:
        x = _scale_x(r, max_round)
        label = ET.SubElement(svg, "text", {
            "x": _format_float(x),
            "y": _format_float(PAD_TOP + PLOT_H + 16),
            "fill": LABEL_COLOR,
            "font-family": "Inter, system-ui, -apple-system, sans-serif",
            "font-size": "11",
            "text-anchor": "middle",
        })
        label.text = str(r)
        r += step
    # Always paint the final-round label too — without it the rightmost
    # x value can look mid-chart and a reader can't tell where the run
    # actually ended.
    if r - step != max_round:
        x = _scale_x(max_round, max_round)
        label = ET.SubElement(svg, "text", {
            "x": _format_float(x),
            "y": _format_float(PAD_TOP + PLOT_H + 16),
            "fill": LABEL_COLOR,
            "font-family": "Inter, system-ui, -apple-system, sans-serif",
            "font-size": "11",
            "text-anchor": "middle",
        })
        label.text = str(max_round)

    # X-axis caption ("Round").
    caption = ET.SubElement(svg, "text", {
        "x": _format_float(PAD_LEFT + PLOT_W / 2),
        "y": _format_float(PAD_TOP + PLOT_H + 34),
        "fill": LABEL_COLOR,
        "font-family": "Inter, system-ui, -apple-system, sans-serif",
        "font-size": "11",
        "text-anchor": "middle",
    })
    caption.text = "Round"


def _add_lines(svg: ET.Element, rows: list[dict], max_round: int) -> None:
    """Draw the three belief polylines."""
    for pct_key, color in (
        ("bullish_pct", BULLISH_COLOR),
        ("neutral_pct", NEUTRAL_COLOR),
        ("bearish_pct", BEARISH_COLOR),
    ):
        points = _polyline_points(rows, pct_key, max_round)
        if not points:
            continue
        ET.SubElement(svg, "polyline", {
            "points": points,
            "fill": "none",
            "stroke": color,
            "stroke-width": "2",
            "stroke-linejoin": "round",
            "stroke-linecap": "round",
        })


def _add_legend(svg: ET.Element) -> None:
    """Render the three-swatch legend inside the top-right padding band.

    Placed inside the padded region (above the plot but below the
    title) so it never overlaps the polylines. Three entries left to
    right: Bullish, Neutral, Bearish — same order as the share card and
    every other belief-display surface.
    """
    legend_y = 28
    # Right-anchored layout so the legend hugs the right edge of the
    # chart regardless of canvas tweaks.
    entries = (
        ("Bullish", BULLISH_COLOR),
        ("Neutral", NEUTRAL_COLOR),
        ("Bearish", BEARISH_COLOR),
    )
    # Each entry is a 10x10 swatch + label, separated by 16px.
    SWATCH_SIZE = 10
    GAP = 6
    LABEL_GAP = 16
    # Measure widths roughly: each label fits in ~52px (8px per char).
    # Layout from the right edge inward so we don't have to measure
    # exactly — pre-compute total width then anchor at the right pad.
    label_widths = {"Bullish": 44, "Neutral": 44, "Bearish": 44}
    total_w = 0
    for name, _ in entries:
        total_w += SWATCH_SIZE + GAP + label_widths[name] + LABEL_GAP
    total_w -= LABEL_GAP  # no trailing gap after the last entry
    cursor = SVG_WIDTH - PAD_RIGHT - total_w

    for name, color in entries:
        ET.SubElement(svg, "rect", {
            "x": _format_float(cursor),
            "y": _format_float(legend_y - SWATCH_SIZE + 2),
            "width": str(SWATCH_SIZE),
            "height": str(SWATCH_SIZE),
            "fill": color,
            "rx": "2",
        })
        text = ET.SubElement(svg, "text", {
            "x": _format_float(cursor + SWATCH_SIZE + GAP),
            "y": _format_float(legend_y),
            "fill": LABEL_COLOR,
            "font-family": "Inter, system-ui, -apple-system, sans-serif",
            "font-size": "11",
        })
        text.text = name
        cursor += SWATCH_SIZE + GAP + label_widths[name] + LABEL_GAP


def _add_title(svg: ET.Element, title: str) -> None:
    """Render the chart title near the top-left of the canvas."""
    if not title:
        return
    elem = ET.SubElement(svg, "text", {
        "x": _format_float(PAD_LEFT),
        "y": "26",
        "fill": TITLE_COLOR,
        "font-family": "Inter, system-ui, -apple-system, sans-serif",
        "font-size": "14",
        "font-weight": "600",
    })
    elem.text = title


def build_chart_svg(rows: list[dict], scenario: Optional[str]) -> ET.Element:
    """Assemble the SVG root element for the trajectory chart.

    The root is a complete SVG 1.1 document with explicit ``viewBox``
    so it scales cleanly when embedded as an ``<img>`` at any size.
    """
    svg = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "viewBox": f"0 0 {SVG_WIDTH} {SVG_HEIGHT}",
        "width": str(SVG_WIDTH),
        "height": str(SVG_HEIGHT),
        "role": "img",
        "aria-label": "MiroShark belief trajectory chart",
    })

    # White background — so the SVG renders correctly when embedded
    # against a dark theme as well (the polylines stay readable).
    ET.SubElement(svg, "rect", {
        "x": "0",
        "y": "0",
        "width": str(SVG_WIDTH),
        "height": str(SVG_HEIGHT),
        "fill": BG_COLOR,
    })

    if rows:
        # Use the largest round on disk as the right-edge anchor. We
        # don't trust the row order (build_rows already sorts, but be
        # defensive — a single re-ordered row would warp the curve).
        max_round = 0
        for r in rows:
            try:
                rn = int(r.get("round") or 0)
            except (TypeError, ValueError):
                continue
            if rn > max_round:
                max_round = rn

        _add_axes_and_grid(svg, max_round)
        _add_lines(svg, rows, max_round)

    _add_legend(svg)
    _add_title(svg, _truncate_title(scenario or ""))

    return svg


def render_chart_svg_bytes(sim_dir: str, scenario: Optional[str]) -> Optional[bytes]:
    """Render the trajectory chart for a sim directory.

    Returns ``None`` when the trajectory is empty so the route handler
    can emit a clean 404 — better than serving a blank canvas the
    embedding site can't distinguish from a "still loading" state.
    """
    rows = load_trajectory_for_chart(sim_dir)
    if not rows:
        return None

    svg = build_chart_svg(rows, scenario)
    # ``short_empty_elements`` keeps ``<rect/>`` compact instead of
    # ``<rect></rect>`` and matches the byte shape every other XML
    # surface in this package uses.
    return ET.tostring(
        svg,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )
