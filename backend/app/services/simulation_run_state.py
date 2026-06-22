"""Real-time simulation run-state types.

Leaf module (stdlib only) holding the runner's status enum and run-state
dataclasses. Kept import-free so the notification/webhook dispatchers can
reference SimulationRunState without importing the heavy simulation_runner
module — which would otherwise form a runtime import cycle.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional


class RunnerStatus(str, Enum):
    """Runner status"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Agent action record"""
    round_num: int
    timestamp: str
    platform: str  # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str  # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "platform": self.platform,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "result": self.result,
            "success": self.success,
        }


@dataclass
class RoundSummary:
    """Per-round summary"""
    round_num: int
    start_time: str
    end_time: Optional[str] = None
    simulated_hour: int = 0
    twitter_actions: int = 0
    reddit_actions: int = 0
    active_agents: List[int] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "simulated_hour": self.simulated_hour,
            "twitter_actions": self.twitter_actions,
            "reddit_actions": self.reddit_actions,
            "active_agents": self.active_agents,
            "actions_count": len(self.actions),
            "actions": [a.to_dict() for a in self.actions],
        }


@dataclass
class SimulationRunState:
    """Simulation run state (real-time)"""
    simulation_id: str
    runner_status: RunnerStatus = RunnerStatus.IDLE

    # Progress info
    current_round: int = 0
    total_rounds: int = 0
    simulated_hours: int = 0
    total_simulation_hours: int = 0

    # Per-platform independent rounds and simulated time (for multi-platform parallel display)
    twitter_current_round: int = 0
    reddit_current_round: int = 0
    polymarket_current_round: int = 0
    twitter_simulated_hours: int = 0
    reddit_simulated_hours: int = 0
    polymarket_simulated_hours: int = 0

    # Platform status
    twitter_running: bool = False
    reddit_running: bool = False
    polymarket_running: bool = False
    twitter_actions_count: int = 0
    reddit_actions_count: int = 0
    polymarket_actions_count: int = 0

    # Platform completion status (detected via simulation_end events in actions.jsonl)
    twitter_completed: bool = False
    reddit_completed: bool = False
    polymarket_completed: bool = False

    # Per-round summaries
    rounds: List[RoundSummary] = field(default_factory=list)

    # Recent actions (for frontend real-time display)
    recent_actions: List[AgentAction] = field(default_factory=list)
    max_recent_actions: int = 50

    # Timestamps
    started_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    # Error info
    error: Optional[str] = None

    # Process ID (for stopping)
    process_pid: Optional[int] = None

    def add_action(self, action: AgentAction):
        """Add action to recent actions list"""
        self.recent_actions.insert(0, action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[:self.max_recent_actions]

        if action.platform == "twitter":
            self.twitter_actions_count += 1
        elif action.platform == "reddit":
            self.reddit_actions_count += 1
        elif action.platform == "polymarket":
            self.polymarket_actions_count += 1

        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "runner_status": self.runner_status.value,
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "simulated_hours": self.simulated_hours,
            "total_simulation_hours": self.total_simulation_hours,
            "progress_percent": round(self.current_round / max(self.total_rounds, 1) * 100, 1),
            # Per-platform independent rounds and time
            "twitter_current_round": self.twitter_current_round,
            "reddit_current_round": self.reddit_current_round,
            "polymarket_current_round": self.polymarket_current_round,
            "twitter_simulated_hours": self.twitter_simulated_hours,
            "reddit_simulated_hours": self.reddit_simulated_hours,
            "polymarket_simulated_hours": self.polymarket_simulated_hours,
            "twitter_running": self.twitter_running,
            "reddit_running": self.reddit_running,
            "polymarket_running": self.polymarket_running,
            "twitter_completed": self.twitter_completed,
            "reddit_completed": self.reddit_completed,
            "polymarket_completed": self.polymarket_completed,
            "twitter_actions_count": self.twitter_actions_count,
            "reddit_actions_count": self.reddit_actions_count,
            "polymarket_actions_count": self.polymarket_actions_count,
            "total_actions_count": self.twitter_actions_count + self.reddit_actions_count + self.polymarket_actions_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "process_pid": self.process_pid,
        }

    def to_detail_dict(self) -> Dict[str, Any]:
        """Detailed info including recent actions"""
        result = self.to_dict()
        result["recent_actions"] = [a.to_dict() for a in self.recent_actions]
        result["rounds_count"] = len(self.rounds)
        return result
