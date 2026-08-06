"""
모든 데이터 수집기(Collector)가 상속받는 베이스 클래스.

각 자산군/소스별 수집기(DartCollector, NewsCollector, LawCollector 등)는
이 클래스를 상속받아 collect() 메서드를 구현한다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawItem:
    """수집기가 반환하는 단일 원본 데이터 항목의 표준 형식."""

    source: str                  # 예: "DART", "네이버뉴스", "법령정보센터"
    asset_class: str             # 예: "stock", "bond", "real_estate", "crypto", "law"
    title: str
    url: str
    published_at: datetime
    summary: str = ""            # 원문 전체가 아닌 요약/제목만 저장 (저작권 고려)
    raw_meta: dict = field(default_factory=dict)  # 소스별 부가 정보 (공시코드, 법령 ID 등)


class BaseCollector(ABC):
    """모든 수집기의 공통 인터페이스."""

    source_name: str = "base"

    @abstractmethod
    def collect(self, start_date: datetime, end_date: datetime) -> list[RawItem]:
        """
        지정된 기간의 데이터를 수집하여 RawItem 리스트로 반환한다.

        주의:
        - 기사 원문 전체를 저장하지 않는다 (제목 + 요약 + 링크만).
        - 각 소스의 robots.txt / 이용약관을 준수한다.
        - 공식 Open API가 있는 소스는 크롤링보다 API를 우선 사용한다.
        """
        raise NotImplementedError
