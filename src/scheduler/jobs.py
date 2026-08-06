"""
스케줄링 작업 정의.

collect_dart / extract_keywords / generate_report의 핵심 로직 함수(run_*)를
조합해서 "수집 -> 분석 -> 보고서" 전체 파이프라인을 하나의 함수 호출로 묶는다.
APScheduler(scripts/run_scheduler.py)나 Windows 작업 스케줄러 양쪽에서 재사용 가능하다.
"""

from config.settings import settings
from scripts.collect_bond import run_collect_bond
from scripts.collect_dart import run_collect_dart
from scripts.collect_fred import run_collect_fred
from scripts.collect_law import run_collect_law
from scripts.collect_news import run_collect_news
from scripts.collect_real_estate import run_collect_real_estate
from scripts.extract_keywords import run_extract_keywords
from scripts.generate_report import run_generate_report
from src.collectors.dart_collector import RECOMMENDED_SUBSTANTIAL_TYPES
from src.reports.emailer import send_report_email

# 절차성 신고(D 지분공시 등)를 걸러낸 추천 조합. collect_dart.py의 "substantial" 프리셋과 동일.
_DEFAULT_PBLNTF_TYPES = RECOMMENDED_SUBSTANTIAL_TYPES

_PERIOD_LABELS = {"daily": "일간", "weekly": "주간", "monthly": "월간", "yearly": "연간"}


def _maybe_email_report(period_type: str, report_result: dict) -> None:
    """SMTP와 수신자가 모두 설정된 경우에만 리포트를 이메일로 발송한다.

    둘 중 하나라도 비어있으면(기본 상태) 조용히 스킵한다 — 이메일 발송은 선택 기능이라
    미설정 사용자의 파이프라인이 이 단계 때문에 실패해서는 안 된다.
    """
    if not (settings.smtp_host and settings.report_email_to):
        return
    label = _PERIOD_LABELS.get(period_type, period_type)
    try:
        send_report_email(
            subject=f"[금융 AI 에이전트] {label} 리포트",
            markdown_content=report_result["content"],
            to_addrs=settings.report_email_to,
            chart_dir="reports_output/charts",
        )
        print(f"      리포트 이메일 발송 완료: {', '.join(settings.report_email_to)}")
    except Exception as e:
        print(f"      [경고] 리포트 이메일 발송 실패: {e}")


def run_daily_pipeline(max_text_fetches: int = 100, top_n_keywords: int = 10) -> dict:
    """
    일별 파이프라인: 최근 1일 공시 수집(원문 포함) -> 키워드 추출 -> 일간 보고서 생성.
    """
    print("=" * 60)
    print("[일별 파이프라인 시작]")
    print("=" * 60)

    collect_result = run_collect_dart(
        days=1,
        pblntf_types=_DEFAULT_PBLNTF_TYPES,
        fetch_text=True,
        max_text_fetches=max_text_fetches,
    )

    bond_result = run_collect_bond(days=1)
    fred_result = run_collect_fred(days=1)
    news_result = run_collect_news(days=1)
    real_estate_result = run_collect_real_estate(days=1)
    law_result = run_collect_law(days=1)

    keyword_result = run_extract_keywords(
        days=1,
        top_n=top_n_keywords,
        use_llm=True,
        only_enriched=True,
        exclude_pattern="structured",
    )

    report_result = run_generate_report(days=1, period_type="daily", top_n_keywords=top_n_keywords)
    _maybe_email_report("daily", report_result)

    print("[일별 파이프라인 완료]")
    return {
        "collect": collect_result,
        "bond": bond_result,
        "fred": fred_result,
        "news": news_result,
        "real_estate": real_estate_result,
        "law": law_result,
        "keywords": keyword_result,
        "report": report_result,
    }


