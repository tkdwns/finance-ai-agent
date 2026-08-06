"""ReAct 자율 추론 엔진 (FinancialAgent) 구현 모듈."""

import json
from typing import Any

from config.settings import settings
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.state import AgentState, AgentStep
from src.agent_tools.registry import ToolRegistry, global_registry


class FinancialAgent:
    """사용자 요청에 대해 도구를 선택하고 추론하는 자율형 금융 AI Agent."""

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        registry: ToolRegistry | None = None,
    ):
        self.provider = provider or settings.llm_provider
        self.api_key = api_key
        self.registry = registry or global_registry

    def run(self, query: str, max_steps: int = 5) -> AgentState:
        """ReAct (Think-Act-Observe) 자율 실행 루프를 수행한다."""
        state = AgentState(query=query)

        for _ in range(max_steps):
            step_result = self._step(state)
            state.add_step(step_result)

            # 도구 호출 없이 최종 답변을 도출했거나 에러인 경우 종료
            if not step_result.tool_name or state.final_answer:
                break

        if not state.final_answer and state.steps:
            state.final_answer = state.steps[-1].thought or "최대 추론 단계를 초과하였습니다."

        return state

    def _step(self, state: AgentState) -> AgentStep:
        """단일 추론 및 도구 실행 단계를 수행한다."""
        if self.provider == "gemini":
            return self._step_gemini(state)
        elif self.provider == "openai":
            return self._step_openai(state)
        elif self.provider == "anthropic":
            return self._step_anthropic(state)
        else:
            raise ValueError(f"지원하지 않는 LLM 제공자입니다: {self.provider}")

    def _step_gemini(self, state: AgentState) -> AgentStep:
        import openai

        client = openai.OpenAI(
            api_key=self.api_key or settings.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": state.query}]

        for step in state.steps:
            if step.tool_name:
                messages.append(
                    {
                        "role": "assistant",
                        "content": step.thought,
                        "tool_calls": [
                            {
                                "id": f"call_{step.tool_name}",
                                "type": "function",
                                "function": {
                                    "name": step.tool_name,
                                    "arguments": json.dumps(step.tool_input or {}),
                                },
                            }
                        ],
                    }
                )
                obs_str = json.dumps(step.observation, ensure_ascii=False)
                if len(obs_str) > 6000:
                    obs_str = obs_str[:6000] + "... (결과가 너무 길어 일부 생략함)"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": f"call_{step.tool_name}",
                        "content": obs_str,
                    }
                )

        tools = self.registry.get_openai_schemas()
        kwargs: dict[str, Any] = {"model": "gemini-1.5-flash", "messages": messages}
        if tools:
            kwargs["tools"] = tools

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        if choice.tool_calls:
            tool_call = choice.tool_calls[0]
            t_name = tool_call.function.name
            t_args = json.loads(tool_call.function.arguments or "{}")
            obs = self.registry.execute(t_name, **t_args)
            return AgentStep(
                thought=choice.content or f"{t_name} 도구 호출을 실행합니다.",
                tool_name=t_name,
                tool_input=t_args,
                observation=obs,
            )
        else:
            state.final_answer = choice.content or ""
            return AgentStep(thought=choice.content or "")

    def _step_openai(self, state: AgentState) -> AgentStep:
        import openai

        client = openai.OpenAI(api_key=self.api_key or settings.openai_api_key)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": state.query}]

        # 이전 수행 단계를 메시지 히스토리에 추가
        for step in state.steps:
            if step.tool_name:
                messages.append(
                    {
                        "role": "assistant",
                        "content": step.thought,
                        "tool_calls": [
                            {
                                "id": f"call_{step.tool_name}",
                                "type": "function",
                                "function": {
                                    "name": step.tool_name,
                                    "arguments": json.dumps(step.tool_input or {}),
                                },
                            }
                        ],
                    }
                )
                obs_str = json.dumps(step.observation, ensure_ascii=False)
                if len(obs_str) > 6000:
                    obs_str = obs_str[:6000] + "... (결과가 너무 길어 일부 생략함)"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": f"call_{step.tool_name}",
                        "content": obs_str,
                    }
                )

        tools = self.registry.get_openai_schemas()
        kwargs: dict[str, Any] = {"model": "gpt-4o-mini", "messages": messages}
        if tools:
            kwargs["tools"] = tools
            if len(state.steps) == 0:
                kwargs["tool_choice"] = "required"

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        if choice.tool_calls:
            tool_call = choice.tool_calls[0]
            t_name = tool_call.function.name
            t_args = json.loads(tool_call.function.arguments or "{}")
            obs = self.registry.execute(t_name, **t_args)
            return AgentStep(
                thought=choice.content or f"{t_name} 도구 호출을 실행합니다.",
                tool_name=t_name,
                tool_input=t_args,
                observation=obs,
            )
        else:
            state.final_answer = choice.content or ""
            return AgentStep(thought=choice.content or "")

    def _step_anthropic(self, state: AgentState) -> AgentStep:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key or settings.anthropic_api_key)
        tools = self.registry.get_anthropic_schemas()

        prompt = f"{state.query}\n"
        for i, step in enumerate(state.steps):
            prompt += f"\nStep {i+1}:\n생각: {step.thought}\n도구: {step.tool_name}\n결과: {step.observation}\n"

        kwargs: dict[str, Any] = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 2000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        if tools:
            kwargs["tools"] = tools

        response = client.messages.create(**kwargs)

        tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
        text_block = next((b for b in response.content if b.type == "text"), None)

        if tool_use_block:
            t_name = tool_use_block.name
            t_args = tool_use_block.input if isinstance(tool_use_block.input, dict) else {}
            obs = self.registry.execute(t_name, **t_args)
            thought_text = text_block.text if text_block else f"{t_name} 도구를 실행합니다."
            return AgentStep(
                thought=thought_text,
                tool_name=t_name,
                tool_input=t_args,
                observation=obs,
            )
        else:
            ans = text_block.text if text_block else ""
            state.final_answer = ans
            return AgentStep(thought=ans)
