"""
중복/유사 기사 제거 모듈.

1. URL이 완전히 동일하면 중복으로 간주한다 (항상 적용).
2. 제목 유사도가 threshold 이상이면 근접 중복(여러 언론사가 같은 통신사 기사를
   재배포하는 경우 등)으로 간주하고 하나만 남긴다 (뉴스류에만 적용 권장).

주의: DART 공시처럼 "분기보고서", "주요사항보고서" 등 서로 다른 회사의 공시가
제목이 거의 동일한 구조화 데이터에는 제목 유사도 dedup을 적용하면 안 된다.
이런 소스는 이미 고유 식별자(rcept_no 등)로 구분되므로 title_similarity_threshold=None
으로 호출해 URL 기준 중복 제거만 수행해야 한다.
"""

from difflib import SequenceMatcher

from src.collectors.base import RawItem


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def deduplicate(
    items: list[RawItem], title_similarity_threshold: float | None = 0.85
) -> list[RawItem]:
    """
    URL 기준 완전 중복 제거 후, 제목 유사도 기반 근접 중복까지 제거한다.

    title_similarity_threshold=None이면 제목 유사도 검사를 건너뛰고 URL 기준 중복
    제거만 수행한다 (제목이 구조적으로 겹치는 공시/지표 데이터에 사용).

    유사 그룹 내에서는 가장 먼저 발행된(published_at이 이른) 항목을 남긴다
    (최초 보도를 우선하기 위함).

    주의: 제목 유사도 검사는 O(n^2)이다. 배치 크기가 수만 건 이상으로 커지면
    제목 앞 N글자 기준 버킷팅 등 사전 클러스터링 최적화가 필요하다.
    """
    seen_urls: set[str] = set()
    url_deduped: list[RawItem] = []
    for item in items:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        url_deduped.append(item)

    if title_similarity_threshold is None:
        return url_deduped

    result: list[RawItem] = []
    for item in url_deduped:
        duplicate_index = None
        for idx, kept in enumerate(result):
            if _title_similarity(item.title, kept.title) >= title_similarity_threshold:
                duplicate_index = idx
                break

        if duplicate_index is None:
            result.append(item)
        elif item.published_at < result[duplicate_index].published_at:
            result[duplicate_index] = item

    return result
