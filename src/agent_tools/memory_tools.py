"""RAG 기억 저장소 시맨틱 검색을 위한 Agent Tool 모듈."""

from typing import Any

from src.agent_tools.registry import global_registry
from src.memory.vector_store import global_memory


@global_registry.register(
    name="search_financial_memory",
    description="과거 수집되어 기억 저장소(Vector Memory)에 보관된 공시, 뉴스, 금리 지표 및 법령을 시맨틱 유사도로 검색합니다.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "검색할 키워드 또는 질문 문장 (예: '합병 공시', '기준금리 인상')",
            },
            "top_k": {
                "type": "integer",
                "description": "가장 관련성 높은 결과 개수 (기본값 5)",
            },
        },
        "required": ["query"],
    },
)
def search_financial_memory(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """기억 저장소에서 관련 문서를 시맨틱 검색하여 반환한다."""
    return global_memory.search(query=query, top_k=top_k)
