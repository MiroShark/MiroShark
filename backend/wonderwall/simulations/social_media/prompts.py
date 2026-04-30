# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
"""Prompt builders for social media simulations.

Localised prompt strings live in ``app.prompts.locales.<locale>.social_simulations``.
The active locale is read from the ``app.utils.i18n`` context var, so the
builder API stays unchanged for upstream callers.
"""
from app.prompts import get_prompt
from app.utils.i18n import get_active_locale
from wonderwall.simulations.base import BasePromptBuilder


def _build_description_block(user_info, locale: str) -> str:
    """Assemble the persona description block from user_info."""
    parts: list[str] = []
    if user_info.name is not None:
        parts.append(get_prompt(
            "social_simulations.description_name",
            locale,
            name=user_info.name,
        ))
    if (user_info.profile is not None
            and "other_info" in user_info.profile
            and "user_profile" in user_info.profile["other_info"]):
        user_profile = user_info.profile["other_info"]["user_profile"]
        if user_profile is not None:
            parts.append(get_prompt(
                "social_simulations.description_profile",
                locale,
                profile=user_profile,
            ))
    return "\n".join(parts)


def _build_demographics(user_info, locale: str) -> str:
    """Optional demographics suffix for Reddit personas."""
    if user_info.profile is None or "other_info" not in user_info.profile:
        return ""
    other = user_info.profile["other_info"]
    keys = ("gender", "age", "mbti", "country")
    if not all(k in other for k in keys):
        return ""
    return get_prompt(
        "social_simulations.description_demographics",
        locale,
        gender=other["gender"],
        age=other["age"],
        mbti=other["mbti"],
        country=other["country"],
    )


class TwitterPromptBuilder(BasePromptBuilder):
    """Builds the system prompt for a Twitter-style simulation."""

    def build_system_prompt(self, user_info) -> str:
        locale = get_active_locale()
        description_block = _build_description_block(user_info, locale)
        return get_prompt(
            "social_simulations.twitter_system",
            locale,
            description_block=description_block,
        )


class RedditPromptBuilder(BasePromptBuilder):
    """Builds the system prompt for a Reddit-style simulation."""

    def build_system_prompt(self, user_info) -> str:
        locale = get_active_locale()
        description_block = (
            _build_description_block(user_info, locale)
            + _build_demographics(user_info, locale)
        )
        return get_prompt(
            "social_simulations.reddit_system",
            locale,
            description_block=description_block,
        )
