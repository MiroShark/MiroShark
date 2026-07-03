"""Message filtering for OpenAI-compatible chat calls.

Kept dependency-free (stdlib typing only) and outside the ``wonderwall``
package so the offline unit-test job — which does not install camel-ai/numpy
— can exercise it without importing the wonderwall package's heavy runtime
chain (see ``wonderwall/__init__.py`` -> ``recsys.py`` -> numpy).
"""

from typing import Any, Dict, List


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
