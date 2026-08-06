"""문서 목록에 적용하는 공통 필터.

원래 extract_keywords.py 전용이었는데, 리포트의 "주요 공시·뉴스" 목록에는 이 필터가
적용되지 않아 키워드 섹션은 정제됐는데 문서 목록엔 노이즈가 그대로 보이는 비대칭이
있다는 피드백에 따라 공통 모듈로 분리해 report_generator.py에서도 재사용한다.
"""

import re

# ELS/DLS 등 구조화 증권 발행 공시는 거의 매일, 대량으로 반복 제출되며
# "등급", "한도", "신탁계약", "해지" 같은 정형화된 법률 문구가 판박이로 들어있어
# 노이즈가 된다. exclude_pattern="structured"로 기본 제공.
EXCLUDE_PRESETS: dict[str, str] = {
    "structured": r"파생결합증권|파생결합사채|주가연계증권|주가연계파생결합사채|ELW|ELS|DLS|신탁증권|수익증권",
}


def resolve_exclude_pattern(raw: str | None) -> str | None:
    if not raw:
        return None
    return EXCLUDE_PRESETS.get(raw, raw)  # 프리셋 이름이면 확장, 아니면 사용자가 준 정규식 그대로


def apply_document_filters(documents: list, exclude_pattern: str | None = None, only_enriched: bool = False) -> list:
    """title 기준 제외 패턴 -> "원문이 채워진 것만"(only_enriched) 순서로 필터링한다.

    documents는 UnifiedDocument처럼 title/summary 속성을 가진 객체 리스트면 된다.
    """
    resolved = resolve_exclude_pattern(exclude_pattern)
    if resolved:
        documents = [d for d in documents if not re.search(resolved, d.title)]
    if only_enriched:
        documents = [d for d in documents if d.summary != d.title]
    return documents
