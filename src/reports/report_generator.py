"""
보고서 생성 모듈.

일별/주별/월별/연별 보고서를 Markdown으로 생성한다.
저장된 문서(storage.queries.get_documents_by_period)와 키워드(get_keywords_by_period)를
Jinja2 템플릿에 바인딩해 사람이 읽을 수 있는 보고서를 만든다.
"""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from src.analysis.summarizer import summarize_documents, summarize_group
from src.common.document_filter import apply_document_filters
from src.reports.charts import generate_bond_charts, generate_real_estate_chart
from src.storage.models import PeriodType
from src.storage.queries import (
    IndicatorPoint,
    TransactionPoint,
    get_bond_indicators_by_period,
    get_documents_by_period,
    get_keywords_by_period,
    get_law_amendments_by_period,
    get_real_estate_transactions_by_period,
)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(disabled_extensions=(".j2",)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_PERIOD_LABELS: dict[str, str] = {
    PeriodType.DAILY: "일간",
    PeriodType.WEEKLY: "주간",
    PeriodType.MONTHLY: "월간",
    PeriodType.YEARLY: "연간",
}

_CONTENT_TYPE_LABELS: dict[str, str] = {
    "news": "뉴스",
    "disclosure": "공시",
    "policy": "정책",
    "notice": "공지",
}

_ASSET_CLASS_LABELS: dict[str, str] = {
    "stock": "주식",
    "bond": "채권",
    "real_estate": "부동산",
    "crypto": "암호화폐",
}


def _summarize_indicators(points: list[IndicatorPoint]) -> list[dict]:
    """지표 코드별로 묶어, 기간 내 첫 값 대비 최근 값의 변화를 요약한다.

    bond_indicators는 날짜별로 여러 행이 쌓이는 시계열이라, 보고서에는 원본 행을
    그대로 늘어놓기보다 "최근 값 + 기간 중 변화"로 요약해서 보여주는 게 더 읽기 쉽다.
    """
    grouped: dict[str, list[IndicatorPoint]] = {}
    for point in points:
        grouped.setdefault(point.indicator_code, []).append(point)

    summaries = []
    for series in grouped.values():
        series_sorted = sorted(series, key=lambda p: p.date)
        first, last = series_sorted[0], series_sorted[-1]
        summaries.append(
            {
                "name": last.indicator_name,
                "latest_value": last.value,
                "latest_date": last.date,
                "unit": last.unit,
                "change": last.value - first.value,
                "is_single_point": len(series_sorted) == 1,
            }
        )
    return summaries


def _summarize_transactions(points: list[TransactionPoint]) -> list[dict]:
    """지역별로 묶어 거래건수/평균가/가격범위를 요약한다.

    개별 거래를 전부 나열하기보다, 지역 단위로 "이번 기간 몇 건 거래됐고 평균/범위가
    어떻게 되는지"를 보여주는 편이 보고서에서 더 유용하다.
    """
    grouped: dict[str, list[TransactionPoint]] = {}
    for point in points:
        grouped.setdefault(point.region, []).append(point)

    summaries = []
    for region, txns in grouped.items():
        prices = [t.transaction_price for t in txns]
        summaries.append(
            {
                "region": region,
                "count": len(txns),
                "avg_price": sum(prices) / len(prices),
                "min_price": min(prices),
                "max_price": max(prices),
            }
        )
    summaries.sort(key=lambda s: s["count"], reverse=True)
    return summaries


def generate_report(
    session: Session,
    period_type: str,
    start_date: datetime,
    end_date: datetime,
    asset_class: str | None = None,
    top_n_keywords: int = 10,
    max_documents: int = 30,
    chart_dir: str | None = None,
    exclude_pattern: str | None = None,
    only_enriched: bool = False,
) -> str:
    """
    지정된 기간의 문서 + 키워드를 조회해 Markdown 보고서 문자열을 생성한다.

    asset_class를 지정하지 않으면 전체 자산군을 대상으로 한다.
    chart_dir을 지정하면 그 폴더 안에 채권/부동산 추이 PNG를 저장하고, 리포트가
    저장될 파일과 같은 폴더 기준 상대경로(`{chart_dir의 마지막 폴더명}/파일명`)로
    이미지를 삽입한다 (예: chart_dir="reports_output/charts" -> "charts/파일명.png").
    생략하면 차트를 생성하지 않는다.
    exclude_pattern/only_enriched는 extract_keywords.py와 동일한 필터로, "주요 공시·뉴스"
    목록에도 키워드 섹션과 같은 정제를 적용해달라는 피드백에 따라 추가됐다(생략하면 필터 없음).
    """
    documents = get_documents_by_period(
        session, start_date, end_date, asset_classes=[asset_class] if asset_class else None
    )
    documents = apply_document_filters(documents, exclude_pattern=exclude_pattern, only_enriched=only_enriched)
    total_documents = len(documents)
    displayed_documents = documents[:max_documents]

    # 항목마다 개별 요약을 나열하면(30건이면 30개 문단) 너무 길어진다는 피드백을 반영해,
    # content_type(공시/뉴스/정책/공지)별로 묶어 각 그룹당 하나의 종합 요약만 보여준다.
    # 다만 요약만 있으면 원문 제목을 확인할 수 없다는 피드백도 있어, 그룹 요약과 별도로
    # 개별 문서 제목 리스트(titles)도 함께 전달한다.
    grouped_documents: dict[str, list] = {}
    for d in displayed_documents:
        grouped_documents.setdefault(d.content_type, []).append(d)

    document_groups = [
        {
            "label": _CONTENT_TYPE_LABELS.get(content_type, content_type),
            "count": len(docs),
            "summary": summarize_group([d.summary for d in docs], max_lines=6)
            or "요약을 생성하지 못했습니다.",
            "titles": [
                {"title": d.title, "entity_name": d.entity_name, "url": d.url, "published_at": d.published_at}
                for d in docs
            ],
        }
        for content_type, docs in grouped_documents.items()
    ]

    keywords = get_keywords_by_period(
        session, period_type, start_date, asset_class=asset_class, top_n=top_n_keywords
    )

    # bond_indicators 테이블은 ECOS(채권)와 FRED(주식 지수)가 함께 저장되는
    # asset_class 비특정 테이블이라, 채권/주식/전체(None) 리포트에서 모두 조회한다.
    # real_estate_transactions는 해당 자산군이거나 전체(None)일 때만 조회한다.
    indicator_points = []
    if asset_class in (None, "bond", "stock"):
        indicator_asset_classes = [asset_class] if asset_class else None
        indicator_points = get_bond_indicators_by_period(
            session, start_date, end_date, asset_classes=indicator_asset_classes
        )
    indicators = _summarize_indicators(indicator_points)

    transaction_points = []
    if asset_class in (None, "real_estate"):
        transaction_points = get_real_estate_transactions_by_period(session, start_date, end_date)
    transactions = _summarize_transactions(transaction_points)

    # law_amendments는 법령 하나가 여러 자산군에 걸칠 수 있어(다대다), asset_class 필터를
    # get_law_amendments_by_period()에 그대로 전달해 해당 자산군에 태깅된 것만 받는다.
    law_amendments = get_law_amendments_by_period(session, start_date, end_date, asset_class=asset_class)

    # amendment_reason_summary는 law_collector.py가 법령 상세 페이지에서 발췌한 원문
    # (발췌 실패 시 메타 정보로 대체된 값)이다. 이걸 LLM으로 3~4줄 요약해 링크 대신 보여준다.
    law_summaries = summarize_documents(
        [(str(law.id), law.amendment_reason_summary) for law in law_amendments], max_lines=4
    )
    law_amendment_items = [
        {
            "title": law.title,
            "amendment_date": law.amendment_date,
            "summary": law_summaries.get(str(law.id), law.amendment_reason_summary),
        }
        for law in law_amendments
    ]

    bond_charts = []
    real_estate_chart_path = None
    if chart_dir:
        chart_prefix = Path(chart_dir).name
        date_tag = f"{start_date.date()}_{period_type}"
        if asset_class in (None, "bond", "stock"):
            # 금리(%)/지수(pt)/환율(원)처럼 단위가 서로 다른 지표를 한 그래프에 겹치면
            # 알아보기 어렵다는 피드백을 반영해 지표별로 개별 이미지를 생성한다
            # (템플릿에서 3열 격자로 배치).
            chart_results = generate_bond_charts(indicator_points, chart_dir, f"{date_tag}_indicators")
            bond_charts = [{"name": name, "path": f"{chart_prefix}/{fname}"} for name, fname in chart_results]
        if asset_class in (None, "real_estate"):
            name = generate_real_estate_chart(transaction_points, chart_dir, f"{date_tag}_real_estate.png")
            real_estate_chart_path = f"{chart_prefix}/{name}" if name else None

    template = _env.get_template("report_template.md.j2")
    return template.render(
        period_label=_PERIOD_LABELS.get(period_type, period_type),
        period_start=start_date.strftime("%Y-%m-%d"),
        period_end=end_date.strftime("%Y-%m-%d"),
        asset_class_label=_ASSET_CLASS_LABELS.get(asset_class, "전체 자산군"),
        keywords=keywords,
        indicators=indicators,
        bond_charts=bond_charts,
        transactions=transactions,
        real_estate_chart_path=real_estate_chart_path,
        law_amendments=law_amendment_items,
        document_groups=document_groups,
        total_documents=total_documents,
        displayed_documents=len(displayed_documents),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
