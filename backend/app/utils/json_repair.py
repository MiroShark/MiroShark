"""Best-effort recovery of malformed or truncated LLM JSON.

LLMs occasionally return JSON that won't parse — most commonly because the
output was cut off mid-structure by a ``max_tokens`` limit, but also from
stray newlines or control characters inside string values. This module
centralizes the salvage logic that was previously copy-pasted across the
profile and config generators, so every JSON call path can opt into the
same recovery behavior.

The functions here are purely syntactic and best-effort: they try to make
a broken payload parseable, never to validate its meaning.
"""
import json
import re
from typing import Any

# Matches a complete JSON string literal, honoring backslash escapes, so the
# newline-collapse pass below only touches characters *inside* string values.
_JSON_STRING_RE = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"')


def close_truncated_json(content: str) -> str:
    """Re-close a JSON string that was truncated mid-structure.

    When an LLM hits its ``max_tokens`` limit the response often ends partway
    through a string or with brackets left open. This appends a closing quote
    for an unterminated trailing string, then the missing ``]``/``}`` for every
    unbalanced bracket. Best-effort and syntactic only — it does not guarantee
    the result parses, just gives it a chance to.
    """
    content = content.strip()

    open_braces = content.count('{') - content.count('}')
    open_brackets = content.count('[') - content.count(']')

    # If the content ends mid-string (not on a quote/comma/closer), close it.
    if content and content[-1] not in '",}]':
        content += '"'

    content += ']' * open_brackets
    content += '}' * open_braces

    return content


def _collapse_string_whitespace(match: "re.Match[str]") -> str:
    """Replace raw newlines/runs of whitespace inside a JSON string value.

    Unescaped newlines inside a string make the document invalid JSON; this
    folds them (and any resulting whitespace runs) into single spaces.
    """
    s = match.group(0)
    s = s.replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', s)


def _isolate_and_parse(text: str) -> Any:
    """Isolate the outermost JSON container in ``text`` and parse it.

    Grabs whichever of ``{...}`` / ``[...]`` opens first (so prose or ```json
    fences around the payload are ignored), folds raw newlines inside strings,
    and parses — retrying once with control characters stripped. Raises
    ``ValueError`` if no container is found or it still won't parse.
    """
    obj = re.search(r'\{[\s\S]*\}', text)
    arr = re.search(r'\[[\s\S]*\]', text)
    candidates = [m for m in (obj, arr) if m]
    if not candidates:
        raise ValueError("no JSON object or array found in content")
    json_str = min(candidates, key=lambda m: m.start()).group()

    # Collapse raw newlines inside string values (a common LLM defect).
    json_str = _JSON_STRING_RE.sub(_collapse_string_whitespace, json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Strip remaining control characters (raw newlines not inside strings,
        # stray NUL bytes, etc.) and fix invalid backslash escapes such as
        # Windows paths (\U, \n used as path sep) or LaTeX (\f, \p, \.).
        # Valid JSON escapes after \ are: " \ / b f n r t u — anything else
        # is replaced with \\ so the parser sees an escaped backslash instead.
        json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
        json_str = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', json_str)
        json_str = re.sub(r'\s+', ' ', json_str)
        return json.loads(json_str)  # raises JSONDecodeError on failure


def repair_json(content: str) -> Any:
    """Parse malformed/truncated LLM JSON, recovering as much as possible.

    Two tiers, each best-effort:

    1. Re-close anything a ``max_tokens`` cut-off left open, then isolate and
       parse the outermost container. This recovers truncations that land on a
       clean boundary (e.g. right after a complete array element).
    2. If that fails — the usual case when the clip lands mid-element — trim
       back to the last complete ``}``/``]``, dropping the partial trailing
       element, and retry. For an array of objects this keeps every fully
       emitted entry and discards only the half-written last one.

    Returns the parsed value (object or array). Raises ``ValueError`` if
    nothing parseable can be recovered, so callers can fall back exactly as
    they would on a normal parse failure.
    """
    if not isinstance(content, str):
        raise ValueError("repair_json expects a string")

    # Tier 1: close the truncation in place and parse.
    try:
        return _isolate_and_parse(close_truncated_json(content))
    except (ValueError, json.JSONDecodeError):
        pass

    # Tier 2: drop a partially-emitted trailing element. Trimming to the last
    # complete closer strips the dangling fragment (and its leading comma)
    # before we re-close the outer container.
    last_close = max(content.rfind('}'), content.rfind(']'))
    if last_close != -1:
        try:
            return _isolate_and_parse(close_truncated_json(content[:last_close + 1]))
        except (ValueError, json.JSONDecodeError):
            pass

    raise ValueError("could not repair JSON")
