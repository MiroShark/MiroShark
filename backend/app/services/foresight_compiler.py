"""
Foresight compiler — synthesise a fully-explored decision tree into a
single master Markdown document. This is the layer where the tool finally
takes a tentative position (the 'sensible compromise' section).
"""

import re
from typing import Dict, List

from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger

logger = get_logger("miroshark.foresight_compiler")


SYSTEM_PROMPT = """You are a foresight writer for a balanced civic-tech tool.
You receive a decision tree exploring a contested policy question. The tree
has already been researched and synthesised — each node has a question and
a summary paragraph distilled from web sources.

Your job: weave those node summaries into a single Markdown foresight
document with this structure:

# {Topic}

## TL;DR
Three or four sentences: state the question, the most consequential findings
that emerged across the tree, and the wise call. Avoid loaded language.

## Background
Two paragraphs setting up why this question matters now. Cite the central
question's framing.

## Framings
Three or four paragraphs drawn from upstream nodes. What assumptions does
this question rest on? Whose worldview makes this question urgent? Where
do reasonable people disagree about the framing itself?

## Decision branches
One subsection per downstream branch. Each subsection should:
- Name the branch
- Summarise what the evidence says about likely consequences
- Note where the evidence is uncertain or contested
- Include any sub-consequences that emerged from expansion

## Cross-jurisdictional analogies
Drawn from analogy nodes. Concrete: "In Norway, a 78% petroleum tax has
not driven investors away" — give the country, the policy, the outcome,
and the cultural caveat that makes the analogy more or less transferable.

## Contested claims verdict
For each free / contested-claim node: the claim, what the evidence shows,
a one-line correction or qualification.

## Sensible compromise
Two paragraphs. **This is where you take a tentative position.** Name a
specific compromise that respects the strongest evidence on each side.
Be concrete: "A staged 20% rate with regional carve-outs, sunset clause
in 2030, paired with..." rather than vague "find common ground" platitudes.
End with a one-line "what would tell you this is wrong" — what evidence
would change your mind.

Tone: balanced, evidence-led, plain English. Do NOT cite raw URLs in this
document — the per-node summaries already contain the citations. Do NOT
fabricate findings — if a section's source nodes had no summary, say
"this dimension hasn't been explored yet" rather than invent.

Output ONLY the Markdown document, no preamble, no code fences."""


def _walk_for_compile(tree: Dict) -> Dict:
    """Group tree nodes by type for the compile prompt.

    Returns {central, upstream[], downstream[], analogy[], free[]} where
    each item is {question, summary, user_notes, children_questions}.
    """
    grouped = {
        "central": None,
        "upstream": [],
        "downstream": [],
        "analogy": [],
        "free": [],
    }

    def _node_payload(node):
        return {
            "question": node.get("question") or "",
            "summary": node.get("summary") or "",
            "user_notes": node.get("user_notes") or "",
            "children": [
                {
                    "question": c.get("question") or "",
                    "summary": c.get("summary") or "",
                }
                for c in (node.get("children") or [])
            ],
        }

    grouped["central"] = _node_payload(tree)
    for child in tree.get("children") or []:
        node_type = child.get("type", "free")
        if node_type in grouped and node_type != "central":
            grouped[node_type].append(_node_payload(child))
        else:
            grouped["free"].append(_node_payload(child))

    return grouped


def _build_user_message(seed: Dict, grouped: Dict) -> str:
    parts = [
        f"# Topic\n{seed.get('topic', '')}",
        f"\n# Stated intent\n{seed.get('intent', '')}",
        "\n# Central question",
        f"Q: {grouped['central']['question']}",
    ]
    if grouped["central"].get("summary"):
        parts.append(f"Summary at root: {grouped['central']['summary']}")

    def _section(label: str, nodes: List[Dict]):
        if not nodes:
            return [f"\n# {label}\n(no nodes of this type)"]
        out = [f"\n# {label}"]
        for n in nodes:
            out.append(f"\n## Q: {n['question']}")
            if n.get("user_notes"):
                out.append(f"User notes: {n['user_notes']}")
            if n.get("summary"):
                out.append(f"Summary:\n{n['summary']}")
            else:
                out.append("(not yet synthesised)")
            for c in n.get("children") or []:
                out.append(f"\n  Sub-Q: {c['question']}")
                if c.get("summary"):
                    out.append(f"  Sub-summary:\n{c['summary']}")
        return out

    parts += _section("Upstream framing nodes", grouped["upstream"])
    parts += _section("Downstream branch nodes", grouped["downstream"])
    parts += _section("Analogy nodes", grouped["analogy"])
    parts += _section("Free / contested-claim nodes", grouped["free"])

    return "\n".join(parts)


def _strip_code_fences(text: str) -> str:
    text = re.sub(r"^```(?:[a-zA-Z0-9_-]+)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def compile_foresight(seed: Dict, tree: Dict) -> str:
    """Compile a master foresight markdown document from a synthesised tree."""
    grouped = _walk_for_compile(tree)
    user_msg = _build_user_message(seed, grouped)
    llm = create_llm_client()
    response = llm.chat(messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    return _strip_code_fences(response)
