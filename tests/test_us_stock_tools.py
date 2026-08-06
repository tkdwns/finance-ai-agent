"""미국 주식 및 글로벌 뉴스 수집 단위 테스트."""

from unittest.mock import MagicMock, patch
from src.collectors.us_stock_collector import USStockCollector
from src.collectors.us_news_collector import USNewsCollector
from src.agent_tools.us_stock_tools import query_us_stock_price
from src.agent_tools.us_news_tools import fetch_us_financial_news


def test_us_stock_collector_resolve_ticker():
    """한글 키워드 및 대소문자 티커 변환을 검증한다."""
    collector = USStockCollector()
    assert collector.resolve_ticker("엔비디아") == "NVDA"
    assert collector.resolve_ticker("애플") == "AAPL"
    assert collector.resolve_ticker("테슬라") == "TSLA"
    assert collector.resolve_ticker("나스닥") == "^IXIC"
    assert collector.resolve_ticker("MSFT") == "MSFT"


@patch("requests.get")
def test_us_stock_collector_get_quote(mock_get):
    """미국 주식 시세 API 응답 수집을 검증한다."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 128.5,
                        "chartPreviousClose": 125.0,
                        "currency": "USD",
                        "shortName": "NVIDIA Corporation",
                        "symbol": "NVDA",
                    }
                }
            ]
        }
    }
    mock_get.return_value = mock_resp

    collector = USStockCollector()
    quote = collector.get_us_stock_quote("NVDA")

    assert quote["symbol"] == "NVDA"
    assert quote["current_price"] == "$128.50"
    assert quote["change_percent"] == "+2.80%"
    assert quote["status"] == "success"


def test_query_us_stock_price_tool():
    """query_us_stock_price Tool 호출을 검증한다."""
    res = query_us_stock_price("엔비디아")
    assert "symbol" in res
    assert res["symbol"] == "NVDA"


def test_fetch_us_financial_news_tool():
    """fetch_us_financial_news Tool 호출을 검증한다."""
    articles = fetch_us_financial_news("NVDA")
    assert isinstance(articles, list)
    assert len(articles) > 0
    assert "title" in articles[0]
