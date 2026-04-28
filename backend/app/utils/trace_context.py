"""
Thread-local trace context for correlating events across call stacks.

Usage:
    TraceContext.set(simulation_id="sim_abc", round_num=5, agent_id=3)
    # ... deep in the call stack, llm_client reads this automatically:
    sim_id = TraceContext.get("simulation_id")
    TraceContext.clear()

Thread-pool caveat: Python's ``threading.local`` doesn't propagate across
``ThreadPoolExecutor`` worker threads. For Langfuse correlation to survive
work spawned inside a pool, the caller must either explicitly snapshot+
restore or use the ``wrap_fn`` helper below, which captures the parent
thread's context and re-applies it inside the worker.
"""

import functools
import threading
import uuid
from typing import Callable

_context = threading.local()


class TraceContext:
    """Thread-local storage for correlation fields."""

    @staticmethod
    def set(**kwargs):
        """Set one or more context fields (simulation_id, round_num, agent_id, agent_name, platform, trace_id, run_id, sim_phase, prompt_type)."""
        for k, v in kwargs.items():
            setattr(_context, k, v)

    @staticmethod
    def get(key, default=None):
        """Read a context field."""
        return getattr(_context, key, default)

    @staticmethod
    def get_all():
        """Return all context fields as a dict."""
        return {k: v for k, v in _context.__dict__.items() if not k.startswith('_')}

    @staticmethod
    def new_trace():
        """Generate and set a new trace_id, returning it."""
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        _context.trace_id = trace_id
        return trace_id

    @staticmethod
    def clear():
        """Remove all context fields."""
        _context.__dict__.clear()

    @staticmethod
    def wrap_fn(fn: Callable) -> Callable:
        """Snapshot the caller's context; restore it in the wrapped fn.

        Use this when submitting to a ThreadPoolExecutor so that child
        threads inherit ``simulation_id`` / ``sim_phase`` / etc. for
        Langfuse correlation. Example:

            snapshot_fn = TraceContext.wrap_fn(_process_chunk)
            executor.submit(snapshot_fn, chunk_idx, chunk)

        The wrapper overwrites the worker thread's existing context —
        thread-pool threads are reused, so stale context from a previous
        task would otherwise leak into the next.
        """
        snapshot = TraceContext.get_all()

        @functools.wraps(fn)
        def _wrapped(*args, **kwargs):
            _context.__dict__.clear()
            for k, v in snapshot.items():
                setattr(_context, k, v)
            return fn(*args, **kwargs)

        return _wrapped
