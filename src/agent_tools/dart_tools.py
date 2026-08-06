"""DART 기업 공시 조회를 위한 Agent Tool 모듈."""

from datetime import datetime, timedelta
from typing import Any

from src.agent_tools.registry import global_registry
from src.collectors.dart_collector import DartCollector
from src.collectors.dart_document_fetcher import DartDocumentFetcher


from src.collectors.corp_code_mapper import global_corp_mapper


@global_registry.register(
    name="search_dart_disclosures",
    description="국내 상장기업의 최근 DART 공시 목록을 검색 및 조회합니다. 기업명(예: '삼성전자') 또는 고유코드 8자리를 입력할 수 있습니다.",
    parameters={
        "type": "object",
        "properties": {
            "corp_name": {
                "type": "string",
                "description": "한글/영문 기업명 (선택사항, 예: '삼성전자', 'SK하이닉스')",
            },
            "corp_code": {
                "type": "string",
                "description": "고유 기업 코드 8자리 (선택사항, 예: '00126380')",
            },
            "days": {
                "type": "integer",
                "description": "조회할 최근 기간(일 단위, 기본값 30일)",
            },
        },
        "required": ["corp_name"],
    },
)
def search_dart_disclosures(
    corp_name: str | None = None, corp_code: str | None = None, days: int = 30
) -> list[dict[str, Any]]:
    """DART 공시 목록을 수집하여 딕셔너리 리스트로 반환한다."""
    resolved_code = corp_code
    if not resolved_code and corp_name:
        resolved_code = global_corp_mapper.get_corp_code(corp_name)

    collector = DartCollector()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    items = collector.collect(start_date=start_date, end_date=end_date, corp_code=resolved_code)

    # 지정 기간 동안 결과가 없는 경우 90일로 확장 조회
    if not items and resolved_code:
        start_date = end_date - timedelta(days=90)
        items = collector.collect(start_date=start_date, end_date=end_date, corp_code=resolved_code)

    return [
        {
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at.strftime("%Y-%m-%d"),
            "corp_name": item.raw_meta.get("corp_name", ""),
            "rcept_no": item.raw_meta.get("rcept_no", ""),
            "report_name": item.raw_meta.get("report_nm", ""),
        }
        for item in items
    ]


@global_registry.register(
    name="fetch_dart_document_text",
    description="특정 DART 공시 접수번호(rcept_no)에 해당하는 본문 텍스트 요약을 조회합니다.",
    parameters={
        "type": "object",
        "properties": {
            "rcept_no": {
                "type": "string",
                "description": "공시 접수번호 14자리 (예: '20231015000001')",
            }
        },
        "required": ["rcept_no"],
    },
)
def fetch_dart_document_text(rcept_no: str) -> dict[str, Any]:
    """공시 원문 텍스트를 조회하여 반환한다."""
    fetcher = DartDocumentFetcher()
    text = fetcher.fetch_text(rcept_no=rcept_no)
    return {"rcept_no": rcept_no, "text": text or "본문을 불러올 수 없습니다."}
