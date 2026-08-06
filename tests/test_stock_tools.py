"""CorpCodeMapper 및 Stock Finance Agent Tools 단위 테스트."""

from unittest.mock import MagicMock, patch

from src.agent_tools import global_registry
from src.collectors.corp_code_mapper import CorpCodeMapper, global_corp_mapper


def test_corp_code_mapper_known_corps():
    """주요 알려진 기업명의 고유코드 및 종목코드 매핑을 검증한다."""
    mapper = CorpCodeMapper()

    samsung_info = mapper.get_info("삼성전자")
    assert samsung_info is not None
    assert samsung_info["corp_code"] == "00126380"
    assert samsung_info["stock_code"] == "005930"

    sk_code = mapper.get_corp_code("SK하이닉스")
    assert sk_code == "00164779"

    naver_stock = mapper.get_stock_code("네이버")
    assert naver_stock == "00266961" or naver_stock == "035420"


def test_get_corp_code_agent_tool():
    """get_corp_code Agent Tool 실행을 검증한다."""
    result = global_registry.execute("get_corp_code", corp_name="삼성전자")
    assert result["found"] is True
    assert result["corp_code"] == "00126380"


@patch("src.collectors.stock_finance_collector.requests.get")
def test_query_stock_price_and_finance_tool(mock_get):
    """query_stock_price_and_finance Agent Tool 파싱 실행을 검증한다."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = """
    <html>
      <p class="no_today"><span class="blind">75,000</span></p>
    </html>
    """
    mock_get.return_value = mock_resp

    result = global_registry.execute("query_stock_price_and_finance", corp_name_or_code="삼성전자")
    assert isinstance(result, dict)
    assert result["stock_code"] == "005930"
    assert result["current_price"] == "75,000"


@patch("src.agent_tools.dart_tools.DartCollector")
def test_search_dart_disclosures_with_corp_name(mock_collector_cls):
    """search_dart_disclosures 도구가 corp_name을 자동으로 corp_code로 변환하는지 검증한다."""
    mock_instance = MagicMock()
    mock_collector_cls.return_value = mock_instance
    dummy_item = MagicMock()
    dummy_item.published_at.strftime.return_value = "2026-08-05"
    dummy_item.raw_meta = {}
    mock_instance.collect.return_value = [dummy_item]

    global_registry.execute("search_dart_disclosures", corp_name="삼성전자", days=7)

    assert mock_instance.collect.called
    assert mock_instance.collect.call_args.kwargs["corp_code"] == "00126380"
