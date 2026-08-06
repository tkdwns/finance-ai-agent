"""금융 뉴스 RSS 조회를 위한 Agent Tool 모듈."""

from datetime import datetime, timedelta
from typing import Any

from src.agent_tools.registry import global_registry
from src.collectors.news_collector import NewsCollector


@global_registry.register(
    name="search_financial_news",
    description="국내 주요 언론사의 최신 금융/경제 RSS 뉴스를 수집 및 검색합니다.",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "조회할 최근 기간(일 단위, 기본값 7일)",
            }
        },
    },
)
def search_financial_news(days: int = 7) -> list[dict[str, Any]]:
    """뉴스 데이터를 수집하여 반환한다."""
    collector = NewsCollector()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    items = collector.collect(start_date=start_date, end_date=end_date)

    return [
        {
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at.strftime("%Y-%m-%d %H:%M"),
            "summary": item.summary,
            "source": item.source,
        }
        for item in items
    ]
