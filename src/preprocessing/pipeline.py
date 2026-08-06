"""
전처리 파이프라인 진입점.

수집기(Collector)가 반환한 RawItem 리스트를 받아
정규화 -> 자산군 태깅 -> 중복 제거 순으로 처리한 뒤 반환한다.
이 결과가 storage 단계(DB 저장)로 전달된다.
"""

from src.collectors.base import RawItem
from src.preprocessing.deduplicator import deduplicate
from src.preprocessing.normalizer import normalize_text
from src.preprocessing.tagger import tag_asset_class


def preprocess(
    items: list[RawItem], title_similarity_threshold: float | None = 0.85
) -> list[RawItem]:
    """
    RawItem 리스트를 정규화 -> 태깅 -> 중복 제거 순으로 처리한다.

    title_similarity_threshold=None으로 호출하면 제목 유사도 dedup을 건너뛰고
    URL 기준 중복 제거만 수행한다. DART 공시처럼 제목이 구조적으로 겹치는
    데이터에는 반드시 None으로 호출해야 한다 (자세한 이유는 deduplicator.py 참고).
    """
    cleaned: list[RawItem] = []
    for item in items:
        item.title = normalize_text(item.title)
        item.summary = normalize_text(item.summary)
        item = tag_asset_class(item)
        cleaned.append(item)

    return deduplicate(cleaned, title_similarity_threshold=title_similarity_threshold)
