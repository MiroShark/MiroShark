"""
Autonomous Strategy Optimizer
Inspired by Karpathy's autoresearch loop pattern.

Given a goal/objective, autonomously:
1. LLM proposes decision branches
2. Runs short simulations (budget-constrained)
3. Evaluates outcomes
4. Keeps promising strategies, discards failures
5. LLM proposes new variations based on what worked
6. Repeats for N iterations

Results logged to results.jsonl for analysis.
"""

import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from ..config import Config
from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger
from ..models.decision_lab import DecisionLabManager, LabStatus, BranchStatus
from .branch_comparison import compare_branches
from .decision_lab_manager import prepare_all_branches, run_all_branches

logger = get_logger("miroshark.autonomous_lab")

PROPOSE_BRANCHES_PROMPT = """You are a strategic decision analyst. Given a situation and optimization goal,
propose {num_branches} distinct decision strategies to test.

SITUATION:
{situation}

OPTIMIZATION GOAL:
{goal}

{prior_results}

Propose exactly {num_branches} decision strategies. Each should be meaningfully different.
Return ONLY a JSON array of objects:
[
  {{"label": "Short label (2-4 words)", "decision_text": "Detailed description of the decision/action..."}}
]"""

EVALUATE_PROMPT = """You are evaluating simulation results for decision branches.

OPTIMIZATION GOAL: {goal}

BRANCH RESULTS:
{results_text}

For each branch, score 0-10 on how well it achieves the optimization goal.
Also identify the single best strategy and explain why.

Return JSON:
{{
  "scores": {{"branch_label": score, ...}},
  "best_branch": "label",
  "reasoning": "why this branch is best",
  "suggestions": ["suggestion for next iteration", ...]
}}"""


@dataclass
class AutoLabState:
    lab_id: str
    goal: str
    status: str = "idle"  # idle, running, paused, completed
    current_iteration: int = 0
    max_iterations: int = 5
    max_rounds_per_sim: int = 20
    branches_per_iteration: int = 3
    results: List[Dict] = field(default_factory=list)
    best_strategy: Optional[Dict] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "lab_id": self.lab_id,
            "goal": self.goal,
            "status": self.status,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "max_rounds_per_sim": self.max_rounds_per_sim,
            "results": self.results,
            "best_strategy": self.best_strategy,
            "error": self.error,
        }


_auto_states: Dict[str, AutoLabState] = {}


def _format_prior_results(results: List[Dict]) -> str:
    if not results:
        return ""
    lines = ["PRIOR RESULTS (learn from these):"]
    for entry in results[-5:]:
        lines.append(f"\nIteration {entry['iteration']}:")
        for branch in entry.get("branches", []):
            score = branch.get("score", "?")
            label = branch.get("label", "?")
            decision = branch.get("decision_text", "")[:100]
            verdict = branch.get("verdict", "")
            lines.append(f"  [{verdict}] {label} (score={score}): {decision}")
        if entry.get("best"):
            lines.append(f"  BEST: {entry['best']}")
        if entry.get("suggestions"):
            lines.append(f"  Suggestions: {'; '.join(entry['suggestions'][:3])}")
    return "\n".join(lines)


def _propose_branches(situation: str, goal: str, prior_results: List[Dict], num: int) -> List[Dict]:
    """Use LLM to propose decision branches."""
    client = create_llm_client()
    prompt = PROPOSE_BRANCHES_PROMPT.format(
        situation=situation,
        goal=goal,
        prior_results=_format_prior_results(prior_results),
        num_branches=num,
    )
    result = client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    if isinstance(result, list):
        return result[:num]
    return []


