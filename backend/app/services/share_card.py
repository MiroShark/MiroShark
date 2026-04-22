"""Social share card renderer.

Builds a 1200x630 PNG (the canonical Open Graph / Twitter large-image size)
from a simulation's embed-summary payload, suitable for unfurling on
Twitter/X, Discord, Slack, LinkedIn, and any platform that reads
``og:image`` / ``twitter:image`` meta tags.

Pure Pillow — no external font files required. Falls back to the platform
DejaVu fonts (present on every standard Linux container we ship) and
finally to PIL's bitmap default if those are missing.

The renderer is intentionally small and deterministic: same input dict
produces a byte-identical PNG, so ``Cache-Control`` + content-hash filenames
on disk are sufficient. No threading, no I/O beyond the cache write.
"""

from __future__ import annotations

import hashlib
import io
import os
from datetime import datetime
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


# Card geometry — fixed 1.91:1 (1200x630) to match Twitter/X / LinkedIn /
# Slack large-image previews. Anything else gets cropped or letterboxed by
# the unfurler so don't change without a reason.
CARD_W = 1200
CARD_H = 630

# Color palette mirrors the MiroShark frontend tokens
# (frontend/src/views/EmbedView.vue --bg/--fg/--bullish/...).
INK = (10, 10, 10)              # #0a0a0a — header/footer band, primary text
INK_SOFT = (75, 75, 75)         # #4b4b4b — secondary text
INK_MUTED = (107, 107, 107)     # #6b6b6b — labels
PAPER = (250, 250, 250)         # #fafafa — body background
PAPER_LINE = (228, 228, 228)    # subtle dividers
BULLISH = (14, 165, 160)        # teal — high-bull consensus / "correct" badge
NEUTRAL = (154, 160, 166)       # slate — split / mixed
BEARISH = (240, 120, 103)       # coral — high-bear / "wrong"
ACCENT = (234, 88, 12)          # MiroShark orange — brand accent only

# Anchor positions
HEADER_H = 78
FOOTER_H = 70
BODY_Y0 = HEADER_H
BODY_Y1 = CARD_H - FOOTER_H
PAD_X = 56


# ── Font discovery ──────────────────────────────────────────────────────────
# Prefer the bundled-on-most-Linux DejaVu family. macOS dev boxes have
# Helvetica; we fall through to the PIL default (a 10px bitmap) if neither
# is available. That fallback still produces a readable card — it just looks
# uglier — so the endpoint never 500s on missing fonts.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
]

_FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
]


def _find_font(candidates: list[str]) -> Optional[str]:
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    path = _find_font(_FONT_BOLD_CANDIDATES if bold else _FONT_CANDIDATES)
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


# ── Text helpers ────────────────────────────────────────────────────────────


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """Measure pixel width — uses textbbox (Pillow 10+) which is accurate
    for both TTF and the bitmap fallback."""
    if not text:
        return 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int
) -> list[str]:
    """Word-wrap ``text`` to fit ``max_width`` pixels, capping at
    ``max_lines``. Long final lines get an ellipsis. Long single words
    that overflow on their own are truncated character-wise."""
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if _text_width(draw, candidate, font) <= max_width:
            cur = candidate
            continue
        # Single word longer than the line — chop with ellipsis
        if not cur:
            truncated = w
            while truncated and _text_width(draw, truncated + "…", font) > max_width:
                truncated = truncated[:-1]
            lines.append((truncated + "…") if truncated else "…")
            cur = ""
            if len(lines) >= max_lines:
                break
            continue
        lines.append(cur)
        cur = w
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)

    # If we ran out of room, mark the last line with an ellipsis.
    if len(lines) >= max_lines and len(words) > sum(len(l.split()) for l in lines):
        last = lines[-1]
        while last and _text_width(draw, last + "…", font) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = (last + "…") if last else "…"
    return lines


def _format_date(iso_date: str) -> str:
    """Convert ``2026-04-22`` (or full ISO timestamp) to ``Apr 22, 2026``.
    Returns the input untouched if parsing fails."""
    if not iso_date:
        return ""
    try:
        s = iso_date[:10]
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%b %-d, %Y")
    except (ValueError, TypeError):
        # %-d isn't supported on Windows — fall back to zero-padded.
        try:
            dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
            return dt.strftime("%b %d, %Y")
        except (ValueError, TypeError):
            return iso_date[:10] or ""


