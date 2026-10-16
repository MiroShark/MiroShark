"""OpenRouter Broadcast fields for Wonderwall agent calls.

Spec: https://openrouter.ai/docs/guides/features/broadcast/langfuse
OpenRouter forwards exactly three top-level request keys to Langfuse:
``user`` (Langfuse userId), ``session_id`` (Langfuse sessionId) and
``trace`` (documented keys such as ``trace_id``, ``trace_name``,
``span_name``, ``generation_name`` and ``environment`` become first-class
fields; any other key becomes filterable trace metadata). Top-level
``metadata``, ``tags`` and ``name`` are dropped at the Broadcast boundary,
so they are never sent.

Kept stdlib-only and outside the ``wonderwall`` package so the offline
unit-test job (no camel-ai) can import it. Mirrors the trace block that
``app/utils/llm_client.py`` sends for the backend's own calls.
"""

from typing import Any, Dict, Mapping, Optional

# Keys older code put in extra_body that Broadcast silently drops.
DROPPED_KEYS = ("metadata", "tags", "name")


def _round_from_env(value: str) -> Optional[int]:
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def wonderwall_broadcast_fields(
    env: Mapping[str, str],
    agent_name: str = "",
    agent_id: Any = None,
) -> Dict[str, Any]:
    """The ``user`` / ``session_id`` / ``trace`` keys for one agent turn.

    ``env`` is the subprocess environment (``MIROSHARK_SIMULATION_ID``,
    ``MIROSHARK_RUN_ID``, ``MIROSHARK_ROUND_NUM``). ``user`` and
    ``session_id`` are only set when a simulation id is known.
    """
    sim_id = env.get("MIROSHARK_SIMULATION_ID", "") or ""
    run_id = env.get("MIROSHARK_RUN_ID", "") or ""
    prompt_type = "agent_action"
    sim_phase = "round"
    agent_name = str(agent_name or "")[:64]

    trace = {
        "trace_id": run_id or sim_id or None,
        "trace_name": "MiroShark Run" if run_id else "MiroShark Call",
        "span_name": sim_phase,
        "generation_name": prompt_type,
        "environment": "miroshark",
        # Free-form keys: Langfuse trace metadata (filterable).
        "source": "miroshark",
        "run_id": run_id or None,
        "simulation_id": sim_id or None,
        "caller": "SocialAgent.perform_action_by_llm",
        "prompt_type": prompt_type,
        "sim_phase": sim_phase,
        "agent_name": agent_name or None,
        "agent_id": str(agent_id) if agent_id not in (None, "") else None,
        "round": _round_from_env(env.get("MIROSHARK_ROUND_NUM", "") or ""),
    }
    fields: Dict[str, Any] = {
        "trace": {k: v for k, v in trace.items() if v not in ("", None)},
    }
    if sim_id:
        fields["user"] = sim_id
        fields["session_id"] = sim_id
    return fields


def apply_wonderwall_broadcast(
    extra_body: Optional[Dict[str, Any]],
    env: Mapping[str, str],
    agent_name: str = "",
    agent_id: Any = None,
) -> Dict[str, Any]:
    """Set the Broadcast keys on an ``extra_body`` dict and return it.

    Drops the stale ``metadata`` / ``tags`` / ``name`` keys, and a stale
    ``user`` / ``session_id`` from an earlier simulation when this one has
    no simulation id. Other keys (``provider``, ``reasoning``, ...) stay.
    """
    extra = dict(extra_body or {})
    for key in DROPPED_KEYS + ("user", "session_id"):
        extra.pop(key, None)
    extra.update(wonderwall_broadcast_fields(env, agent_name, agent_id))
    return extra
