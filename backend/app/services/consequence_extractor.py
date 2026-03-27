"""
Consequence Extractor
3-stage pipeline to extract causal consequence trees from simulation action logs.

Stage 1: Build deterministic event graph from action logs (reply-to, reactions)
Stage 2: LLM scores causal significance of events
Stage 3: Construct consequence tree with unintended consequences flagged
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger
from .simulation_runner import SimulationRunner, AgentAction

logger = get_logger("miroshark.consequence_extractor")

CONTENT_ACTION_TYPES = {"CREATE_POST", "CREATE_COMMENT", "QUOTE_POST", "REPOST"}
NOISE_ACTION_TYPES = {"DO_NOTHING", "REFRESH", "TREND", "SEARCH_POSTS", "SEARCH_USER", "MUTE"}

CAUSAL_SCORING_PROMPT = """You are analyzing a social media simulation to extract causal chains.

The simulation was triggered by this decision scenario:
"{decision_text}"

Below are the key events from the simulation (posts, comments, reposts).
For each event, determine:
1. Is it a DIRECT consequence of the injected decision? (true/false)
2. Which earlier event(s) caused it? (list event IDs, empty if it's a root reaction)
3. What type of consequence is it? One of:
   - "direct_reaction" — responds directly to the decision
   - "cascade" — responds to another agent's reaction
   - "counter_reaction" — opposes or pushes back on earlier events
   - "escalation" — amplifies or intensifies earlier events
   - "unintended" — an outcome nobody would have predicted from the decision
   - "reversal" — opinion or stance reversal from earlier position
4. Importance score (0-10): how significant is this event in the chain?

Return a JSON array of objects:
[
  {{
    "event_id": "evt_001",
    "caused_by": [],
    "is_direct": true,
    "consequence_type": "direct_reaction",
    "importance": 8,
    "summary": "Brief description of what happened and why it matters"
  }}
]

Only include events scoring 5 or higher in importance.

Events:
{events_text}"""


@dataclass
class ConsequenceNode:
    event_id: str
    round_num: int
    agent_name: str
    action_type: str
    content: str
    consequence_type: str = "direct_reaction"
    importance: float = 5.0
    is_unintended: bool = False
    summary: str = ""
    children: List["ConsequenceNode"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "round_num": self.round_num,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "content": self.content[:200],
            "consequence_type": self.consequence_type,
            "importance": self.importance,
            "is_unintended": self.is_unintended,
            "summary": self.summary,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class ConsequenceTree:
    decision_text: str
    root: Optional[ConsequenceNode] = None
    total_nodes: int = 0
    unintended_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_text": self.decision_text,
            "root": self.root.to_dict() if self.root else None,
            "total_nodes": self.total_nodes,
            "unintended_count": self.unintended_count,
        }


def _stage1_filter_actions(actions: List[AgentAction]) -> List[Dict]:
    """Stage 1: Filter to content-producing actions, assign event IDs."""
    events = []
    for idx, action in enumerate(actions):
        if action.action_type in NOISE_ACTION_TYPES:
            continue
        if action.action_type not in CONTENT_ACTION_TYPES:
            if action.action_type not in {"LIKE_POST", "DISLIKE_POST", "FOLLOW"}:
                continue

        content = ""
        args = action.action_args or {}
        if "post_content" in args:
            content = args["post_content"]
        elif "content" in args:
            content = args["content"]
        elif action.result:
            content = action.result

        events.append({
            "event_id": f"evt_{idx:04d}",
            "round_num": action.round_num,
            "agent_name": action.agent_name,
            "agent_id": action.agent_id,
            "action_type": action.action_type,
            "content": str(content)[:300],
            "platform": action.platform,
        })

    logger.info(f"Stage 1: {len(events)} content events from {len(actions)} total actions")
    return events


def _stage2_score_causality(
    decision_text: str, events: List[Dict], batch_size: int = 25
) -> List[Dict]:
    """Stage 2: Use LLM to score causal significance of events."""
    if not events:
        return []

    scored_events = []
    client = create_llm_client()

    for batch_start in range(0, len(events), batch_size):
        batch = events[batch_start : batch_start + batch_size]
        events_text = "\n".join(
            f"[{e['event_id']}] Round {e['round_num']} | {e['agent_name']} | "
            f"{e['action_type']} | {e['content'][:150]}"
            for e in batch
        )

        try:
            prompt = CAUSAL_SCORING_PROMPT.format(
                decision_text=decision_text, events_text=events_text
            )
            result = client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4096,
            )
            if isinstance(result, list):
                scored_events.extend(result)
        except Exception as llm_err:
            logger.warning(f"LLM scoring failed for batch at {batch_start}: {llm_err}")

    logger.info(f"Stage 2: {len(scored_events)} events scored by LLM")
    return scored_events


def _stage3_build_tree(
    decision_text: str,
    events: List[Dict],
    scored: List[Dict],
) -> ConsequenceTree:
    """Stage 3: Build consequence tree from scored events."""
    tree = ConsequenceTree(decision_text=decision_text)

    event_map = {e["event_id"]: e for e in events}
    score_map = {s["event_id"]: s for s in scored if isinstance(s, dict) and "event_id" in s}

    nodes = {}
    for scored_event in scored:
        if not isinstance(scored_event, dict):
            continue
        eid = scored_event.get("event_id", "")
        if eid not in event_map:
            continue

        event = event_map[eid]
        ctype = scored_event.get("consequence_type", "direct_reaction")

        node = ConsequenceNode(
            event_id=eid,
            round_num=event.get("round_num", 0),
            agent_name=event.get("agent_name", ""),
            action_type=event.get("action_type", ""),
            content=event.get("content", ""),
            consequence_type=ctype,
            importance=scored_event.get("importance", 5),
            is_unintended=ctype in ("unintended", "reversal"),
            summary=scored_event.get("summary", ""),
        )
        nodes[eid] = node

    root = ConsequenceNode(
        event_id="root",
        round_num=0,
        agent_name="Decision",
        action_type="DECISION_INJECTED",
        content=decision_text[:200],
        consequence_type="root",
        importance=10,
        summary=f"Decision: {decision_text[:100]}",
    )

    orphans = []
    for eid, node in nodes.items():
        scored_info = score_map.get(eid, {})
        caused_by = scored_info.get("caused_by", [])
        is_direct = scored_info.get("is_direct", False)

        attached = False
        if caused_by:
            for parent_id in caused_by:
                if parent_id in nodes and parent_id != eid:
                    nodes[parent_id].children.append(node)
                    attached = True
                    break

        if not attached and is_direct:
            root.children.append(node)
            attached = True

        if not attached:
            orphans.append(node)

    for orphan in orphans:
        root.children.append(orphan)

    root.children.sort(key=lambda n: n.round_num)
    tree.root = root
    tree.total_nodes = len(nodes) + 1
    tree.unintended_count = sum(1 for n in nodes.values() if n.is_unintended)

    logger.info(
        f"Stage 3: tree built — {tree.total_nodes} nodes, "
        f"{tree.unintended_count} unintended consequences"
    )
    return tree


def extract_consequences(
    simulation_id: str,
    decision_text: str,
    max_actions: int = 500,
) -> ConsequenceTree:
    """
    Full pipeline: extract consequence tree from a simulation's action logs.

    Args:
        simulation_id: The simulation to analyze.
        decision_text: The decision scenario that was injected.
        max_actions: Maximum actions to process.

    Returns:
        ConsequenceTree with hierarchical causal chains.
    """
    logger.info(f"Extracting consequences for sim={simulation_id}")

    actions = SimulationRunner.get_actions(simulation_id, limit=max_actions)
    if not actions:
        logger.warning(f"No actions found for simulation {simulation_id}")
        return ConsequenceTree(decision_text=decision_text)

    events = _stage1_filter_actions(actions)
    scored = _stage2_score_causality(decision_text, events)
    tree = _stage3_build_tree(decision_text, events, scored)

    return tree
