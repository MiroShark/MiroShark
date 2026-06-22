"""Unit tests for the LLM reasoning-budget directive resolver.

Pure offline — no Flask, no network, no LLM. These cover
``LLMClient._resolve_reasoning_directive``, which decides what (if
anything) MiroShark attaches under OpenRouter's ``extra_body["reasoning"]``
key. The directive sizes a reasoning model's *thinking* budget independently
of the top-level ``max_tokens`` *response* budget (issue #193).

Precedence under test:
  1. ``LLM_REASONING_MAX_TOKENS`` > 0 → ``{"max_tokens": N}`` (and overrides
     ``LLM_DISABLE_REASONING``).
  2. ``LLM_REASONING_EFFORT`` set → ``{"effort": "..."}`` (token count wins
     when both are set).
  3. ``LLM_DISABLE_REASONING`` true → ``{"enabled": False}``.
  4. Nothing set, reasoning not disabled → ``None`` (model default).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config import Config
from app.utils.llm_client import LLMClient


@pytest.fixture(autouse=True)
def _reset_reasoning_config(monkeypatch):
    """Start each test from the documented defaults, then let it override."""
    monkeypatch.setattr(Config, "LLM_DISABLE_REASONING", True, raising=False)
    monkeypatch.setattr(Config, "LLM_REASONING_MAX_TOKENS", 0, raising=False)
    monkeypatch.setattr(Config, "LLM_REASONING_EFFORT", "", raising=False)


def test_default_disables_reasoning(monkeypatch):
    # Out of the box LLM_DISABLE_REASONING=true → CoT off.
    assert LLMClient._resolve_reasoning_directive() == {"enabled": False}


def test_no_directive_when_reasoning_allowed_but_unbudgeted(monkeypatch):
    # Reasoning allowed (flag off) but no explicit budget → leave the key
    # unset so the model keeps its own default.
    monkeypatch.setattr(Config, "LLM_DISABLE_REASONING", False)
    assert LLMClient._resolve_reasoning_directive() is None


def test_max_tokens_sets_thinking_budget(monkeypatch):
    monkeypatch.setattr(Config, "LLM_DISABLE_REASONING", False)
    monkeypatch.setattr(Config, "LLM_REASONING_MAX_TOKENS", 2000)
    assert LLMClient._resolve_reasoning_directive() == {"max_tokens": 2000}


def test_max_tokens_overrides_disable_flag(monkeypatch):
    # Asking for a thinking budget implies wanting the model to think, even
    # if the disable flag is left at its default.
    monkeypatch.setattr(Config, "LLM_DISABLE_REASONING", True)
    monkeypatch.setattr(Config, "LLM_REASONING_MAX_TOKENS", 1500)
    assert LLMClient._resolve_reasoning_directive() == {"max_tokens": 1500}


def test_effort_sets_reasoning_effort(monkeypatch):
    monkeypatch.setattr(Config, "LLM_DISABLE_REASONING", False)
    monkeypatch.setattr(Config, "LLM_REASONING_EFFORT", "high")
    assert LLMClient._resolve_reasoning_directive() == {"effort": "high"}


def test_effort_overrides_disable_flag(monkeypatch):
    monkeypatch.setattr(Config, "LLM_DISABLE_REASONING", True)
    monkeypatch.setattr(Config, "LLM_REASONING_EFFORT", "low")
    assert LLMClient._resolve_reasoning_directive() == {"effort": "low"}


def test_token_budget_wins_when_both_set(monkeypatch):
    # A concrete token count is more specific than an effort level.
    monkeypatch.setattr(Config, "LLM_DISABLE_REASONING", False)
    monkeypatch.setattr(Config, "LLM_REASONING_MAX_TOKENS", 800)
    monkeypatch.setattr(Config, "LLM_REASONING_EFFORT", "high")
    assert LLMClient._resolve_reasoning_directive() == {"max_tokens": 800}


def test_zero_and_empty_are_treated_as_unset(monkeypatch):
    # The zero/empty sentinels must not be mistaken for an explicit budget.
    monkeypatch.setattr(Config, "LLM_DISABLE_REASONING", False)
    monkeypatch.setattr(Config, "LLM_REASONING_MAX_TOKENS", 0)
    monkeypatch.setattr(Config, "LLM_REASONING_EFFORT", "")
    assert LLMClient._resolve_reasoning_directive() is None
