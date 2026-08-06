"""국내 상장 주식 실시간 시세 및 정량 재무 지표(PER/PBR/ROE) 수집기 모듈."""

from dataclasses import dataclass
from typing import Any
import requests
from bs4 import BeautifulSoup

from src.collectors.corp_code_mapper import global_corp_mapper


@dataclass
class StockFinanceInfo:
    """주식 종목의 실시간 시세 및 핵심 재무 지표 데이터 구조."""

    corp_name: str
    stock_code: str
    current_price: str
    change_rate: str
    market_cap: str
    per: str
    pbr: str
    roe: str


class StockFinanceCollector:
    """네이버 금융 오픈 페이지를 파싱하여 종목 시세 및 재무 지표를 수집하는 클래스."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.base_url = "https://finance.naver.com/item/main.naver"

    def fetch_info(self, corp_name_or_code: str) -> dict[str, Any]:
        """기업명 또는 종목코드로 시세 및 재무 지표를 조회하여 반환한다."""
        info = global_corp_mapper.get_info(corp_name_or_code)
        stock_code = info["stock_code"] if info and info.get("stock_code") else corp_name_or_code.zfill(6)

        url = f"{self.base_url}?code={stock_code}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        try:
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 시세 정보 및 핵심 재무 지표 HTML 파싱
            rate_elem = soup.find("p", class_="no_today")
            current_price = rate_elem.find("span", class_="blind").text.strip() if rate_elem and rate_elem.find("span", class_="blind") else "N/A"

            cap_elem = soup.find(id="_market_sum")
            if cap_elem:
                raw_text = "".join(cap_elem.text.split())
                if "조" in raw_text:
                    idx = raw_text.find("조")
                    market_cap = f"{raw_text[:idx+1]} {raw_text[idx+1:]}억원"
                else:
                    market_cap = f"{raw_text}억원"
            else:
                market_cap = "N/A"

            per_elem = soup.find(id="_per")
            per = per_elem.text.strip() if per_elem else "N/A"

            pbr_elem = soup.find(id="_pbr")
            pbr = pbr_elem.text.strip() if pbr_elem else "N/A"

            return {
                "corp_name": corp_name_or_code,
                "stock_code": stock_code,
                "current_price": current_price,
                "market_cap": market_cap,
                "per": per,
                "pbr": pbr,
                "url": url,
            }
        except Exception as e:
            return {
                "corp_name": corp_name_or_code,
                "stock_code": stock_code,
                "current_price": "조회 불가",
                "market_cap": "N/A",
                "per": "N/A",
                "pbr": "N/A",
                "error": f"주가 수집 중 오류: {e}",
            }