def run_weekly_pipeline(max_text_fetches: int = 300, top_n_keywords: int = 10) -> dict:
    """
    주별 파이프라인: 최근 7일 공시 수집(원문 포함) -> 키워드 추출 -> 주간 보고서 생성.
    """
    print("=" * 60)
    print("[주별 파이프라인 시작]")
    print("=" * 60)

    collect_result = run_collect_dart(
        days=7,
        pblntf_types=_DEFAULT_PBLNTF_TYPES,
        fetch_text=True,
        max_text_fetches=max_text_fetches,
    )

    bond_result = run_collect_bond(days=7)
    fred_result = run_collect_fred(days=7)
    news_result = run_collect_news(days=7)
    real_estate_result = run_collect_real_estate(days=7)
    law_result = run_collect_law(days=7)

    keyword_result = run_extract_keywords(
        days=7,
        top_n=top_n_keywords,
        use_llm=True,
        only_enriched=True,
        exclude_pattern="structured",
    )

    report_result = run_generate_report(days=7, period_type="weekly", top_n_keywords=top_n_keywords)
    _maybe_email_report("weekly", report_result)

    print("[주별 파이프라인 완료]")
    return {
        "collect": collect_result,
        "bond": bond_result,
        "fred": fred_result,
        "news": news_result,
        "real_estate": real_estate_result,
        "law": law_result,
        "keywords": keyword_result,
        "report": report_result,
    }


def run_monthly_pipeline(max_text_fetches: int = 500, top_n_keywords: int = 15) -> dict:
    """월별 파이프라인: 최근 30일 공시 수집 -> 키워드 추출 -> 월간 보고서 생성."""
    print("=" * 60)
    print("[월별 파이프라인 시작]")
    print("=" * 60)

    collect_result = run_collect_dart(
        days=30,
        pblntf_types=_DEFAULT_PBLNTF_TYPES,
        fetch_text=True,
        max_text_fetches=max_text_fetches,
    )

    bond_result = run_collect_bond(days=30)
    fred_result = run_collect_fred(days=30)
    news_result = run_collect_news(days=30)
    real_estate_result = run_collect_real_estate(days=30)
    law_result = run_collect_law(days=30)

    keyword_result = run_extract_keywords(
        days=30,
        top_n=top_n_keywords,
        use_llm=True,
        only_enriched=True,
        exclude_pattern="structured",
    )

    report_result = run_generate_report(days=30, period_type="monthly", top_n_keywords=top_n_keywords)
    _maybe_email_report("monthly", report_result)

    print("[월별 파이프라인 완료]")
    return {
        "collect": collect_result,
        "bond": bond_result,
        "fred": fred_result,
        "news": news_result,
        "real_estate": real_estate_result,
        "law": law_result,
        "keywords": keyword_result,
        "report": report_result,
    }


def run_yearly_pipeline(max_text_fetches: int = 1000, top_n_keywords: int = 20) -> dict:
    """연별 파이프라인: 최근 365일 공시 수집 -> 키워드 추출 -> 연간 보고서 생성."""
    print("=" * 60)
    print("[연별 파이프라인 시작]")
    print("=" * 60)

    collect_result = run_collect_dart(
        days=365,
        pblntf_types=_DEFAULT_PBLNTF_TYPES,
        fetch_text=True,
        max_text_fetches=max_text_fetches,
    )

    bond_result = run_collect_bond(days=365)
    fred_result = run_collect_fred(days=365)
    news_result = run_collect_news(days=365)
    real_estate_result = run_collect_real_estate(days=365)
    law_result = run_collect_law(days=365)

    keyword_result = run_extract_keywords(
        days=365,
        top_n=top_n_keywords,
        use_llm=True,
        only_enriched=True,
        exclude_pattern="structured",
    )

    report_result = run_generate_report(days=365, period_type="yearly", top_n_keywords=top_n_keywords)
    _maybe_email_report("yearly", report_result)

    print("[연별 파이프라인 완료]")
    return {
        "collect": collect_result,
        "bond": bond_result,
        "fred": fred_result,
        "news": news_result,
        "real_estate": real_estate_result,
        "law": law_result,
        "keywords": keyword_result,
        "report": report_result,
    }