def _evaluate_results(goal: str, comparison: Dict) -> Dict:
    """Use LLM to evaluate simulation results against the goal."""
    branches = comparison.get("branches", {})
    results_text = ""
    for label, metrics in branches.items():
        results_text += f"\n{label}:\n"
        results_text += f"  Posts: {metrics.get('total_posts', 0)}, "
        results_text += f"Comments: {metrics.get('total_comments', 0)}, "
        results_text += f"Engagement: {metrics.get('engagement_rate', 0)}, "
        results_text += f"Likes: {metrics.get('total_likes', 0)}, "
        results_text += f"Dislikes: {metrics.get('total_dislikes', 0)}, "
        results_text += f"Active agents: {metrics.get('active_agents', 0)}"

    client = create_llm_client()
    prompt = EVALUATE_PROMPT.format(goal=goal, results_text=results_text)
    result = client.chat_json(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    if isinstance(result, dict):
        return result
    return {"scores": {}, "best_branch": "", "reasoning": "", "suggestions": []}


def _wait_for_lab_completion(lab_id: str, timeout: int = 3600) -> bool:
    """Poll lab status until all branches complete or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        lab = DecisionLabManager.get_lab(lab_id)
        if not lab:
            return False
        all_done = all(
            b.status in (BranchStatus.COMPLETED, BranchStatus.FAILED)
            for b in lab.branches
        )
        if all_done:
            return True
        if lab.status == LabStatus.FAILED:
            return False
        time.sleep(10)
    return False


def _run_iteration(state: AutoLabState, storage) -> Dict:
    """Run a single iteration: propose → prepare → run → evaluate."""
    lab = DecisionLabManager.get_lab(state.lab_id)
    if not lab:
        raise ValueError(f"Lab not found: {state.lab_id}")

    iteration = state.current_iteration
    logger.info(f"Auto iteration {iteration}: proposing branches...")

    # Clear existing branches
    for branch in list(lab.branches):
        DecisionLabManager.remove_branch(lab.lab_id, branch.branch_id)

    # Propose new branches
    proposals = _propose_branches(
        situation=lab.situation,
        goal=state.goal,
        prior_results=state.results,
        num=state.branches_per_iteration,
    )

    if not proposals:
        raise ValueError("LLM failed to propose branches")

    # Add branches
    for proposal in proposals:
        DecisionLabManager.add_branch(
            lab.lab_id,
            label=proposal.get("label", f"Strategy {iteration}"),
            decision_text=proposal.get("decision_text", ""),
        )

    # Prepare
    logger.info(f"Auto iteration {iteration}: preparing branches...")
    lab = DecisionLabManager.get_lab(state.lab_id)
    lab.status = LabStatus.CREATED
    DecisionLabManager.save_lab(lab)
    prepare_all_branches(state.lab_id, storage)

    # Wait for preparation
    for _ in range(120):
        time.sleep(5)
        lab = DecisionLabManager.get_lab(state.lab_id)
        if lab and lab.status in (LabStatus.READY, LabStatus.FAILED):
            break

    if not lab or lab.status != LabStatus.READY:
        raise ValueError("Branch preparation failed or timed out")

    # Run simulations
    logger.info(f"Auto iteration {iteration}: running simulations ({state.max_rounds_per_sim} rounds)...")
    run_all_branches(state.lab_id, max_rounds=state.max_rounds_per_sim)

    # Wait for completion
    completed = _wait_for_lab_completion(state.lab_id, timeout=1800)
    if not completed:
        logger.warning(f"Auto iteration {iteration}: simulations timed out")

    # Evaluate
    logger.info(f"Auto iteration {iteration}: evaluating results...")
    comparison = compare_branches(state.lab_id)
    evaluation = _evaluate_results(state.goal, comparison)

    # Build iteration result
    iteration_result = {
        "iteration": iteration,
        "timestamp": datetime.now().isoformat(),
        "branches": [],
        "best": evaluation.get("best_branch"),
        "reasoning": evaluation.get("reasoning"),
        "suggestions": evaluation.get("suggestions", []),
    }

    scores = evaluation.get("scores", {})
    lab = DecisionLabManager.get_lab(state.lab_id)
    for branch in lab.branches:
        score = scores.get(branch.label, 0)
        verdict = "KEEP" if score >= 6 else "DISCARD"
        iteration_result["branches"].append({
            "label": branch.label,
            "decision_text": branch.decision_text,
            "score": score,
            "verdict": verdict,
            "simulation_id": branch.simulation_id,
        })

    # Track best strategy
    best_label = evaluation.get("best_branch")
    if best_label:
        for br in iteration_result["branches"]:
            if br["label"] == best_label:
                state.best_strategy = {
                    "label": br["label"],
                    "decision_text": br["decision_text"],
                    "score": br["score"],
                    "iteration": iteration,
                    "reasoning": evaluation.get("reasoning", ""),
                }

    return iteration_result


def _auto_loop(lab_id: str, storage):
    """Main autonomous loop — runs in background thread."""
    state = _auto_states.get(lab_id)
    if not state:
        return

    state.status = "running"
    results_path = os.path.join(
        Config.UPLOAD_FOLDER, "decision_labs", lab_id, "auto_results.jsonl"
    )

    try:
        while state.current_iteration < state.max_iterations and state.status == "running":
            state.current_iteration += 1
            logger.info(f"=== Auto Lab {lab_id}: iteration {state.current_iteration}/{state.max_iterations} ===")

            iteration_result = _run_iteration(state, storage)
            state.results.append(iteration_result)

            # Append to results file
            os.makedirs(os.path.dirname(results_path), exist_ok=True)
            with open(results_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(iteration_result, ensure_ascii=False) + "\n")

            logger.info(
                f"Iteration {state.current_iteration} complete: "
                f"best={iteration_result.get('best')}, "
                f"scores={[b['score'] for b in iteration_result['branches']]}"
            )

        state.status = "completed"
        logger.info(f"Auto Lab {lab_id} completed after {state.current_iteration} iterations")
        if state.best_strategy:
            logger.info(f"Best strategy: {state.best_strategy['label']} (score={state.best_strategy['score']})")

    except Exception as exc:
        state.status = "failed"
        state.error = str(exc)
        logger.error(f"Auto Lab {lab_id} failed: {exc}")


def start_auto_lab(
    lab_id: str,
    goal: str,
    storage,
    max_iterations: int = 5,
    max_rounds_per_sim: int = 20,
    branches_per_iteration: int = 3,
) -> AutoLabState:
    """Start an autonomous optimization loop for a Decision Lab."""
    state = AutoLabState(
        lab_id=lab_id,
        goal=goal,
        max_iterations=max_iterations,
        max_rounds_per_sim=max_rounds_per_sim,
        branches_per_iteration=branches_per_iteration,
    )
    _auto_states[lab_id] = state

    thread = threading.Thread(target=_auto_loop, args=(lab_id, storage), daemon=True)
    thread.start()
    logger.info(f"Started autonomous lab: {lab_id}, goal='{goal}', iterations={max_iterations}")

    return state


def get_auto_state(lab_id: str) -> Optional[AutoLabState]:
    """Get the current state of an autonomous lab run."""
    return _auto_states.get(lab_id)


def stop_auto_lab(lab_id: str) -> bool:
    """Stop a running autonomous lab."""
    state = _auto_states.get(lab_id)
    if not state:
        return False
    state.status = "paused"
    logger.info(f"Stopping autonomous lab: {lab_id}")
    return True
