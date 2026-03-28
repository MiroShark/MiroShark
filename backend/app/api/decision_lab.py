"""
Decision Lab API routes
Manages decision labs with parallel simulation branches for comparative analysis.
"""

import traceback
from flask import request, jsonify

from flask import current_app

from . import decision_lab_bp
from ..models.decision_lab import DecisionLabManager, LabStatus, BranchStatus
from ..models.project import ProjectManager
from ..services.decision_lab_manager import (
    prepare_all_branches,
    run_all_branches,
    get_lab_status_detail,
)
from ..services.consequence_extractor import extract_consequences
from ..services.branch_comparison import compare_branches
from ..services.autonomous_lab import start_auto_lab, get_auto_state, stop_auto_lab
from ..utils.logger import get_logger

logger = get_logger("miroshark.api.decision_lab")


@decision_lab_bp.route("/create", methods=["POST"])
def create_lab():
    """
    Create a new Decision Lab from an existing project with a completed graph.

    Request (JSON):
        {
            "project_id": "proj_xxxx",
            "name": "Iran conflict analysis",
            "situation": "Base scenario description"
        }
    """
    try:
        data = request.get_json() or {}
        project_id = data.get("project_id")
        if not project_id:
            return jsonify({"success": False, "error": "project_id is required"}), 400

        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({"success": False, "error": f"Project not found: {project_id}"}), 404

        if not project.graph_id:
            return jsonify({"success": False, "error": "Project must have a completed graph"}), 400

        name = data.get("name", project.name or "Decision Lab")
        situation = data.get("situation", project.simulation_requirement or "")

        lab = DecisionLabManager.create_lab(
            project_id=project_id,
            graph_id=project.graph_id,
            name=name,
            situation=situation,
        )
        logger.info(f"Created Decision Lab: {lab.lab_id} for project {project_id}")

        return jsonify({"success": True, "data": lab.to_dict()})

    except Exception as exc:
        logger.error(f"Failed to create lab: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@decision_lab_bp.route("/<lab_id>", methods=["GET"])
def get_lab(lab_id: str):
    """Get Decision Lab details including all branches."""
    lab = DecisionLabManager.get_lab(lab_id)
    if not lab:
        return jsonify({"success": False, "error": f"Lab not found: {lab_id}"}), 404
    return jsonify({"success": True, "data": lab.to_dict()})


@decision_lab_bp.route("/list", methods=["GET"])
def list_labs():
    """List all Decision Labs, newest first."""
    limit = request.args.get("limit", 50, type=int)
    labs = DecisionLabManager.list_labs(limit=limit)
    return jsonify({
        "success": True,
        "data": [lab.to_dict() for lab in labs],
        "count": len(labs),
    })


@decision_lab_bp.route("/<lab_id>/branch", methods=["POST"])
def add_branch(lab_id: str):
    """
    Add a decision branch to a lab.

    Request (JSON):
        {
            "label": "Sanctions",
            "decision_text": "The US imposes severe economic sanctions on Iran..."
        }
    """
    try:
        data = request.get_json() or {}
        label = data.get("label", "").strip()
        decision_text = data.get("decision_text", "").strip()

        if not label:
            return jsonify({"success": False, "error": "label is required"}), 400
        if not decision_text:
            return jsonify({"success": False, "error": "decision_text is required"}), 400

        branch = DecisionLabManager.add_branch(lab_id, label, decision_text)
        logger.info(f"Added branch '{label}' to lab {lab_id}")

        lab = DecisionLabManager.get_lab(lab_id)
        return jsonify({"success": True, "data": {"branch": branch.to_dict(), "lab": lab.to_dict()}})

    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as exc:
        logger.error(f"Failed to add branch: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@decision_lab_bp.route("/<lab_id>/branch/<branch_id>", methods=["DELETE"])
def remove_branch(lab_id: str, branch_id: str):
    """Remove a branch from a lab."""
    try:
        removed = DecisionLabManager.remove_branch(lab_id, branch_id)
        if not removed:
            return jsonify({"success": False, "error": f"Branch not found: {branch_id}"}), 404
        logger.info(f"Removed branch {branch_id} from lab {lab_id}")
        lab = DecisionLabManager.get_lab(lab_id)
        return jsonify({"success": True, "data": lab.to_dict()})
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as exc:
        logger.error(f"Failed to remove branch: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@decision_lab_bp.route("/<lab_id>/status", methods=["GET"])
def get_lab_status(lab_id: str):
    """Get detailed status including per-branch simulation progress."""
    detail = get_lab_status_detail(lab_id)
    if not detail:
        return jsonify({"success": False, "error": f"Lab not found: {lab_id}"}), 404
    return jsonify({"success": True, "data": detail})


@decision_lab_bp.route("/<lab_id>/prepare", methods=["POST"])
def prepare_lab(lab_id: str):
    """
    Prepare all branches (generate profiles + configs) in parallel.
    Returns immediately — poll /status for progress.
    """
    try:
        storage = current_app.extensions.get("neo4j_storage")
        if not storage:
            return jsonify({"success": False, "error": "Neo4j storage not initialized"}), 503
        prepare_all_branches(lab_id, storage)
        logger.info(f"Started preparation for lab {lab_id}")
        return jsonify({"success": True, "data": {"lab_id": lab_id, "message": "Preparation started"}})
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as exc:
        logger.error(f"Failed to prepare lab: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@decision_lab_bp.route("/<lab_id>/run", methods=["POST"])
def run_lab(lab_id: str):
    """
    Start simulations for all ready branches in parallel.

    Request (JSON, optional):
        { "max_rounds": 72 }
    """
    try:
        data = request.get_json() or {}
        max_rounds = data.get("max_rounds", 72)
        run_all_branches(lab_id, max_rounds=max_rounds)
        logger.info(f"Started simulations for lab {lab_id}")
        return jsonify({"success": True, "data": {"lab_id": lab_id, "message": "Simulations started"}})
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as exc:
        logger.error(f"Failed to run lab: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@decision_lab_bp.route("/<lab_id>/consequences/<branch_id>", methods=["GET"])
def get_consequences(lab_id: str, branch_id: str):
    """
    Extract consequence tree for a completed branch simulation.
    Returns a hierarchical causal chain with unintended consequences flagged.
    """
    try:
        lab = DecisionLabManager.get_lab(lab_id)
        if not lab:
            return jsonify({"success": False, "error": f"Lab not found: {lab_id}"}), 404

        branch = next((b for b in lab.branches if b.branch_id == branch_id), None)
        if not branch:
            return jsonify({"success": False, "error": f"Branch not found: {branch_id}"}), 404
        if not branch.simulation_id:
            return jsonify({"success": False, "error": "Branch has no simulation"}), 400

        tree = extract_consequences(
            simulation_id=branch.simulation_id,
            decision_text=branch.decision_text,
        )
        return jsonify({"success": True, "data": tree.to_dict()})

    except Exception as exc:
        logger.error(f"Failed to extract consequences: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@decision_lab_bp.route("/<lab_id>/branch/<branch_id>/retry", methods=["POST"])
def retry_branch(lab_id: str, branch_id: str):
    """Retry a failed branch — resets it to pending and re-triggers preparation."""
    try:
        lab = DecisionLabManager.get_lab(lab_id)
        if not lab:
            return jsonify({"success": False, "error": f"Lab not found: {lab_id}"}), 404
        branch = next((b for b in lab.branches if b.branch_id == branch_id), None)
        if not branch:
            return jsonify({"success": False, "error": f"Branch not found: {branch_id}"}), 404
        branch.status = BranchStatus.PENDING
        branch.simulation_id = None
        branch.error = None
        lab.status = LabStatus.CREATED
        DecisionLabManager.save_lab(lab)
        storage = current_app.extensions.get("neo4j_storage")
        if storage:
            prepare_all_branches(lab_id, storage)
        return jsonify({"success": True, "data": lab.to_dict()})
    except Exception as exc:
        logger.error(f"Failed to retry branch: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


@decision_lab_bp.route("/<lab_id>/compare", methods=["GET"])
def compare_lab_branches(lab_id: str):
    """
    Compare all branches side-by-side: activity metrics, engagement rates,
    per-round timelines, top posters.
    """
    try:
        result = compare_branches(lab_id)
        return jsonify({"success": True, "data": result})
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as exc:
        logger.error(f"Failed to compare branches: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@decision_lab_bp.route("/<lab_id>/inject", methods=["POST"])
def inject_info(lab_id: str):
    """
    Inject new information into a lab and re-run affected branches.

    Request (JSON):
        {
            "info_text": "Russia announces joint military exercises with Iran",
            "branch_ids": ["branch_xxx"],  // optional — re-run specific branches, or all
            "max_rounds": 72
        }
    """
    try:
        data = request.get_json() or {}
        info_text = data.get("info_text", "").strip()
        if not info_text:
            return jsonify({"success": False, "error": "info_text is required"}), 400

        lab = DecisionLabManager.get_lab(lab_id)
        if not lab:
            return jsonify({"success": False, "error": f"Lab not found: {lab_id}"}), 404

        branch_ids = data.get("branch_ids") or [b.branch_id for b in lab.branches]
        max_rounds = data.get("max_rounds", 72)

        for branch in lab.branches:
            if branch.branch_id in branch_ids:
                original_text = branch.decision_text
                branch.decision_text = f"{original_text}\n\nNEW DEVELOPMENT: {info_text}"
                branch.status = BranchStatus.PENDING
                branch.simulation_id = None
                branch.error = None

        lab.status = LabStatus.CREATED
        DecisionLabManager.save_lab(lab)

        storage = current_app.extensions.get("neo4j_storage")
        if storage:
            prepare_all_branches(lab_id, storage)

        logger.info(f"Injected new info into lab {lab_id}, re-preparing {len(branch_ids)} branches")
        return jsonify({
            "success": True,
            "data": {
                "lab_id": lab_id,
                "injected_text": info_text,
                "affected_branches": branch_ids,
                "message": "Branches re-preparing with new information",
            },
        })

    except Exception as exc:
        logger.error(f"Failed to inject info: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@decision_lab_bp.route("/<lab_id>/export", methods=["GET"])
def export_lab(lab_id: str):
    """Export full Decision Lab data (lab config + comparison + consequences) as JSON."""
    try:
        lab = DecisionLabManager.get_lab(lab_id)
        if not lab:
            return jsonify({"success": False, "error": f"Lab not found: {lab_id}"}), 404
        export_data = {"lab": lab.to_dict()}
        try:
            export_data["comparison"] = compare_branches(lab_id)
        except Exception:
            export_data["comparison"] = None
        for branch in lab.branches:
            if branch.simulation_id:
                try:
                    tree = extract_consequences(branch.simulation_id, branch.decision_text)
                    export_data.setdefault("consequences", {})[branch.label] = tree.to_dict()
                except Exception:
                    pass
        response = jsonify(export_data)
        response.headers['Content-Disposition'] = f'attachment; filename={lab_id}_export.json'
        return response
    except Exception as exc:
        logger.error(f"Failed to export lab: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


@decision_lab_bp.route("/<lab_id>/auto/start", methods=["POST"])
def start_auto(lab_id: str):
    """
    Start autonomous strategy optimization.
    LLM proposes, tests, and refines branches iteratively.

    Request (JSON):
        {
            "goal": "Find the decision that minimizes escalation risk",
            "max_iterations": 5,
            "max_rounds_per_sim": 20,
            "branches_per_iteration": 3
        }
    """
    try:
        data = request.get_json() or {}
        goal = data.get("goal", "").strip()
        if not goal:
            return jsonify({"success": False, "error": "goal is required"}), 400

        storage = current_app.extensions.get("neo4j_storage")
        if not storage:
            return jsonify({"success": False, "error": "Neo4j storage not initialized"}), 503

        state = start_auto_lab(
            lab_id=lab_id,
            goal=goal,
            storage=storage,
            max_iterations=data.get("max_iterations", 5),
            max_rounds_per_sim=data.get("max_rounds_per_sim", 20),
            branches_per_iteration=data.get("branches_per_iteration", 3),
        )
        return jsonify({"success": True, "data": state.to_dict()})

    except Exception as exc:
        logger.error(f"Failed to start auto lab: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@decision_lab_bp.route("/<lab_id>/auto/status", methods=["GET"])
def auto_status(lab_id: str):
    """Get autonomous optimization status and results."""
    state = get_auto_state(lab_id)
    if not state:
        return jsonify({"success": False, "error": "No autonomous run found for this lab"}), 404
    return jsonify({"success": True, "data": state.to_dict()})


@decision_lab_bp.route("/<lab_id>/auto/stop", methods=["POST"])
def stop_auto(lab_id: str):
    """Stop a running autonomous optimization."""
    stopped = stop_auto_lab(lab_id)
    if not stopped:
        return jsonify({"success": False, "error": "No running auto lab found"}), 404
    return jsonify({"success": True, "data": {"message": "Auto lab stopping after current iteration"}})


@decision_lab_bp.route("/<lab_id>", methods=["DELETE"])
def delete_lab(lab_id: str):
    """Delete a Decision Lab and all its data."""
    try:
        deleted = DecisionLabManager.delete_lab(lab_id)
        if not deleted:
            return jsonify({"success": False, "error": f"Lab not found: {lab_id}"}), 404
        logger.info(f"Deleted Decision Lab: {lab_id}")
        return jsonify({"success": True, "data": {"deleted": lab_id}})
    except Exception as exc:
        logger.error(f"Failed to delete lab: {exc}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500
