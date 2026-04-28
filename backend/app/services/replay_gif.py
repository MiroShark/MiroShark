"""Animated belief-replay GIF renderer.

Builds a 1200×630 animated GIF from a simulation's per-round belief
distribution — one frame per round, belief bars sliding from each round's
``bullish/neutral/bearish`` percentage to the next, with a round counter
and progress bar.

Distribution-shaped: X / Discord / Slack render direct GIF URLs as
auto-playing inline media, so the same canvas dimensions as the share
card (1200×630, 1.91:1 OG aspect) keep the unfurl shape stable while
giving the simulation motion that a static PNG can't.

Pure Pillow — no FFmpeg, no extra dependencies. The font discovery /
text wrap / pill helpers are deliberately mirrored from
``share_card.py`` rather than imported, so a refactor to either renderer
can happen independently. ``render_replay_gif`` is deterministic: the
same input dict produces byte-identical output, so a content-hash cache
on disk is sufficient.
"""

from __future__ import annotations

import hashlib
import io
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


# Canvas geometry — same 1200×630 (1.91:1) as the share card so X/Discord
# preview shapes stay consistent across the static + animated formats.
CARD_W = 1200
CARD_H = 630

# Frame timing — 600ms per round is fast enough that a 20-round
# simulation finishes in ~12s (well under the typical X autoplay window)
# but slow enough that viewers can read each round's bar shifts. The
# final frame holds 3× longer so the resting consensus reads as the
# punch-line.
FRAME_MS = 600
FINAL_HOLD_MS = 1800
# Safety cap — if a simulation somehow produced 200 rounds we don't want
# to render a 2-minute GIF that nobody will watch. Past the cap we skip
# evenly through the trajectory rather than dropping the tail.
MAX_FRAMES = 60

# Color palette — dark theme so the GIF reads on both light and dark X
# / Discord backgrounds. Mirrors the frontend EmbedView dark tokens.
BG = (10, 10, 10)
PANEL = (24, 24, 24)
INK = (250, 250, 250)
INK_SOFT = (190, 190, 190)
INK_MUTED = (130, 130, 130)
RULE = (50, 50, 50)
BULLISH = (14, 165, 160)
NEUTRAL = (154, 160, 166)
BEARISH = (240, 120, 103)
ACCENT = (234, 88, 12)

PAD_X = 56
HEADER_H = 78
FOOTER_H = 70


# ── Font discovery ─────────────────────────────────────────────────────────
# Same candidate list as share_card.py — DejaVu on Linux containers,
# Helvetica on macOS dev boxes, fall through to PIL's default bitmap.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
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


# ── Text helpers ───────────────────────────────────────────────────────────


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    if not text:
        return 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int
) -> list[str]:
    """Word-wrap to ``max_width``, capped at ``max_lines``. Long final
    lines get an ellipsis. Single words longer than the line are
    character-chopped so the wrap loop terminates."""
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

    if len(lines) >= max_lines and len(words) > sum(len(l.split()) for l in lines):
        last = lines[-1]
        while last and _text_width(draw, last + "…", font) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = (last + "…") if last else "…"
    return lines


# ── Trajectory extraction ──────────────────────────────────────────────────


def extract_frames_from_summary(summary: dict) -> list[dict]:
    """Pull per-round belief percentages out of the embed-summary payload.

    Returns a list of ``{round, bullish, neutral, bearish}`` dicts in
    round order. Returns an empty list when the summary lacks belief
    data — caller should render a single "no data yet" frame.

    Subsamples to ``MAX_FRAMES`` evenly across the trajectory if longer
    so the GIF stays under ~1 minute of playback even for very long
    simulations. The final round is always preserved so the resting
    consensus is visible.
    """
    belief = summary.get("belief") or {}
    rounds = belief.get("rounds") or []
    bullish = belief.get("bullish") or []
    neutral = belief.get("neutral") or []
    bearish = belief.get("bearish") or []

    n = min(len(rounds), len(bullish), len(neutral), len(bearish))
    if n == 0:
        return []

    raw = [
        {
            "round": int(rounds[i]),
            "bullish": float(bullish[i]),
            "neutral": float(neutral[i]),
            "bearish": float(bearish[i]),
        }
        for i in range(n)
    ]

    if n <= MAX_FRAMES:
        return raw

    # Evenly subsample, always keep the last frame so the resting
    # consensus stays visible.
    step = (n - 1) / (MAX_FRAMES - 1)
    indices = sorted({int(round(i * step)) for i in range(MAX_FRAMES - 1)})
    indices.append(n - 1)
    indices = sorted(set(indices))
    return [raw[i] for i in indices]


