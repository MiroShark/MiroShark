"""
Node scorer — LLM-driven multi-dimensional scoring for decision tree nodes.

Returns JSON with confidence/contestedness/salience and a 1-line
stance_summary. Stored on node.scores by the API layer.
"""

from typing import Dict

from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger

logger = get_logger("miroshark.node_scorer")


VALID_CONFIDENCE = ("low", "medium", "high")
VALID_CONTESTEDNESS = ("settled", "contested", "disputed")
VALID_SALIENCE = ("niche", "moderate", "high")

EMPTY_SCORES = {
    "confidence": "low",
    "contestedness": "contested",
    "salience": "moderate",
    "stance_summary": "",
}

SYSTEM_PROMPT = """You are an evidence-evaluation assistant for a policy
decision tree. Given a question, an existing synthesis, and source excerpts,
score the node on three dimensions and write one summary sentence.

Return a single JSON object with EXACTLY these keys:

{
  "confidence": "low | medium | high",
  "contestedness": "settled | contested | disputed",
  "salience": "niche | moderate | high",
  "stance_summary": "one sentence in plain English summarising where the evidence points"
}

Definitions:
- confidence: how strongly the evidence supports a clear answer to this node's question. high = several substantive sources converge; low = thin or absent evidence.
- contestedness: how much sources disagree. settled = consensus or only minor variation; contested = real disagreement among credible sources; disputed = active partisan / values-driven disagreement.
- salience: how prominent this question is in the fetched discourse. high = the central thread of the topic; niche = a specialist concern.
- stance_summary: a single declarative sentence — what does the evidence say? Avoid loaded language. Don't take a position; describe the position evidence points to.

Output ONLY the JSON object."""


def _build_user_message(node: Dict) -> str:
    parts = [
        f"Question: {node.get('question') or ''}",
    ]
    summary = (node.get("summary") or "").strip()
    if summary:
        parts.append(f"\nExisting synthesis:\n{summary}")

    usable = [
        e for e in (node.get("evidence") or [])
        if e.get("text") and not e.get("fetch_error")
    ]
    if usable:
        parts.append(f"\nFetched sources ({len(usable)} usable):")
        for i, e in enumerate(usable, 1):
            title = e.get("title") or "(untitled)"
            url = e.get("url", "")
            body = (e.get("text") or "").strip()
            excerpt = body[:600] + ("..." if len(body) > 600 else "")
            parts += [
                f"[{i}] {title} — {url}",
                f"    Excerpt: {excerpt}",
            ]
    else:
        parts.append("\n(No fetched sources — score on question + summary alone.)")
    return "\n".join(parts)


def _normalise_scores(raw: Dict) -> Dict:
    """Coerce LLM output into the strict shape; fall back to empties on bad data."""
    scores = dict(EMPTY_SCORES)
    if not isinstance(raw, dict):
        return scores

    conf = str(raw.get("confidence", "")).strip().lower()
    if conf in VALID_CONFIDENCE:
        scores["confidence"] = conf

    cont = str(raw.get("contestedness", "")).strip().lower()
    if cont in VALID_CONTESTEDNESS:
        scores["contestedness"] = cont

    sal = str(raw.get("salience", "")).strip().lower()
    if sal in VALID_SALIENCE:
        scores["salience"] = sal

    summary = raw.get("stance_summary", "")
    if isinstance(summary, str):
        scores["stance_summary"] = summary.strip()

    return scores


def score_node(node: Dict) -> Dict:
    """Compute scores for one node. Returns dict matching EMPTY_SCORES shape."""
    llm = create_llm_client()
    user_msg = _build_user_message(node)
    try:
        envelope = llm.chat_json(messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("node_scorer: malformed LLM response (%s)", exc)
        return dict(EMPTY_SCORES)

    return _normalise_scores(envelope)
