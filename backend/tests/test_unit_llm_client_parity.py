"""Unit tests for LLMClient / ClaudeCodeClient interface parity.

Pure offline - no Flask, no network, no ``claude`` CLI. ClaudeCodeClient is
a drop-in replacement for LLMClient (``LLM_PROVIDER=claude-code``), so any
keyword a caller passes to one must be accepted by the other. #321: NER and
graph tools pass ``repair_truncated=True``, which ClaudeCodeClient rejected
with a TypeError, so claude-code mode silently extracted 0 entities.

The classes are compared via ``inspect.signature`` on the unbound methods so
neither constructor runs (ClaudeCodeClient's shells out to ``claude --version``).
"""
import inspect
import json

import pytest

from app.utils.claude_code_client import ClaudeCodeClient
from app.utils.llm_client import LLMClient


def _params(cls, name):
    """(name, kind, default) for every parameter of ``cls.<name>``."""
    sig = inspect.signature(getattr(cls, name))
    return [(p.name, p.kind, p.default) for p in sig.parameters.values()]


@pytest.mark.parametrize("method", ["chat", "chat_json"])
def test_claude_code_client_matches_llm_client_signature(method):
    assert _params(ClaudeCodeClient, method) == _params(LLMClient, method)


def _claude_client_returning(text):
    """A ClaudeCodeClient whose .chat() yields ``text``, built without __init__."""
    client = ClaudeCodeClient.__new__(ClaudeCodeClient)
    client.chat = lambda **kwargs: text  # type: ignore[assignment]
    return client


_TRUNCATED = json.dumps({"entities": [{"name": "A"}, {"name": "B"}]})[:-12]


def test_claude_code_chat_json_repairs_truncated_when_opted_in():
    client = _claude_client_returning(_TRUNCATED)
    parsed = client.chat_json([{"role": "user", "content": "x"}], repair_truncated=True)
    assert parsed["entities"][0] == {"name": "A"}


def test_claude_code_chat_json_strict_by_default_raises_on_truncation():
    client = _claude_client_returning(_TRUNCATED)
    with pytest.raises(ValueError):
        client.chat_json([{"role": "user", "content": "x"}])