def _short_sim_id(sim_id: str) -> str:
    """``sim_abc123def456`` → ``SIM_ABC123``."""
    if not sim_id:
        return ""
    body = sim_id.replace("sim_", "", 1).split("_", 1)[0]
    return f"SIM_{body[:6].upper()}"


# ── Drawing primitives ─────────────────────────────────────────────────────


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font,
    bg: tuple,
    fg: tuple,
    pad_x: int = 14,
    pad_y: int = 6,
) -> tuple[int, int]:
    """Draw a rounded-rect pill, return (right_x, bottom_y) for chaining."""
    tw = _text_width(draw, text, font)
    th_bbox = draw.textbbox((0, 0), text, font=font)
    th = th_bbox[3] - th_bbox[1]
    w = tw + pad_x * 2
    h = th + pad_y * 2
    radius = h // 2
    draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=bg)
    # textbbox y0 isn't always 0 — offset so glyphs sit centered.
    draw.text((x + pad_x - th_bbox[0], y + pad_y - th_bbox[1]), text, fill=fg, font=font)
    return x + w, y + h


def _draw_belief_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    bullish_pct: float,
    neutral_pct: float,
    bearish_pct: float,
) -> None:
    """Three-segment horizontal stacked bar — bullish | neutral | bearish.
    Percentages are normalized so they always fill the bar exactly, even when
    the source data sums to 99.9 due to rounding."""
    total = max(bullish_pct + neutral_pct + bearish_pct, 0.01)
    bu_w = int(round(width * (bullish_pct / total)))
    ne_w = int(round(width * (neutral_pct / total)))
    be_w = width - bu_w - ne_w  # absorb any rounding drift here

    cur_x = x
    if bu_w > 0:
        draw.rectangle((cur_x, y, cur_x + bu_w, y + height), fill=BULLISH)
        cur_x += bu_w
    if ne_w > 0:
        draw.rectangle((cur_x, y, cur_x + ne_w, y + height), fill=NEUTRAL)
        cur_x += ne_w
    if be_w > 0:
        draw.rectangle((cur_x, y, cur_x + be_w, y + height), fill=BEARISH)


# ── Public entry points ────────────────────────────────────────────────────


