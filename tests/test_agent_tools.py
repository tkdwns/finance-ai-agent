"""Agent Tools 및 ToolRegistry 단위 테스트."""

from unittest.mock import MagicMock, patch

from src.agent_tools import global_registry


def test_global_registry_registration():
    """모든 주요 도구들이 레지스트리에 정상 등록되었는지 검증한다."""
    tools = global_registry.list_tools()
    tool_names = [t.name for t in tools]

    assert "search_dart_disclosures" in tool_names
    assert "fetch_dart_document_text" in tool_names
    assert "query_ecos_indicators" in tool_names
    assert "query_fred_indicators" in tool_names
    assert "search_financial_news" in tool_names
    assert "search_financial_laws" in tool_names


def test_openai_and_anthropic_schemas():
    """도구들이 OpenAI 및 Anthropic API 전용 스키마로 올바르게 변환되는지 검증한다."""
    openai_schemas = global_registry.get_openai_schemas()
    anthropic_schemas = global_registry.get_anthropic_schemas()

    assert len(openai_schemas) >= 6
    assert len(anthropic_schemas) >= 6

    # OpenAI 형식 검증
    first_openai = openai_schemas[0]
    assert first_openai["type"] == "function"
    assert "name" in first_openai["function"]
    assert "description" in first_openai["function"]
    assert "parameters" in first_openai["function"]

    # Anthropic 형식 검증
    first_anthropic = anthropic_schemas[0]
    assert "name" in first_anthropic
    assert "description" in first_anthropic
    assert "input_schema" in first_anthropic


@patch("src.agent_tools.dart_tools.DartCollector")
def test_search_dart_disclosures_execution(mock_collector_cls):
    """search_dart_disclosures 도구 실행을 테스트한다."""
    mock_instance = MagicMock()
    mock_collector_cls.return_value = mock_instance

    mock_item = MagicMock()
    mock_item.title = "삼성전자 사업보고서 제출"
    mock_item.url = "http://dart.fss.or.kr/test"
    mock_item.published_at = MagicMock()
    mock_item.published_at.strftime.return_value = "2026-08-01"
    mock_item.raw_meta = {"corp_name": "삼성전자", "rcept_no": "20260801000001", "report_nm": "사업보고서"}

    mock_instance.collect.return_value = [mock_item]

    result = global_registry.execute("search_dart_disclosures", corp_code="00126380", days=7)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["title"] == "삼성전자 사업보고서 제출"
    assert result[0]["corp_name"] == "삼성전자"


def test_invalid_tool_execution():
    """존재하지 않는 도구를 실행할 때 에러 메시지를 반환하는지 검증한다."""
    result = global_registry.execute("non_existent_tool")
    assert "error" in result
    assert "등록되지 않은 도구" in result["error"]
