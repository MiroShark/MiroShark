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
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import List, Union

from wonderwall.environment.env_action import LLMAction, ManualAction
from wonderwall.social_agent.agent import SocialAgent
from wonderwall.social_agent.agent_graph import AgentGraph
from wonderwall.social_agent.agents_generator import generate_custom_agents
from wonderwall.social_platform.channel import Channel
from wonderwall.social_platform.platform import Platform
from wonderwall.social_platform.typing import (ActionType, DefaultPlatformType,
                                          RecsysType)

# Create log directory if it doesn't exist
log_dir = "./log"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configure logger
env_log = logging.getLogger("wonderwall.env")
env_log.setLevel("INFO")

# Add file handler to save logs to file
current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
file_handler = logging.FileHandler(f"{log_dir}/wonderwall-{current_time}.log",
                                   encoding="utf-8")
file_handler.setLevel("INFO")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
env_log.addHandler(file_handler)


def _is_interview_action(action) -> bool:
    """Check if an action is an interview, handling both enum and string."""
    action_type = action.action_type
    if hasattr(action_type, "value"):
        return action_type.value == "interview"
    return action_type == "interview"


class WonderwallEnv:

    def __init__(
        self,
        agent_graph: AgentGraph,
        platform: Union[DefaultPlatformType, Platform, "BasePlatform",
                         "SimulationConfig"] = None,
        database_path: str = None,
        semaphore: int = 128,
        # Accepts a SimulationConfig for generic (non-social) simulations
        simulation=None,
    ) -> None:
        r"""Init the wonderwall environment.

        Args:
            agent_graph: The AgentGraph to use in the simulation.
            platform: The platform type to use. Including
                ``DefaultPlatformType.TWITTER`` or
                ``DefaultPlatformType.REDDIT``, a custom ``Platform``
                instance, or any ``BasePlatform`` subclass instance.
            database_path: The path to create a sqlite3 database.
            semaphore: Max concurrent LLM requests.
            simulation: A ``SimulationConfig`` that will be used to create
                the platform.  If provided, ``platform`` is ignored.
        """
        # Initialize the agent graph
        self.agent_graph = agent_graph
        # Use a semaphore to limit the number of concurrent requests
        self.llm_semaphore = asyncio.Semaphore(semaphore)
        # Track simulation config if provided
        self.simulation = simulation

        # ------------------------------------------------------------------
        # New path: SimulationConfig
        # ------------------------------------------------------------------
        if simulation is not None:
            from wonderwall.simulations.base import SimulationConfig
            if isinstance(simulation, SimulationConfig):
                if database_path is None:
                    raise ValueError(
                        "database_path is required when using SimulationConfig"
                    )
                self.channel = Channel()
                self.platform = simulation.platform_cls(
                    db_path=database_path,
                    channel=self.channel,
                    **simulation.platform_kwargs,
                )
                self.platform_type = None  # Generic — no legacy type
                return

        # ------------------------------------------------------------------
        # New path: any BasePlatform subclass instance
        # ------------------------------------------------------------------
        _is_base_platform = False
        try:
            from wonderwall.simulations.base import BasePlatform
            _is_base_platform = isinstance(platform, BasePlatform)
        except ImportError:
            pass

        if _is_base_platform and not isinstance(platform, Platform):
            self.platform = platform
            self.channel = platform.channel
            self.platform_type = None
            return

        # ------------------------------------------------------------------
        # Legacy path: DefaultPlatformType enum
        # ------------------------------------------------------------------
        if isinstance(platform, DefaultPlatformType):
            if database_path is None:
                raise ValueError(
                    "database_path is required for DefaultPlatformType")
            self.platform = platform
            if platform == DefaultPlatformType.TWITTER:
                self.channel = Channel()
                self.platform = Platform(
                    db_path=database_path,
                    channel=self.channel,
                    recsys_type="twhin-bert",
                    refresh_rec_post_count=2,
                    max_rec_post_len=2,
                    following_post_count=3,
                )
                self.platform_type = DefaultPlatformType.TWITTER
            elif platform == DefaultPlatformType.REDDIT:
                self.channel = Channel()
                self.platform = Platform(
                    db_path=database_path,
                    channel=self.channel,
                    recsys_type="reddit",
                    allow_self_rating=True,
                    show_score=True,
                    max_rec_post_len=100,
                    refresh_rec_post_count=5,
                )
                self.platform_type = DefaultPlatformType.REDDIT
            else:
                raise ValueError(f"Invalid platform: {platform}. Only "
                                 "DefaultPlatformType.TWITTER or "
                                 "DefaultPlatformType.REDDIT are supported.")

        # ------------------------------------------------------------------
        # Legacy path: custom Platform instance
        # ------------------------------------------------------------------
        elif isinstance(platform, Platform):
            if database_path and database_path != platform.db_path:
                env_log.warning("database_path is not the same as the "
                                "platform.db_path, using the platform.db_path")
            self.platform = platform
            self.channel = platform.channel
            if platform.recsys_type == RecsysType.REDDIT:
                self.platform_type = DefaultPlatformType.REDDIT
            else:
                self.platform_type = DefaultPlatformType.TWITTER
        else:
            raise ValueError(
                f"Invalid platform: {platform}. You should pass a "
                "DefaultPlatformType, a Platform instance, a BasePlatform "
                "subclass, or use the simulation= parameter with a "
                "SimulationConfig.")

    async def reset(self) -> None:
        r"""Start the platform and sign up the agents."""
        self.platform_task = asyncio.create_task(self.platform.running())
        self.agent_graph = await generate_custom_agents(
            channel=self.channel, agent_graph=self.agent_graph)

    async def _perform_llm_action(self, agent):
        r"""Send the request to the llm model and execute the action."""
        async with self.llm_semaphore:
            return await agent.perform_action_by_llm()

    async def _perform_interview_action(self, agent, interview_prompt: str):
        r"""Send the request to the llm model and execute the interview."""
        async with self.llm_semaphore:
            return await agent.perform_interview(interview_prompt)

    async def step(
        self, actions: dict[SocialAgent, Union[ManualAction, LLMAction,
                                               List[Union[ManualAction,
                                                          LLMAction]]]]
    ) -> None:
        r"""Update the recommendation system and perform the actions.

        Args:
            actions(dict[SocialAgent, Union[ManualAction, LLMAction,
                List[Union[ManualAction, LLMAction]]]]): The actions to
                perform, including the manual(pre-defined) actions and llm
                actions.
        Returns:
            None
        """
        # Update the recommendation system (no-op for platforms that don't
        # implement it).
        if hasattr(self.platform, 'update_rec_table'):
            await self.platform.update_rec_table()
            env_log.info("update rec table.")

        # Create tasks for both manual and LLM actions
        tasks = []
        for agent, action in actions.items():
            if isinstance(action, list):
                for single_action in action:
                    if isinstance(single_action, ManualAction):
                        if _is_interview_action(single_action):
                            interview_prompt = single_action.action_args.get(
                                "prompt", "")
                            tasks.append(
                                self._perform_interview_action(
                                    agent, interview_prompt))
                        else:
                            tasks.append(
                                agent.perform_action_by_data(
                                    single_action.action_type,
                                    **single_action.action_args))
                    elif isinstance(single_action, LLMAction):
                        tasks.append(self._perform_llm_action(agent))
            else:
                if isinstance(action, ManualAction):
                    if _is_interview_action(action):
                        interview_prompt = action.action_args.get("prompt", "")
                        tasks.append(
                            self._perform_interview_action(
                                agent, interview_prompt))
                    else:
                        tasks.append(
                            agent.perform_action_by_data(
                                action.action_type, **action.action_args))
                elif isinstance(action, LLMAction):
                    tasks.append(self._perform_llm_action(agent))

        # Execute all tasks concurrently
        await asyncio.gather(*tasks)
        env_log.info("performed all actions.")

        # Update the clock for time-step-based simulations
        if (self.platform_type == DefaultPlatformType.TWITTER
                if self.platform_type is not None else False):
            self.platform.sandbox_clock.time_step += 1
        elif self.platform_type is None and hasattr(self.platform,
                                                     'tick_clock'):
            # Generic simulations can implement tick_clock()
            self.platform.tick_clock()

    async def close(self) -> None:
        r"""Stop the platform and close the environment."""
        # Send exit signal — works with both ActionType enum and plain string.
        try:
            await self.channel.write_to_receive_queue(
                (None, None, ActionType.EXIT))
        except Exception:
            # For generic platforms that use string-based actions.
            await self.channel.write_to_receive_queue(
                (None, None, "exit"))
        await self.platform_task
        env_log.info("Simulation finished! Please check the results in the "
                     f"database: {self.platform.db_path}. Note that the trace "
                     "table stored all the actions of the agents.")
