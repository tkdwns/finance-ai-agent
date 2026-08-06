"""
FRED(세인트루이스 연방준비은행) Open API 기반 해외 주요 지수 수집기.

나스닥종합지수(NASDAQCOM), S&P500(SP500) 등 미국 지수를 가져온다. ECOS와 마찬가지로
날짜별 숫자값 시계열이라 RawIndicator(ecos_collector.py)를 그대로 재사용한다.

사용 전 준비물:
1. https://fred.stlouisfed.org 에서 회원가입 후 API Key 발급 (무료, 즉시 발급)
2. 발급받은 키를 .env 파일의 FRED_API_KEY에 입력
"""

from datetime import datetime

import requests

from config.settings import settings
from src.collectors.ecos_collector import RawIndicator

# series_id는 FRED에 등록된 공식 시리즈 이름. asset_class="stock"으로 등록해
# report_generator.py가 주식/전체 필터 리포트에 함께 표시한다.
INDICATOR_PRESETS: dict[str, dict] = {
    "nasdaq": {"series_id": "NASDAQCOM", "name": "나스닥종합지수", "unit": "pt", "asset_class": "stock"},
    "sp500": {"series_id": "SP500", "name": "S&P500", "unit": "pt", "asset_class": "stock"},
}


class FredApiError(RuntimeError):
    """FRED API가 에러를 반환했을 때 발생시키는 예외."""


class FredCollector:
    source_name = "FRED"

    def __init__(self, api_key: str | None = None, timeout: int = 10):
        self.api_key = api_key or settings.fred_api_key
        self.base_url = "https://api.stlouisfed.org/fred/series/observations"
        self.timeout = timeout

    def collect(
        self, start_date: datetime, end_date: datetime, indicators: list[str] | None = None
    ) -> list[RawIndicator]:
        if not self.api_key:
            raise FredApiError("FRED_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요 (.env.example 참고).")

        keys = indicators or list(INDICATOR_PRESETS.keys())
        invalid = [k for k in keys if k not in INDICATOR_PRESETS]
        if invalid:
            raise ValueError(f"알 수 없는 지표 키: {invalid}. 사용 가능한 키: {list(INDICATOR_PRESETS.keys())}")

        results: list[RawIndicator] = []
        for key in keys:
            results.extend(self._fetch_series(INDICATOR_PRESETS[key], start_date, end_date))
        return results

    def _fetch_series(self, preset: dict, start_date: datetime, end_date: datetime) -> list[RawIndicator]:
        params = {
            "series_id": preset["series_id"],
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d"),
        }
        response = requests.get(self.base_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        if "error_message" in payload:
            raise FredApiError(f"FRED API 오류: {payload['error_message']}")

        results = []
        for obs in payload.get("observations", []):
            date = self._parse_date(obs.get("date"))
            value = self._parse_value(obs.get("value"))
            if date is None or value is None:
                continue  # 휴장일 등은 value="."로 오는 경우가 있어 건너뜀
            results.append(
                RawIndicator(
                    source=self.source_name,
                    asset_class=preset["asset_class"],
                    indicator_code=preset["series_id"],
                    indicator_name=preset["name"],
                    date=date,
                    value=value,
                    unit=preset["unit"],
                )
            )
        return results

    @staticmethod
    def _parse_date(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            return None

    @staticmethod
    def _parse_value(raw: str | None) -> float | None:
        if not raw or raw == ".":
            return None
        try:
            return float(raw)
        except ValueError:
            return None
