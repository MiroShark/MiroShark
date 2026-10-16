"""OpenRouter app attribution headers (offline, no network).

Every OpenRouter inference call (LLMClient, EmbeddingService, the camel
model the wonderwall sim scripts build) must send the same attribution
headers so usage lands on the MiroShark app page. They live in one place,
``OPENROUTER_BASE_HEADERS``; this pins the values and stops new callers
from inlining a drifting copy.
"""

from __future__ import annotations

from pathlib import Path

from app.utils.llm_client import OPENROUTER_BASE_HEADERS, openrouter_headers

ROOT = Path(__file__).resolve().parent.parent


def test_base_headers_values():
    assert OPENROUTER_BASE_HEADERS == {
        "HTTP-Referer": "https://www.miroshark.xyz/",
        "X-OpenRouter-Title": "MiroShark - Simulate anything, for $1 & less than 10 min.",
        "X-OpenRouter-Categories": "roleplay,personal-agent",
    }


def test_openrouter_headers_adds_user_agent():
    headers = openrouter_headers("MiroShark/1.0 (Test)")
    assert headers == {**OPENROUTER_BASE_HEADERS, "User-Agent": "MiroShark/1.0 (Test)"}


def test_no_inlined_copies():
    owner = ROOT / "app" / "utils" / "llm_client.py"
    offenders = [
        str(path.relative_to(ROOT))
        for folder in ("app", "scripts", "wonderwall")
        for path in (ROOT / folder).rglob("*.py")
        if path != owner and "X-OpenRouter-Title" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"use openrouter_headers() instead of inlining: {offenders}"


def test_sim_scripts_use_shared_headers():
    for name in ("run_parallel_simulation", "run_reddit_simulation", "run_twitter_simulation"):
        src = (ROOT / "scripts" / f"{name}.py").read_text(encoding="utf-8")
        assert "default_headers=openrouter_headers(" in src, name