# ── Frame composition ─────────────────────────────────────────────────────


def _draw_belief_bars(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    bullish_pct: float,
    neutral_pct: float,
    bearish_pct: float,
    fonts: dict,
) -> int:
    """Render three labelled horizontal bars, one per stance.

    Returns the y-coordinate immediately below the rendered block so
    the caller can stack additional content (round progress bar)
    underneath.
    """
    bar_h = 32
    label_h = 22
    row_gap = 14
    block_h = (label_h + bar_h + row_gap) * 3 - row_gap

    rows = [
        ("Bullish", bullish_pct, BULLISH),
        ("Neutral", neutral_pct, NEUTRAL),
        ("Bearish", bearish_pct, BEARISH),
    ]

    cur_y = y
    for label, pct, color in rows:
        # Label row — name on the left, percentage on the right (right-
        # aligned so the eye can scan a fixed column even as values
        # shift between rounds).
        pct_text = f"{int(round(pct))}%"
        draw.text((x, cur_y), label, fill=INK_SOFT, font=fonts["bar_label"])
        pct_w = _text_width(draw, pct_text, fonts["bar_value"])
        draw.text(
            (x + width - pct_w, cur_y - 2),
            pct_text,
            fill=INK,
            font=fonts["bar_value"],
        )

        bar_y = cur_y + label_h
        # Bar background — subtle so the eye reads the filled portion.
        draw.rounded_rectangle(
            (x, bar_y, x + width, bar_y + bar_h),
            radius=bar_h // 2,
            fill=PANEL,
        )
        # Filled portion — clamp to [0, 100] so out-of-range values
        # don't paint past the rounded background.
        clamped = max(0.0, min(100.0, pct))
        fill_w = int(round(width * clamped / 100.0))
        if fill_w > 0:
            # Width must clear the rounded radius for the fill to render
            # cleanly; below ~bar_h pixels Pillow's rounded_rectangle
            # produces a thin pill which is the desired visual.
            draw.rounded_rectangle(
                (x, bar_y, x + max(fill_w, bar_h // 2), bar_y + bar_h),
                radius=bar_h // 2,
                fill=color,
            )

        cur_y += label_h + bar_h + row_gap

    return y + block_h


def _draw_round_progress(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    current: int,
    total: int,
    fonts: dict,
) -> None:
    """Thin progress bar at the bottom showing where we are in the run."""
    track_h = 6
    pos_text = f"Round {current} / {total}"
    pos_w = _text_width(draw, pos_text, fonts["progress"])
    draw.text((x + width - pos_w, y - 22), pos_text, fill=INK_MUTED, font=fonts["progress"])

    draw.rounded_rectangle(
        (x, y, x + width, y + track_h), radius=track_h // 2, fill=PANEL
    )
    if total > 0:
        pct = max(0.0, min(1.0, current / total))
        fill_w = int(round(width * pct))
        if fill_w > 0:
            draw.rounded_rectangle(
                (x, y, x + max(fill_w, track_h), y + track_h),
                radius=track_h // 2,
                fill=ACCENT,
            )


def _render_frame(scenario: str, frame: dict, total_rounds: int, fonts: dict) -> Image.Image:
    """Draw a single 1200×630 frame for the GIF.

    ``frame`` is one entry from ``extract_frames_from_summary`` plus the
    round counter. ``total_rounds`` drives the bottom progress bar.
    """
    img = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(img)

    # ── Header band ───────────────────────────────────────────────────
    draw.rectangle((0, 0, CARD_W, HEADER_H), fill=PANEL)
    draw.text((PAD_X, 22), "MIROSHARK", fill=INK, font=fonts["brand"])
    brand_w = _text_width(draw, "MIROSHARK", fonts["brand"])
    draw.text((PAD_X + brand_w + 18, 30), "▸  Belief replay", fill=INK_MUTED, font=fonts["brand_sub"])

    # ── Scenario block ────────────────────────────────────────────────
    body_x = PAD_X
    body_w = CARD_W - PAD_X * 2
    cur_y = HEADER_H + 26

    scenario_lines = _wrap_text(draw, scenario.strip(), fonts["scenario"], body_w, max_lines=2)
    line_h = fonts["scenario"].size + 6 if hasattr(fonts["scenario"], "size") else 30
    for line in scenario_lines:
        draw.text((body_x, cur_y), line, fill=INK, font=fonts["scenario"])
        cur_y += line_h
    if not scenario_lines:
        # Make space even when no scenario exists so the bar block
        # doesn't jump up into the header band.
        cur_y += line_h

    cur_y += 10
    draw.line((body_x, cur_y, body_x + body_w, cur_y), fill=RULE, width=1)
    cur_y += 24

    # ── Belief bars ───────────────────────────────────────────────────
    cur_y = _draw_belief_bars(
        draw,
        body_x,
        cur_y,
        body_w,
        frame.get("bullish", 0.0),
        frame.get("neutral", 0.0),
        frame.get("bearish", 0.0),
        fonts,
    )

    # ── Round progress bar (anchored above the footer band) ──────────
    progress_y = CARD_H - FOOTER_H - 22
    _draw_round_progress(
        draw,
        body_x,
        progress_y,
        body_w,
        int(frame.get("round", 0)),
        max(int(total_rounds or 0), int(frame.get("round", 0))),
        fonts,
    )

    # ── Footer band ───────────────────────────────────────────────────
    draw.rectangle((0, CARD_H - FOOTER_H, CARD_W, CARD_H), fill=PANEL)
    draw.text(
        (PAD_X, CARD_H - FOOTER_H + 24),
        "github.com/aaronjmars/MiroShark",
        fill=INK_MUTED,
        font=fonts["footer"],
    )
    cta_text = "▶ Replay belief drift"
    cta_w = _text_width(draw, cta_text, fonts["footer"])
    draw.text(
        (CARD_W - PAD_X - cta_w, CARD_H - FOOTER_H + 24),
        cta_text,
        fill=ACCENT,
        font=fonts["footer"],
    )

    return img


def _render_empty_frame(scenario: str, fonts: dict) -> Image.Image:
    """Single-frame poster shown when a simulation has no trajectory yet
    (e.g. a freshly published READY run). Keeps the endpoint from 500-ing
    and gives unfurlers a usable image while the run starts up."""
    img = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, CARD_W, HEADER_H), fill=PANEL)
    draw.text((PAD_X, 22), "MIROSHARK", fill=INK, font=fonts["brand"])
    brand_w = _text_width(draw, "MIROSHARK", fonts["brand"])
    draw.text((PAD_X + brand_w + 18, 30), "▸  Belief replay", fill=INK_MUTED, font=fonts["brand_sub"])

    body_x = PAD_X
    body_w = CARD_W - PAD_X * 2

    scenario_lines = _wrap_text(draw, scenario.strip(), fonts["scenario"], body_w, max_lines=2)
    cur_y = HEADER_H + 40
    line_h = fonts["scenario"].size + 6 if hasattr(fonts["scenario"], "size") else 30
    for line in scenario_lines:
        draw.text((body_x, cur_y), line, fill=INK, font=fonts["scenario"])
        cur_y += line_h
    cur_y += 30

    msg = "Belief trajectory not available yet"
    sub = "Run hasn't recorded snapshots — check back when it has rounds."
    draw.text((body_x, cur_y), msg, fill=INK_SOFT, font=fonts["bar_value"])
    draw.text((body_x, cur_y + 38), sub, fill=INK_MUTED, font=fonts["bar_label"])

    draw.rectangle((0, CARD_H - FOOTER_H, CARD_W, CARD_H), fill=PANEL)
    draw.text(
        (PAD_X, CARD_H - FOOTER_H + 24),
        "github.com/aaronjmars/MiroShark",
        fill=INK_MUTED,
        font=fonts["footer"],
    )
    return img


