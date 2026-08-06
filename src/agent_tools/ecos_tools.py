"""한국은행 ECOS 경제지표 및 금리 조회를 위한 Agent Tool 모듈."""

from datetime import datetime, timedelta
from typing import Any

from src.agent_tools.registry import global_registry
from src.collectors.ecos_collector import EcosCollector


@global_registry.register(
    name="query_ecos_indicators",
    description="한국은행 ECOS API를 통해 기준금리, 코스피, 환율 등 한국 주요 경제지표 시계열을 조회합니다.",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "조회할 최근 기간(일 단위, 기본값 30일)",
            },
            "indicators": {
                "type": "array",
                "items": {"type": "string"},
                "description": "조회할 지표 프리셋 목록 (선택사항, 예: ['base_rate', 'kospi', 'usd_krw'])",
            },
        },
    },
)
def query_ecos_indicators(
    days: int = 30, indicators: list[str] | None = None
) -> list[dict[str, Any]]:
    """ECOS 지표 데이터를 수집하여 반환한다."""
    collector = EcosCollector()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    items = collector.collect(start_date=start_date, end_date=end_date, indicators=indicators)

    return [
        {
            "name": item.indicator_name,
            "code": item.indicator_code,
            "date": item.date.strftime("%Y-%m-%d"),
            "value": item.value,
            "unit": item.unit,
        }
        for item in items
    ]
