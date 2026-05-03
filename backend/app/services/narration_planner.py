"""Create short plain-English narration scripts for infographic sequences."""

from __future__ import annotations

from typing import Any

WORDS_PER_SECOND = 2.45


def plan_narration(infographic_plan: dict[str, Any], *, target_seconds: int = 75) -> dict[str, Any]:
    slides = infographic_plan.get("sequence") or []
    # Each slide gets a short, self-contained beat. The final audio is simply
    # these slide beats joined in sequence, so images and narration stay aligned.
    per_slide = max(3, min(6, round(target_seconds / max(1, len(slides)))))
    script_slides = []
    for index, slide in enumerate(slides):
        voiceover = _voiceover_for(slide, index, len(slides))
        duration = max(4, round(len(voiceover.split()) / WORDS_PER_SECOND))
        duration = min(max(duration, per_slide - 1), per_slide + 3)
        script_slides.append({
            "slide_index": index,
            "slide_id": slide.get("slide_id") or str(index),
            "slide_type": slide.get("slide_type"),
            "duration_seconds": duration,
            "caption": _caption_for(slide),
            "voiceover": voiceover,
        })
    full_text = " ".join(s["voiceover"] for s in script_slides)
    return {
        "schema_version": "narration-script/v1",
        "format": "short_video_narration",
        "voice_style": "calm, friendly Australian explainer; clear and non-technical",
        "target_duration_seconds": target_seconds,
        "estimated_duration_seconds": sum(s["duration_seconds"] for s in script_slides),
        "slides": script_slides,
        "full_voiceover": full_text,
        "tts_notes": {
            "provider_candidate": "k2-fsa/OmniVoice on Hugging Face Spaces",
            "language": "English",
            "pace": "slightly slower than normal TikTok narration",
        },
    }