def _build_fonts() -> dict:
    return {
        "brand": _load_font(28, bold=True),
        "brand_sub": _load_font(15, bold=True),
        "scenario": _load_font(28, bold=True),
        "bar_label": _load_font(18, bold=True),
        "bar_value": _load_font(26, bold=True),
        "progress": _load_font(14, bold=True),
        "footer": _load_font(18, bold=True),
    }


# ── Public entry point ────────────────────────────────────────────────────


def render_replay_gif(summary: dict) -> bytes:
    """Render an animated GIF from the embed-summary payload.

    Always returns valid GIF bytes — a missing trajectory renders a
    single-frame "Belief trajectory not available yet" poster so the
    endpoint never 500s on a freshly published run that hasn't yet
    snapshotted any belief state.
    """
    fonts = _build_fonts()
    scenario = (summary.get("scenario") or "Untitled simulation").strip()
    total_rounds = int(summary.get("total_rounds") or 0)

    frames_data = extract_frames_from_summary(summary)
    if not frames_data:
        # Single-frame still — Pillow GIF encoder accepts one frame, the
        # output is essentially a static GIF that scrapers still treat
        # as image/gif.
        poster = _render_empty_frame(scenario, fonts)
        buf = io.BytesIO()
        poster.save(buf, format="GIF", optimize=False)
        return buf.getvalue()

    if not total_rounds:
        # When the summary doesn't carry a planned total, fall back to
        # the last observed round so the progress bar reads "Round N / N"
        # at the end rather than dividing by zero.
        total_rounds = max(int(f["round"]) for f in frames_data)

    # Render every frame upfront — the GIF encoder needs them all in
    # memory anyway, and rendering is cheap (a few hundred ms total
    # for a 20-round simulation).
    frames: list[Image.Image] = [
        _render_frame(scenario, frame, total_rounds, fonts) for frame in frames_data
    ]

    # Per-frame durations: every frame is FRAME_MS except the last,
    # which holds longer so the resting consensus reads as the punch-line.
    durations = [FRAME_MS] * (len(frames) - 1) + [FINAL_HOLD_MS]

    buf = io.BytesIO()
    # ``loop=0`` means infinite repeat — the right default for embed
    # contexts (X / Discord) where viewers expect a perpetual loop.
    # ``disposal=2`` clears each frame back to the canvas background
    # before the next one paints, preventing ghosting on bars that
    # shrink between rounds (Pillow's default disposal can leave the
    # previous frame behind).
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
        disposal=2,
    )
    return buf.getvalue()


# ── Cache helpers ──────────────────────────────────────────────────────────


def summary_cache_key(summary: dict) -> str:
    """Stable hash of the inputs that affect the rendered GIF.

    Two summaries with the same hash produce byte-identical GIFs (as
    long as the renderer code itself doesn't change), so disk cache
    hits are safe.
    """
    belief = summary.get("belief") or {}
    rounds = belief.get("rounds") or []
    bullish = belief.get("bullish") or []
    neutral = belief.get("neutral") or []
    bearish = belief.get("bearish") or []

    # Round each percentage to one decimal place — matches the existing
    # share-card cache-key resolution and avoids floating-point noise
    # busting the cache between identical runs.
    def _round_series(series):
        return tuple(round(float(v), 1) for v in series)

    parts = {
        "scenario": (summary.get("scenario") or "").strip(),
        "total_rounds": int(summary.get("total_rounds") or 0),
        "rounds": tuple(int(r) for r in rounds),
        "bullish": _round_series(bullish),
        "neutral": _round_series(neutral),
        "bearish": _round_series(bearish),
    }
    blob = repr(sorted(parts.items())).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
