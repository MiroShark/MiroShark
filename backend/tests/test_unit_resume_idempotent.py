"""Unit tests for resuming a simulation on top of its existing DBs (#322).

Covers:

  1. Every Wonderwall schema file is idempotent: running all of a
     platform's schemas twice on the same SQLite file raises nothing and
     keeps the rows written in between (a resume re-runs the schemas).
  2. ``PolymarketPlatform`` (which goes through ``BasePlatform._init_db``)
     can be initialised twice on the same DB file. Needs the full
     wonderwall deps (camel, torch), so it is skipped in the thin CI job.
  3. A resumed run state is seeded with the prior round progress instead
     of zero, so a resume that fails early keeps its progress.
  4. ``POST /api/simulation/start`` with ``resume=true`` and no completed
     rounds returns 409 instead of silently starting fresh (which would
     delete the platform DBs).

Pure offline: no Neo4j, no LLM, no subprocess.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_WONDERWALL = _BACKEND / "wonderwall"
_SCHEMA_DIRS = sorted(p for p in _WONDERWALL.rglob("schema") if p.is_dir())
_CREATE_RE = re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?(TABLE|INDEX)\b(?!\s+IF\s+NOT\s+EXISTS)", re.I)


# ── 1. Schema files are idempotent ───────────────────────────────────────


def test_schema_dirs_found():
    assert len(_SCHEMA_DIRS) >= 3, _SCHEMA_DIRS


@pytest.mark.parametrize("schema_file", sorted(_WONDERWALL.rglob("schema/*.sql")), ids=str)
def test_schema_file_uses_if_not_exists(schema_file: Path):
    sql = schema_file.read_text(encoding="utf-8")
    assert not _CREATE_RE.search(sql), f"{schema_file} has a CREATE without IF NOT EXISTS"


def _apply_schemas(db_path: Path, files: list[Path]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        for f in files:
            conn.executescript(f.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize("schema_dir", _SCHEMA_DIRS, ids=lambda p: str(p.relative_to(_WONDERWALL)))
def test_schemas_apply_twice_on_same_db(schema_dir: Path, tmp_path: Path):
    files = sorted(schema_dir.glob("*.sql"))
    # Polymarket loads the core social user/trace schemas first.
    if schema_dir.parent.name == "polymarket":
        core = _WONDERWALL / "social_platform" / "schema"
        files = [core / "user.sql", core / "trace.sql", *files]
    db = tmp_path / "sim.db"

    _apply_schemas(db, files)
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.execute("INSERT INTO user (user_id, agent_id) VALUES (1, 1)")
    conn.commit()
    conn.close()

    # Second pass = what a resume does. Must not raise or drop data.
    _apply_schemas(db, files)
    conn = sqlite3.connect(db)
    assert {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} == tables
    assert conn.execute("SELECT COUNT(*) FROM user").fetchone()[0] == 1
    conn.close()


# ── 2. BasePlatform init twice (needs camel) ─────────────────────────────


def test_polymarket_platform_init_twice(tmp_path: Path):
    try:
        from wonderwall.simulations.polymarket.platform import PolymarketPlatform
    except ImportError as exc:  # thin CI env: no camel / torch
        pytest.skip(f"wonderwall deps not installed: {exc}")

    db = str(tmp_path / "polymarket_simulation.db")
    first = PolymarketPlatform(db_path=db)
    first.db.execute("INSERT INTO user (user_id, agent_id) VALUES (7, 7)")
    first.db.commit()
    first.db.close()

    second = PolymarketPlatform(db_path=db)  # raised "table user already exists" before
    assert second.db.execute("SELECT COUNT(*) FROM user").fetchone()[0] == 1
    second.db.close()


# ── 3. Resumed run state keeps prior progress ────────────────────────────


def test_seed_resumed_progress_carries_rounds():
    from app.services.simulation_runner import SimulationRunner
    from app.services.simulation_run_state import RunnerStatus, SimulationRunState

    previous = SimulationRunState(
        simulation_id="sim_abc",
        runner_status=RunnerStatus.STOPPED,
        current_round=21,
        simulated_hours=10,
        twitter_current_round=21,
        reddit_current_round=20,
        polymarket_current_round=19,
        twitter_actions_count=300,
    )
    state = SimulationRunState(simulation_id="sim_abc", runner_status=RunnerStatus.STARTING)

    SimulationRunner._seed_resumed_progress(state, previous, 21)

    assert state.current_round == 21
    assert state.simulated_hours == 10
    assert (state.twitter_current_round, state.reddit_current_round, state.polymarket_current_round) == (21, 20, 19)
    assert state.twitter_actions_count == 300


def test_seed_resumed_progress_without_previous_state():
    from app.services.simulation_runner import SimulationRunner
    from app.services.simulation_run_state import SimulationRunState

    state = SimulationRunState(simulation_id="sim_abc")
    SimulationRunner._seed_resumed_progress(state, None, 5)
    assert state.current_round == 5


# ── 4. resume=true with nothing to resume is a 409 ───────────────────────


@pytest.fixture
def start_client(monkeypatch):
    from flask import Flask

    from app.api import simulation_bp
    from app.services.simulation_runner import SimulationRunner

    started = []
    monkeypatch.setattr(
        SimulationRunner, "start_simulation",
        classmethod(lambda cls, **kw: started.append(kw)),
    )
    app = Flask(__name__)
    app.register_blueprint(simulation_bp, url_prefix="/api/simulation")
    client = app.test_client()
    client.started = started
    return client


@pytest.mark.parametrize("current_round", [None, 0])
def test_resume_without_progress_returns_409(start_client, monkeypatch, current_round):
    from app.services.simulation_runner import SimulationRunner
    from app.services.simulation_run_state import RunnerStatus, SimulationRunState

    state = None
    if current_round is not None:
        state = SimulationRunState(
            simulation_id="sim_abc", runner_status=RunnerStatus.FAILED, current_round=current_round
        )
    monkeypatch.setattr(SimulationRunner, "get_run_state", classmethod(lambda cls, sid: state))

    resp = start_client.post(
        "/api/simulation/start", json={"simulation_id": "sim_abc", "resume": True, "force": True}
    )

    assert resp.status_code == 409
    body = resp.get_json()
    assert body["success"] is False
    assert "resume" in body["error"].lower()
    assert start_client.started == []
