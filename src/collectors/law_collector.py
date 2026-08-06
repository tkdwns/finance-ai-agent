"""
법령 개정 이력 수집기 (국가법령정보센터 Open API, target=law 목록 조회).

주의(정확도 한계): 이 API의 법령 목록 조회는 법령명으로 검색 시 보통 "현재 시행중인
버전" 1건을 반환한다. 즉 이 수집기는 과거 개정 이력 전체가 아니라 "조회 시점 기준
가장 최근 개정이 지정 기간 안에 있었는지"만 감지한다. 응답 XML의 필드명(시행일자,
공포일자, 제개정구분명 등)은 공식 문서를 실시간으로 확인하지 못해 일반적으로 알려진
값으로 가정했다 — 실제 실행 결과가 다르면 raw XML을 확인해 조정이 필요하다.

개정 이유 추출 (2026-08-01 라이브 검증 후 수정): 법령상세링크(법령상세링크 XML 필드)
URL을 그대로 요청하면 실제 내용이 아니라 <iframe>으로 본문 페이지를 감싼 래퍼 HTML만
반환된다(예전 코드는 이 래퍼 페이지에서 바로 "개정이유"를 찾으려 해서 실사용 중 15건
전부 추출 실패했음). 게다가 그 iframe이 가리키는 본문 페이지(lsInfoP.do)에도 조문
본문만 있고 "제·개정이유"는 없다 — 해당 텍스트는 별도 엔드포인트(lsRvsDocInfoR.do,
?lsRvsGubun=Rsn)에서만 내려온다. 그래서 1) 래퍼 페이지에서 lsiSeq/chrClsCd를 정규식으로
뽑아 2) lsRvsDocInfoR.do를 다시 요청해 그 안에서 "개정이유" 텍스트를 찾는 2단계 방식으로
수정했다. 그래도 못 찾으면 조용히 None을 반환하고, 호출부는 메타 정보로 대체한다.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config.settings import settings
from src.collectors.base import BaseCollector, RawItem

TARGET_LAWS = [
    "자본시장과 금융투자업에 관한 법률",
    "은행법",
    "금융소비자 보호에 관한 법률",
]

# 법령 상세 페이지에서 개정 이유 본문을 찾기 위해 시도하는 제목 문자열(우선순위 순).
_REASON_HEADINGS = ["제·개정이유", "제개정이유", "개정이유", "제안이유"]
_REASON_EXCERPT_LEN = 1500

# 법령상세링크(래퍼 페이지) 안의 <iframe src="...lsInfoP.do?lsiSeq=NNN&chrClsCd=NNN...">에서
# 실제 본문 페이지 식별자를 뽑아내는 정규식.
_IFRAME_PARAMS_RE = re.compile(r"lsInfoP\.do\?lsiSeq=(\d+)&chrClsCd=(\d+)")


class LawApiError(RuntimeError):
    """법령정보센터 API가 에러를 반환했을 때 발생시키는 예외."""


class LawCollector(BaseCollector):
    source_name = "법제처"

    def __init__(self, api_key: str | None = None, timeout: int = 10):
        self.api_key = api_key or settings.law_api_key
        self.base_url = "https://www.law.go.kr/DRF/lawSearch.do"
        self.timeout = timeout

    def collect(
        self, start_date: datetime, end_date: datetime, laws: list[str] | None = None
    ) -> list[RawItem]:
        if not self.api_key:
            raise LawApiError("LAW_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요 (.env.example 참고).")

        results: list[RawItem] = []
        for law_name in laws or TARGET_LAWS:
            root = self._search_law(law_name)
            results.extend(self._to_raw_items(root, law_name, start_date, end_date))
        return results

    def _search_law(self, law_name: str) -> ET.Element:
        params = {"OC": self.api_key, "target": "law", "type": "XML", "query": law_name}
        response = requests.get(self.base_url, params=params, timeout=self.timeout)
        response.raise_for_status()
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            raise LawApiError(f"응답을 XML로 파싱하지 못했습니다: {e}") from e

        if root.tag != "LawSearch":
            raise LawApiError(f"법령정보센터 API 오류 응답: {response.text[:200]}")

        return root

    def _to_raw_items(
        self, root: ET.Element, law_name: str, start_date: datetime, end_date: datetime
    ) -> list[RawItem]:
        items = []
        for law in root.findall(".//law"):
            amendment_date = self._parse_date(law.findtext("시행일자")) or self._parse_date(
                law.findtext("공포일자")
            )
            if amendment_date is None or not (start_date <= amendment_date <= end_date):
                continue

            detail_link = (law.findtext("법령상세링크") or "").strip()
            url = f"https://www.law.go.kr{detail_link}" if detail_link.startswith("/") else (
                detail_link or f"https://www.law.go.kr/법령/{law_name}"
            )

            # 법령명 검색은 "은행법"처럼 검색해도 은행법 시행령/시행규칙 등 연관 법령까지
            # 함께 반환하므로, 제목에는 검색어(law_name)가 아니라 응답의 실제 법령명을 쓴다.
            actual_law_name = law.findtext("법령명한글") or law_name

            meta_summary = (
                f"{law.findtext('소관부처명', '')} · 공포일자 {law.findtext('공포일자', '')} "
                f"· 시행일자 {law.findtext('시행일자', '')}"
            )
            reason_text = self._fetch_reason_excerpt(url)

            items.append(
                RawItem(
                    source=self.source_name,
                    asset_class="law",
                    title=f"{actual_law_name} {law.findtext('제개정구분명', '개정')}",
                    url=url,
                    published_at=amendment_date,
                    summary=meta_summary,
                    raw_meta={"law_name": law_name, "reason_text": reason_text},
                )
            )
        return items

    def _fetch_reason_excerpt(self, url: str) -> str | None:
        """법령 개정 이유 본문을 최선 노력으로 추출한다 (2단계 요청, 모듈 docstring 참고).

        1) 법령상세링크(래퍼 페이지)를 요청해 iframe에 담긴 lsiSeq/chrClsCd를 뽑는다.
        2) 그 값으로 lsRvsDocInfoR.do(제·개정이유 전용 페이지)를 다시 요청해 본문을 찾는다.

        어느 단계든 실패하거나 텍스트를 못 찾으면 None을 반환하고, 호출부는 메타 정보
        (부처/공포일자/시행일자)로 대체한다 (전체 수집이 이 단계 때문에 실패하지는 않는다).
        """
        try:
            wrapper = requests.get(url, timeout=self.timeout)
            wrapper.raise_for_status()
        except requests.RequestException:
            return None

        match = _IFRAME_PARAMS_RE.search(wrapper.text)
        if not match:
            return None
        lsi_seq, chr_cls_cd = match.group(1), match.group(2)

        reason_url = (
            f"https://www.law.go.kr/LSW/lsRvsDocInfoR.do?"
            f"lsiSeq={lsi_seq}&chrClsCd={chr_cls_cd}&lsRvsGubun=Rsn"
        )
        try:
            response = requests.get(reason_url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException:
            return None

        try:
            page_text = BeautifulSoup(response.text, "html.parser").get_text("\n")
        except Exception:
            return None

        for heading in _REASON_HEADINGS:
            idx = page_text.find(heading)
            if idx == -1:
                continue
            excerpt = page_text[idx + len(heading) : idx + len(heading) + _REASON_EXCERPT_LEN]
            excerpt = re.sub(r"\n{2,}", "\n", excerpt).strip("\n \t】")
            if len(excerpt) >= 30:  # 너무 짧으면 실제 본문이 아닐 가능성이 높음
                return excerpt
        return None

    @staticmethod
    def _parse_date(raw: str | None) -> datetime | None:
        if not raw or len(raw.strip()) != 8:
            return None
        try:
            return datetime.strptime(raw.strip(), "%Y%m%d")
        except ValueError:
            return None
