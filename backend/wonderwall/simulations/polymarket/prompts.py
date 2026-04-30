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
"""Prompt builder for Polymarket agents."""
from __future__ import annotations

from app.prompts import get_prompt
from app.utils.i18n import get_active_locale
from wonderwall.simulations.base import BasePromptBuilder


class PolymarketPromptBuilder(BasePromptBuilder):
    """Builds system prompts for prediction market trader agents."""

    def build_system_prompt(self, user_info) -> str:
        locale = get_active_locale()

        name_str = ""
        if user_info.name:
            name_str = get_prompt(
                "social_simulations.polymarket_name",
                locale,
                name=user_info.name,
            )

        profile_str = ""
        risk_str = get_prompt(
            "social_simulations.polymarket_default_risk", locale,
        )

        if user_info.profile and "other_info" in user_info.profile:
            other = user_info.profile["other_info"]
            user_profile = other.get("user_profile")
            if user_profile:
                profile_str = get_prompt(
                    "social_simulations.polymarket_profile",
                    locale,
                    profile=user_profile,
                )
            if "risk_tolerance" in other:
                risk_str = other["risk_tolerance"]

        return get_prompt(
            "social_simulations.polymarket_system",
            locale,
            name_str=name_str,
            profile_str=profile_str,
            risk_str=risk_str,
        )
