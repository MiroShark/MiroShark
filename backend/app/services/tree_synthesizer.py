"""Tree synthesiser — turn a node's evidence into a balanced markdown summary."""

import re
from typing import Dict, List

from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger

logger = get_logger("miroshark.tree_synthesizer")


SYSTEM_PROMPT = """You are a balanced research synthesiser for a policy
investigation tool. Given a specific question and a set of source excerpts,
write a 2-3 paragraph synthesis in Markdown that:

1. **States what the evidence says** about the question, in plain language.
2. **Notes where sources agree** — converging facts, shared framings.
3. **Calls out where sources conflict or contradict** — disagreements,
   selective framings, missing perspectives. Name the conflict explicitly.
4. **Cites sources inline** as markdown links: e.g.,
   "estimates $5bn in lost revenue ([Treasury 2026](https://...))".
5. **Does NOT take a position.** This is a synthesis layer, not a
   recommendation layer. Stay descriptive.

Output ONLY the synthesis markdown, no preamble, no code fences. Keep it
tight — 2-3 paragraphs, ~150-300 words."""


def _build_user_message(
    question: str,
    user_notes: str,
    evidence: List[Dict],
) -> str:
    parts = [
        f"Question: {question}",
    ]
    if user_notes and user_notes.strip():
        parts.append(f"User notes: {user_notes.strip()}")

    usable = [
        e for e in (evidence or [])
        if e.get("text") and not e.get("fetch_error")
    ]
    if not usable:
        parts.append(
            "\n(No fetched source content available — synthesise from question "
            "+ user notes alone, and explicitly note that no web sources were "
            "fetched.)"
        )
        return "\n".join(parts)

    parts.append("\nSources:")
    for i, source in enumerate(usable, 1):
        title = source.get("title") or "(untitled)"
        url = source.get("url", "")
        body = (source.get("text") or "").strip()
        excerpt = body[:1500] + ("..." if len(body) > 1500 else "")
        parts += [
            f"[{i}] {title}",
            f"    URL: {url}",
            f"    Excerpt: {excerpt}",
        ]
    return "\n".join(parts)


def _strip_code_fences(text: str) -> str:
    text = re.sub(r"^```(?:[a-zA-Z0-9_-]+)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def synthesise_node(node: Dict) -> str:
    """Generate a markdown synthesis for one node from its evidence + notes."""
    llm = create_llm_client()
    user_msg = _build_user_message(
        question=node.get("question") or "",
        user_notes=node.get("user_notes") or "",
        evidence=node.get("evidence") or [],
    )
    response = llm.chat(messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    return _strip_code_fences(response)
