"""
Branch Comparison
Computes side-by-side metrics across Decision Lab branches for comparative analysis.
"""

from typing import List, Dict, Any, Optional
from collections import Counter

from ..utils.logger import get_logger
from ..models.decision_lab import DecisionLabManager, DecisionLab
from .simulation_runner import SimulationRunner

logger = get_logger("miroshark.branch_comparison")


def _compute_branch_metrics(simulation_id: str) -> Dict[str, Any]:
    """Compute aggregate metrics for a single branch simulation."""
    actions = SimulationRunner.get_all_actions(simulation_id)
    if not actions:
        return {"total_actions": 0, "error": "No actions found"}

    action_types = Counter(a.action_type for a in actions)
    agents_active = set()
    posts = []
    rounds_seen = set()

    for action in actions:
        agents_active.add(action.agent_name)
        rounds_seen.add(action.round_num)
        if action.action_type in ("CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"):
            content = ""
            args = action.action_args or {}
            if "post_content" in args:
                content = args["post_content"]
            elif "content" in args:
                content = args["content"]
            elif action.result:
                content = str(action.result)
            posts.append({
                "agent": action.agent_name,
                "round": action.round_num,
                "content": str(content)[:200],
                "type": action.action_type,
            })

    total_posts = action_types.get("CREATE_POST", 0)
    total_comments = action_types.get("CREATE_COMMENT", 0)
    total_likes = action_types.get("LIKE_POST", 0)
    total_dislikes = action_types.get("DISLIKE_POST", 0)
    total_reposts = action_types.get("REPOST", 0) + action_types.get("QUOTE_POST", 0)

    engagement_rate = 0
    if total_posts > 0:
        engagement_rate = round((total_comments + total_likes + total_reposts) / total_posts, 2)

    return {
        "total_actions": len(actions),
        "total_posts": total_posts,
        "total_comments": total_comments,
        "total_likes": total_likes,
        "total_dislikes": total_dislikes,
        "total_reposts": total_reposts,
        "engagement_rate": engagement_rate,
        "active_agents": len(agents_active),
        "rounds_completed": len(rounds_seen),
        "top_posters": Counter(p["agent"] for p in posts).most_common(5),
        "action_types": dict(action_types),
    }


def _compute_round_timeline(simulation_id: str) -> List[Dict]:
    """Compute per-round activity counts for timeline comparison."""
    timeline = SimulationRunner.get_timeline(simulation_id)
    simplified = []
    for entry in timeline:
        if isinstance(entry, dict):
            simplified.append({
                "round": entry.get("round_num", 0),
                "twitter": entry.get("twitter_actions", 0),
                "reddit": entry.get("reddit_actions", 0),
                "agents": len(entry.get("active_agents", set())),
            })
    return simplified


def compare_branches(lab_id: str) -> Dict[str, Any]:
    """
    Compare all branches in a Decision Lab side by side.

    Returns metrics per branch and divergence analysis.
    """
    lab = DecisionLabManager.get_lab(lab_id)
    if not lab:
        raise ValueError(f"Lab not found: {lab_id}")

    branch_metrics = {}
    branch_timelines = {}

    for branch in lab.branches:
        if not branch.simulation_id:
            continue
        label = branch.label
        branch_metrics[label] = _compute_branch_metrics(branch.simulation_id)
        branch_timelines[label] = _compute_round_timeline(branch.simulation_id)

    comparison_keys = [
        "total_posts", "total_comments", "total_likes",
        "total_dislikes", "engagement_rate", "active_agents",
    ]
    summary = {}
    for key in comparison_keys:
        summary[key] = {
            label: metrics.get(key, 0)
            for label, metrics in branch_metrics.items()
        }

    return {
        "lab_id": lab_id,
        "branches": branch_metrics,
        "timelines": branch_timelines,
        "summary": summary,
    }
