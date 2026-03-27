"""
Decision Lab API routes
Manages decision labs with parallel simulation branches for comparative analysis.
"""

import traceback
from flask import request, jsonify

from . import decision_lab_bp
from ..models.decision_lab import DecisionLabManager, LabStatus, BranchStatus
from ..models.project import ProjectManager
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
    """Get aggregated status of all branches in a lab."""
    lab = DecisionLabManager.get_lab(lab_id)
    if not lab:
        return jsonify({"success": False, "error": f"Lab not found: {lab_id}"}), 404

    branch_statuses = [b.to_dict() for b in lab.branches]
    return jsonify({
        "success": True,
        "data": {
            "lab_id": lab.lab_id,
            "status": lab.status.value if isinstance(lab.status, LabStatus) else lab.status,
            "branches": branch_statuses,
            "total_branches": len(lab.branches),
        },
    })


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
