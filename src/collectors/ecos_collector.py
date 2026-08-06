"""
한국은행 ECOS(경제통계시스템) Open API 수집기.

2순위 확장 대상 중 채권(Bond) 자산군의 수치형 지표(기준금리, 국고채 금리 등)를 수집한다.
공식 문서: https://ecos.bok.or.kr/api/

다른 수집기(DartCollector 등)는 뉴스/공시처럼 "문서형" 데이터를 RawItem(title/url/summary)으로
반환하지만, ECOS는 날짜별 숫자값으로 이루어진 시계열 데이터라 문서형과 맞지 않는다.
models.py의 설계 원칙(수치형 테이블은 문서형과 분리)에 맞춰, 이 모듈은 BaseCollector를
상속하지 않고 RawIndicator라는 별도 반환 타입을 사용한다.

사용 전 준비물:
1. https://ecos.bok.or.kr 에서 회원가입 후 Open API 인증키 발급 (승인까지 다소 시간이 걸릴 수 있음)
2. 발급받은 인증키를 .env 파일의 ECOS_API_KEY에 입력

통계표코드/항목코드 참고:
- ECOS 통계코드검색(https://ecos.bok.or.kr/api/#/DevGuide/StatisticalCodeSearch)에서 확인 가능.
- 아래 INDICATOR_PRESETS에는 검증된 것만 등록했다. 국고채 3년물 등 추가 지표가 필요하면
  통계코드검색으로 정확한 stat_code/item_code1을 확인한 뒤 같은 형식으로 추가하면 된다.
"""

from dataclasses import dataclass
from datetime import datetime

import requests

from config.settings import settings


@dataclass
class RawIndicator:
    """ECOS처럼 수치형 시계열을 반환하는 수집기의 표준 반환 단위.

    문서형 RawItem(title/url 등)과 달리, 날짜별 숫자값 하나를 표현한다.
    """

    source: str
    asset_class: str
    indicator_code: str
    indicator_name: str
    date: datetime
    value: float
    unit: str = "%"


# 주기(cycle): "A"(연) / "Q"(분기) / "M"(월) / "D"(일)
# asset_class: 리포트에서 이 지표를 어느 자산군 필터에 포함시킬지 (생략하면 "bond").
INDICATOR_PRESETS: dict[str, dict] = {
    "base_rate": {
        "stat_code": "722Y001",
        "item_code1": "0101000",
        "name": "한국은행 기준금리",
        "cycle": "M",
        "unit": "%",
        "asset_class": "bond",
    },
    # stat_code는 scripts/lookup_ecos_table.py로 사용자가 직접 조회해 확인함 (2026-07-31).
    "kospi": {
        "stat_code": "802Y001",
        "item_code1": "0001000",
        "name": "코스피지수",
        "cycle": "D",
        "unit": "pt",
        "asset_class": "stock",
    },
    "kosdaq": {
        "stat_code": "802Y001",
        "item_code1": "0089000",
        "name": "코스닥지수",
        "cycle": "D",
        "unit": "pt",
        "asset_class": "stock",
    },
    "usd_krw": {
        "stat_code": "731Y001",
        "item_code1": "0000001",
        "name": "원/달러 환율(매매기준율)",
        "cycle": "D",
        "unit": "원",
        "asset_class": "bond",
    },
}


class EcosApiError(RuntimeError):
    """ECOS API가 에러를 반환했을 때 발생시키는 예외."""


