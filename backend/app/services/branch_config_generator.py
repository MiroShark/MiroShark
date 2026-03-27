"""
Branch Config Generator
Wraps SimulationConfigGenerator to inject decision text into the simulation
requirement, producing branch-specific agent behavior configurations.

The decision text is prepended to the simulation requirement so the LLM
generates agent stances, sentiment biases, and activity levels that reflect
the specific decision scenario for each branch.
"""

from typing import List, Optional, Callable

from ..utils.logger import get_logger
from .entity_reader import EntityNode
from .simulation_config_generator import SimulationConfigGenerator, SimulationParameters

logger = get_logger("miroshark.branch_config")

DECISION_INJECTION_TEMPLATE = """## Decision Scenario
The following decision/action has been taken in this branch of the simulation:

{decision_text}

All agent behavior configurations (sentiment_bias, stance, activity_level,
posts_per_hour) should reflect how agents would react AFTER this decision
is announced. Consider:
- Which agents would support or oppose this decision?
- How would activity levels change (more posting, less posting)?
- What emotional reactions would this trigger?
- Would any agents change their usual stance?

## Original Simulation Requirement
{original_requirement}"""


def build_branch_requirement(original_requirement: str, decision_text: str) -> str:
    """
    Merge the original simulation requirement with a decision injection.

    Args:
        original_requirement: The base simulation requirement from the project.
        decision_text: The decision scenario for this branch.

    Returns:
        An augmented requirement string that the LLM uses for config generation.
    """
    return DECISION_INJECTION_TEMPLATE.format(
        decision_text=decision_text.strip(),
        original_requirement=original_requirement.strip(),
    )


def generate_branch_config(
    simulation_id: str,
    project_id: str,
    graph_id: str,
    original_requirement: str,
    decision_text: str,
    document_text: str,
    entities: List[EntityNode],
    enable_twitter: bool = True,
    enable_reddit: bool = True,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> SimulationParameters:
    """
    Generate simulation config for a single decision branch.

    Injects the decision text into the simulation requirement, then delegates
    to the standard SimulationConfigGenerator.

    Args:
        simulation_id: Unique ID for this branch's simulation.
        project_id: Parent project ID.
        graph_id: Shared knowledge graph ID.
        original_requirement: Base simulation requirement from the project.
        decision_text: Decision scenario text for this branch.
        document_text: Original document content.
        entities: Filtered entity list from the graph.
        enable_twitter: Enable Twitter simulation.
        enable_reddit: Enable Reddit simulation.
        progress_callback: Optional progress callback.

    Returns:
        SimulationParameters configured for this decision branch.
    """
    branch_requirement = build_branch_requirement(original_requirement, decision_text)

    logger.info(
        f"Generating branch config: sim={simulation_id}, "
        f"decision='{decision_text[:80]}...', entities={len(entities)}"
    )

    generator = SimulationConfigGenerator()
    params = generator.generate_config(
        simulation_id=simulation_id,
        project_id=project_id,
        graph_id=graph_id,
        simulation_requirement=branch_requirement,
        document_text=document_text,
        entities=entities,
        enable_twitter=enable_twitter,
        enable_reddit=enable_reddit,
        progress_callback=progress_callback,
    )

    logger.info(
        f"Branch config complete: sim={simulation_id}, "
        f"agents={len(params.agent_configs)}"
    )
    return params
