"""
Simulation IPC Communication Module
Used for inter-process communication between Flask backend and simulation scripts

Implements a simple command/response pattern via the filesystem:
1. Flask writes commands to the commands/ directory
2. The simulation script polls the commands directory, executes commands, and writes responses to the responses/ directory
3. Flask polls the responses directory to obtain results
"""

import os
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger('miroshark.simulation_ipc')


class CommandType(str, Enum):
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"


class CommandStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IPCCommand:
    command_id: str
    command_type: CommandType
    args: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "args": self.args,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCCommand':
        return cls(
            command_id=data["command_id"],
            command_type=CommandType(data["command_type"]),
            args=data.get("args", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class IPCResponse:
    command_id: str
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCResponse':
        return cls(
            command_id=data["command_id"],
            status=CommandStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


class SimulationIPCClient:
    """
    Simulation IPC Client (used by the Flask side)

    Used to send commands to the simulation process and wait for responses
    """

    def __init__(self, simulation_dir: str):
        """
        Initialize IPC client

        Args:
            simulation_dir: Simulation data directory
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")

        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def send_command(
        self,
        command_type: CommandType,
        args: Dict[str, Any],
        timeout: float = 60.0,
        poll_interval: float = 0.5
    ) -> IPCResponse:
        """
        Send a command and wait for a response

        Args:
            command_type: Command type
            args: Command arguments
            timeout: Timeout in seconds
            poll_interval: Polling interval in seconds

        Returns:
            IPCResponse

        Raises:
            TimeoutError: Response wait timed out
        """
        command_id = str(uuid.uuid4())
        command = IPCCommand(
            command_id=command_id,
            command_type=command_type,
            args=args
        )
        
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        with open(command_file, 'w', encoding='utf-8') as f:
            json.dump(command.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Sent IPC command: {command_type.value}, command_id={command_id}")

        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r', encoding='utf-8') as f:
                        response_data = json.load(f)
                    response = IPCResponse.from_dict(response_data)

                    try:
                        os.remove(command_file)
                        os.remove(response_file)
                    except OSError:
                        pass
                    
                    logger.info(f"Received IPC response: command_id={command_id}, status={response.status.value}")
                    return response
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse response: {e}")
            
            time.sleep(poll_interval)

        logger.error(f"Timed out waiting for IPC response: command_id={command_id}")

        try:
            os.remove(command_file)
        except OSError:
            pass
        
        raise TimeoutError(f"Timed out waiting for command response ({timeout}s)")
    
    def send_interview(
        self,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> IPCResponse:
        """
        Send a single agent interview command

        Args:
            agent_id: Agent ID
            prompt: Interview question
            platform: Specify platform (optional)
                - "twitter": Interview on Twitter platform only
                - "reddit": Interview on Reddit platform only
                - None: Interview both platforms in dual-platform mode, or the active platform in single-platform mode
            timeout: Timeout in seconds

        Returns:
            IPCResponse with interview result in the result field
        """
        args = {
            "agent_id": agent_id,
            "prompt": prompt
        }
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_batch_interview(
        self,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> IPCResponse:
        """
        Send a batch interview command

        Args:
            interviews: Interview list, each element contains {"agent_id": int, "prompt": str, "platform": str (optional)}
            platform: Default platform (optional, overridden by each interview item's platform)
                - "twitter": Default to interviewing on Twitter platform only
                - "reddit": Default to interviewing on Reddit platform only
                - None: Interview each agent on both platforms in dual-platform mode
            timeout: Timeout in seconds

        Returns:
            IPCResponse with all interview results in the result field
        """
        args = {"interviews": interviews}
        if platform:
            args["platform"] = platform
            
        return self.send_command(
            command_type=CommandType.BATCH_INTERVIEW,
            args=args,
            timeout=timeout
        )
    
    def send_close_env(self, timeout: float = 30.0) -> IPCResponse:
        """
        Send a close environment command

        Args:
            timeout: Timeout in seconds

        Returns:
            IPCResponse
        """
        return self.send_command(
            command_type=CommandType.CLOSE_ENV,
            args={},
            timeout=timeout
        )
    
    def check_env_alive(self) -> bool:
        """
        Check whether the simulation environment is alive

        Checks the env_status.json file and verifies the PID is still running.
        """
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        if not os.path.exists(status_file):
            return False

        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            pid = status.get("pid")
            if status.get("status") != "alive":
                # Status says not alive — but check if the process is actually
                # running (handles race where old process overwrites new status)
                if pid:
                    try:
                        os.kill(pid, 0)  # signal 0 = check if process exists
                        return False  # PID exists but status is stopped — trust it
                    except OSError:
                        pass  # PID is dead
                return False
            # Status says "alive" — verify the PID is still running to catch
            # the case where the worker crashed after writing the status file.
            if pid:
                try:
                    os.kill(pid, 0)
                except OSError:
                    return False  # PID is gone — stale "alive" status
            return True
        except (json.JSONDecodeError, OSError):
            return False
