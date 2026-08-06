"""미 연준 FRED 경제지표 조회를 위한 Agent Tool 모듈."""

from datetime import datetime, timedelta
from typing import Any

from src.agent_tools.registry import global_registry
from src.collectors.fred_collector import FredCollector


@global_registry.register(
    name="query_fred_indicators",
    description="미국 연준 FRED API를 통해 미국 기준금리(FEDFUNDS), 10년물 국채금리(DGS10) 등 글로벌 마크로 지표를 조회합니다.",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "조회할 최근 기간(일 단위, 기본값 30일)",
            },
            "series_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "조회할 FRED 시리즈 ID 목록 (선택사항, 예: ['FEDFUNDS', 'DGS10'])",
            },
        },
    },
)
def query_fred_indicators(
    days: int = 30, series_ids: list[str] | None = None
) -> list[dict[str, Any]]:
    """FRED 지표 데이터를 수집하여 반환한다."""
    collector = FredCollector()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    items = collector.collect(start_date=start_date, end_date=end_date, indicators=series_ids)

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
