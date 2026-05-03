"""Deterministic hybrid infographic cards.

These cards lock the layout in code while preserving a friendly infographic look.
AI-generated icons can later be dropped into the illustration slot, but the text,
boxes, colours, and positions stay deterministic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

W, H = 1024, 1536
BG = (250, 247, 239)
INK = (20, 24, 31)
MUTED = (87, 97, 112)
BLUE = (95, 140, 210)
TEAL = (70, 160, 145)
YELLOW = (245, 190, 80)
ORANGE = (230, 125, 70)
GREEN = (99, 170, 105)
RED = (210, 92, 92)
PANEL = (255, 253, 247)


def render_hybrid_card(slide: dict[str, Any], *, output_dir: Path, filename: str) -> dict[str, Any]:
    template = slide.get("template_id") or "GOV_SPEND_CARD"
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    fonts = _fonts()
    if template == "GOV_SPEND_DETAIL":
        _draw_detail_card(draw, slide, fonts)
    else:
        _draw_gov_card(draw, slide, fonts)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    img.save(path, "PNG")
    return {
        "filename": filename,
        "mime_type": "image/png",
        "bytes": path.stat().st_size,
        "model": "hybrid-fixed-layout",
        "provider": "hybrid",
        "aspect_ratio": "9:16",
        "size": "1024x1536",
        "template_id": template,
    }


def _fonts() -> dict[str, ImageFont.FreeTypeFont]:
    base = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return {
        "title": ImageFont.truetype(bold, 42),
        "subtitle": ImageFont.truetype(bold, 28),
        "body": ImageFont.truetype(base, 29),
        "body_bold": ImageFont.truetype(bold, 30),
        "small": ImageFont.truetype(base, 23),
        "small_bold": ImageFont.truetype(bold, 23),
        "big": ImageFont.truetype(bold, 68),
    }


def _draw_gov_card(draw: ImageDraw.ImageDraw, slide: dict[str, Any], fonts: dict[str, Any]) -> None:
    title = slide.get("title", "Government period")
    labels = slide.get("labels") or []
    facts = [f.get("text", "") for f in slide.get("facts", [])]
    party = labels[0] if labels else _party_from_title(title)
    years = _years_from_title(title)
    duration = labels[1] if len(labels) > 1 else ""
    total = _find(r"total expenses (?:were|are estimated at) \$([0-9.]+b)", facts) or _find(r"Reference year [^:]+: total expenses were \$([0-9.]+b)", facts) or "Total TBD"
    buckets = _bucket_values(facts, labels)
    benefits = _after_prefix(facts, "Benefits shown:") or _after_prefix(facts, "Benefit story:") or "Public services and support"
    negatives = _negative_for(title, facts)
    debt = _after_prefix(facts, "Debt marker:") or _first_contains(facts, "net debt") or "Debt marker: —"

    # Outer framed poster — fixed structure, softer infographic look.
    _rounded(draw, (38, 34, 986, 1500), 38, (255, 252, 244), outline=INK, width=5)
    _rounded(draw, (62, 58, 962, 202), 30, (245, 238, 222), outline=INK, width=4)
    _center_text(draw, title, (86, 78, 938, 132), fonts["title"], fill=INK)
    _center_text(draw, f"{party} · {years} · {duration}", (86, 136, 938, 182), fonts["subtitle"], fill=MUTED)

    # Same framed structure every card: hero total, four bucket frames, benefit/risk frames, debt marker.
    _mini_panel(draw, (62, 232, 962, 392), "TOTAL SPEND", total, fonts, icon="money", accent=YELLOW)

    y=430
    boxes=[(62,y,496,y+176),(528,y,962,y+176),(62,y+206,496,y+382),(528,y+206,962,y+382)]
    data=[("Welfare", buckets.get("Welfare","focus"), "people", YELLOW), ("Health", buckets.get("Health","focus"), "health", GREEN), ("Education", buckets.get("Education","focus"), "book", BLUE), ("Defence/Other", buckets.get("Defence","focus"), "shield", ORANGE)]
    for box,(head,val,icon,col) in zip(boxes,data):
        _mini_panel(draw, box, head, val, fonts, icon=icon, accent=col)

    _story_panel(draw, (62, 850, 962, 1112), "BENEFITS", benefits, fonts, icon="benefit", accent=GREEN, max_lines=3)
    _story_panel(draw, (62, 1142, 962, 1334), "NEGATIVES", negatives, fonts, icon="risk", accent=RED, max_lines=2)
    _story_panel(draw, (62, 1364, 962, 1472), "DEBT MARKER", debt.replace("Debt marker:", ""), fonts, icon="debt", accent=(230,230,235), max_lines=1)

def _draw_detail_card(draw: ImageDraw.ImageDraw, slide: dict[str, Any], fonts: dict[str, Any]) -> None:
    title = slide.get("title", "Spending detail")
    labels = slide.get("labels") or []
    facts = [f.get("text", "") for f in slide.get("facts", [])]
    item = labels[0] if labels else _after_prefix(facts, "Spend item:") or "Spend item"
    benefit = _after_prefix(facts, "Benefit:") or "Public benefit"
    negative = _after_prefix(facts, "Negative:") or "Risk or downside"
    scale = _after_prefix(facts, "Scale check:") or "Compare with total spending and debt"

    _rounded(draw, (54, 44, 970, 184), 34, (86, 103, 180), width=0, fill=True)
    _center_text(draw, title, (70, 62, 954, 126), fonts["title"], fill=(255, 255, 255))
    _center_text(draw, "DEEPER SPENDING ITEM", (70, 124, 954, 166), fonts["subtitle"], fill=(255, 255, 255))

    _section(draw, (64, 224, 960, 438), "SPEND ITEM", fonts, accent=BLUE)
    _center_text(draw, item, (92, 286, 932, 382), fonts["big"], fill=INK)
    _draw_icon(draw, (760, 268, 920, 408), title)

    _section(draw, (64, 482, 960, 764), "BENEFITS", fonts, accent=GREEN)
    _bullets(draw, benefit, (92, 546, 930, 735), fonts["body"], max_lines=4)

    _section(draw, (64, 808, 960, 1090), "NEGATIVES / RISKS", fonts, accent=RED)
    _bullets(draw, negative, (92, 872, 930, 1062), fonts["body"], max_lines=4)

    _section(draw, (64, 1134, 960, 1460), "SCALE CHECK", fonts, accent=YELLOW)
    _bullets(draw, scale, (92, 1200, 930, 1430), fonts["body_bold"], max_lines=5)



def _mini_panel(draw, box, heading, value, fonts, icon="money", accent=YELLOW):
    _rounded(draw, box, 26, PANEL, outline=INK, width=4)
    ix1, iy1 = box[0] + 22, box[1] + 38
    ix2, iy2 = ix1 + 92, iy1 + 92
    _rounded(draw, (ix1-10, iy1-10, ix2+10, iy2+10), 22, (250, 247, 239), outline=accent, width=5)
    _draw_named_icon(draw, (ix1, iy1, ix2, iy2), icon, accent)
    draw.text((box[0] + 140, box[1] + 34), heading, font=fonts["small_bold"], fill=MUTED)
    _wrap_text(draw, value, (box[0] + 140, box[1] + 72, box[2] - 26, box[3] - 18), fonts["body_bold"], fill=INK, max_lines=2)


def _story_panel(draw, box, heading, text, fonts, icon="benefit", accent=GREEN, max_lines=3):
    _rounded(draw, box, 26, PANEL, outline=INK, width=4)
    _rounded(draw, (box[0], box[1], box[2], box[1] + 48), 26, accent, width=0, fill=True)
    draw.text((box[0] + 24, box[1] + 12), heading, font=fonts["small_bold"], fill=INK)
    ix1, iy1 = box[2] - 148, box[1] + 72
    ix2, iy2 = box[2] - 42, iy1 + 106
    _rounded(draw, (ix1-8, iy1-8, ix2+8, iy2+8), 24, (250,247,239), outline=accent, width=5)
    _draw_named_icon(draw, (ix1, iy1, ix2, iy2), icon, accent)
    _bullets(draw, text, (box[0] + 28, box[1] + 68, box[2] - 178, box[3] - 18), fonts["body"], max_lines=max_lines)


def _draw_named_icon(draw, box, icon, color):
    x1,y1,x2,y2=box; cx=(x1+x2)//2; cy=(y1+y2)//2
    if icon in {"money", "debt"}:
        draw.ellipse((cx-36, cy-36, cx+36, cy+36), outline=INK, width=4)
        draw.text((cx-13, cy-28), "$", font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42), fill=INK)
        if icon == "debt": draw.line((x1+8,y2-10,x2-8,y1+10), fill=RED, width=5)
    elif icon == "people":
        for dx in (-22,22):
            draw.ellipse((cx+dx-13,cy-36,cx+dx+13,cy-10), fill=color, outline=INK, width=3)
            draw.line((cx+dx,cy-8,cx+dx,cy+34), fill=INK, width=5)
    elif icon == "health":
        draw.line((cx-35,cy,cx+35,cy), fill=INK, width=8)
        draw.line((cx,cy-35,cx,cy+35), fill=INK, width=8)
    elif icon == "book":
        draw.rectangle((x1+10,y1+20,cx, y2-10), outline=INK, width=4)
        draw.rectangle((cx,y1+20,x2-10, y2-10), outline=INK, width=4)
    elif icon == "shield":
        draw.polygon([(cx,y1+8),(x2-12,y1+25),(x2-25,y2-18),(cx,y2-5),(x1+25,y2-18),(x1+12,y1+25)], outline=INK, fill=(245,238,222))
    elif icon == "benefit":
        draw.arc((x1+10,y1+22,x2-10,y2+8), 200, 340, fill=INK, width=6)
        draw.ellipse((cx-20,y1+8,cx+20,y1+48), fill=color, outline=INK, width=3)
    elif icon == "risk":
        draw.polygon([(cx,y1+8),(x2-8,y2-8),(x1+8,y2-8)], outline=INK, width=5)
        draw.line((cx,cy-16,cx,cy+22), fill=INK, width=6)
        draw.ellipse((cx-4,cy+34,cx+4,cy+42), fill=INK)
    else:
        draw.ellipse(box, outline=INK, width=4)

def _section(draw, box, title, fonts, accent=YELLOW):
    _rounded(draw, box, 28, PANEL, outline=INK, width=4)
    _rounded(draw, (box[0], box[1], box[2], box[1] + 54), 28, accent, width=0, fill=True)
    draw.text((box[0] + 24, box[1] + 13), title, font=fonts["small_bold"], fill=INK)


def _rounded(draw, box, radius, color, outline=None, width=1, fill=False):
    if fill:
        draw.rounded_rectangle(box, radius=radius, fill=color)
    else:
        draw.rounded_rectangle(box, radius=radius, fill=color, outline=outline or color, width=width)


def _center_text(draw, text, box, font, fill=INK):
    text = str(text)
    # If too long, draw wrapped centered.
    lines = _wrap_lines(draw, text, font, box[2] - box[0])[:2]
    total_h = len(lines) * (font.size + 8)
    y = box[1] + ((box[3] - box[1]) - total_h) / 2
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        x = box[0] + ((box[2] - box[0]) - (bb[2] - bb[0])) / 2
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + 8


def _bullets(draw, text, box, font, max_lines=4):
    chunks = re.split(r";|, and | and ", text)
    lines=[]
    for c in chunks:
        c=c.strip(" .")
        if c: lines.extend(_wrap_lines(draw, "• "+c, font, box[2]-box[0]))
    y=box[1]
    for line in lines[:max_lines]:
        draw.text((box[0], y), line, font=font, fill=INK)
        y += font.size + 12


def _wrap_text(draw, text, box, font, fill=INK, max_lines=3):
    y=box[1]
    for line in _wrap_lines(draw, text, font, box[2]-box[0])[:max_lines]:
        draw.text((box[0], y), line, font=font, fill=fill)
        y += font.size + 8


def _wrap_lines(draw, text, font, max_width):
    words=str(text).split()
    lines=[]; cur=""
    for w in words:
        test=(cur+" "+w).strip()
        bb=draw.textbbox((0,0), test, font=font)
        if bb[2]-bb[0] <= max_width or not cur:
            cur=test
        else:
            lines.append(cur); cur=w
    if cur: lines.append(cur)
    return lines


def _draw_icon(draw, box, title):
    x1,y1,x2,y2=box; cx=(x1+x2)//2; cy=(y1+y2)//2
    draw.ellipse((x1,y1,x2,y2), fill=(240,248,245), outline=INK, width=4)
    t=title.lower()
    if "covid" in t or "jobkeeper" in t:
        draw.ellipse((cx-38,cy-38,cx+38,cy+38), outline=RED, width=6)
        for a in range(0,360,45):
            import math
            dx=int(math.cos(math.radians(a))*58); dy=int(math.sin(math.radians(a))*58)
            draw.line((cx,cy,cx+dx,cy+dy), fill=RED, width=4)
    elif "carbon" in t or "renew" in t:
        draw.polygon([(cx,cy-60),(cx-55,cy+40),(cx+55,cy+40)], outline=GREEN, fill=(226,246,223))
        draw.line((cx-25,cy+5,cx+35,cy-25), fill=GREEN, width=6)
    elif "ndis" in t or "aged" in t:
        draw.arc((cx-45,cy-45,cx+45,cy+45), 200, 520, fill=BLUE, width=8)
        draw.ellipse((cx-20,cy-55,cx+20,cy-15), fill=BLUE)
    else:
        draw.rectangle((cx-45,cy-35,cx+45,cy+45), outline=INK, width=5)
        draw.text((cx-18, cy-28), "$", fill=INK, width=2)


def _party_from_title(title):
    return "Labor" if any(x in title for x in ("Rudd", "Gillard", "Albanese")) else "Coalition"

def _years_from_title(title):
    m=re.search(r"(\d{4})[–-](\d{4})", title)
    return m.group(0) if m else ""

def _find(pattern, facts):
    for f in facts:
        m=re.search(pattern, f, flags=re.I)
        if m: return "$"+m.group(1)
    return ""

def _first_label_with(labels, needle):
    return next((l for l in labels if needle in l), "")

def _first_contains(facts, needle):
    return next((f for f in facts if needle.lower() in f.lower()), "")

def _after_prefix(facts, prefix):
    for f in facts:
        if f.startswith(prefix): return f[len(prefix):].strip()
    return ""

def _bucket_values(facts, labels):
    joined="; ".join(facts+labels)
    out={}
    for key in ["welfare", "health", "education", "defence"]:
        m=re.search(key+r"\s+\$?([0-9.]+b)", joined, flags=re.I)
        if m: out[key.title()]="$"+m.group(1)
    # Detail/fuzzy fallbacks keep the layout stable even when exact buckets are not known yet.
    out.setdefault("Welfare", "focus")
    out.setdefault("Health", "focus")
    out.setdefault("Education", "focus")
    out.setdefault("Defence", "focus")
    return out

def _negative_for(title, facts):
    explicit = _after_prefix(facts, "Negative:") or _after_prefix(facts, "Cost story:")
    if explicit: return explicit
    t=title.lower()
    if "howard" in t: return "Future obligations remained; boom revenue made choices easier"
    if "rudd" in t: return "Deficits began; some stimulus waste and program failures"
    if "gillard" in t: return "Cost growth, backlash, and design fights"
    if "abbott" in t: return "Cuts blocked; repair politics hurt trust"
    if "turnbull" in t: return "Structural gap persisted; debt kept rising"
    if "morrison" in t and "covid" not in t: return "Debt already high before the pandemic"
    if "covid" in t: return "Overpayments and large permanent debt step-up"
    if "albanese" in t: return "Cost growth, fraud risk, and high interest bill"
    return "Trade-offs and long-term costs"