class EcosCollector:
    source_name = "ECOS"

    def __init__(self, api_key: str | None = None, timeout: int = 10):
        self.api_key = api_key or settings.ecos_api_key
        self.base_url = "https://ecos.bok.or.kr/api/StatisticSearch"
        self.timeout = timeout

    def collect(
        self,
        start_date: datetime,
        end_date: datetime,
        indicators: list[str] | None = None,
    ) -> list[RawIndicator]:
        """
        지정된 기간의 지표를 수집하여 RawIndicator 리스트로 반환한다.

        Args:
            start_date: 조회 시작일
            end_date: 조회 종료일
            indicators: INDICATOR_PRESETS 키 목록. None이면 등록된 전체 지표를 수집.
        """
        if not self.api_key:
            raise EcosApiError(
                "ECOS_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요 (.env.example 참고)."
            )

        target_keys = indicators or list(INDICATOR_PRESETS.keys())
        all_items: list[RawIndicator] = []
        for key in target_keys:
            if key not in INDICATOR_PRESETS:
                raise ValueError(
                    f"알 수 없는 지표 키: {key}. 등록된 키: {list(INDICATOR_PRESETS.keys())}"
                )
            preset = INDICATOR_PRESETS[key]
            rows = self._fetch_rows(preset, start_date, end_date)
            all_items.extend(self._to_raw_indicators(preset, rows))

        return all_items

    def _fetch_rows(self, preset: dict, start_date: datetime, end_date: datetime) -> list[dict]:
        cycle = preset["cycle"]
        search_start = self._format_date(start_date, cycle)
        search_end = self._format_date(end_date, cycle)

        # 경로 형식: /StatisticSearch/{인증키}/{파일타입}/{언어}/{시작건수}/{종료건수}/
        #            {통계표코드}/{주기}/{검색시작일자}/{검색종료일자}/{항목코드1}
        url = (
            f"{self.base_url}/{self.api_key}/json/kr/1/10000/"
            f"{preset['stat_code']}/{cycle}/{search_start}/{search_end}/{preset['item_code1']}"
        )
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        if "StatisticSearch" not in payload:
            result = payload.get("RESULT", {})
            code = result.get("CODE", "UNKNOWN")
            # INFO-200은 "조회된 데이터가 없습니다"로, 에러가 아니라 단순 결과 없음을 의미
            if code == "INFO-200":
                return []
            raise EcosApiError(f"ECOS API 오류 ({code}): {result.get('MESSAGE', payload)}")

        return payload["StatisticSearch"].get("row", [])

    def _to_raw_indicators(self, preset: dict, rows: list[dict]) -> list[RawIndicator]:
        result: list[RawIndicator] = []
        for row in rows:
            date = self._parse_time(row.get("TIME", ""), preset["cycle"])
            if date is None:
                continue
            try:
                value = float(row.get("DATA_VALUE", ""))
            except (TypeError, ValueError):
                continue

            result.append(
                RawIndicator(
                    source=self.source_name,
                    asset_class=preset.get("asset_class", "bond"),
                    # stat_code만 쓰면 코스피/코스닥처럼 같은 통계표(802Y001)를 공유하고
                    # item_code1만 다른 여러 지표가 (indicator_code, date) DB 유니크 제약에
                    # 충돌한다. stat_code_item_code1 조합으로 시리즈 단위 유일성을 보장한다.
                    indicator_code=f"{preset['stat_code']}_{preset['item_code1']}",
                    indicator_name=row.get("ITEM_NAME1") or preset["name"],
                    date=date,
                    value=value,
                    # ECOS가 반환하는 UNIT_NAME은 코스피/코스닥처럼 "1980.01.04=100" 같은
                    # 기준시점 설명일 때가 있어 리포트에 그대로 쓰면 깨져 보인다.
                    # 항상 프리셋에 직접 지정한(검증된) 단위를 사용한다.
                    unit=preset["unit"],
                )
            )
        return result

    @staticmethod
    def _format_date(dt: datetime, cycle: str) -> str:
        if cycle == "A":
            return dt.strftime("%Y")
        if cycle == "Q":
            quarter = (dt.month - 1) // 3 + 1
            return f"{dt.strftime('%Y')}Q{quarter}"
        if cycle == "M":
            return dt.strftime("%Y%m")
        return dt.strftime("%Y%m%d")  # "D"(일)

    @staticmethod
    def _parse_time(time_str: str, cycle: str) -> datetime | None:
        try:
            if cycle == "A":
                return datetime.strptime(time_str, "%Y")
            if cycle == "Q":
                year, q = time_str.split("Q")
                month = (int(q) - 1) * 3 + 1
                return datetime(int(year), month, 1)
            if cycle == "M":
                return datetime.strptime(time_str, "%Y%m")
            return datetime.strptime(time_str, "%Y%m%d")
        except (ValueError, IndexError):
            return None
