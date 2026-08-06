"""Agent Tool 기본 인터페이스 및 데코레이터 모듈."""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentTool:
    """LLM Agent가 호출 가능한 도구 규격."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)

    def execute(self, **kwargs: Any) -> Any:
        """도구 함수를 안전하게 실행한다."""
        try:
            return self.func(**kwargs)
        except Exception as e:
            return {"error": f"도구 실행 중 오류 발생: {e}"}

    def to_openai_schema(self) -> dict[str, Any]:
        """OpenAI Function Calling 규격으로 변환한다."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Anthropic Tool Use 규격으로 변환한다."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters or {"type": "object", "properties": {}},
        }
