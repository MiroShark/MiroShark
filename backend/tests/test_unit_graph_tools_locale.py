"""Locale propagation tests for the fallback interview path.

`GraphToolsService._fallback_interview` runs each agent interview in a
`ThreadPoolExecutor` worker. `ContextVar`-based locale state does NOT
propagate into pool workers, so the worker must capture the active locale
on the parent thread and re-apply it inside the worker (mirrors PR #194's
fix for `report_agent`). These tests guard that the worker's role-play
prompt is built in the user's locale rather than silently falling back to
English. Regression target: issue #195.
"""
import pytest

from app.prompts import get_prompt
from app.prompts.registry import _reset_cache_for_tests
from app.services.graph_tools import GraphToolsService
from app.utils import i18n


@pytest.fixture(autouse=True)
def _reset_registry():
    _reset_cache_for_tests()
    yield
    _reset_cache_for_tests()


class _RecordingLLM:
    """Fake fast LLM client that records the prompts it is handed."""

    def __init__(self):
        self.prompts: list[str] = []

    def chat(self, messages, temperature=0.7, max_tokens=1024):
        self.prompts.append(messages[-1]["content"])
        return "response text"


def _make_service():
    svc = GraphToolsService(storage=None)
    # Inject the fake so no real LLM client is constructed.
    svc._fast_llm_client = _RecordingLLM()
    return svc


def test_roleplay_prompt_is_localized_for_each_locale():
    """The new role-play prompt key resolves per-locale, not just English."""
    en = get_prompt(
        "graph_tools.interview_single_agent_roleplay", "en",
        profile_desc="Name: X", combined_prompt="Q?",
    )
    assert "role-playing" in en

    zh = get_prompt(
        "graph_tools.interview_single_agent_roleplay", "zh-CN",
        profile_desc="Name: X", combined_prompt="Q?",
    )
    assert any("一" <= c <= "鿿" for c in zh), zh[:120]

    de = get_prompt(
        "graph_tools.interview_single_agent_roleplay", "de",
        profile_desc="Name: X", combined_prompt="Q?",
    )
    assert "Rolle" in de, de[:120]

    fr = get_prompt(
        "graph_tools.interview_single_agent_roleplay", "fr",
        profile_desc="Name: X", combined_prompt="Q?",
    )
    assert "personnage" in fr, fr[:120]


def test_fallback_interview_threads_locale_into_thread_pool_worker():
    """The worker must see the user's locale even though it runs in a thread.

    Without the capture+use_locale fix, `get_active_locale()` inside the
    pool worker returns the default ("en") and the role-play prompt would
    be English. This asserts the Chinese prompt reaches the worker.
    """
    from app.services.graph_tools import InterviewResult

    svc = _make_service()
    agents = [
        {"realname": "小明", "profession": "记者", "bio": "", "persona": ""},
        {"realname": "小红", "profession": "教师", "bio": "", "persona": ""},
    ]
    result = InterviewResult(
        interview_topic="测试主题",
        interview_questions=["你怎么看？"],
        selected_agents=agents,
    )

    with i18n.use_locale("zh-CN"):
        svc._fallback_interview(
            result=result,
            selected_agents=agents,
            selected_indices=[0, 1],
            combined_prompt="你怎么看？",
            interview_requirement="测试主题",
        )

    recorded = svc._fast_llm_client.prompts
    # The two role-play worker prompts are the first calls; assert at least
    # one carries CJK content (the localized role-play framing).
    roleplay_prompts = [p for p in recorded if "你怎么看" in p]
    assert roleplay_prompts, "no worker prompt captured"
    assert any(
        any("一" <= c <= "鿿" for c in p) for p in roleplay_prompts
    ), "worker prompt was not localized to zh-CN (locale dropped across ThreadPoolExecutor)"
