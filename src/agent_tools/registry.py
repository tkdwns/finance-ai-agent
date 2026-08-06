"""Agent Tool 레지스트리 관리 모듈."""

from typing import Any, Callable

from src.agent_tools.base import AgentTool


class ToolRegistry:
    """Agent가 사용할 수 있는 도구(Tool)들을 중앙에서 등록 및 관리하는 클래스."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(
        self, name: str, description: str, parameters: dict[str, Any] | None = None
    ) -> Callable:
        """데코레이터 형태로 도구를 등록한다."""

        def decorator(func: Callable) -> Callable:
            tool = AgentTool(
                name=name,
                description=description,
                func=func,
                parameters=parameters or {"type": "object", "properties": {}},
            )
            self._tools[name] = tool
            return func

        return decorator

    def get_tool(self, name: str) -> AgentTool | None:
        """이름으로 등록된 도구를 가져온다."""
        return self._tools.get(name)

    def list_tools(self) -> list[AgentTool]:
        """등록된 모든 도구 리스트를 반환한다."""
        return list(self._tools.values())

    def get_openai_schemas(self) -> list[dict[str, Any]]:
        """OpenAI 형식의 도구 정의 리스트를 반환한다."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def get_anthropic_schemas(self) -> list[dict[str, Any]]:
        """Anthropic 형식의 도구 정의 리스트를 반환한다."""
        return [tool.to_anthropic_schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs: Any) -> Any:
        """이름에 해당하는 도구를 찾아 실행한다."""
        tool = self.get_tool(name)
        if not tool:
            return {"error": f"등록되지 않은 도구입니다: {name}"}
        return tool.execute(**kwargs)


# 전역 기본 레지스트리 인스턴스
global_registry = ToolRegistry()
