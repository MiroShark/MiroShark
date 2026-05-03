"""
Decision-tree helpers for the seed-chat workflow.

The tree is stored on session.tree as a single root node. Each node has
{id, type, question, user_notes, evidence, children}. Pure helpers here;
network/LLM calls live in the API layer.
"""

import uuid
from typing import Dict, List, Optional

from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger

logger = get_logger("miroshark.decision_tree")

NODE_TYPES = ("central", "upstream", "downstream", "analogy", "free")

BIG_PICTURE_SEEDS = [
    ("Where does government tax money come from?", "upstream"),
    ("How do federal, state, and local taxes fit together?", "upstream"),
    ("How much does government spend on welfare, health, defence, and services?", "downstream"),
    ("How much extra money could this policy realistically raise?", "downstream"),
    ("Who pays now, and who would pay more under this idea?", "downstream"),
    ("Why might the current government avoid this tax?", "free"),
    ("What political risks would leaders face if they supported it?", "free"),
    ("What simple story would help a non-expert understand the trade-off?", "free"),
]

STORY_DEPTH_SEEDS = [
    ("Which countries tried higher resource or windfall taxes, and where did it work?", "analogy"),
    ("Where did resource or windfall tax reforms backfire, and why?", "analogy"),
    ("What happened in Australia’s RSPT and MRRT fights?", "analogy"),
    ("How have gas and mining companies influenced public debate or campaigns?", "free"),
    ("What misinformation or misleading claims commonly appear in resource-tax debates?", "free"),
    ("How has Australian government debt changed since 2006, and who was in power?", "upstream"),
    ("How do gas royalties, PRRT, company tax, and export profits fit together?", "upstream"),
    ("What would a fair compromise design look like?", "downstream"),
]


EXPAND_PROMPTS = {
    "central": (
        "You are helping someone think through a contested policy question.\n"
        "Propose 3-5 sub-questions that ASKING themselves would deepen "
        "understanding of this central question. Mix upstream framing "
        "questions, downstream consequence questions, and analogous-policy "
        "questions. Each sub-question should be standalone and answerable.\n"
    ),
    "upstream": (
        "Propose 3-5 deeper UPSTREAM framing questions — the assumptions, "
        "principles, or political-philosophy questions that legitimise asking "
        "the parent question. Each should be standalone and answerable.\n"
    ),
    "downstream": (
        "Propose 3-5 specific consequence questions that follow if the "
        "parent question's scenario plays out. Cover economic, social, "
        "political, and second-order effects. Each should be answerable "
        "with evidence.\n"
    ),
    "analogy": (
        "Propose 3-5 cross-cultural / cross-jurisdictional comparison "
        "questions: where else has something like the parent question been "
        "tried, with what cultural/political context, and what happened? "
        "Each should name a specific country or precedent.\n"
    ),
    "free": (
        "Propose 3-5 follow-up questions that drill deeper into the parent "
        "question. Mix factual, analytical, and 'what if' questions.\n"
    ),
}


def _new_node(
    question: str,
    node_type: str,
    user_notes: str = "",
) -> Dict:
    return {
        "id": str(uuid.uuid4()),
        "type": node_type,
        "question": question,
        "user_notes": user_notes,
        "evidence": [],
        "children": [],
    }


def initialise_tree(seed_state: Dict) -> Dict:
    """Build the initial tree from a seed.

    The root is the central question (= seed.topic). It gets seeded children:
    one upstream placeholder, one analogy placeholder, one downstream node per
    decision_branches entry, and a free child per contested_claim.
    """
    topic = (seed_state.get("topic") or "").strip() or "Untitled question"
    intent = (seed_state.get("intent") or "").strip()

    root = _new_node(
        question=topic,
        node_type="central",
        user_notes=intent,
    )

    upstream = _new_node(
        question="What broader framing makes this question worth asking?",
        node_type="upstream",
    )
    root["children"].append(upstream)

    for branch in seed_state.get("decision_branches") or []:
        label = (branch.get("label") or "").strip()
        description = (branch.get("description") or "").strip()
        question = f"{label}: {description}" if label else description
        if not question:
            continue
        node = _new_node(question=question, node_type="downstream")
        root["children"].append(node)

    analogy = _new_node(
        question="Where has something like this been tried elsewhere, and what happened?",
        node_type="analogy",
    )
    root["children"].append(analogy)

    existing_questions = {c.get("question") for c in root["children"]}
    for question, node_type in BIG_PICTURE_SEEDS:
        if question not in existing_questions:
            root["children"].append(_new_node(question=question, node_type=node_type))
            existing_questions.add(question)

    for claim in seed_state.get("contested_claims") or []:
        text = (claim or "").strip()
        if not text:
            continue
        node = _new_node(
            question=f'Is this claim accurate: "{text}"?',
            node_type="free",
        )
        root["children"].append(node)

    return root



