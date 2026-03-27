"""
Decision Lab Manager
Orchestrates parallel branch preparation and simulation execution.
Reuses SimulationManager for per-branch lifecycle and injects decision text
via branch_config_generator.
"""

import threading
from typing import Optional, List

from ..config import Config
from ..utils.logger import get_logger
from ..models.decision_lab import (
    DecisionLabManager as LabStore,
    LabStatus,
    BranchStatus,
)
from ..models.project import ProjectManager
from .simulation_manager import SimulationManager
from .branch_config_generator import generate_branch_config
from .entity_reader import EntityReader
from .oasis_profile_generator import OasisProfileGenerator
from .simulation_runner import SimulationRunner

logger = get_logger("miroshark.decision_lab")


def prepare_branch(
    lab_id: str,
    branch_id: str,
    project_id: str,
    graph_id: str,
    original_requirement: str,
    decision_text: str,
    document_text: str,
    storage,
):
    """
    Prepare a single branch: create simulation, generate profiles and config.
    Runs in a background thread.
    """
    sim_manager = SimulationManager()

    try:
        LabStore.update_branch_status(lab_id, branch_id, BranchStatus.PREPARING)

        state = sim_manager.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=True,
            enable_reddit=True,
        )
        simulation_id = state.simulation_id
        LabStore.update_branch_status(
            lab_id, branch_id, BranchStatus.PREPARING, simulation_id=simulation_id
        )
        logger.info(f"Branch {branch_id}: created simulation {simulation_id}")

        sim_manager.prepare_simulation(
            simulation_id=simulation_id,
            simulation_requirement=f"{decision_text}\n\n{original_requirement}",
            document_text=document_text,
            storage=storage,
        )

        LabStore.update_branch_status(lab_id, branch_id, BranchStatus.READY)
        logger.info(f"Branch {branch_id}: preparation complete")

    except Exception as exc:
        logger.error(f"Branch {branch_id} preparation failed: {exc}")
        LabStore.update_branch_status(
            lab_id, branch_id, BranchStatus.FAILED, error=str(exc)
        )


def prepare_all_branches(lab_id: str, storage):
    """
    Prepare all branches in a lab concurrently (each in its own thread).
    Updates lab status to PREPARING, then READY when all branches finish.
    """
    lab = LabStore.get_lab(lab_id)
    if not lab:
        raise ValueError(f"Lab not found: {lab_id}")
    if not lab.branches:
        raise ValueError("No branches defined")

    project = ProjectManager.get_project(lab.project_id)
    if not project:
        raise ValueError(f"Project not found: {lab.project_id}")

    document_text = ProjectManager.get_extracted_text(lab.project_id) or ""
    original_requirement = lab.situation or project.simulation_requirement or ""

    lab.status = LabStatus.PREPARING
    LabStore.save_lab(lab)

    threads = []
    for branch in lab.branches:
        thread = threading.Thread(
            target=prepare_branch,
            args=(
                lab_id,
                branch.branch_id,
                lab.project_id,
                lab.graph_id,
                original_requirement,
                branch.decision_text,
                document_text,
                storage,
            ),
            daemon=True,
        )
        threads.append(thread)
        thread.start()
        logger.info(f"Started preparation thread for branch {branch.branch_id}")

    def wait_and_finalize():
        for thread in threads:
            thread.join()
        lab_final = LabStore.get_lab(lab_id)
        if not lab_final:
            return
        all_ready = all(b.status == BranchStatus.READY for b in lab_final.branches)
        any_failed = any(b.status == BranchStatus.FAILED for b in lab_final.branches)
        if all_ready:
            lab_final.status = LabStatus.READY
        elif any_failed:
            lab_final.status = LabStatus.FAILED
            lab_final.error = "One or more branches failed preparation"
        LabStore.save_lab(lab_final)
        logger.info(f"Lab {lab_id} preparation finalized: status={lab_final.status.value}")

    finalizer = threading.Thread(target=wait_and_finalize, daemon=True)
    finalizer.start()


def run_all_branches(lab_id: str, max_rounds: int = 72):
    """
    Start simulations for all ready branches concurrently.
    """
    lab = LabStore.get_lab(lab_id)
    if not lab:
        raise ValueError(f"Lab not found: {lab_id}")

    ready_branches = [b for b in lab.branches if b.status == BranchStatus.READY]
    if not ready_branches:
        raise ValueError("No branches are ready to run")

    lab.status = LabStatus.RUNNING
    LabStore.save_lab(lab)

    for branch in ready_branches:
        if not branch.simulation_id:
            LabStore.update_branch_status(
                lab_id, branch.branch_id, BranchStatus.FAILED,
                error="No simulation_id — branch was not prepared"
            )
            continue
        try:
            SimulationRunner.start_simulation(
                simulation_id=branch.simulation_id,
                platform="parallel",
                max_rounds=max_rounds,
            )
            LabStore.update_branch_status(lab_id, branch.branch_id, BranchStatus.RUNNING)
            logger.info(f"Started simulation for branch {branch.branch_id}: {branch.simulation_id}")
        except Exception as exc:
            logger.error(f"Failed to start branch {branch.branch_id}: {exc}")
            LabStore.update_branch_status(
                lab_id, branch.branch_id, BranchStatus.FAILED, error=str(exc)
            )


def get_lab_status_detail(lab_id: str) -> dict:
    """
    Get detailed status including per-branch simulation progress.
    """
    lab = LabStore.get_lab(lab_id)
    if not lab:
        return {}

    branches_detail = []
    for branch in lab.branches:
        detail = branch.to_dict()
        if branch.simulation_id and branch.status == BranchStatus.RUNNING:
            run_state = SimulationRunner.get_run_state(branch.simulation_id)
            if run_state:
                detail["current_round"] = run_state.get("current_round", 0)
                detail["total_rounds"] = run_state.get("total_rounds", 0)
                detail["twitter_actions"] = run_state.get("twitter_actions_count", 0)
                detail["reddit_actions"] = run_state.get("reddit_actions_count", 0)
        branches_detail.append(detail)

    return {
        "lab_id": lab.lab_id,
        "status": lab.status.value,
        "branches": branches_detail,
        "total_branches": len(lab.branches),
    }
