# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
__version__ = "0.3.0"

from wonderwall.environment.env_action import LLMAction, ManualAction
from wonderwall.environment.make import make
from wonderwall.social_agent import (generate_reddit_agent_graph,
                                generate_twitter_agent_graph)
from wonderwall.social_agent.agent import SocialAgent
from wonderwall.social_agent.agent_graph import AgentGraph
from wonderwall.social_platform.config import UserInfo
from wonderwall.social_platform.platform import Platform
from wonderwall.social_platform.typing import ActionType, DefaultPlatformType
from wonderwall.testing.show_db import print_db_contents

# Generic simulation framework (MiroShark extension over upstream CAMEL)
from wonderwall.simulations.base import (
    BasePlatform,
    BaseAction,
    BaseEnvironment,
    BasePromptBuilder,
    SimulationConfig,
)

__all__ = [
    "make", "Platform", "ActionType", "DefaultPlatformType", "ManualAction",
    "LLMAction", "print_db_contents", "AgentGraph", "SocialAgent", "UserInfo",
    "generate_reddit_agent_graph", "generate_twitter_agent_graph",
    "BasePlatform", "BaseAction", "BaseEnvironment", "BasePromptBuilder",
    "SimulationConfig",
]
