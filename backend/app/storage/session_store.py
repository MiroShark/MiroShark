"""
File-backed session store for seed-chat conversations.

Each session is stored as `{base_dir}/{session_id}.json`. The store has no
indexing — list() walks the directory. Acceptable since we expect <1000
sessions for a single-user local tool.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    """CRUD for seed-chat sessions on disk."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def create(self) -> Dict:
        """Create a new empty session, persist it, and return it."""
        now = _now_iso()
        session = {
            "id": str(uuid.uuid4()),
            "title": "",
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "seed_state": {},
            "ready_to_launch": False,
        }
        self.save(session, _bump_updated=False)
        return session

    def save(self, session: Dict, _bump_updated: bool = True) -> None:
        """Persist a session. Updates `updated_at` unless _bump_updated=False."""
        if _bump_updated:
            session["updated_at"] = _now_iso()
        path = self._path(session["id"])
        path.write_text(json.dumps(session, indent=2))

    def load(self, session_id: str) -> Optional[Dict]:
        """Return the session dict, or None if not found."""
        path = self._path(session_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list(self) -> List[Dict]:
        """Return summaries (id/title/created_at/updated_at) sorted by updated_at desc."""
        summaries = []
        for path in self.base_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            summaries.append({
                "id": data.get("id", path.stem),
                "title": data.get("title", ""),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
            })
        summaries.sort(key=lambda s: s["updated_at"], reverse=True)
        return summaries

    def delete(self, session_id: str) -> None:
        """Remove the session file. No-op if not found."""
        path = self._path(session_id)
        if path.exists():
            path.unlink()
