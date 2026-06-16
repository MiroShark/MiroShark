"""Smoke test: the wonderwall ``SocialAgent`` must stay call-compatible with
the installed ``camel-ai`` version.

camel-ai periodically refactors ``ChatAgent`` internals. In 0.2.90 it changed
how it invokes the overridable ``_aget_model_response`` (it dropped the
``num_tokens`` positional argument), which silently broke **every** agent step
in the simulation loop until the override was made signature-agnostic — every
``perform_action_by_llm`` raised ``TypeError: _aget_model_response() missing 1
required positional argument: 'num_tokens'``, the exception was swallowed per
agent, and simulations "completed" with zero actions (see PR #181).

The backend unit suite cannot catch this because it deliberately does not
install camel-ai/torch. This module is run by the dedicated ``camel-smoke`` CI
job, which installs them. It is driven by camel's STUB model, so it needs no
API key and makes no network calls.
"""
import asyncio
import inspect

import pytest

# Heavy deps (camel-ai, torch) are only present in the camel-smoke CI job.
# Skip the whole module cleanly in the thin unit job instead of erroring.
pytest.importorskip("camel")
pytest.importorskip("torch")

from camel.models import ModelFactory  # noqa: E402
from camel.types import ModelPlatformType  # noqa: E402

from wonderwall.social_agent.agent import SocialAgent  # noqa: E402
from wonderwall.social_platform import Channel  # noqa: E402
from wonderwall.social_platform.config import UserInfo  # noqa: E402


def _make_stub_agent() -> SocialAgent:
    """A SocialAgent backed by camel's STUB model — no API key, no network."""
    model = ModelFactory.create(
        model_platform=ModelPlatformType.STUB,
        model_type="stub",
    )
    user_info = UserInfo(
        is_controllable=False,
        profile={"other_info": {"user_profile": "smoke-test persona"}},
        recsys_type="twitter",
    )
    return SocialAgent(
        agent_id=0,
        user_info=user_info,
        channel=Channel(),
        model=model,
    )


def test_aget_model_response_is_signature_forward_compatible():
    """The override must accept whatever args camel passes, so a future camel
    signature change can't break it the way 0.2.90 did (#181)."""
    kinds = {
        p.kind
        for p in inspect.signature(SocialAgent._aget_model_response).parameters.values()
    }
    assert inspect.Parameter.VAR_POSITIONAL in kinds, (
        "_aget_model_response must forward *args — camel passes model-response "
        "args positionally and hardcoding them broke the agent loop in #181"
    )
    assert inspect.Parameter.VAR_KEYWORD in kinds, (
        "_aget_model_response must forward **kwargs to absorb new camel kwargs"
    )


def test_socialagent_step_drives_aget_model_response_without_signature_error():
    """End-to-end: camel must be able to drive SocialAgent's overridden async
    model-response path. Reproduces the exact code path #181 broke. astep()
    (not step()) goes through the async ``_aget_model_response`` override."""
    agent = _make_stub_agent()
    response = asyncio.run(agent.astep("Say hello."))
    assert response is not None
    # A wrong override signature would have raised TypeError above before
    # returning a response.
