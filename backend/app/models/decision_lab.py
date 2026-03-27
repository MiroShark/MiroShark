"""
Decision Lab Data Model
Manages decision labs with multiple simulation branches for comparative analysis.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field

from ..config import Config


class LabStatus(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BranchStatus(str, Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DecisionBranch:
    branch_id: str
    label: str
    decision_text: str
    status: BranchStatus = BranchStatus.PENDING
    simulation_id: Optional[str] = None
    error: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "label": self.label,
            "decision_text": self.decision_text,
            "status": self.status.value if isinstance(self.status, BranchStatus) else self.status,
            "simulation_id": self.simulation_id,
            "error": self.error,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionBranch":
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = BranchStatus(status)
        return cls(
            branch_id=data["branch_id"],
            label=data.get("label", ""),
            decision_text=data.get("decision_text", ""),
            status=status,
            simulation_id=data.get("simulation_id"),
            error=data.get("error"),
            created_at=data.get("created_at", ""),
        )


@dataclass
class DecisionLab:
    lab_id: str
    project_id: str
    graph_id: str
    name: str
    situation: str
    status: LabStatus = LabStatus.CREATED
    branches: List[DecisionBranch] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lab_id": self.lab_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "name": self.name,
            "situation": self.situation,
            "status": self.status.value if isinstance(self.status, LabStatus) else self.status,
            "branches": [b.to_dict() for b in self.branches],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionLab":
        status = data.get("status", "created")
        if isinstance(status, str):
            status = LabStatus(status)
        branches = [DecisionBranch.from_dict(b) for b in data.get("branches", [])]
        return cls(
            lab_id=data["lab_id"],
            project_id=data["project_id"],
            graph_id=data["graph_id"],
            name=data.get("name", ""),
            situation=data.get("situation", ""),
            status=status,
            branches=branches,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            error=data.get("error"),
        )


class DecisionLabManager:
    """Manages Decision Lab persistence on disk."""

    LABS_DIR = os.path.join(Config.UPLOAD_FOLDER, "decision_labs")

    @classmethod
    def _ensure_dir(cls):
        os.makedirs(cls.LABS_DIR, exist_ok=True)

    @classmethod
    def _lab_dir(cls, lab_id: str) -> str:
        return os.path.join(cls.LABS_DIR, lab_id)

    @classmethod
    def _meta_path(cls, lab_id: str) -> str:
        return os.path.join(cls._lab_dir(lab_id), "lab.json")

    @classmethod
    def create_lab(
        cls,
        project_id: str,
        graph_id: str,
        name: str,
        situation: str,
    ) -> DecisionLab:
        cls._ensure_dir()
        lab_id = f"lab_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        lab = DecisionLab(
            lab_id=lab_id,
            project_id=project_id,
            graph_id=graph_id,
            name=name,
            situation=situation,
            created_at=now,
            updated_at=now,
        )
        lab_dir = cls._lab_dir(lab_id)
        os.makedirs(lab_dir, exist_ok=True)
        os.makedirs(os.path.join(lab_dir, "branches"), exist_ok=True)
        cls.save_lab(lab)
        return lab

    @classmethod
    def save_lab(cls, lab: DecisionLab):
        lab.updated_at = datetime.now().isoformat()
        meta_path = cls._meta_path(lab.lab_id)
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(lab.to_dict(), fh, ensure_ascii=False, indent=2)

    @classmethod
    def get_lab(cls, lab_id: str) -> Optional[DecisionLab]:
        meta_path = cls._meta_path(lab_id)
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, "r", encoding="utf-8") as fh:
            return DecisionLab.from_dict(json.load(fh))

    @classmethod
    def list_labs(cls, limit: int = 50) -> List[DecisionLab]:
        cls._ensure_dir()
        labs = []
        for entry in os.listdir(cls.LABS_DIR):
            lab = cls.get_lab(entry)
            if lab:
                labs.append(lab)
        labs.sort(key=lambda l: l.created_at, reverse=True)
        return labs[:limit]

    @classmethod
    def add_branch(cls, lab_id: str, label: str, decision_text: str) -> DecisionBranch:
        lab = cls.get_lab(lab_id)
        if not lab:
            raise ValueError(f"Lab not found: {lab_id}")
        if len(lab.branches) >= 5:
            raise ValueError("Maximum 5 branches per lab")
        branch_id = f"branch_{uuid.uuid4().hex[:8]}"
        branch = DecisionBranch(
            branch_id=branch_id,
            label=label,
            decision_text=decision_text,
            created_at=datetime.now().isoformat(),
        )
        lab.branches.append(branch)
        cls.save_lab(lab)
        branch_dir = os.path.join(cls._lab_dir(lab_id), "branches", branch_id)
        os.makedirs(branch_dir, exist_ok=True)
        return branch

    @classmethod
    def remove_branch(cls, lab_id: str, branch_id: str) -> bool:
        lab = cls.get_lab(lab_id)
        if not lab:
            raise ValueError(f"Lab not found: {lab_id}")
        original_count = len(lab.branches)
        lab.branches = [b for b in lab.branches if b.branch_id != branch_id]
        if len(lab.branches) == original_count:
            return False
        cls.save_lab(lab)
        return True

    @classmethod
    def update_branch_status(
        cls,
        lab_id: str,
        branch_id: str,
        status: BranchStatus,
        simulation_id: Optional[str] = None,
        error: Optional[str] = None,
    ):
        lab = cls.get_lab(lab_id)
        if not lab:
            raise ValueError(f"Lab not found: {lab_id}")
        for branch in lab.branches:
            if branch.branch_id == branch_id:
                branch.status = status
                if simulation_id is not None:
                    branch.simulation_id = simulation_id
                if error is not None:
                    branch.error = error
                break
        cls.save_lab(lab)

    @classmethod
    def delete_lab(cls, lab_id: str) -> bool:
        lab_dir = cls._lab_dir(lab_id)
        if not os.path.exists(lab_dir):
            return False
        import shutil
        shutil.rmtree(lab_dir)
        return True
