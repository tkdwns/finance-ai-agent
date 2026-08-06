"""
저장된 문서(공시 + 뉴스)에서 키워드를 추출해 keywords 테이블에 저장하는 스크립트.

사용법 (프로젝트 루트에서):
    python -m scripts.extract_keywords --days 7                  # 최근 7일, 전체 자산군, 통계+LLM 하이브리드
    python -m scripts.extract_keywords --days 7 --asset-class bond  # 채권 문서만 대상
    python -m scripts.extract_keywords --days 7 --no-llm          # LLM 없이 통계 결과만 (API 키 불필요)
    python -m scripts.extract_keywords --days 7 --top-n 15
    python -m scripts.extract_keywords --days 7 --provider openai # Anthropic 대신 OpenAI로 정제

사전 준비:
    --no-llm 없이 실행하려면 .env의 LLM_PROVIDER에 맞는 API 키
    (ANTHROPIC_API_KEY 또는 OPENAI_API_KEY)가 설정되어 있어야 한다.

자산군 처리 방식:
    --asset-class를 생략하면(기본값) DB에 저장된 문서 전체(공시 + 뉴스)를 대상으로 하되,
    자산군별로 나누어 각각 따로 키워드를 추출하고 저장한다. keywords 테이블의 한 행은
    하나의 asset_class에만 속할 수 있어서(models.py 참고), 여러 자산군 텍스트를 한 번에
    섞어 분석하면 결과가 어느 자산군 것인지 알 수 없게 되기 때문이다.
"""

import argparse
import re

from config.settings import settings
from src.analysis.keyword_extractor import extract_keywords
from src.common.document_filter import resolve_exclude_pattern
from src.common.period import get_period_bounds
from src.storage.db import ensure_schema_up_to_date, get_session
from src.storage.models import AssetClass, Base, Keyword, PeriodType
from src.storage.queries import UnifiedDocument, get_documents_by_period


def _extract_and_save_for_class(
    session,
    documents: list[UnifiedDocument],
    asset_class: str,
    period_type: str,
    start_date,
    end_date,
    top_n: int,
    use_llm: bool,
    only_enriched: bool,
    max_df: float,
    provider: str | None,
) -> tuple[int, list[dict]]:
    """documents(이미 asset_class 하나로 나뉜 상태)에서 키워드를 추출해 저장한다.

    DART 공시는 --fetch-text 없이 수집하면 summary가 title(report_name)과 동일해
    "제목만 있는 건"으로 간주하고, RSS 뉴스는 summary가 항상 title과 다른 설명
    텍스트라 자연히 "원문이 채워진 건"으로 간주된다.
    """
    texts = [doc.summary for doc in documents]

    enriched_docs = [doc for doc in documents if doc.summary != doc.title]
    enriched_ratio = len(enriched_docs) / len(documents) if documents else 0
    print(
        f"      원문(요약)이 채워진 건: {len(enriched_docs)}건 / 제목만 있는 건: {len(documents) - len(enriched_docs)}건"
    )
    if enriched_ratio < 0.3:
        print(
            "      [주의] 원문이 채워진 비율이 낮습니다. 이 상태로 키워드를 뽑으면 실제 사건 내용보다\n"
            "             공시 유형 이름이 상위에 뽑힐 수 있습니다. 먼저 --fetch-text --max-text-fetches를\n"
            "             늘려 원문을 더 채우거나, --only-enriched 옵션으로 원문이 채워진 건만 사용해보세요."
        )

    if only_enriched:
        if not enriched_docs:
            print(f"      [{asset_class}] 원문이 채워진 문서가 없어 건너뜁니다.")
            return 0, []
        texts = [doc.summary for doc in enriched_docs]
        print(f"      --only-enriched: 원문이 채워진 {len(enriched_docs)}건만 대상으로 추출합니다.")

    resolved_provider = provider or settings.llm_provider
    provider_label = "OpenAI API" if resolved_provider == "openai" else "Claude API"
    mode = "TF-IDF 통계만" if not use_llm else f"TF-IDF + {provider_label} 정제"
    print(f"      [{asset_class}] 키워드 추출 중 ({mode})")
    results = extract_keywords(texts, top_n=top_n, use_llm=use_llm, max_df=max_df, provider=provider)

    if not results:
        print(f"      [{asset_class}] 추출된 키워드가 없습니다 (텍스트가 너무 적거나 전부 불용어일 수 있습니다).")
        return 0, []

    saved = 0
    for item in results:
        existing = (
            session.query(Keyword)
            .filter_by(
                asset_class=asset_class,
                period_type=period_type,
                period_start=start_date,
                keyword=item["keyword"],
            )
            .first()
        )
        if existing:
            existing.score = item["score"]
            existing.explanation = item.get("explanation", "")
            continue

        session.add(
            Keyword(
                asset_class=asset_class,
                period_type=period_type,
                period_start=start_date,
                period_end=end_date,
                keyword=item["keyword"],
                score=item["score"],
                explanation=item.get("explanation", ""),
            )
        )
        saved += 1
    session.commit()

    print(f"\n      [{asset_class}] {'순위':<4} {'키워드':<15} {'점수':<8} {'등장건수':<8} 설명")
    print("      " + "-" * 90)
    for idx, item in enumerate(results, start=1):
        explanation = item["explanation"] or "(통계 결과만 사용, 설명 없음)"
        doc_count = sum(1 for t in texts if item["keyword"] in t)
        print(f"      {idx:<4} {item['keyword']:<15} {item['score']:<8.2f} {doc_count:<8} {explanation}")
    print(f"      [{asset_class}] 새로 저장/갱신된 키워드: {saved}건")

    return saved, results