def _voiceover_for(slide: dict[str, Any], index: int, total: int) -> str:
    title = _simple(slide.get("title") or "")
    message = _simple(slide.get("message") or "")
    slide_type = slide.get("slide_type") or ""
    if slide_type == "overview":
        return "Should gas companies pay more tax? Public resource, private profit, public services."
    if slide_type == "tax_context":
        return "First, zoom out. Government money comes from people, companies, GST, and states."
    if slide_type == "spending_context":
        return "Then ask where it goes: welfare, health, schools, defence, infrastructure, and debt."
    if slide_type == "tax_revenue_numbers":
        return "Here are the big tax buckets: workers, companies, GST, duties, then tiny PRRT."
    if slide_type == "spending_numbers":
        return "This is the cash map: welfare, health, schools, defence, and other spending."
    if slide_type.startswith("spending_breakdown_"):
        breakdown_lines = {
            "spending_breakdown_welfare": "Welfare is the biggest bucket: seniors, NDIS, aged care, families and safety nets.",
            "spending_breakdown_health": "Health pays for Medicare, hospitals and medicines, but ageing keeps pushing costs up.",
            "spending_breakdown_education": "Education is smaller, but it buys skills, schools, universities and future productivity.",
            "spending_breakdown_defence": "Defence buys security and capability, but big projects can run late and over budget.",
            "spending_breakdown_other": "Other is not small: states, debt interest, infrastructure and government services sit here.",
        }
        return breakdown_lines.get(slide_type, "This breaks one big spending bucket into simple parts.")
    if slide_type == "spending_timeline":
        return "Since 2006, the total is much bigger, and the mix has shifted."
    if slide_type == "extra_money_sources":
        return "So where does extra money come from? Mostly workers, companies, GST, super, and debt."
    if slide_type == "tax_per_person":
        return "Per person, the tax take is much higher in dollar terms. But averages need context."
    if slide_type == "tax_pressure_reasons":
        return "Why does it rise? Inflation, wages, bracket creep, service costs, debt, and budget repair."
    if slide_type.startswith("spending_period_"):
        period_lines = {
            "spending_period_howard_1996_2007": "Howard and Costello: eleven years, low debt, surplus, core services funded.",
            "spending_period_rudd_2007_2010": "Rudd: the GFC hits, and stimulus spending protects jobs and demand.",
            "spending_period_gillard_2010_2013": "Gillard: disability, schools, health, and household compensation become key spending stories.",
            "spending_period_abbott_2013_2015": "Abbott and Hockey: repair is attempted, but many cuts are blocked.",
            "spending_period_turnbull_2015_2018": "Turnbull and Morrison: NDIS, health, infrastructure, and debt keep growing.",
            "spending_period_morrison_pre_covid_2018_2020": "Morrison before COVID: near repair, but debt is already much higher.",
            "spending_period_morrison_covid_2020_2022": "Morrison during COVID: emergency support helps now, but debt jumps.",
            "spending_period_albanese_2022_2026": "Albanese and Chalmers: surpluses help, but the big bills remain huge.",
        }
        return period_lines.get(slide_type, "Same template: who governed, what they spent, what changed, and what people got.")
    if slide_type.startswith("spending_detail_"):
        detail_lines = {
            "spending_detail_gillard_ndis": "Now zoom into NDIS: big human benefit, real fraud risk, scale matters.",
            "spending_detail_gillard_carbon": "Now zoom into carbon policy: compensation, renewables, backlash, and repeal risk.",
            "spending_detail_morrison_jobkeeper": "Now zoom into JobKeeper: jobs protected, but some money was wasted.",
            "spending_detail_albanese_ndis_aged": "Now zoom into care spending: huge benefits, but cost control matters.",
        }
        return detail_lines.get(slide_type, "Now zoom into one program: benefits, negatives, and scale.")
    if slide_type == "politics_context":
        return "Why avoid it? Jobs claims, investment warnings, campaigns, and key seats."
    if slide_type == "decision_fork":
        return "The fork is simple: tax more, compromise, or leave it alone."
    if slide_type == "viewpoint_compare":
        return "Supporters say share extra profits. Opponents warn rule changes scare investment."
    if slide_type == "evidence_check":
        return "Now check evidence: which claims are numbers, and which are slogans?"
    if slide_type == "country_success_cases":
        return "Where it worked: clear rules, steady design, visible public benefit."
    if slide_type == "country_backfire_cases":
        return "Where it failed: bad timing, confusing design, or fierce campaigns."
    if slide_type == "campaign_influence":
        return "Follow the megaphone: who pays to shape the public story?"
    if slide_type == "debt_power_timeline":
        return "Debt adds context: governments changed, shocks hit, revenue pressure grew."
    if slide_type == "debt_chapter_intro":
        return "Now open the debt chapter: who governed, what happened, and how to repair it."
    if slide_type == "debt_starting_point":
        return "Start before the shocks: low debt, mining-boom revenue, and budget surpluses."
    if slide_type == "debt_who_in_power":
        return "Put governments on the line first. Timing matters before blame."
    if slide_type == "debt_big_shocks":
        return "The big jumps came from shocks: the GFC, COVID, and higher interest costs."
    if slide_type == "debt_where_money_went":
        return "Then show where money went: welfare, health, NDIS, aged care, defence, interest."
    if slide_type == "debt_why_not_paid_down":
        return "More revenue does not pay debt down unless spending and interest leave a real surplus."
    if slide_type == "debt_fault_map":
        return "Fault is not one box: choices, shocks, ageing, tax design, and politics."
    if slide_type == "debt_unwind_options":
        return "To unwind debt, grow faster, spend less, tax more, or mix all three."
    if slide_type == "precedent_timeline":
        return "Other countries show the lesson: design matters more than slogans."
    if slide_type == "stakeholder_map":
        return "Different groups feel different costs: households, companies, workers, investors, buyers."
    if slide_type == "confidence_map":
        return "Separate solid facts from argued claims and thin evidence."
    if slide_type == "recommendation":
        return "The real question: fair public return, without avoidable harm."
    if message:
        return message
    return title or f"Slide {index + 1} of {total}."


def _caption_for(slide: dict[str, Any]) -> str:
    title = _simple(slide.get("title") or "")
    if len(title) <= 54:
        return title
    return title[:51].rsplit(" ", 1)[0] + "…"


def _simple(text: str) -> str:
    replacements = {
        "extra profit": "extra-profit",
        "government": "government",
        "investment": "investment",
    }
    out = " ".join(str(text or "").split())
    for old, new in replacements.items():
        out = out.replace(old, new)
    return out
