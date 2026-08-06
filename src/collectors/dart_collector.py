"""
DART(전자공시시스템) Open API 수집기.

1단계 MVP의 핵심 대상. 국내 상장기업의 공시 목록을 가져온다.
공식 문서: https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS001

사용 전 준비물:
1. https://opendart.fss.or.kr 에서 회원가입 후 오픈API 이용 신청 (즉시 발급)
2. 발급받은 인증키를 .env 파일의 DART_API_KEY에 입력
"""

from datetime import datetime

import requests

from config.settings import settings
from src.collectors.base import BaseCollector, RawItem

# DART 응답 status 코드
_STATUS_OK = "000"          # 정상
_STATUS_NO_DATA = "013"     # 조회된 데이터가 없습니다 (에러 아님, 단순 결과 없음)

# DART 공시 유형(pblntf_ty) 코드. list.json API는 한 번에 코드 1개만 필터링 가능하므로
# 여러 유형을 함께 조회하려면 collect_by_types()로 유형별로 나눠 호출 후 병합해야 한다.
DART_DISCLOSURE_TYPES: dict[str, str] = {
    "A": "정기공시 (사업보고서/반기보고서/분기보고서 등)",
    "B": "주요사항보고 (인수합병, 자산양수도 등 실질적 이벤트)",
    "C": "발행공시 (증권신고서, 투자설명서 등)",
    "D": "지분공시 (임원·주요주주 소유상황, 대량보유상황 등 절차성 신고)",
    "E": "기타공시 (자율공시, IR 개최 안내 등)",
    "F": "외부감사관련",
    "G": "펀드공시",
    "H": "자산유동화",
    "I": "거래소공시 (공정공시, 주주총회소집공고 등)",
    "J": "공정위공시",
}

# 실질적인 경영 이벤트 위주로 보고 싶을 때 추천하는 조합
# (D 지분공시처럼 절차성 신고가 대부분을 차지하는 유형은 제외)
RECOMMENDED_SUBSTANTIAL_TYPES: list[str] = ["A", "B", "C"]


class DartApiError(RuntimeError):
    """DART API가 에러 상태 코드를 반환했을 때 발생시키는 예외."""


class DartCollector(BaseCollector):
    source_name = "DART"

    def __init__(self, api_key: str | None = None, timeout: int = 10):
        self.api_key = settings.dart_api_key if api_key is None else api_key
        self.base_url = "https://opendart.fss.or.kr/api/list.json"
        self.timeout = timeout

    def collect(
        self,
        start_date: datetime,
        end_date: datetime,
        corp_code: str | None = None,
        pblntf_ty: str | None = None,
        page_count: int = 100,
    ) -> list[RawItem]:
        """
        지정된 기간의 공시 목록을 조회하여 RawItem 리스트로 반환한다.

        Args:
            start_date: 조회 시작일
            end_date: 조회 종료일
            corp_code: 특정 기업의 DART 고유번호 (없으면 전체 상장기업 대상)
            pblntf_ty: 공시 유형 코드 1개 (DART_DISCLOSURE_TYPES 참고). None이면 전체 유형.
            page_count: 페이지당 건수 (DART 최대 100)
        """
        if not self.api_key:
            raise DartApiError(
                "DART_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요 (.env.example 참고)."
            )

        all_items: list[RawItem] = []
        page_no = 1

        while True:
            payload = self._fetch_page(
                start_date, end_date, page_no, page_count, corp_code, pblntf_ty
            )
            status = payload.get("status")

            if status == _STATUS_NO_DATA:
                break
            if status != _STATUS_OK:
                raise DartApiError(f"DART API 오류 (status={status}): {payload.get('message')}")

            all_items.extend(self._to_raw_items(payload.get("list", [])))

            total_page = payload.get("total_page", 1)
            if page_no >= total_page:
                break
            page_no += 1

        return all_items

    def collect_by_types(
        self,
        start_date: datetime,
        end_date: datetime,
        pblntf_types: list[str],
        corp_code: str | None = None,
        page_count: int = 100,
    ) -> list[RawItem]:
        """
        여러 공시 유형을 각각 조회한 뒤 하나로 병합한다 (rcept_no 기준 중복 제거).

        DART list.json API가 유형을 1개씩만 필터링할 수 있어서, "정기공시 + 주요사항보고
        + 발행공시"처럼 여러 유형을 함께 보고 싶을 때 이 메서드를 사용한다.
        """
        merged: dict[str, RawItem] = {}
        for ty in pblntf_types:
            items = self.collect(start_date, end_date, corp_code=corp_code, pblntf_ty=ty, page_count=page_count)
            for item in items:
                rcept_no = item.raw_meta.get("rcept_no", item.url)
                merged[rcept_no] = item  # 동일 rcept_no면 마지막 값으로 덮어써도 무방 (내용 동일)

        return list(merged.values())

    def _fetch_page(
        self,
        start_date: datetime,
        end_date: datetime,
        page_no: int,
        page_count: int,
        corp_code: str | None,
        pblntf_ty: str | None,
    ) -> dict:
        params = {
            "crtfc_key": self.api_key,
            "bgn_de": start_date.strftime("%Y%m%d"),
            "end_de": end_date.strftime("%Y%m%d"),
            "page_no": page_no,
            "page_count": page_count,
        }
        if corp_code:
            params["corp_code"] = corp_code
        if pblntf_ty:
            params["pblntf_ty"] = pblntf_ty

        response = requests.get(self.base_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _to_raw_items(self, entries: list[dict]) -> list[RawItem]:
        result: list[RawItem] = []
        for entry in entries:
            rcept_no = entry.get("rcept_no", "")
            rcept_dt = entry.get("rcept_dt", "")
            try:
                published_at = datetime.strptime(rcept_dt, "%Y%m%d")
            except ValueError:
                continue  # 날짜 파싱에 실패한 항목은 건너뛴다

            report_name = entry.get("report_nm", "")
            result.append(
                RawItem(
                    source=self.source_name,
                    asset_class="stock",
                    title=report_name,
                    url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
                    published_at=published_at,
                    # DART 목록 API는 본문 요약을 제공하지 않아 보고서명을 요약으로 사용
                    summary=report_name,
                    raw_meta={
                        "corp_name": entry.get("corp_name", ""),
                        "corp_code": entry.get("corp_code", ""),
                        "rcept_no": rcept_no,
                        "report_name": report_name,
                    },
                )
            )
        return result