def add_big_picture_nodes(tree: Dict) -> int:
    """Append missing big-picture context nodes to an existing tree.

    Returns the number of nodes added. This lets older sessions gain the
    broader tax/spending/political-story scaffold without reinitialising and
    losing existing research.
    """
    existing_questions = {c.get("question") for c in tree.get("children") or []}
    added = 0
    for question, node_type in BIG_PICTURE_SEEDS:
        if question not in existing_questions:
            tree.setdefault("children", []).append(_new_node(question=question, node_type=node_type))
            existing_questions.add(question)
            added += 1
    return added


def add_story_depth_nodes(tree: Dict) -> int:
    """Append missing deeper story nodes for richer research-to-media arcs."""
    existing_questions = {c.get("question") for c in tree.get("children") or []}
    added = 0
    for question, node_type in STORY_DEPTH_SEEDS:
        if question not in existing_questions:
            tree.setdefault("children", []).append(_new_node(question=question, node_type=node_type))
            existing_questions.add(question)
            added += 1
    return added

def find_node(tree: Dict, node_id: str) -> Optional[Dict]:
    """Locate a node by id (depth-first). Returns the node dict or None."""
    if tree.get("id") == node_id:
        return tree
    for child in tree.get("children") or []:
        found = find_node(child, node_id)
        if found is not None:
            return found
    return None


def update_node(tree: Dict, node_id: str, fields: Dict) -> bool:
    """Patch question / user_notes on a node. Returns True if found."""
    node = find_node(tree, node_id)
    if node is None:
        return False
    if "question" in fields and isinstance(fields["question"], str):
        node["question"] = fields["question"]
    if "user_notes" in fields and isinstance(fields["user_notes"], str):
        node["user_notes"] = fields["user_notes"]
    return True


def attach_evidence(tree: Dict, node_id: str, sources: List[Dict]) -> bool:
    """Append sources to node.evidence, deduping by URL. Returns True if found."""
    node = find_node(tree, node_id)
    if node is None:
        return False
    existing_urls = {s.get("url") for s in (node.get("evidence") or [])}
    for source in sources:
        if source.get("url") and source["url"] not in existing_urls:
            existing_urls.add(source["url"])
            node["evidence"].append(source)
    return True


def set_summary(tree: Dict, node_id: str, summary: str) -> bool:
    """Set node.summary on the matching node. Returns True if found."""
    node = find_node(tree, node_id)
    if node is None:
        return False
    node["summary"] = summary
    return True


def set_scores(tree: Dict, node_id: str, scores: Dict) -> bool:
    """Set node.scores. Returns True if found."""
    node = find_node(tree, node_id)
    if node is None:
        return False
    node["scores"] = scores
    return True


def attach_children(tree: Dict, parent_id: str, children: List[Dict]) -> bool:
    """Append child nodes to a parent. Returns True if parent found."""
    node = find_node(tree, parent_id)
    if node is None:
        return False
    node["children"].extend(children)
    return True


def propose_subquestions(
    parent: Dict,
    seed_state: Dict,
) -> List[Dict]:
    """Ask Claude to propose 3-5 sub-questions appropriate to the parent's type.

    Returns a list of new node dicts. Children inherit a logical type:
    - upstream parent -> upstream children
    - downstream parent -> downstream children
    - analogy parent -> analogy children
    - central / free parent -> mixed types based on Claude's output (default 'free')
    """
    node_type = parent.get("type", "free")
    expansion_prompt = EXPAND_PROMPTS.get(node_type, EXPAND_PROMPTS["free"])

    system = (
        f"{expansion_prompt}\n\n"
        f"Return a single JSON object with one key 'questions' whose value is "
        f"a list of strings (one question per element). No prose, no commentary."
    )
    user = (
        f"Parent question: {parent.get('question', '')}\n"
        f"User notes on the parent: {parent.get('user_notes', '') or '(none)'}\n"
        f"Topic context: {seed_state.get('topic', '')}\n"
        f"Intent: {seed_state.get('intent', '')}\n"
    )

    llm = create_llm_client()
    try:
        envelope = llm.chat_json(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("decision_tree: malformed LLM response (%s)", exc)
        return []

    raw_questions = envelope.get("questions") or []
    if not isinstance(raw_questions, list):
        return []

    children = []
    child_type = node_type if node_type in ("upstream", "downstream", "analogy") else "free"
    limit = 8 if node_type == "central" else 5
    for q in raw_questions[:limit]:
        text = str(q).strip() if q is not None else ""
        if not text:
            continue
        children.append(_new_node(question=text, node_type=child_type))
    return children
