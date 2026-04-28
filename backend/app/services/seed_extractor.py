"""
Seed extractor: drives one turn of the seed-chat conversation.

Each call sends the full message history + current slot state to the LLM and
expects a single JSON envelope: {reply, slots, ready}. The backend re-checks
required slots so a hallucinated `ready=True` from the LLM cannot launch
an under-specified pipeline.
"""

import subprocess
from typing import Dict, List, Tuple

from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger

logger = get_logger("miroshark.seed_extractor")

REQUIRED_SLOTS = ("topic", "intent", "output_format")
REQUIRED_LIST_SLOTS = ("stakeholders",)
MIN_STAKEHOLDERS = 2

EMPTY_STATE: Dict = {
    "topic": "",
    "intent": "",
    "stakeholders": [],
    "decision_branches": [],
    "contested_claims": [],
    "output_format": "",
}

SYSTEM_PROMPT = """You are MiroShark's seed-chat assistant. Your job is to help the user
turn a vague research question into a structured "seed" that drives a downstream
research and simulation pipeline.

You must return a single JSON object with exactly these keys:

{
  "reply": "string — your next message to the user",
  "slots": {
    "topic": "string — the issue/question being investigated",
    "intent": "string — what the user wants out of this (e.g., pros/cons brief, decision memo)",
    "stakeholders": [{"name": "string", "role": "string", "stance": "supporting|opposing|neutral|unknown"}],
    "decision_branches": [{"label": "string", "description": "string"}],
    "contested_claims": ["string — a claim worth investigating"],
    "output_format": "pros_cons | decision_memo | executive_summary | full_report"
  },
  "ready": true | false
}

Rules:
- Required slots: topic, intent, stakeholders (at least 2), output_format.
- decision_branches and contested_claims are optional. Leave empty arrays if not applicable. Do NOT invent.
- Each turn, re-emit the FULL slots object — fill what you can, preserve what was already there.
- Set ready=true only when required slots are populated AND the user has confirmed they're done refining.
- Ask one targeted question per turn, prioritising the most consequential missing slot.
- Be concise. The reply field is shown verbatim to the user.

If the user pushes back on a suggestion, accept their version and update slots accordingly.
"""


def _required_slots_filled(slots: Dict) -> bool:
    for key in REQUIRED_SLOTS:
        if not slots.get(key):
            return False
    if len(slots.get("stakeholders", [])) < MIN_STAKEHOLDERS:
        return False
    return True


def _normalise_slots(slots: Dict) -> Dict:
    """Ensure all expected keys exist; fill missing with empty defaults."""
    normalised = dict(EMPTY_STATE)
    for key in EMPTY_STATE:
        if key in slots:
            normalised[key] = slots[key]
    return normalised


def process_turn(
    messages: List[Dict[str, str]],
    current_state: Dict,
) -> Tuple[str, Dict, bool]:
    """
    Run one Q&A turn.

    Args:
        messages: full chat history as [{"role": "user"|"assistant", "content": str}, ...]
        current_state: prior slot state (so the LLM can re-emit it intact)

    Returns:
        (assistant_reply, updated_slots, ready_to_launch)
    """
    llm = create_llm_client()

    state_summary = (
        "Current slot state (re-emit and update):\n"
        + str(current_state)
    )
    full_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": state_summary},
        *messages,
    ]

    try:
        envelope = llm.chat_json(messages=full_messages)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("seed_extractor: malformed LLM response (%s); preserving state", exc)
        return (
            "Sorry — I had trouble parsing my own response. Could you say that again, or rephrase?",
            current_state,
            False,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error("seed_extractor: Claude CLI timed out (%s)", exc)
        raise RuntimeError("claude_cli_timeout") from exc

    reply = envelope.get("reply", "").strip()
    slots = _normalise_slots(envelope.get("slots", {}))
    llm_ready = bool(envelope.get("ready", False))

    ready = llm_ready and _required_slots_filled(slots)

    if not reply:
        reply = "(no response — please continue)"

    return reply, slots, ready
