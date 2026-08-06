"""국가법령정보센터 금융 규제 개정 동향 조회를 위한 Agent Tool 모듈."""

from datetime import datetime, timedelta
from typing import Any

from src.agent_tools.registry import global_registry
from src.collectors.law_collector import LawCollector


@global_registry.register(
    name="search_financial_laws",
    description="자본시장법, 금융소비자보호법 등 최근 제·개정된 금융 관련 법령 및 규제 동향을 조회합니다.",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "조회할 최근 기간(일 단위, 기본값 30일)",
            }
        },
    },
)
def search_financial_laws(days: int = 30) -> list[dict[str, Any]]:
    """법령 개정 동향 데이터를 수집하여 반환한다."""
    collector = LawCollector()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    items = collector.collect(start_date=start_date, end_date=end_date)

    return [
        {
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at.strftime("%Y-%m-%d"),
            "summary": item.summary,
            "law_name": item.raw_meta.get("law_name", ""),
        }
        for item in items
    ]
