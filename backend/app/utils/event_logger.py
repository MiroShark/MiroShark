"""
Unified event logger for MiroShark observability.

Writes structured JSONL events to:
  - backend/logs/events.jsonl  (global, Flask-process events)
  - {sim_dir}/events.jsonl     (per-simulation, including subprocess events)

Non-blocking: emit() enqueues to a background writer thread.
SSE support: subscribers get notified of new events via threading.Event.

Env vars:
  MIROSHARK_LOG_PROMPTS  — log full LLM prompts/responses (default: false)
  MIROSHARK_LOG_LEVEL    — debug|info|warn (default: info)
"""

import json
import os
import threading
import uuid
from collections import deque
from datetime import datetime
from queue import Queue, Empty
from typing import Any, Dict, List, Optional, Set

from .trace_context import TraceContext

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LOG_PROMPTS = os.environ.get('MIROSHARK_LOG_PROMPTS', 'false').lower() == 'true'
LOG_LEVEL = os.environ.get('MIROSHARK_LOG_LEVEL', 'info').lower()

_LEVEL_RANK = {'debug': 0, 'info': 1, 'warn': 2}

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def should_log(level: str) -> bool:
    return _LEVEL_RANK.get(level, 1) >= _LEVEL_RANK.get(LOG_LEVEL, 1)


def _build_event(
    event_type: str,
    data: Dict[str, Any],
    *,
    simulation_id: Optional[str] = None,
    round_num: Optional[int] = None,
    agent_id: Optional[int] = None,
    agent_name: Optional[str] = None,
    platform: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble one structured event dict (fresh id + UTC millisecond timestamp).

    Single source of truth for the on-disk event shape — both the
    standalone subprocess writer and the in-process ``EventLogger.emit``
    serialize the dict this returns, so the JSONL schema stays identical
    across both paths.
    """
    return {
        'event_id': f'evt_{uuid.uuid4().hex[:12]}',
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(timespec='milliseconds') + 'Z',
        'simulation_id': simulation_id,
        'trace_id': trace_id,
        'round_num': round_num,
        'agent_id': agent_id,
        'agent_name': agent_name,
        'platform': platform,
        'data': data,
    }


# ---------------------------------------------------------------------------
# Standalone helper for subprocess usage (no singleton, no SSE bus)
# ---------------------------------------------------------------------------
def write_simulation_event(
    sim_dir: str,
    event_type: str,
    data: Dict[str, Any],
    *,
    simulation_id: Optional[str] = None,
    round_num: Optional[int] = None,
    agent_id: Optional[int] = None,
    agent_name: Optional[str] = None,
    platform: Optional[str] = None,
    trace_id: Optional[str] = None,
    level: str = 'info',
) -> None:
    """Append one event to {sim_dir}/events.jsonl.  Safe to call from any process."""
    if not should_log(level):
        return

    event = _build_event(
        event_type,
        data,
        simulation_id=simulation_id,
        round_num=round_num,
        agent_id=agent_id,
        agent_name=agent_name,
        platform=platform,
        trace_id=trace_id,
    )

    path = os.path.join(sim_dir, 'events.jsonl')
    os.makedirs(sim_dir, exist_ok=True)
    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + '\n')
    except Exception:
        pass  # never break the simulation for a logging failure


# ---------------------------------------------------------------------------
# EventLogger singleton (Flask process)
# ---------------------------------------------------------------------------
class EventLogger:
    """Non-blocking JSONL event logger with SSE subscriber support."""

    _instance: Optional['EventLogger'] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._initialized = False
                cls._instance = inst
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        os.makedirs(LOG_DIR, exist_ok=True)
        self._global_path = os.path.join(LOG_DIR, 'events.jsonl')
        self._queue: Queue = Queue(maxsize=10_000)
        self._ring: deque = deque(maxlen=2000)

        # SSE subscriber management
        self._subscribers: List[_Subscriber] = []
        self._sub_lock = threading.Lock()

        # Start background writer
        self._writer = threading.Thread(target=self._write_loop, daemon=True)
        self._writer.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def emit(
        self,
        event_type: str,
        data: Dict[str, Any],
        *,
        simulation_id: Optional[str] = None,
        round_num: Optional[int] = None,
        agent_id: Optional[int] = None,
        agent_name: Optional[str] = None,
        platform: Optional[str] = None,
        trace_id: Optional[str] = None,
        level: str = 'info',
    ) -> None:
        """Enqueue an event (non-blocking)."""
        if not should_log(level):
            return

        # Auto-fill from TraceContext if not explicitly provided
        ctx = TraceContext.get_all()
        simulation_id = simulation_id or ctx.get('simulation_id')
        round_num = round_num if round_num is not None else ctx.get('round_num')
        agent_id = agent_id if agent_id is not None else ctx.get('agent_id')
        agent_name = agent_name or ctx.get('agent_name')
        platform = platform or ctx.get('platform')
        trace_id = trace_id or ctx.get('trace_id')

        event = _build_event(
            event_type,
            data,
            simulation_id=simulation_id,
            round_num=round_num,
            agent_id=agent_id,
            agent_name=agent_name,
            platform=platform,
            trace_id=trace_id,
        )

        try:
            self._queue.put_nowait(event)
        except Exception:
            pass  # drop on overflow rather than block

    def subscribe(
        self,
        simulation_id: Optional[str] = None,
        event_types: Optional[Set[str]] = None,
    ) -> '_Subscriber':
        """Create a new SSE subscriber. Returns a _Subscriber with a poll() method."""
        sub = _Subscriber(simulation_id=simulation_id, event_types=event_types)
        with self._sub_lock:
            self._subscribers.append(sub)
        return sub

    def unsubscribe(self, sub: '_Subscriber') -> None:
        with self._sub_lock:
            try:
                self._subscribers.remove(sub)
            except ValueError:
                pass

    def get_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the last N events from the ring buffer."""
        items = list(self._ring)
        return items[-limit:]

    # ------------------------------------------------------------------
    # Background writer
    # ------------------------------------------------------------------

    def _write_loop(self):
        while True:
            try:
                event = self._queue.get(timeout=1.0)
            except Empty:
                continue

            # Write to global JSONL
            line = json.dumps(event, ensure_ascii=False, default=str) + '\n'
            try:
                with open(self._global_path, 'a', encoding='utf-8') as f:
                    f.write(line)
            except Exception:
                pass

            # Also write to simulation-specific file if applicable
            sim_id = event.get('simulation_id')
            if sim_id:
                sim_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    'uploads', 'simulations', sim_id,
                )
                try:
                    os.makedirs(sim_dir, exist_ok=True)
                    with open(os.path.join(sim_dir, 'events.jsonl'), 'a', encoding='utf-8') as f:
                        f.write(line)
                except Exception:
                    pass

            # Push to ring buffer + notify subscribers
            self._ring.append(event)
            with self._sub_lock:
                dead = []
                for sub in self._subscribers:
                    if not sub.alive:
                        dead.append(sub)
                        continue
                    sub._push(event)
                for d in dead:
                    try:
                        self._subscribers.remove(d)
                    except ValueError:
                        pass