def render_share_card(summary: dict) -> bytes:
    """Render a summary dict into a 1200x630 PNG. Always returns valid PNG
    bytes — missing fields render as a stripped-down "Setup" card instead
    of erroring. ``summary`` is the same shape as the embed-summary
    endpoint response.

    The dict keys consumed (all optional except ``simulation_id``):
        simulation_id, scenario, status, runner_status,
        current_round, total_rounds, profiles_count, created_date,
        belief: { final: {bullish, neutral, bearish}, consensus_round, consensus_stance },
        quality: { health },
        resolution: { actual_outcome, accuracy_score }
    """
    img = Image.new("RGB", (CARD_W, CARD_H), PAPER)
    draw = ImageDraw.Draw(img)

    # Fonts — sized for 1200px width.
    f_brand = _load_font(28, bold=True)
    f_section = _load_font(18, bold=True)
    f_scenario = _load_font(48, bold=True)
    f_scenario_sm = _load_font(40, bold=True)  # used when text wraps to 3+ lines
    f_metric_label = _load_font(16, bold=True)
    f_metric_value = _load_font(36, bold=True)
    f_pct = _load_font(20, bold=True)
    f_pct_label = _load_font(16, bold=True)
    f_footer = _load_font(18, bold=False)
    f_pill = _load_font(15, bold=True)

    # ── Header band ────────────────────────────────────────────────────────
    draw.rectangle((0, 0, CARD_W, HEADER_H), fill=INK)
    draw.text((PAD_X, 22), "MIROSHARK", fill=PAPER, font=f_brand)
    # Brand subtitle to the right of the wordmark.
    brand_w = _text_width(draw, "MIROSHARK", f_brand)
    sub_x = PAD_X + brand_w + 18
    draw.text((sub_x, 30), "▸  Simulation share", fill=(180, 180, 180), font=f_pill)

    # Right-aligned simulation id badge in header.
    sim_id_text = _short_sim_id(summary.get("simulation_id", ""))
    if sim_id_text:
        sid_w = _text_width(draw, sim_id_text, f_pill)
        sid_x = CARD_W - PAD_X - sid_w - 28
        sid_y = HEADER_H // 2 - 14
        draw.rounded_rectangle(
            (sid_x, sid_y, sid_x + sid_w + 28, sid_y + 28),
            radius=14,
            fill=(40, 40, 40),
        )
        draw.text((sid_x + 14, sid_y + 6), sim_id_text, fill=(220, 220, 220), font=f_pill)

    # ── Body ───────────────────────────────────────────────────────────────
    body_x = PAD_X
    body_w = CARD_W - PAD_X * 2
    cur_y = BODY_Y0 + 28

    # Scenario headline. Try the larger size first, drop down if it can't fit
    # in 3 lines.
    scenario = (summary.get("scenario") or "Untitled simulation").strip()
    scenario_lines = _wrap_text(draw, scenario, f_scenario, body_w, max_lines=3)
    scenario_font = f_scenario
    if not scenario_lines or _text_width(draw, scenario_lines[0], f_scenario) > body_w:
        scenario_font = f_scenario_sm
        scenario_lines = _wrap_text(draw, scenario, scenario_font, body_w, max_lines=3)
    line_h = scenario_font.size + 8 if hasattr(scenario_font, "size") else 56
    for line in scenario_lines:
        draw.text((body_x, cur_y), line, fill=INK, font=scenario_font)
        cur_y += line_h
    cur_y += 12

    # ── Status / quality / resolution pills row ──
    pills_y = cur_y
    pill_x = body_x

    status_label, status_bg, status_fg = _status_pill(summary)
    if status_label:
        pill_x, _ = _draw_pill(draw, pill_x, pills_y, status_label, f_pill, status_bg, status_fg)
        pill_x += 8

    quality_health = (summary.get("quality") or {}).get("health")
    if quality_health:
        q_bg, q_fg = _quality_colors(quality_health)
        pill_x, _ = _draw_pill(
            draw, pill_x, pills_y, f"Quality · {quality_health}", f_pill, q_bg, q_fg
        )
        pill_x += 8

    resolution = summary.get("resolution") or {}
    res_label = _resolution_label(resolution)
    if res_label:
        r_bg, r_fg = _resolution_colors(resolution)
        pill_x, _ = _draw_pill(draw, pill_x, pills_y, res_label, f_pill, r_bg, r_fg)
        pill_x += 8

    consensus = (summary.get("belief") or {}).get("consensus_round")
    if consensus:
        stance = (summary.get("belief") or {}).get("consensus_stance") or ""
        cons_text = f"Consensus R{consensus}"
        if stance:
            cons_text += f" · {stance.capitalize()}"
        pill_x, _ = _draw_pill(
            draw, pill_x, pills_y, cons_text, f_pill, (240, 240, 240), INK
        )

    cur_y = pills_y + 40

    # ── Metrics row (3 columns) ──
    metrics = _build_metrics(summary)
    if metrics:
        col_w = body_w // len(metrics)
        for i, (label, value) in enumerate(metrics):
            col_x = body_x + i * col_w
            draw.text((col_x, cur_y), label.upper(), fill=INK_MUTED, font=f_metric_label)
            draw.text((col_x, cur_y + 22), value, fill=INK, font=f_metric_value)
        cur_y += 90

    # ── Belief bar ──
    belief = (summary.get("belief") or {}).get("final") or {}
    has_belief = any(belief.get(k) for k in ("bullish", "neutral", "bearish"))
    if has_belief:
        bar_y = cur_y
        bar_h = 28
        bu = float(belief.get("bullish") or 0)
        ne = float(belief.get("neutral") or 0)
        be = float(belief.get("bearish") or 0)
        _draw_belief_bar(draw, body_x, bar_y, body_w, bar_h, bu, ne, be)

        # Legend row beneath the bar.
        legend_y = bar_y + bar_h + 14
        items = [
            (f"Bullish {int(round(bu))}%", BULLISH),
            (f"Neutral {int(round(ne))}%", NEUTRAL),
            (f"Bearish {int(round(be))}%", BEARISH),
        ]
        legend_x = body_x
        for text, color in items:
            # Color square + label
            draw.rectangle((legend_x, legend_y + 4, legend_x + 14, legend_y + 18), fill=color)
            draw.text((legend_x + 22, legend_y), text, fill=INK_SOFT, font=f_pct)
            legend_x += _text_width(draw, text, f_pct) + 60

    # ── Footer band ────────────────────────────────────────────────────────
    draw.rectangle((0, BODY_Y1, CARD_W, CARD_H), fill=INK)
    repo_text = "github.com/aaronjmars/MiroShark"
    draw.text((PAD_X, BODY_Y1 + 24), repo_text, fill=(220, 220, 220), font=f_footer)

    date_text = _format_date(summary.get("created_date") or "")
    if date_text:
        dw = _text_width(draw, date_text, f_footer)
        draw.text((CARD_W - PAD_X - dw, BODY_Y1 + 24), date_text, fill=(160, 160, 160), font=f_footer)

    # Output PNG bytes (optimize=False keeps generation fast and
    # deterministic; 1200x630 cards are ~30-60 KB without it).
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


