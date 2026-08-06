"""미국 주식 및 주요 증시 지수 수집 모듈 (USStockCollector)."""

import json
from typing import Any
import requests

# 주요 미국 종목 및 지수 매핑 사전
US_TICKER_MAP = {
    "엔비디아": "NVDA",
    "NVIDIA": "NVDA",
    "NVDA": "NVDA",
    "애플": "AAPL",
    "APPLE": "AAPL",
    "AAPL": "AAPL",
    "마이크로소프트": "MSFT",
    "MICROSOFT": "MSFT",
    "MSFT": "MSFT",
    "테슬라": "TSLA",
    "TESLA": "TSLA",
    "TSLA": "TSLA",
    "알파벳": "GOOGL",
    "구글": "GOOGL",
    "GOOGL": "GOOGL",
    "나스닥": "^IXIC",
    "NASDAQ": "^IXIC",
    "S&P500": "^GSPC",
    "SP500": "^GSPC",
    "필라델피아반도체": "^SOX",
}


class USStockCollector:
    """미국 증시 종목 시세 및 주요 재무 수치를 수집하는 클래스."""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def resolve_ticker(self, symbol_or_name: str) -> str:
        """한글 또는 기업명을 Yahoo Finance 티커 기호로 변환한다."""
        clean_name = symbol_or_name.strip().upper().replace(" ", "")
        return US_TICKER_MAP.get(clean_name, US_TICKER_MAP.get(symbol_or_name.strip(), symbol_or_name.strip().upper()))

    def get_us_stock_quote(self, symbol_or_name: str) -> dict[str, Any]:
        """미국 종목/지수의 실시간 시세 및 재무 지표를 조회한다."""
        ticker = self.resolve_ticker(symbol_or_name)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"

        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("chart", {}).get("result", [])[0]
                meta = result.get("meta", {})
                
                price = meta.get("regularMarketPrice", "N/A")
                prev_close = meta.get("chartPreviousClose", "N/A")
                currency = meta.get("currency", "USD")
                name = meta.get("shortName") or meta.get("symbol") or ticker

                pct_change_str = "N/A"
                if isinstance(price, (int, float)) and isinstance(prev_close, (int, float)) and prev_close > 0:
                    pct = ((price - prev_close) / prev_close) * 100
                    pct_change_str = f"{pct:+.2f}%"

                return {
                    "symbol": ticker,
                    "name": name,
                    "current_price": f"${price:,.2f}" if isinstance(price, (int, float)) else str(price),
                    "change_percent": pct_change_str,
                    "currency": currency,
                    "url": f"https://finance.yahoo.com/quote/{ticker}",
                    "status": "success",
                }
        except Exception as e:
            pass

        # 에러 시 Fallback 데이터 구조
        return {
            "symbol": ticker,
            "name": symbol_or_name,
            "current_price": "N/A",
            "change_percent": "N/A",
            "currency": "USD",
            "url": f"https://finance.yahoo.com/quote/{ticker}",
            "status": "fallback",
        }
