"""미국 주식 시세 조회 Tool 등록 모듈."""

from typing import Any
from src.agent_tools.registry import global_registry
from src.collectors.us_stock_collector import USStockCollector

us_stock_collector = USStockCollector()


@global_registry.register(
    name="query_us_stock_price",
    description="미국 주식 종목(엔비디아, 애플, 테슬라 등) 및 주가지수(나스닥, S&P500)의 실시간 주가 시세와 변동률을 조회한다.",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "미국 종목 티커 기호(NVDA, AAPL, TSLA) 또는 한글 기업명(엔비디아, 애플, 나스닥, S&P500)",
            }
        },
        "required": ["symbol"],
    },
)
def query_us_stock_price(symbol: str) -> dict[str, Any]:
    """미국 주식/지수의 현재 주가 및 시세 정보를 반환한다."""
    if not symbol or not symbol.strip():
        return {"error": "종목 코드 또는 이름을 입력하세요."}

    return us_stock_collector.get_us_stock_quote(symbol.strip())
