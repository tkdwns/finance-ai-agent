"""
자산군 자동 태깅 모듈.

DART, 실거래가 API처럼 출처 자체가 자산군을 특정할 수 있는 수집기는
이미 asset_class를 채워서 RawItem을 넘겨준다. 하지만 일반 뉴스 RSS처럼
자산군이 불분명한 항목은 이 규칙 기반 키워드 매칭으로 자산군을 추정한다.

주의: 규칙 기반 태깅은 완벽하지 않다. 매칭되는 키워드가 없으면 "unknown"으로
남겨두고, 이후 LLM 기반 정제(3단계) 대상으로 넘긴다. 즉, 이 모듈은 최종 판단이
아니라 1차 필터 역할이다.
"""

from src.collectors.base import RawItem

ASSET_CLASS_KEYWORDS: dict[str, list[str]] = {
    "stock": ["코스피", "코스닥", "상장", "주가", "증시", "공모주", "배당"],
    "bond": ["국채", "국고채", "회사채", "금리", "스프레드", "채권"],
    "real_estate": ["아파트", "전세", "월세", "분양", "실거래가", "재건축", "부동산"],
    "crypto": ["비트코인", "이더리움", "가상자산", "암호화폐", "거래소", "스테이블코인"],
}


def guess_asset_class(text: str) -> str | None:
    """텍스트에서 자산군별 키워드 매칭 개수를 세어 가장 많이 매칭된 자산군을 반환한다.
    아무 키워드도 매칭되지 않으면 None을 반환한다."""
    scores = {asset: 0 for asset in ASSET_CLASS_KEYWORDS}
    for asset, keywords in ASSET_CLASS_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[asset] += 1

    best_asset = max(scores, key=scores.get)
    if scores[best_asset] == 0:
        return None
    return best_asset


def tag_asset_class(item: RawItem) -> RawItem:
    """item.asset_class가 비어있을 때만 제목+요약 기반으로 자산군을 추정해 채운다.
    이미 자산군이 지정된 항목(예: DART 수집기가 채운 "stock")은 건드리지 않는다."""
    if item.asset_class:
        return item

    guessed = guess_asset_class(f"{item.title} {item.summary}")
    item.asset_class = guessed or "unknown"
    return item
