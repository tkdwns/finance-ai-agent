"""
국토교통부 아파트 매매 실거래가 Open API 수집기 (공공데이터포털).

4단계 확장 대상. 지역(법정동코드)별·월별 아파트 매매 실거래 내역을 가져온다.
공식 문서: https://www.data.go.kr/data/15126469/openapi.do
엔드포인트: https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade

다른 수집기와 마찬가지로 이 데이터도 뉴스/공시 같은 "문서형"이 아니라 거래 한 건 한 건이
숫자·범주값으로 이루어진 정형 데이터라, RawItem이 아닌 RawTransaction을 반환한다
(ecos_collector.py의 RawIndicator와 같은 설계 원칙).

사용 전 준비물:
1. https://www.data.go.kr 에서 회원가입 후 "국토교통부_아파트 매매 실거래가 자료"
   활용신청 (보통 즉시 또는 1영업일 내 승인)
2. 마이페이지 > 오픈API > 인증키 발급현황에서 발급받은 서비스키(Decoding 방식 권장)를
   .env 파일의 MOLIT_API_KEY에 입력
3. .env의 REAL_ESTATE_REGIONS에 관심 지역의 법정동코드(5자리)를 콤마로 구분해 입력
   (비워두면 아래 REGION_PRESETS 기본값 사용)

지역코드(LAWD_CD) 참고:
- 법정동코드 5자리(시군구 코드)만 사용한다. 정확한 코드는 행정표준코드관리시스템
  (https://www.code.go.kr/stdcode/regCodeL.do)에서 확인할 수 있다.
- 아래 REGION_PRESETS는 자주 언급되는 서울 지역 몇 곳만 기본 등록했다. 관심 지역이
  다르면 직접 코드를 찾아 .env의 REAL_ESTATE_REGIONS에 추가하면 된다.

주의:
- 이 API는 DART/ECOS와 달리 날짜 범위가 아니라 "지역 1곳 + 연월 1개"당 한 번씩 호출해야
  한다. collect()가 요청 기간을 내부적으로 연월 목록으로 변환해 지역별로 반복 호출한다.
- 일일 호출 한도(기본 1,000건)가 낮은 편이라, 여러 지역 x 여러 달을 한 번에 수집하면
  빠르게 소진될 수 있다.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime

import requests

from config.settings import settings

# 법정동코드(5자리, 시군구 단위). 참고: https://www.code.go.kr/stdcode/regCodeL.do
REGION_PRESETS: dict[str, str] = {
    "seoul_jongno": "11110",  # 서울특별시 종로구
    "seoul_gangnam": "11680",  # 서울특별시 강남구
    "seoul_seocho": "11650",  # 서울특별시 서초구
    "seoul_songpa": "11710",  # 서울특별시 송파구
}


@dataclass
class RawTransaction:
    """MOLIT처럼 정형 거래 데이터를 반환하는 수집기의 표준 반환 단위.

    문서형 RawItem(title/url 등)과 달리, 거래 한 건의 지역·가격·면적·층·거래일을 표현한다.
    """

    source: str
    region: str
    complex_name: str
    transaction_price: float  # 만원 단위
    area_m2: float | None
    floor: int | None
    transaction_date: datetime


class MolitApiError(RuntimeError):
    """MOLIT/공공데이터포털 API가 에러를 반환했을 때 발생시키는 예외."""


class MolitCollector:
    source_name = "MOLIT"

    def __init__(self, api_key: str | None = None, timeout: int = 10):
        self.api_key = api_key or settings.molit_api_key
        self.base_url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
        self.timeout = timeout

    def collect(
        self,
        start_date: datetime,
        end_date: datetime,
        region_codes: list[str] | None = None,
        page_count: int = 100,
    ) -> list[RawTransaction]:
        """
        지정된 기간에 해당하는 연월들에 대해, 지역별로 아파트 매매 실거래 내역을 조회한다.

        Args:
            start_date, end_date: 조회 기간 (거래일 기준으로 이 범위 안의 건만 반환)
            region_codes: 법정동코드(5자리) 목록. None이면 REGION_PRESETS 값 또는
                .env의 REAL_ESTATE_REGIONS를 사용
            page_count: 페이지당 건수 (최대 1000 정도까지 가능하나 기본 100 권장)
        """
        if not self.api_key:
            raise MolitApiError(
                "MOLIT_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요 (.env.example 참고)."
            )

        target_regions = region_codes or settings.real_estate_regions or list(REGION_PRESETS.values())
        target_months = self._months_in_range(start_date, end_date)

        all_items: list[RawTransaction] = []
        for region_code in target_regions:
            for deal_ymd in target_months:
                all_items.extend(self._collect_region_month(region_code, deal_ymd, page_count))

        return [
            item for item in all_items if start_date <= item.transaction_date <= end_date
        ]

    def _collect_region_month(self, region_code: str, deal_ymd: str, page_count: int) -> list[RawTransaction]:
        items: list[RawTransaction] = []
        page_no = 1

        while True:
            root = self._fetch_page(region_code, deal_ymd, page_no, page_count)
            items.extend(self._to_raw_transactions(root))

            total_count = self._find_int(root, ".//totalCount") or 0
            if page_no * page_count >= total_count:
                break
            page_no += 1

        return items

    def _fetch_page(self, region_code: str, deal_ymd: str, page_no: int, page_count: int) -> ET.Element:
        params = {
            "serviceKey": self.api_key,
            "LAWD_CD": region_code,
            "DEAL_YMD": deal_ymd,
            "pageNo": page_no,
            "numOfRows": page_count,
        }
        response = requests.get(self.base_url, params=params, timeout=self.timeout)
        response.raise_for_status()

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            raise MolitApiError(f"응답을 XML로 파싱하지 못했습니다: {e}") from e

        if root.tag == "OpenAPI_ServiceResponse":
            err_msg = root.findtext(".//errMsg", "알 수 없는 오류")
            auth_msg = root.findtext(".//returnAuthMsg", "")
            raise MolitApiError(f"MOLIT API 오류: {err_msg} ({auth_msg})")

        result_code = root.findtext(".//resultCode")
        if result_code not in ("00", "000"):
            result_msg = root.findtext(".//resultMsg", "알 수 없는 오류")
            raise MolitApiError(f"MOLIT API 오류 (resultCode={result_code}): {result_msg}")

        return root

    def _to_raw_transactions(self, root: ET.Element) -> list[RawTransaction]:
        result: list[RawTransaction] = []
        for item in root.findall(".//item"):
            price = self._parse_price(item.findtext("dealAmount"))
            if price is None:
                continue

            date = self._parse_date(item)
            if date is None:
                continue

            region_name = (item.findtext("umdNm") or "").strip()
            complex_name = (item.findtext("aptNm") or "").strip()
            area = self._find_float(item, "excluUseAr") or self._find_float(item, "exclUseAr")
            floor = self._find_int(item, "floor")

            result.append(
                RawTransaction(
                    source=self.source_name,
                    region=region_name,
                    complex_name=complex_name,
                    transaction_price=price,
                    area_m2=area,
                    floor=floor,
                    transaction_date=date,
                )
            )
        return result

    @staticmethod
    def _parse_price(raw: str | None) -> float | None:
        if not raw:
            return None
        try:
            return float(raw.replace(",", "").strip())
        except ValueError:
            return None

    @staticmethod
    def _parse_date(item: ET.Element) -> datetime | None:
        year = item.findtext("dealYear")
        month = item.findtext("dealMonth")
        day = item.findtext("dealDay")
        try:
            if year and month and day:
                return datetime(int(year), int(month), int(day))
        except ValueError:
            return None

        # 일부 응답(구버전 필드명)은 분리된 년/월/일 대신 dealYmd(YYYYMMDD) 하나로 온다.
        combined = item.findtext("dealYmd")
        if combined and len(combined.strip()) == 8:
            try:
                return datetime.strptime(combined.strip(), "%Y%m%d")
            except ValueError:
                return None
        return None

    @staticmethod
    def _find_float(elem: ET.Element, tag: str) -> float | None:
        text = elem.findtext(tag)
        if not text or not text.strip():
            return None
        try:
            return float(text.strip())
        except ValueError:
            return None

    @staticmethod
    def _find_int(elem: ET.Element, path: str) -> int | None:
        text = elem.findtext(path)
        if not text or not text.strip():
            return None
        try:
            return int(text.strip())
        except ValueError:
            return None

    @staticmethod
    def _months_in_range(start_date: datetime, end_date: datetime) -> list[str]:
        """[start_date, end_date] 범위가 걸치는 모든 연월(YYYYMM)을 중복 없이 반환한다."""
        months = []
        year, month = start_date.year, start_date.month
        while (year, month) <= (end_date.year, end_date.month):
            months.append(f"{year}{month:02d}")
            month += 1
            if month > 12:
                month = 1
                year += 1
        return months


# 하위 호환성용 클래스 별칭
RealEstateCollector = MolitCollector
