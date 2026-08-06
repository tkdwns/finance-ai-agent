"""Agent 추론 상태 및 대화 이력 관리 모듈."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentStep:
    """Agent의 단일 추론/실행 단계 (Think-Act-Observe)."""

    thought: str
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    observation: Any | None = None


@dataclass
class AgentState:
    """Agent의 전체 실행 상태 및 추론 이력."""

    query: str
    steps: list[AgentStep] = field(default_factory=list)
    final_answer: str | None = None

    def add_step(self, step: AgentStep) -> None:
        """추론 단계를 추가한다."""
        self.steps.append(step)
