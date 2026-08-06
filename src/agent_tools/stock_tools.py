"""기업명 고유코드 매핑 및 실시간 주가/재무 수치 분석을 위한 Agent Tool 모듈."""

from typing import Any

from src.agent_tools.registry import global_registry
from src.collectors.corp_code_mapper import global_corp_mapper
from src.collectors.stock_finance_collector import StockFinanceCollector


@global_registry.register(
    name="get_corp_code",
    description="국내 기업명(예: '삼성전자', 'SK하이닉스', '카카오')을 DART 8자리 고유코드 및 KRX 6자리 주식 종목코드로 전환합니다.",
    parameters={
        "type": "object",
        "properties": {
            "corp_name": {
                "type": "string",
                "description": "조회할 한글 또는 영문 기업명 (예: '삼성전자')",
            }
        },
        "required": ["corp_name"],
    },
)
def get_corp_code(corp_name: str) -> dict[str, Any]:
    """기업 정보 및 코드를 조회하여 반환한다."""
    info = global_corp_mapper.get_info(corp_name)
    if not info:
        return {"corp_name": corp_name, "found": False, "message": "등록되지 않은 기업명입니다."}
    return {"corp_name": corp_name, "found": True, **info}


@global_registry.register(
    name="query_stock_price_and_finance",
    description="국내 상장기업의 실시간 주가 시세, 시가총액 및 핵심 정량 재무 지표(PER, PBR)를 분석 조회합니다.",
    parameters={
        "type": "object",
        "properties": {
            "corp_name_or_code": {
                "type": "string",
                "description": "기업명 또는 종목코드 (예: '삼성전자' 또는 '005930')",
            }
        },
        "required": ["corp_name_or_code"],
    },
)
def query_stock_price_and_finance(corp_name_or_code: str) -> dict[str, Any]:
    """실시간 주가 시세 및 재무 지표 데이터를 수집하여 반환한다."""
    collector = StockFinanceCollector()
    return collector.fetch_info(corp_name_or_code)
