"""
Brief writer: turn a complete seed + chat history into a structured deliverable.

Called by /api/seed-chat/launch. Uses the same LLM provider configured for the
project (typically claude-code via the Max-plan CLI).
"""

import re
from typing import Dict, List, Optional

from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger

logger = get_logger("miroshark.brief_writer")

OUTPUT_FORMAT_GUIDANCE = {
    "pros_cons": (
        "Produce a structured Pros/Cons brief in Markdown. Include sections: "
        "Background (2-4 sentences), Pros (each as a heading + 1-3 sentence rationale, "
        "labelled with the supporting stakeholder), Cons (same shape, labelled with the "
        "opposing stakeholder), Contested claims (one bullet per claim with a brief "
        "evidence-or-doubt note), and a final 'Bottom line' paragraph that names trade-offs "
        "without taking a side."
    ),
    "decision_memo": (
        "Produce a decision memo in Markdown. Include: Question, Options (one per "
        "decision branch with rationale and risks), Recommendation, and Open questions."
    ),
    "executive_summary": (
        "Produce a 1-page executive summary in Markdown. Lead with a 3-sentence TL;DR, "
        "then 4-6 key findings as bullets, then a 'What to watch' section."
    ),
    "full_report": (
        "Produce a full research report in Markdown with: Executive summary, Background, "
        "Stakeholder analysis (one subsection per stakeholder), Decision branches "
        "(one subsection each), Contested claims, and Conclusions."
    ),
    "media_landscape": (
        "Produce a Media Landscape report in Markdown. The structure is "
        "claims-first — the document is organised around contested claims, "
        "not around stakeholders or pros/cons.\n\n"
        "Required sections:\n\n"
        "## Background\n"
        "Two to four sentences setting up the topic and why the messaging matters.\n\n"
        "## Claims map\n"
        "One subsection per contested claim, in this exact format:\n\n"
        "### Claim: \"<verbatim claim text>\"\n"
        "**Pushed by:** <comma-separated stakeholders or media outlets that "
        "advance this claim>.\n\n"
        "**Evidence assessment:** Mark with one of these prefixes:\n"
        "- ✓ Supported — backed by reliable evidence in the sources\n"
        "- ⚠ Partial — has a kernel of truth but is misleading or selective\n"
        "- ✗ Misleading — contradicted by the sources, or unsupported\n"
        "- ? Disputed — sources disagree; mention the disagreement\n\n"
        "Then 2-4 sentences citing the evidence (use markdown links to "
        "sources when available).\n\n"
        "**Counter-framing:** A short, plain-language reframing that a "
        "campaigner could use to push back if challenged. One or two "
        "sentences. Concrete, not abstract.\n\n"
        "## Stakeholder cheat-sheet\n"
        "A compact list — one line per stakeholder — naming the talking "
        "points they push and the framing they prefer. This is a quick "
        "reference, not a re-analysis.\n\n"
        "## Where to dig deeper\n"
        "Three to five questions whose answers would sharpen the brief — "
        "things the user could research next or specific claims that need "
        "more evidence."
    ),
}

DEFAULT_GUIDANCE = (
    "Produce a clear, well-organised Markdown brief that makes the trade-offs visible."
)


def _build_writer_prompt(seed: Dict, research_sources: Optional[List[Dict]] = None) -> str:
    fmt = seed.get("output_format") or "full_report"
    guidance = OUTPUT_FORMAT_GUIDANCE.get(fmt, DEFAULT_GUIDANCE)
    stakeholder_lines = "\n".join(
        f"- {s.get('name', '?')} ({s.get('role', '?')}) — stance: {s.get('stance', 'unknown')}"
        for s in seed.get("stakeholders", [])
    )
    branch_lines = "\n".join(
        f"- {b.get('label', '?')}: {b.get('description', '')}"
        for b in seed.get("decision_branches", [])
    )
    claim_lines = "\n".join(f"- {c}" for c in seed.get("contested_claims", []))

    sections = [
        f"You are MiroShark's research-brief writer.",
        "",
        f"Topic: {seed.get('topic', '')}",
        f"User intent: {seed.get('intent', '')}",
        f"Output format: {fmt}",
        "",
        "Stakeholders:",
        stakeholder_lines or "- (none specified)",
    ]
    if branch_lines:
        sections += ["", "Decision branches:", branch_lines]
    if claim_lines:
        sections += ["", "Contested claims to investigate:", claim_lines]

    usable_sources = [
        s for s in (research_sources or [])
        if s.get("text") and not s.get("fetch_error")
    ]
    if usable_sources:
        sections += ["", "Web research sources (cite these inline using markdown links):"]
        for i, source in enumerate(usable_sources, 1):
            title = source.get("title") or "(untitled)"
            url = source.get("url", "")
            body = (source.get("text") or "").strip()
            # Trim each source body to keep total prompt size reasonable
            body_excerpt = body[:1500] + ("..." if len(body) > 1500 else "")
            sections += [
                f"[{i}] {title}",
                f"    URL: {url}",
                f"    Excerpt: {body_excerpt}",
            ]
        sections += [
            "",
            "Citation guidance: when stating a claim, cite the supporting source as a "
            "markdown link, e.g., 'estimates $5 bn ([Treasury 2026](https://...))'. "
            "Use only the sources listed above; do not invent URLs. If a claim has no "
            "supporting source, state it without a citation rather than fabricating one.",
        ]

    sections += [
        "",
        "Instructions:",
        guidance,
        "",
        "Respect the conversation history that follows — incorporate the user's framing "
        "and any specifics they've already discussed. Output the brief as Markdown only, "
        "no preamble, no code fences.",
    ]
    return "\n".join(sections)


def _strip_code_fences(text: str) -> str:
    text = re.sub(r"^```(?:[a-zA-Z0-9_-]+)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def write_brief(
    seed: Dict,
    history: List[Dict],
    research_sources: Optional[List[Dict]] = None,
) -> str:
    """
    Generate a brief from the seed + chat history.

    If research_sources is provided, fetched sources with non-empty text are
    embedded in the system prompt with citation guidance.

    Returns the brief as Markdown text (no code fences).
    """
    llm = create_llm_client()
    system_prompt = _build_writer_prompt(seed, research_sources=research_sources)
    full_messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": "Now produce the brief as instructed."},
    ]
    response = llm.chat(messages=full_messages)
    return _strip_code_fences(response)