# ---------------------------------------------------------------------------
# SSE Subscriber
# ---------------------------------------------------------------------------
class _Subscriber:
    """Per-connection event buffer with optional filters."""

    def __init__(
        self,
        simulation_id: Optional[str] = None,
        event_types: Optional[Set[str]] = None,
    ):
        self.simulation_id = simulation_id
        self.event_types = event_types
        self._buffer: deque = deque(maxlen=5000)
        self._event = threading.Event()
        self.alive = True

    def _push(self, event: Dict[str, Any]) -> None:
        """Called by EventLogger writer thread."""
        if self.simulation_id and event.get('simulation_id') != self.simulation_id:
            return
        if self.event_types and event.get('event_type') not in self.event_types:
            return
        self._buffer.append(event)
        self._event.set()

    def poll(self, timeout: float = 1.0) -> List[Dict[str, Any]]:
        """Wait up to timeout seconds, then drain all buffered events."""
        self._event.wait(timeout=timeout)
        self._event.clear()
        events = []
        while self._buffer:
            try:
                events.append(self._buffer.popleft())
            except IndexError:
                break
        return events

    def close(self) -> None:
        self.alive = False
        self._event.set()


# ---------------------------------------------------------------------------
# FileTailer — reads new lines from a JSONL file (for subprocess events)
# ---------------------------------------------------------------------------
class FileTailer:
    """Tail a JSONL file from last-read position. Thread-safe."""

    def __init__(self, path: str):
        self.path = path
        self._pos = 0

    def read_new_lines(self) -> List[str]:
        """Return complete lines appended since last call."""
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                f.seek(self._pos)
                raw = f.read()
                self._pos = f.tell()
        except Exception:
            return []

        lines = []
        for line in raw.split('\n'):
            line = line.strip()
            if line:
                lines.append(line)
        return lines

    def read_new_events(self) -> List[Dict[str, Any]]:
        """Return parsed events from new lines."""
        events = []
        for line in self.read_new_lines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return events