# ── Pill / metric helpers ──────────────────────────────────────────────────


def _status_pill(summary: dict) -> tuple[str, tuple, tuple]:
    s = (summary.get("runner_status") or summary.get("status") or "").lower()
    if s in ("completed", "finished", "stopped"):
        return "Completed", (217, 245, 240), BULLISH
    if s in ("running", "in_progress"):
        return "Running", (255, 232, 209), ACCENT
    if s in ("failed", "error"):
        return "Failed", (255, 224, 219), BEARISH
    if s == "ready":
        return "Ready", (236, 236, 236), INK_SOFT
    return ("Setup", (236, 236, 236), INK_SOFT)


def _quality_colors(health: str) -> tuple[tuple, tuple]:
    h = (health or "").lower()
    if h == "excellent":
        return (217, 245, 240), BULLISH
    if h == "good":
        return (255, 240, 204), (180, 83, 9)
    if h == "low":
        return (255, 224, 219), BEARISH
    return (236, 236, 236), INK_SOFT


def _resolution_label(resolution: dict) -> str:
    if not resolution:
        return ""
    actual = resolution.get("actual_outcome")
    if actual is None:
        return ""
    score = resolution.get("accuracy_score")
    if score is None:
        return f"Actual {actual}"
    if score >= 1.0:
        return f"✓ Correct · Actual {actual}"
    if score <= 0.0:
        return f"✗ Missed · Actual {actual}"
    return f"~ Split · Actual {actual}"


def _resolution_colors(resolution: dict) -> tuple[tuple, tuple]:
    if not resolution:
        return (236, 236, 236), INK_SOFT
    score = resolution.get("accuracy_score")
    if score is None:
        return (236, 236, 236), INK_SOFT
    if score >= 1.0:
        return (217, 245, 240), BULLISH
    if score <= 0.0:
        return (255, 224, 219), BEARISH
    return (236, 236, 236), INK_SOFT


def _build_metrics(summary: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    agents = summary.get("profiles_count")
    if agents:
        out.append(("Agents", str(int(agents))))

    cur = int(summary.get("current_round") or 0)
    total = int(summary.get("total_rounds") or 0)
    if total:
        out.append(("Rounds", f"{cur}/{total}"))
    elif cur:
        out.append(("Rounds", str(cur)))

    belief = (summary.get("belief") or {}).get("final") or {}
    if belief:
        bu = belief.get("bullish")
        be = belief.get("bearish")
        if bu is not None and be is not None:
            net = round(bu - be)
            sign = "+" if net > 0 else ""
            out.append(("Net Bull-Bear", f"{sign}{net}%"))

    return out[:4]


# ── Cache helpers ──────────────────────────────────────────────────────────


def summary_cache_key(summary: dict) -> str:
    """Stable hash of the inputs that affect the rendered card. Two cards
    with the same hash are guaranteed byte-identical (as long as the
    renderer code itself doesn't change)."""
    parts = {
        "scenario": summary.get("scenario") or "",
        "runner_status": summary.get("runner_status") or summary.get("status") or "",
        "current_round": summary.get("current_round") or 0,
        "total_rounds": summary.get("total_rounds") or 0,
        "profiles_count": summary.get("profiles_count") or 0,
        "created_date": summary.get("created_date") or "",
    }
    belief_final = (summary.get("belief") or {}).get("final") or {}
    parts["belief_final"] = (
        round(float(belief_final.get("bullish") or 0), 1),
        round(float(belief_final.get("neutral") or 0), 1),
        round(float(belief_final.get("bearish") or 0), 1),
    )
    parts["consensus_round"] = (summary.get("belief") or {}).get("consensus_round") or 0
    parts["consensus_stance"] = (summary.get("belief") or {}).get("consensus_stance") or ""
    parts["quality"] = (summary.get("quality") or {}).get("health") or ""
    res = summary.get("resolution") or {}
    parts["resolution"] = (
        res.get("actual_outcome") or "",
        res.get("accuracy_score"),
    )
    blob = repr(sorted(parts.items())).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
