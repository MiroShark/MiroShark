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
from __future__ import annotations

import inspect
import logging
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Union

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import BaseModelBackend, ModelManager
from camel.prompts import TextPrompt
from camel.toolkits import FunctionTool
from camel.types import OpenAIBackendRole

from wonderwall.social_agent.agent_action import SocialAction
from wonderwall.social_agent.agent_environment import SocialEnvironment
from wonderwall.social_platform import Channel
from wonderwall.social_platform.config import UserInfo
from wonderwall.social_platform.typing import ActionType

if TYPE_CHECKING:
    from wonderwall.social_agent import AgentGraph

if "sphinx" not in sys.modules:
    agent_log = logging.getLogger(name="social.agent")
    agent_log.setLevel("DEBUG")

    if not agent_log.handlers:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_handler = logging.FileHandler(
            f"./log/social.agent-{str(now)}.log")
        file_handler.setLevel("DEBUG")
        file_handler.setFormatter(
            logging.Formatter(
                "%(levelname)s - %(asctime)s - %(name)s - %(message)s"))
        agent_log.addHandler(file_handler)

ALL_SOCIAL_ACTIONS = [action.value for action in ActionType]


class SocialAgent(ChatAgent):
    r"""Agent that participates in a Wonderwall simulation.

    Supports both the legacy social-media workflow (``SocialAction`` +
    ``SocialEnvironment``) and the new generic simulation framework
    (any ``BaseAction`` + ``BaseEnvironment`` via ``SimulationConfig``).
    """

    def __init__(self,
                 agent_id: int,
                 user_info: UserInfo,
                 user_info_template: TextPrompt | None = None,
                 channel: Channel | None = None,
                 model: Optional[Union[BaseModelBackend,
                                       List[BaseModelBackend],
                                       ModelManager]] = None,
                 agent_graph: "AgentGraph" = None,
                 available_actions: list[ActionType] = None,
                 tools: Optional[List[Union[FunctionTool, Callable]]] = None,
                 max_iteration: int = 1,
                 interview_record: bool = False,
                 # --- New: generic simulation support ---
                 simulation=None):
        self.social_agent_id = agent_id
        self.user_info = user_info
        self.channel = channel or Channel()

        # ------------------------------------------------------------------
        # Build action/environment/prompt from SimulationConfig if provided
        # ------------------------------------------------------------------
        if simulation is not None:
            from wonderwall.simulations.base import SimulationConfig
            if isinstance(simulation, SimulationConfig):
                action_instance = simulation.action_cls(agent_id, self.channel)
                self.env = simulation.environment_cls(action_instance)
                if user_info_template is not None:
                    system_message_content = (
                        self.user_info.to_custom_system_message(
                            user_info_template))
                else:
                    system_message_content = (
                        simulation.prompt_builder.build_system_prompt(
                            user_info))
                # Default actions from SimulationConfig if none specified
                if available_actions is None and simulation.default_actions:
                    available_actions = simulation.default_actions
            else:
                raise ValueError(
                    f"simulation must be a SimulationConfig, got "
                    f"{type(simulation)}")
        else:
            # Legacy path: social media
            self.env = SocialEnvironment(
                SocialAction(agent_id, self.channel))
            if user_info_template is None:
                system_message_content = self.user_info.to_system_message()
            else:
                system_message_content = (
                    self.user_info.to_custom_system_message(
                        user_info_template))

        system_message = BaseMessage.make_assistant_message(
            role_name="system",
            content=system_message_content,
        )

        if not available_actions:
            agent_log.info("No available actions defined, using all actions.")
            self.action_tools = self.env.action.get_openai_function_list()
        else:
            all_tools = self.env.action.get_openai_function_list()
            all_possible_actions = [tool.func.__name__ for tool in all_tools]

            for action in available_actions:
                action_name = action.value if isinstance(
                    action, ActionType) else action
                if action_name not in all_possible_actions:
                    agent_log.warning(
                        f"Action {action_name} is not supported. Supported "
                        f"actions are: {', '.join(all_possible_actions)}")
            self.action_tools = [
                tool for tool in all_tools if tool.func.__name__ in [
                    a.value if isinstance(a, ActionType) else a
                    for a in available_actions
                ]
            ]
        all_tools = (tools or []) + (self.action_tools or [])
        super().__init__(
            system_message=system_message,
            model=model,
            scheduling_strategy='random_model',
            tools=all_tools,
        )
        self.max_iteration = max_iteration
        self.interview_record = interview_record
        self.agent_graph = agent_graph
        self.test_prompt = (
            "\n"
            "Helen is a successful writer who usually writes popular western "
            "novels. Now, she has an idea for a new novel that could really "
            "make a big impact. If it works out, it could greatly "
            "improve her career. But if it fails, she will have spent "
            "a lot of time and effort for nothing.\n"
            "\n"
            "What do you think Helen should do?")

    async def _aget_model_response(self, openai_messages, num_tokens, **kwargs):
        """Filter empty-content messages that Gemini rejects with INVALID_ARGUMENT,
        and emit llm_call observability events for Wonderwall subprocess visibility."""
        import os as _os
        import time as _time

        filtered = [
            msg for msg in openai_messages
            if msg.get("content") is not None and str(msg["content"]).strip()
        ]
        if not filtered:
            filtered = [{"role": "user", "content": "(empty context)"}]

        # Inject OpenRouter metadata per-call so each generation is tagged.
        # Structured for Langfuse: `user` becomes the Langfuse sessionId,
        # `metadata` lands on the trace, `tags` powers the filter sidebar.
        base_url = _os.environ.get('OPENAI_API_BASE_URL', '')
        if 'openrouter' in base_url:
            try:
                sim_id = _os.environ.get('MIROSHARK_SIMULATION_ID', '') or ''
                run_id = _os.environ.get('MIROSHARK_RUN_ID', '') or ''
                round_env = _os.environ.get('MIROSHARK_ROUND_NUM', '')
                round_num: Optional[int]
                try:
                    round_num = int(round_env) if round_env else None
                except (TypeError, ValueError):
                    round_num = None
                agent_name = str(getattr(self.user_info, 'name', ''))[:64]
                prompt_type = 'agent_action'
                sim_phase = 'round'
                config = self.model_backend.model_config_dict
                extra = config.get('extra_body', {})
                metadata = {
                    'caller': 'SocialAgent.perform_action_by_llm',
                    'prompt_type': prompt_type,
                    'sim_phase': sim_phase,
                    'run_id': run_id,
                    'simulation_id': sim_id,
                    'agent_name': agent_name,
                    'agent_id': str(self.social_agent_id or ''),
                    'round': round_num,
                }
                extra['metadata'] = {k: v for k, v in metadata.items()
                                     if v not in ('', None)}
                if sim_id:
                    extra['user'] = sim_id  # OpenRouter → Langfuse sessionId
                tags = ['miroshark', prompt_type, f'phase:{sim_phase}']
                if run_id:
                    tags.append(f'run:{run_id}')
                extra['tags'] = tags
                extra['name'] = prompt_type
                config['extra_body'] = extra
            except Exception:
                pass

        start = _time.time()
        error_msg = None
        result = None
        try:
            result = await super()._aget_model_response(filtered, num_tokens, **kwargs)
            return result
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            try:
                self._emit_llm_call_event(filtered, start, error_msg, result)
            except Exception:
                pass

    async def perform_action_by_llm(self):
        # Get environment observation:
        env_prompt = await self.env.to_text_prompt()
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=(
                f"Please perform actions after observing the "
                f"platform environment. Use the available tools to take "
                f"action. Don't limit yourself to just one type of action. "
                f"Here is your current environment: {env_prompt}"))
        try:
            agent_log.info(
                f"Agent {self.social_agent_id} observing environment: "
                f"{env_prompt}")
            response = await self.astep(user_msg)
            tool_calls_data = []
            for tool_call in response.info['tool_calls']:
                action_name = tool_call.tool_name
                args = tool_call.args
                agent_log.info(f"Agent {self.social_agent_id} performed "
                               f"action: {action_name} with args: {args}")
                tool_calls_data.append({
                    'tool_name': action_name,
                    'args': args,
                    'result': str(tool_call.result)[:200] if tool_call.result else None,
                })
                if action_name not in ALL_SOCIAL_ACTIONS:
                    agent_log.info(
                        f"Agent {self.social_agent_id} get the result: "
                        f"{tool_call.result}")

                # Emit agent_decision event (best-effort, never breaks agent)
                try:
                    self._emit_decision_event(env_prompt, response, tool_calls_data)
                except Exception:
                    pass

                return response
        except Exception as e:
            agent_log.error(f"Agent {self.social_agent_id} error: {e}")
            # Emit error event
            try:
                self._emit_decision_event(env_prompt, None, [], error=e)
            except Exception:
                pass
            return e

    def _emit_decision_event(self, env_prompt, response, tool_calls_data, error=None):
        """Emit an agent_decision observability event to events.jsonl (best-effort)."""
        try:
            import os as _os
            import json as _json
            import uuid as _uuid
            from datetime import datetime as _dt

            log_prompts = _os.environ.get('MIROSHARK_LOG_PROMPTS', 'false').lower() == 'true'

            llm_response_text = None
            if response and hasattr(response, 'msgs') and response.msgs:
                llm_response_text = response.msgs[0].content if response.msgs else None
            elif response and hasattr(response, 'output_messages') and response.output_messages:
                llm_response_text = response.output_messages[0].content

            parsed_action = None
            if tool_calls_data:
                parsed_action = {
                    'action_type': tool_calls_data[0].get('tool_name'),
                    'action_args': tool_calls_data[0].get('args'),
                }

            data = {
                'env_prompt_preview': (env_prompt or '')[:300],
                'llm_response_preview': (llm_response_text or '')[:300],
                'parsed_action': parsed_action,
                'tool_calls': tool_calls_data,
                'success': error is None,
                'error': str(error) if error else None,
            }
            if log_prompts:
                data['env_prompt'] = env_prompt
                data['llm_response'] = llm_response_text

            event = {
                'event_id': f'evt_{_uuid.uuid4().hex[:12]}',
                'event_type': 'agent_decision',
                'timestamp': _dt.utcnow().isoformat(timespec='milliseconds') + 'Z',
                'simulation_id': None,
                'trace_id': None,
                'round_num': None,
                'agent_id': self.social_agent_id,
                'agent_name': getattr(self.user_info, 'name', None),
                'platform': None,
                'data': data,
            }

            # Try to find the simulation events.jsonl via CWD or env
            sim_dir = _os.environ.get('MIROSHARK_SIM_DIR', '.')
            events_path = _os.path.join(sim_dir, 'events.jsonl')
            with open(events_path, 'a', encoding='utf-8') as f:
                f.write(_json.dumps(event, ensure_ascii=False, default=str) + '\n')
        except Exception:
            pass  # never break agent execution

    def _emit_llm_call_event(self, openai_messages, start_time, error_msg=None, result=None):
        """Emit an llm_call observability event from the Wonderwall subprocess."""
        try:
            import os as _os
            import json as _json
            import time as _time
            import uuid as _uuid
            from datetime import datetime as _dt

            latency_ms = (_time.time() - start_time) * 1000
            log_prompts = _os.environ.get('MIROSHARK_LOG_PROMPTS', 'false').lower() == 'true'

            # Extract model name from environment (set by simulation runner)
            model = _os.environ.get('WONDERWALL_MODEL_NAME') or _os.environ.get('LLM_MODEL_NAME', 'unknown')

            # Extract real token counts from CAMEL ModelResponse if available
            tokens_input = 0
            tokens_output = 0
            response_preview = None
            if result is not None:
                # ModelResponse has usage_dict with prompt_tokens/completion_tokens
                usage = getattr(result, 'usage_dict', None)
                if usage:
                    tokens_input = usage.get('prompt_tokens', 0) or 0
                    tokens_output = usage.get('completion_tokens', 0) or 0
                # Fallback: try the raw ChatCompletion response
                if not tokens_output:
                    raw_response = getattr(result, 'response', None)
                    if raw_response:
                        raw_usage = getattr(raw_response, 'usage', None)
                        if raw_usage:
                            tokens_input = getattr(raw_usage, 'prompt_tokens', 0) or 0
                            tokens_output = getattr(raw_usage, 'completion_tokens', 0) or 0
                # Extract response preview from output_messages
                out_msgs = getattr(result, 'output_messages', None)
                if out_msgs:
                    content = getattr(out_msgs[0], 'content', None) if out_msgs else None
                    if content:
                        response_preview = str(content)[:200]

            # Fallback: estimate input tokens from message content
            if not tokens_input:
                input_chars = sum(len(str(m.get('content', ''))) for m in openai_messages)
                tokens_input = input_chars // 4

            data = {
                'caller': 'SocialAgent.perform_action_by_llm',
                'model': model,
                'tokens_input': tokens_input,
                'tokens_output': tokens_output,
                'tokens_total': tokens_input + tokens_output,
                'latency_ms': round(latency_ms, 1),
                'error': error_msg,
                'response_preview': response_preview,
            }
            if log_prompts:
                data['messages'] = openai_messages

            sim_id = _os.environ.get('MIROSHARK_SIMULATION_ID')

            event = {
                'event_id': f'evt_{_uuid.uuid4().hex[:12]}',
                'event_type': 'llm_call',
                'timestamp': _dt.utcnow().isoformat(timespec='milliseconds') + 'Z',
                'simulation_id': sim_id,
                'trace_id': None,
                'round_num': None,
                'agent_id': self.social_agent_id,
                'agent_name': getattr(self.user_info, 'name', None),
                'platform': None,
                'data': data,
            }

            sim_dir = _os.environ.get('MIROSHARK_SIM_DIR', '.')
            events_path = _os.path.join(sim_dir, 'events.jsonl')
            with open(events_path, 'a', encoding='utf-8') as f:
                f.write(_json.dumps(event, ensure_ascii=False, default=str) + '\n')
        except Exception:
            pass  # never break agent execution

    async def perform_test(self):
        """
        doing group polarization test for all agents.
        TODO: rewrite the function according to the ChatAgent.
        TODO: unify the test and interview function.
        """
        # user conduct test to agent
        _ = BaseMessage.make_user_message(role_name="User",
                                          content=("You are a twitter user."))
        # Test memory should not be writed to memory.
        # self.memory.write_record(MemoryRecord(user_msg,
        #                                       OpenAIBackendRole.USER))

        openai_messages, num_tokens = self.memory.get_context()

        openai_messages = ([{
            "role":
            self.system_message.role_name,
            "content":
            self.system_message.content.split("# RESPONSE METHOD")[0],
        }] + openai_messages + [{
            "role": "user",
            "content": self.test_prompt
        }])

        agent_log.info(f"Agent {self.social_agent_id}: {openai_messages}")
        # NOTE: this is a temporary solution.
        # Camel can not stop updating the agents' memory after stop and astep
        # now.
        response = await self._aget_model_response(
            openai_messages=openai_messages, num_tokens=num_tokens)
        content = response.output_messages[0].content
        agent_log.info(
            f"Agent {self.social_agent_id} receive response: {content}")
        return {
            "user_id": self.social_agent_id,
            "prompt": openai_messages,
            "content": content
        }

    async def perform_interview(self, interview_prompt: str):
        """
        Perform an interview with the agent.
        """
        # user conduct test to agent
        user_msg = BaseMessage.make_user_message(
            role_name="User", content=("You are a twitter user."))

        if self.interview_record:
            # Test memory should not be writed to memory.
            self.update_memory(message=user_msg, role=OpenAIBackendRole.SYSTEM)

        openai_messages, num_tokens = self.memory.get_context()

        openai_messages = ([{
            "role":
            self.system_message.role_name,
            "content":
            self.system_message.content.split("# RESPONSE METHOD")[0],
        }] + openai_messages + [{
            "role": "user",
            "content": interview_prompt
        }])

        agent_log.info(f"Agent {self.social_agent_id}: {openai_messages}")
        # NOTE: this is a temporary solution.
        # Camel can not stop updating the agents' memory after stop and astep
        # now.

        response = await self._aget_model_response(
            openai_messages=openai_messages, num_tokens=num_tokens)

        content = response.output_messages[0].content

        if self.interview_record:
            # Test memory should not be writed to memory.
            self.update_memory(message=response.output_messages[0],
                               role=OpenAIBackendRole.USER)
        agent_log.info(
            f"Agent {self.social_agent_id} receive response: {content}")

        # Record the complete interview (prompt + response) through the channel
        interview_data = {"prompt": interview_prompt, "response": content}
        result = await self.env.action.perform_action(
            interview_data, ActionType.INTERVIEW.value)

        # Return the combined result
        return {
            "user_id": self.social_agent_id,
            "prompt": openai_messages,
            "content": content,
            "success": result.get("success", False)
        }

    async def perform_action_by_hci(self) -> Any:
        print("Please choose one function to perform:")
        function_list = self.env.action.get_openai_function_list()
        for i in range(len(function_list)):
            agent_log.info(f"Agent {self.social_agent_id} function: "
                           f"{function_list[i].func.__name__}")

        selection = int(input("Enter your choice: "))
        if not 0 <= selection < len(function_list):
            agent_log.error(f"Agent {self.social_agent_id} invalid input.")
            return
        func = function_list[selection].func

        params = inspect.signature(func).parameters
        args = []
        for param in params.values():
            while True:
                try:
                    value = input(f"Enter value for {param.name}: ")
                    args.append(value)
                    break
                except ValueError:
                    agent_log.error("Invalid input, please enter an integer.")

        result = await func(*args)
        return result

    async def perform_action_by_data(self, func_name, *args, **kwargs) -> Any:
        func_name = func_name.value if isinstance(func_name,
                                                  ActionType) else func_name
        function_list = self.env.action.get_openai_function_list()
        for i in range(len(function_list)):
            if function_list[i].func.__name__ == func_name:
                func = function_list[i].func
                result = await func(*args, **kwargs)
                self.update_memory(message=BaseMessage.make_user_message(
                    role_name=OpenAIBackendRole.SYSTEM,
                    content=f"Agent {self.social_agent_id} performed "
                    f"{func_name} with args: {args} and kwargs: {kwargs}"
                    f"and the result is {result}"),
                                   role=OpenAIBackendRole.SYSTEM)
                agent_log.info(f"Agent {self.social_agent_id}: {result}")
                return result
        raise ValueError(f"Function {func_name} not found in the list.")

    def perform_agent_graph_action(
        self,
        action_name: str,
        arguments: dict[str, Any],
    ):
        r"""Remove edge if action is unfollow or add edge
        if action is follow to the agent graph.
        """
        if "unfollow" in action_name:
            followee_id: int | None = arguments.get("followee_id", None)
            if followee_id is None:
                return
            self.agent_graph.remove_edge(self.social_agent_id, followee_id)
            agent_log.info(
                f"Agent {self.social_agent_id} unfollowed Agent {followee_id}")
        elif "follow" in action_name:
            followee_id: int | None = arguments.get("followee_id", None)
            if followee_id is None:
                return
            self.agent_graph.add_edge(self.social_agent_id, followee_id)
            agent_log.info(
                f"Agent {self.social_agent_id} followed Agent {followee_id}")

    def __str__(self) -> str:
        return (f"{self.__class__.__name__}(agent_id={self.social_agent_id}, "
                f"model_type={self.model_type.value})")