def run_extract_keywords(
    days: int,
    top_n: int = 10,
    use_llm: bool = True,
    only_enriched: bool = False,
    exclude_pattern: str | None = None,
    max_df: float = 0.5,
    provider: str | None = None,
    asset_class: str | None = None,
) -> dict:
    """
    키워드 추출의 핵심 로직. CLI(argparse)와 스케줄러 양쪽에서 재사용할 수 있도록
    인자를 명시적으로 받는 함수로 분리했다.

    asset_class를 지정하면 그 자산군 문서만 대상으로 하고, 생략하면 저장된 모든
    자산군(현재는 stock/bond)을 각각 따로 추출한다.

    Returns:
        {"target_count": int, "saved": int, "keywords": {asset_class: [...]}} 형태의 결과 요약
    """
    ensure_schema_up_to_date(Base)

    start_date, end_date = get_period_bounds(days)
    period_type = PeriodType.DAILY if days <= 1 else PeriodType.WEEKLY

    session = get_session()
    try:
        target_classes = [asset_class] if asset_class else None
        documents = get_documents_by_period(session, start_date, end_date, asset_classes=target_classes)
        print(f"[1/3] 대상 문서 {len(documents)}건 조회 완료 ({start_date.date()} ~ {end_date.date()})")

        if not documents:
            print(
                "대상 데이터가 없습니다. 먼저 수집 스크립트를 실행하세요 "
                "(scripts.collect_dart / scripts.collect_bond / scripts.collect_news)."
            )
            return {"target_count": 0, "saved": 0, "keywords": {}}

        resolved_exclude_pattern = resolve_exclude_pattern(exclude_pattern)
        if resolved_exclude_pattern:
            before = len(documents)
            documents = [d for d in documents if not re.search(resolved_exclude_pattern, d.title)]
            print(f"      제외 패턴 적용: {before}건 -> {len(documents)}건 ({before - len(documents)}건 제외)")

        if not documents:
            print("제외 패턴 적용 후 남은 데이터가 없습니다. 패턴을 완화해보세요.")
            return {"target_count": 0, "saved": 0, "keywords": {}}

        grouped: dict[str, list[UnifiedDocument]] = {}
        for doc in documents:
            # doc.asset_class는 필터 없이 조회했을 때는 AssetClass enum 멤버,
            # --asset-class로 필터링했을 때는 그대로 넘긴 문자열이라 타입이 섞여 있다.
            # 콘솔 출력과 Keyword 저장 모두 일관되게 소문자 문자열("stock")을 쓰도록 정규화한다.
            key = getattr(doc.asset_class, "value", doc.asset_class)
            grouped.setdefault(key, []).append(doc)

        print(f"[2/3] 자산군별 분류: " + ", ".join(f"{cls}({len(docs)}건)" for cls, docs in grouped.items()))

        print("[3/3] 자산군별 키워드 추출 및 저장")
        total_saved = 0
        results_by_class: dict[str, list[dict]] = {}
        for cls, docs in grouped.items():
            saved, results = _extract_and_save_for_class(
                session, docs, cls, period_type, start_date, end_date,
                top_n, use_llm, only_enriched, max_df, provider,
            )
            total_saved += saved
            results_by_class[cls] = results

        return {"target_count": len(documents), "saved": total_saved, "keywords": results_by_class}
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="공시/뉴스 데이터에서 키워드 추출 및 저장")
    parser.add_argument("--days", type=int, default=7, help="최근 며칠간의 데이터를 대상으로 할지 (기본 7일)")
    parser.add_argument("--top-n", type=int, default=10, help="추출할 키워드 개수 (기본 10)")
    parser.add_argument(
        "--asset-class",
        type=str,
        default=None,
        choices=[c.value for c in AssetClass],
        help="특정 자산군만 대상으로 추출. 생략하면 저장된 전체 자산군을 각각 따로 추출",
    )
    parser.add_argument("--no-llm", action="store_true", help="LLM 정제 없이 TF-IDF 통계 결과만 사용")
    parser.add_argument(
        "--only-enriched",
        action="store_true",
        help="원문(요약)이 제목과 다른, 내용이 채워진 문서만 대상으로 추출 (제목뿐인 건 제외)",
    )
    parser.add_argument(
        "--max-df",
        type=float,
        default=0.5,
        help="이 비율 이상의 문서에 등장하는 단어는 제외 (기본 0.5). 공시 유형명처럼 "
        "반복되는 상투어를 걸러내는 용도. 문서가 5건 미만이면 자동으로 무시됨",
    )
    parser.add_argument(
        "--exclude-pattern",
        type=str,
        default=None,
        help="제목이 매치되면 추출 대상에서 제외할 정규식. 'structured'를 넘기면 "
        "ELS/DLS 등 구조화 증권 발행 공시 제외 프리셋 사용",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        choices=["anthropic", "openai"],
        help="LLM 정제에 사용할 제공자. 생략하면 .env의 LLM_PROVIDER를 따름 (기본 anthropic)",
    )
    args = parser.parse_args()

    run_extract_keywords(
        days=args.days,
        top_n=args.top_n,
        use_llm=not args.no_llm,
        only_enriched=args.only_enriched,
        exclude_pattern=args.exclude_pattern,
        max_df=args.max_df,
        provider=args.provider,
        asset_class=args.asset_class,
    )


if __name__ == "__main__":
    main()
