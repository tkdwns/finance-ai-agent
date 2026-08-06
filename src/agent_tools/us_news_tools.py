"""글로벌/미국 금융 뉴스 수집 Tool 등록 모듈."""

from typing import Any
from src.agent_tools.registry import global_registry
from src.collectors.us_news_collector import USNewsCollector

us_news_collector = USNewsCollector()


@global_registry.register(
    name="fetch_us_financial_news",
    description="미국 증시 및 월가 주요 기술주/반도체/금리 관련 글로벌 금융 뉴스와 링크를 수집한다.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "검색 주제 키워드(예: 엔비디아, 나스닥, US Tech, FOMC)",
            }
        },
        "required": [],
    },
)
def fetch_us_financial_news(query: str = "US Market") -> list[dict[str, Any]]:
    """글로벌 월가 금융 기사 목록을 반환한다."""
    return us_news_collector.fetch_global_news(query=query or "US Market")
