"""Unit tests for the best-effort JSON salvage helpers.

Pure offline — no Flask, no network, no LLM. These cover the recovery
behavior that ``suggest_scenarios`` (and the profile/config generators)
rely on when a model truncates its JSON at the ``max_tokens`` boundary:

  1. ``close_truncated_json`` re-closes unterminated strings/brackets.
  2. ``repair_json`` round-trips already-valid objects and arrays.
  3. A truncation on a clean array-element boundary is fully recovered.
  4. A truncation mid-element drops only the partial trailing entry and
     keeps every complete one (the realistic suggest_scenarios case).
  5. Stray raw newlines inside string values are tolerated.
  6. Unrecoverable / non-string input raises ``ValueError``.
  7. ``LLMClient.chat_json(repair_truncated=True)`` salvages a truncated
     response, while the default strict path still raises.
"""
import json

import pytest

from app.utils.json_repair import close_truncated_json, repair_json


# A complete, well-formed scenario response — the shape suggest_scenarios
# asks the model for. Used as the basis for the truncation cases below.
_FULL = {
    "suggestions": [
        {"question": "Will the central bank cut rates in Q3?", "label": "Bull",
         "expected_yes_range": [55, 70], "rationale": "Dovish minutes signal an easing bias."},
        {"question": "Will headline CPI exceed 4% next print?", "label": "Bear",
         "expected_yes_range": [20, 35], "rationale": "Base effects keep prints elevated."},
        {"question": "Will unemployment hold near 4%?", "label": "Neutral",
         "expected_yes_range": [45, 60], "rationale": "Labor market shows little slack change."},
    ]
}


# ── 1. close_truncated_json ────────────────────────────────────────────────

def test_close_truncated_json_closes_unterminated_string_and_brackets():
    out = close_truncated_json('{"a": [1, 2, "partial val')
    # An unterminated string gets a closing quote, then the open [ and { close.
    assert out.endswith('"]}')
    assert json.loads(out) == {"a": [1, 2, "partial val"]}


def test_close_truncated_json_leaves_balanced_input_parseable():
    src = '{"a": 1}'
    assert json.loads(close_truncated_json(src)) == {"a": 1}


# ── 2. repair_json round-trips valid input ─────────────────────────────────

def test_repair_json_passes_through_valid_object():
    assert repair_json(json.dumps(_FULL)) == _FULL


def test_repair_json_passes_through_valid_array():
    assert repair_json('[1, 2, 3]') == [1, 2, 3]


def test_repair_json_ignores_markdown_fences_and_prose():
    wrapped = "Here you go:\n```json\n" + json.dumps({"x": 1}) + "\n```"
    assert repair_json(wrapped) == {"x": 1}


# ── 3 & 4. truncation recovery ─────────────────────────────────────────────

def test_repair_json_recovers_truncation_on_clean_boundary():
    """Clip after a complete object but before the closing ]} — tier 1."""
    full = json.dumps(_FULL)
    clipped = full[: full.rindex("}") ]  # drop the final outer brace
    recovered = repair_json(clipped)
    assert len(recovered["suggestions"]) == 3
    assert recovered["suggestions"][0]["label"] == "Bull"


def test_repair_json_drops_partial_trailing_element():
    """Clip mid-third-object — tier 2 keeps the two complete suggestions."""
    full = json.dumps(_FULL)
    # Cut somewhere inside the third suggestion's question string.
    clipped = full[: full.index("Will unemployment") + 5]
    recovered = repair_json(clipped)
    assert isinstance(recovered, dict)
    # The two fully-emitted suggestions survive; the half-written one is gone.
    assert len(recovered["suggestions"]) == 2
    assert [s["label"] for s in recovered["suggestions"]] == ["Bull", "Bear"]


def test_repair_json_tolerates_raw_newlines_in_strings():
    recovered = repair_json('{"rationale": "line one\nline two"}')
    assert recovered["rationale"] == "line one line two"


# ── 6. unrecoverable input ─────────────────────────────────────────────────

def test_repair_json_raises_on_garbage():
    with pytest.raises(ValueError):
        repair_json("this is not json at all")


def test_repair_json_raises_on_non_string():
    with pytest.raises(ValueError):
        repair_json(None)  # type: ignore[arg-type]


# ── 7. chat_json opt-in integration ────────────────────────────────────────

def _client_returning(text):
    """An LLMClient whose .chat() yields ``text`` without any network I/O."""
    from app.utils.llm_client import LLMClient
    client = LLMClient(api_key="test-key")
    client.chat = lambda **kwargs: text  # type: ignore[assignment]
    return client


def test_chat_json_repairs_truncated_when_opted_in():
    full = json.dumps(_FULL)
    clipped = full[: full.index("Will unemployment") + 5]
    client = _client_returning(clipped)
    parsed = client.chat_json([{"role": "user", "content": "x"}], repair_truncated=True)
    assert len(parsed["suggestions"]) == 2


def test_chat_json_strict_by_default_raises_on_truncation():
    full = json.dumps(_FULL)
    clipped = full[: full.index("Will unemployment") + 5]
    client = _client_returning(clipped)
    with pytest.raises(ValueError):
        client.chat_json([{"role": "user", "content": "x"}])
