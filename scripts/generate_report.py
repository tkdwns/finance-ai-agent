"""
보고서 생성 실행 스크립트.

키워드 추출(scripts.extract_keywords)까지 끝난 뒤 실행하면, 그 기간의 문서와
키워드를 모아 Markdown 보고서를 만들어 reports_output/ 에 파일로 저장하고,
reports 테이블에도 기록한다.

사용법 (프로젝트 루트에서):
    python -m scripts.generate_report --days 7                    # 최근 7일, 전체 자산군
    python -m scripts.generate_report --days 7 --asset-class stock  # 주식만
    python -m scripts.generate_report --days 1 --period-type daily  # 일간 보고서
"""

import argparse

from src.common.period import get_period_bounds
from src.reports.report_generator import generate_report
from src.storage.db import ensure_schema_up_to_date, get_session
from src.storage.models import AssetClass, Base, PeriodType, Report

# period-type 라벨("주간" 등)에 대응하는 표준 기간(일). --days를 생략하면 이 값을 쓴다.
_CANONICAL_DAYS: dict[str, int] = {"daily": 1, "weekly": 7, "monthly": 30, "yearly": 365}


def _resolve_days(explicit_days: int | None, period_type: str) -> int:
    """
    --days를 생략하면 --period-type에 맞는 표준 기간을 쓰고, 명시했는데 표준값과
    다르면 리포트 제목("주간"/"월간" 등)과 실제 기간이 어긋난다는 안내를 출력한다.

    (예: --days 90 --period-type weekly 로 실행하면 "주간 리포트"라는 제목인데 실제로는
    90일치 데이터가 담기는 혼란이 있었음 — 이를 방지하기 위한 안전장치)
    """
    canonical = _CANONICAL_DAYS.get(period_type)
    if explicit_days is None:
        return canonical if canonical is not None else 7

    if canonical is not None and explicit_days != canonical:
        print(
            f"[안내] --days {explicit_days}는 '{period_type}' 라벨의 표준 기간({canonical}일)과 다릅니다. "
            f"리포트 제목은 '{period_type}'로 표시되지만 실제로는 {explicit_days}일치 데이터가 포함됩니다."
        )
    return explicit_days


def run_generate_report(
    days: int,
    period_type: str = "weekly",
    asset_class: str | None = None,
    top_n_keywords: int = 10,
    max_documents: int = 30,
    exclude_pattern: str | None = None,
    only_enriched: bool = False,
) -> dict:
    """
    보고서 생성의 핵심 로직. CLI(argparse)와 스케줄러 양쪽에서 재사용할 수 있도록
    인자를 명시적으로 받는 함수로 분리했다.

    Returns:
        {"output_path": str, "content": str} 형태의 실행 결과 요약
    """
    ensure_schema_up_to_date(Base)

    start_date, end_date = get_period_bounds(days)

    print(f"[1/2] 보고서 생성 중: {start_date.date()} ~ {end_date.date()} ({period_type})")

    session = get_session()
    try:
        content = generate_report(
            session,
            period_type,
            start_date,
            end_date,
            asset_class=asset_class,
            top_n_keywords=top_n_keywords,
            max_documents=max_documents,
            chart_dir="reports_output/charts",
            exclude_pattern=exclude_pattern,
            only_enriched=only_enriched,
        )

        asset_suffix = f"_{asset_class}" if asset_class else "_all"
        filename = f"{start_date.date()}_{period_type}{asset_suffix}.md"
        output_path = f"reports_output/{filename}"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"      파일 저장 완료: {output_path}")

        print("[2/2] reports 테이블에 기록 중")
        session.add(
            Report(
                period_type=period_type,
                period_start=start_date,
                period_end=end_date,
                asset_class=asset_class,
                content_markdown=content,
            )
        )
        session.commit()
        print("      완료")

        return {"output_path": output_path, "content": content}
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="기간별 금융 리포트 생성")
    parser.add_argument(
        "--days", type=int, default=None,
        help="오늘로부터 며칠 전까지를 대상으로 할지 (생략 시 --period-type에 맞는 표준값: "
        "daily=1, weekly=7, monthly=30, yearly=365)",
    )
    parser.add_argument(
        "--period-type", type=str, default="weekly",
        choices=["daily", "weekly", "monthly", "yearly"], help="보고서 기간 라벨 (기본 weekly)",
    )
    parser.add_argument(
        "--asset-class", type=str, default=None,
        choices=["stock", "bond", "real_estate", "crypto"], help="특정 자산군만 (생략 시 전체)",
    )
    parser.add_argument("--top-n-keywords", type=int, default=10, help="표시할 키워드 개수 (기본 10)")
    parser.add_argument("--max-documents", type=int, default=30, help="표시할 문서 최대 건수 (기본 30)")
    parser.add_argument(
        "--exclude-pattern", type=str, default=None,
        help="제목이 매치되면 '주요 공시·뉴스' 목록에서 제외할 정규식. 'structured'를 넘기면 "
        "ELS/DLS 등 구조화 증권 발행 공시 제외 프리셋 사용 (extract_keywords.py와 동일)",
    )
    parser.add_argument(
        "--only-enriched", action="store_true",
        help="원문(요약)이 제목과 다른, 내용이 채워진 문서만 '주요 공시·뉴스' 목록에 포함",
    )
    args = parser.parse_args()

    days = _resolve_days(args.days, args.period_type)

    result = run_generate_report(
        days=days,
        period_type=args.period_type,
        asset_class=args.asset_class,
        top_n_keywords=args.top_n_keywords,
        max_documents=args.max_documents,
        exclude_pattern=args.exclude_pattern,
        only_enriched=args.only_enriched,
    )
    print("\n--- 보고서 미리보기 (앞부분) ---\n")
    print(result["content"][:1000])


if __name__ == "__main__":
    main()
