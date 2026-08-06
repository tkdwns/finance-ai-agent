"""리포트를 생성해 이메일로 발송하는 스크립트.

generate_report.py와 동일한 옵션으로 리포트를 만든 뒤(파일 저장 + DB 기록까지 그대로
수행됨), HTML 이메일로 변환해 발송한다.

사용법 (프로젝트 루트에서):
    python -m scripts.send_report_email --days 7                     # 최근 7일, .env의 REPORT_EMAIL_TO로 발송
    python -m scripts.send_report_email --days 30 --period-type monthly --to a@example.com,b@example.com

사전 준비: .env 파일에 SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD와
수신자(REPORT_EMAIL_TO 또는 --to)가 설정되어 있어야 한다 (.env.example 참고).
"""

import argparse

from config.settings import settings
from scripts.generate_report import _resolve_days, run_generate_report
from src.reports.emailer import send_report_email

_PERIOD_LABELS = {"daily": "일간", "weekly": "주간", "monthly": "월간", "yearly": "연간"}


def run_send_report_email(
    days: int,
    period_type: str = "weekly",
    asset_class: str | None = None,
    top_n_keywords: int = 10,
    max_documents: int = 30,
    exclude_pattern: str | None = None,
    only_enriched: bool = False,
    to_addrs: list[str] | None = None,
) -> dict:
    """리포트 생성의 핵심 로직. CLI와 스케줄러 양쪽에서 재사용할 수 있도록 분리했다."""
    resolved_to = to_addrs or settings.report_email_to
    if not resolved_to:
        raise RuntimeError("수신자가 없습니다. --to 또는 .env의 REPORT_EMAIL_TO를 설정하세요.")

    result = run_generate_report(
        days=days,
        period_type=period_type,
        asset_class=asset_class,
        top_n_keywords=top_n_keywords,
        max_documents=max_documents,
        exclude_pattern=exclude_pattern,
        only_enriched=only_enriched,
    )

    label = _PERIOD_LABELS.get(period_type, period_type)
    asset_label = f" ({asset_class})" if asset_class else ""
    subject = f"[금융 AI 에이전트] {label} 리포트{asset_label}"

    print(f"[3/3] 이메일 발송 중: {', '.join(resolved_to)}")
    send_report_email(
        subject=subject,
        markdown_content=result["content"],
        to_addrs=resolved_to,
        chart_dir="reports_output/charts",
    )
    print("      발송 완료")

    return {**result, "sent_to": resolved_to}


def main():
    parser = argparse.ArgumentParser(description="기간별 금융 리포트 생성 및 이메일 발송")
    parser.add_argument(
        "--days", type=int, default=None,
        help="오늘로부터 며칠 전까지를 대상으로 할지 (생략 시 --period-type에 맞는 표준값)",
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
        help="제목이 매치되면 문서 목록에서 제외할 정규식. 'structured'는 프리셋 사용",
    )
    parser.add_argument("--only-enriched", action="store_true", help="원문이 채워진 문서만 포함")
    parser.add_argument(
        "--to", type=str, default=None,
        help="콤마로 구분한 수신자 목록. 생략하면 .env의 REPORT_EMAIL_TO 사용",
    )
    args = parser.parse_args()

    days = _resolve_days(args.days, args.period_type)
    to_addrs = [a.strip() for a in args.to.split(",") if a.strip()] if args.to else None

    try:
        run_send_report_email(
            days=days,
            period_type=args.period_type,
            asset_class=args.asset_class,
            top_n_keywords=args.top_n_keywords,
            max_documents=args.max_documents,
            exclude_pattern=args.exclude_pattern,
            only_enriched=args.only_enriched,
            to_addrs=to_addrs,
        )
    except RuntimeError as e:
        print(f"발송 실패: {e}")


if __name__ == "__main__":
    main()
