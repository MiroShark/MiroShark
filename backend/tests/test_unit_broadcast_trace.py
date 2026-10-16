"""Wonderwall agent calls send OpenRouter Broadcast fields in the shape it keeps.

Broadcast (https://openrouter.ai/docs/guides/features/broadcast/langfuse)
forwards only top-level ``user``, ``session_id`` and ``trace`` to Langfuse.
The agent used to send ``metadata`` / ``tags`` / ``name`` (all dropped) and
put the simulation id in ``user`` only, so Langfuse rows had no session.
"""

from __future__ import annotations

from app.utils.broadcast_trace import (
    apply_wonderwall_broadcast,
    wonderwall_broadcast_fields,
)

ENV = {
    "MIROSHARK_SIMULATION_ID": "sim_abc",
    "MIROSHARK_RUN_ID": "run_123",
    "MIROSHARK_ROUND_NUM": "4",
}


def test_sets_only_the_keys_broadcast_forwards():
    fields = wonderwall_broadcast_fields(ENV, agent_name="Alice", agent_id=7)
    assert set(fields) == {"user", "session_id", "trace"}
    assert fields["user"] == "sim_abc"
    assert fields["session_id"] == "sim_abc"


def test_trace_block_uses_documented_keys_and_metadata():
    trace = wonderwall_broadcast_fields(ENV, agent_name="Alice", agent_id=7)["trace"]
    assert trace["trace_id"] == "run_123"
    assert trace["trace_name"] == "MiroShark Run"
    assert trace["span_name"] == "round"
    assert trace["generation_name"] == "agent_action"
    assert trace["environment"] == "miroshark"
    assert trace["simulation_id"] == "sim_abc"
    assert trace["agent_name"] == "Alice"
    assert trace["agent_id"] == "7"
    assert trace["round"] == 4


def test_agent_id_zero_is_kept():
    trace = wonderwall_broadcast_fields(ENV, agent_id=0)["trace"]
    assert trace["agent_id"] == "0"


def test_no_simulation_id_means_no_user_or_session():
    fields = wonderwall_broadcast_fields({}, agent_name="")
    assert set(fields) == {"trace"}
    trace = fields["trace"]
    assert trace["trace_name"] == "MiroShark Call"
    assert "trace_id" not in trace
    assert "round" not in trace
    assert all(v not in ("", None) for v in trace.values())


def test_bad_round_is_dropped():
    trace = wonderwall_broadcast_fields({**ENV, "MIROSHARK_ROUND_NUM": "x"})["trace"]
    assert "round" not in trace


def test_long_agent_name_is_capped():
    trace = wonderwall_broadcast_fields(ENV, agent_name="n" * 200)["trace"]
    assert len(trace["agent_name"]) == 64


def test_apply_drops_fields_broadcast_ignores_and_keeps_routing():
    old = {
        "metadata": {"caller": "x"},
        "tags": ["miroshark"],
        "name": "agent_action",
        "user": "old_sim",
        "session_id": "old_sim",
        "provider": {"order": ["Together"]},
        "reasoning": {"enabled": False},
    }
    out = apply_wonderwall_broadcast(old, {}, agent_name="Bob")
    for key in ("metadata", "tags", "name", "user", "session_id"):
        assert key not in out
    assert out["provider"] == {"order": ["Together"]}
    assert out["reasoning"] == {"enabled": False}
    assert out["trace"]["agent_name"] == "Bob"
    # the caller's dict is not changed in place
    assert old["tags"] == ["miroshark"]


def test_apply_handles_missing_extra_body():
    out = apply_wonderwall_broadcast(None, ENV)
    assert out["session_id"] == "sim_abc"
