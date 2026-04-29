"""
Ad-script distillation: turn a seed + brief + sources into balanced
short-form video ad scripts.

The prompt is deliberately tuned to call out misleading framing on both
sides (not just one party's position). Output is Markdown with three
scripts of varying length and angle.
"""

import re
from typing import Dict, List, Optional

from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger

logger = get_logger("miroshark.ad_script_writer")


SYSTEM_PROMPT = """You are a fair-minded video ad scriptwriter for an advocacy
organisation that prizes accuracy over partisanship. Your job is to take a
research brief on a contested public-policy topic and produce short video ad
scripts designed for the general public — not for activists, not for experts.

The audience is a regular voter who has heard incomplete arguments from both
sides. Your scripts should:

1. **Cite specific facts and statistics** from the brief and sources, not vague
   talking points.
2. **Call out misleading framing on both sides** — not just the one you
   disagree with. If a stakeholder is exaggerating, name it. If an opponent is
   selectively quoting, name that too.
3. **Avoid loaded language** — no "evil corporations", no "out-of-touch
   activists". Treat the audience as adults capable of weighing evidence.
4. **Push toward a sensible compromise**, not toward a partisan victory. The
   CTA should be "look at the actual numbers" or "ask your representative
   these specific questions", not "support side X".
5. **Include visual cues** in square brackets so a video producer knows what
   to show: `[graph: corporate tax rates 2010-2026]`, `[footage: mining town
   main street]`, `[on-screen text: "$X bn"]`. Be concrete.
6. **Time the script** with second markers `[0:00]`, `[0:05]`, etc.

Produce exactly THREE scripts, in this order:

## Script 1 — 30-second version (the punchy one)
A tight 30-second script with a strong hook, 2-3 fact callouts, and a clear CTA.

## Script 2 — 60-second version (the explanatory one)
A 60-second script that walks through the issue more carefully, with 4-6 fact
callouts including the strongest piece of evidence on each side.

## Script 3 — 60-second "what both sides aren't telling you" version
A 60-second script focused specifically on misleading claims being pushed in
the public debate. For each claim, give the misleading framing, the actual
evidence, and a one-line correction.

Use Markdown. Each script should look like a screenplay: lines starting with
`NARRATOR:` or `TEXT ON SCREEN:` or `VISUAL:` and timed markers.

End the document with a `## Citations` section listing each source URL used.

Output ONLY the markdown. No preamble, no code fences."""


def _build_user_message(seed: Dict, brief: str, sources: Optional[List[Dict]]) -> str:
    parts = [
        f"Topic: {seed.get('topic', '')}",
        f"User's stated intent: {seed.get('intent', '')}",
        "",
        "## Stakeholders",
    ]
    for s in seed.get("stakeholders", []) or []:
        parts.append(
            f"- **{s.get('name', '?')}** ({s.get('role', '?')}) — stance: {s.get('stance', 'unknown')}"
        )

    if seed.get("decision_branches"):
        parts += ["", "## Decision branches under debate"]
        for b in seed["decision_branches"]:
            parts.append(f"- **{b.get('label', '?')}**: {b.get('description', '')}")

    if seed.get("contested_claims"):
        parts += ["", "## Contested claims (each must be addressed somewhere across the three scripts)"]
        for c in seed["contested_claims"]:
            parts.append(f"- {c}")

    parts += ["", "## Brief", brief or "(no brief — write from the seed alone)"]

    usable_sources = [
        s for s in (sources or [])
        if s.get("text") and not s.get("fetch_error")
    ]
    if usable_sources:
        parts += ["", "## Source materials (cite by URL in the citations block)"]
        for i, source in enumerate(usable_sources, 1):
            title = source.get("title") or "(untitled)"
            url = source.get("url", "")
            body = (source.get("text") or "").strip()
            body_excerpt = body[:1200] + ("..." if len(body) > 1200 else "")
            parts += [
                f"[{i}] {title}",
                f"    URL: {url}",
                f"    Excerpt: {body_excerpt}",
            ]

    return "\n".join(parts)


def _strip_code_fences(text: str) -> str:
    text = re.sub(r"^```(?:[a-zA-Z0-9_-]+)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def write_ad_scripts(
    seed: Dict,
    brief: str,
    sources: Optional[List[Dict]] = None,
) -> str:
    """
    Generate three balanced ad scripts (30s, 60s, 60s).

    Returns markdown with three scripts in the structure described in the
    system prompt.
    """
    llm = create_llm_client()
    user_message = _build_user_message(seed, brief, sources)
    full_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    response = llm.chat(messages=full_messages)
    return _strip_code_fences(response)
