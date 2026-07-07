"""Message and tool-call sanitation for OpenAI-compatible chat calls.

Kept dependency-free (stdlib only) and outside the ``wonderwall``
package so the offline unit-test job — which does not install camel-ai/numpy
— can exercise it without importing the wonderwall package's heavy runtime
chain (see ``wonderwall/__init__.py`` -> ``recsys.py`` -> numpy).
"""

import json
from typing import Any, Dict, List, Optional, Tuple


def filter_openai_messages_for_api(
    openai_messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Prepare CAMEL memory messages for an OpenAI-compatible chat call.

    Gemini rejects assistant/user turns whose ``content`` is empty
    (INVALID_ARGUMENT).  Drop those, but **keep** assistant turns that only
    carry ``tool_calls`` (empty content is normal) and their ``tool`` /
    ``function`` results — Azure returns 400 if a ``tool`` message is not
    immediately preceded by an assistant message with ``tool_calls``.
    """
    filtered: List[Dict[str, Any]] = []
    for msg in openai_messages:
        content = msg.get("content")
        has_content = content is not None and str(content).strip()
        role = msg.get("role")
        if has_content:
            filtered.append(msg)
        elif role == "assistant" and msg.get("tool_calls"):
            filtered.append(msg)
        elif role in ("tool", "function"):
            filtered.append(msg)
    if not filtered:
        filtered = [{"role": "user", "content": "(empty context)"}]
    return filtered


def repair_tool_call_arguments(arguments: str) -> Optional[Tuple[str, str]]:
    """Repair a malformed tool_call ``arguments`` JSON string.

    Some providers (observed on DeepSeek-V4-Flash) reliably append stray
    trailing data after an otherwise-valid JSON value — e.g. ``'{}""'`` for a
    zero-arg tool call. CAMEL's ``json.loads`` has no tolerance for that, so
    keep only the first valid JSON value and drop the trailing garbage.

    Returns ``(repaired_json, dropped_suffix)`` when ``arguments`` begins with
    a valid JSON value followed by extra data. Returns ``None`` when the
    arguments are already valid (nothing to do) or are not recoverable this
    way (let the caller's ``json.loads`` raise on it as before).
    """
    try:
        json.loads(arguments)
        return None  # already valid — nothing to repair
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        obj, end = json.JSONDecoder().raw_decode(arguments)
    except (json.JSONDecodeError, TypeError):
        return None  # unrecoverable — leave untouched
    return json.dumps(obj), arguments[end:]
