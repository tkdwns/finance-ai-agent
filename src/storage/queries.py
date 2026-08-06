"""
자산군을 가로지르는(cross-asset-class) 조회 헬퍼 함수.

docs/DB_SCHEMA.md에서 설명한 대로, 주식/채권/부동산/암호화폐 테이블은
서로 독립되어 있다. 하지만 보고서 생성 단계에서는 "이번 주 전체 자산군 뉴스"처럼
여러 테이블을 가로지르는 조회가 필요하다. 이 모듈이 그 역할을 담당하며,
서로 다른 테이블의 row를 UnifiedDocument라는 공통 형태로 변환해 반환한다.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.storage.models import (
    AssetClass,
    BondIndicator,
    BondNews,
    CryptoNews,
    CryptoNotice,
    Keyword,
    LawAmendment,
    RealEstateNews,
    RealEstatePolicy,
    RealEstateTransaction,
    StockDisclosure,
    StockNews,
    law_amendment_asset_class,
)


@dataclass
class UnifiedDocument:
    """자산군마다 다른 테이블의 row를 하나의 공통 형태로 표현한다."""

    asset_class: str
    content_type: str  # "news" | "disclosure" | "policy" | "notice"
    source: str
    title: str
    url: str
    summary: str
    published_at: datetime
    entity_name: str = ""  # 관련 기업/거래소명 (StockDisclosure.corp_name 등, 없으면 빈 문자열)


# 자산군별 "문서형" 테이블과 콘텐츠 유형 라벨 매핑.
# 수치형 테이블(bond_indicators, real_estate_transactions)은 문서가 아니므로 제외한다.
_ASSET_CLASS_DOCUMENT_TABLES: dict[str, list[tuple[type, str]]] = {
    AssetClass.STOCK: [(StockNews, "news"), (StockDisclosure, "disclosure")],
    AssetClass.BOND: [(BondNews, "news")],
    AssetClass.REAL_ESTATE: [(RealEstateNews, "news"), (RealEstatePolicy, "policy")],
    AssetClass.CRYPTO: [(CryptoNews, "news"), (CryptoNotice, "notice")],
}


def get_documents_by_period(
    session: Session,
    start: datetime,
    end: datetime,
    asset_classes: list[str] | None = None,
) -> list[UnifiedDocument]:
    """
    지정된 기간의 문서형 데이터(뉴스/공시/정책/공지)를 자산군을 가로질러 조회한다.

    asset_classes를 지정하지 않으면 전체 자산군(주식/채권/부동산/암호화폐)을 대상으로 하며,
    결과는 published_at 내림차순으로 정렬되어 반환된다. 보고서 생성 단계(일/주/월/연간)에서
    "이 기간의 전체 자산군 문서"가 필요할 때 이 함수 하나로 해결한다.
    """
    target_classes = asset_classes or list(_ASSET_CLASS_DOCUMENT_TABLES.keys())

    results: list[UnifiedDocument] = []
    for asset_class in target_classes:
        tables = _ASSET_CLASS_DOCUMENT_TABLES.get(asset_class, [])
        for model, content_type in tables:
            stmt = select(model).where(
                model.published_at >= start, model.published_at <= end
            )
            rows = session.execute(stmt).scalars().all()
            for row in rows:
                # 테이블마다 "관련 주체" 필드명이 다르므로(corp_name, exchange_name 등)
                # 있는 것부터 우선순위대로 찾아 채운다. 없으면 빈 문자열.
                entity_name = getattr(row, "corp_name", "") or getattr(row, "exchange_name", "") or ""
                results.append(
                    UnifiedDocument(
                        asset_class=asset_class,
                        content_type=content_type,
                        source=row.source,
                        title=row.title,
                        url=row.url,
                        summary=row.summary,
                        published_at=row.published_at,
                        entity_name=entity_name,
                    )
                )

    results.sort(key=lambda d: d.published_at, reverse=True)
    return results


def get_law_amendments_by_period(
    session: Session,
    start: datetime,
    end: datetime,
    asset_class: str | None = None,
) -> list[LawAmendment]:
    """
    기간 내 법령 개정 이력을 조회한다.

    asset_class를 지정하면 law_amendment_asset_class 다대다 연결 테이블을 통해
    해당 자산군에 태깅된 개정 건만 반환한다 (예: 자본시장법 개정 중 "stock"에 영향 주는 것만).
    """
    stmt = select(LawAmendment).where(
        LawAmendment.published_at >= start, LawAmendment.published_at <= end
    )
    if asset_class:
        stmt = stmt.join(
            law_amendment_asset_class,
            law_amendment_asset_class.c.law_amendment_id == LawAmendment.id,
        ).where(law_amendment_asset_class.c.asset_class == asset_class)

    return list(session.execute(stmt).scalars().all())


@dataclass
class IndicatorPoint:
    """수치형 지표(bond_indicators 등) 한 행을 표현하는 공통 형태."""

    indicator_code: str
    indicator_name: str
    date: datetime
    value: float
    unit: str
    source: str
    asset_class: str = "bond"


@dataclass
class TransactionPoint:
    """부동산 실거래(real_estate_transactions) 한 행을 표현하는 공통 형태."""

    region: str
    complex_name: str
    transaction_price: float
    area_m2: float | None
    floor: int | None
    transaction_date: datetime
    source: str


def get_real_estate_transactions_by_period(
    session: Session,
    start: datetime,
    end: datetime,
    regions: list[str] | None = None,
) -> list[TransactionPoint]:
    """
    기간 내 아파트 매매 실거래 내역을 조회한다.

    real_estate_transactions는 문서형(뉴스/정책)이 아니라 거래 건별 정형 데이터라
    get_documents_by_period()와는 별도 함수로 분리했다 (models.py 설계 주석 참고).
    """
    stmt = select(RealEstateTransaction).where(
        RealEstateTransaction.transaction_date >= start, RealEstateTransaction.transaction_date <= end
    )
    if regions:
        stmt = stmt.where(RealEstateTransaction.region.in_(regions))
    stmt = stmt.order_by(RealEstateTransaction.transaction_date.asc())

    rows = session.execute(stmt).scalars().all()
    return [
        TransactionPoint(
            region=row.region,
            complex_name=row.complex_name,
            transaction_price=row.transaction_price,
            area_m2=row.area_m2,
            floor=row.floor,
            transaction_date=row.transaction_date,
            source=row.source,
        )
        for row in rows
    ]


def get_bond_indicators_by_period(
    session: Session,
    start: datetime,
    end: datetime,
    indicator_codes: list[str] | None = None,
    asset_classes: list[str] | None = None,
) -> list[IndicatorPoint]:
    """
    기간 내 수치형 지표(채권 금리, 주가지수 등) 시계열을 조회한다.

    bond_indicators는 문서형(뉴스/공시)이 아니라 날짜별 숫자값 테이블이라
    get_documents_by_period()와는 별도 함수로 분리했다 (models.py 설계 주석 참고).
    ECOS(채권)와 FRED(주식지수)가 같은 테이블에 저장되므로, asset_classes를 지정하면
    해당 자산군만 걸러서 반환한다 (레거시 행은 asset_class가 NULL이라 "bond"로 취급).
    결과는 date 오름차순으로 정렬되어, 기간 내 추이를 그대로 순회할 수 있다.

    기준금리처럼 월별로만 갱신되는 지표는 (정확히 이번 달에 값 변경이 없어서) 리포트
    기간 안에 데이터가 하나도 없을 수 있다 — 이 경우 지표 자체가 리포트에서 통째로
    빠지는 문제가 실사용 중 발견됨. 기간 내 값이 전혀 없는 지표는 기간 이전의 가장
    최근 값을 하나 보충해 "최신 기준"으로라도 표시되게 한다(추이 그래프는 여전히 2건
    미만이면 생략됨).
    """
    filters = []
    if indicator_codes:
        filters.append(BondIndicator.indicator_code.in_(indicator_codes))
    if asset_classes:
        conditions = [BondIndicator.asset_class == ac for ac in asset_classes]
        if "bond" in asset_classes:
            conditions.append(BondIndicator.asset_class.is_(None))
        filters.append(or_(*conditions))

    stmt = (
        select(BondIndicator)
        .where(BondIndicator.date >= start, BondIndicator.date <= end, *filters)
        .order_by(BondIndicator.date.asc())
    )
    rows = list(session.execute(stmt).scalars().all())

    present_codes = {row.indicator_code for row in rows}
    all_codes_stmt = select(BondIndicator.indicator_code).distinct().where(*filters)
    all_codes = {code for (code,) in session.execute(all_codes_stmt).all()}

    for code in all_codes - present_codes:
        latest_stmt = (
            select(BondIndicator)
            .where(BondIndicator.indicator_code == code, BondIndicator.date <= end, *filters)
            .order_by(BondIndicator.date.desc())
            .limit(1)
        )
        latest = session.execute(latest_stmt).scalar_one_or_none()
        if latest is not None:
            rows.append(latest)

    rows.sort(key=lambda r: r.date)
    return [
        IndicatorPoint(
            indicator_code=row.indicator_code,
            indicator_name=row.indicator_name,
            date=row.date,
            value=row.value,
            unit=row.unit,
            source=row.source,
            asset_class=row.asset_class or "bond",
        )
        for row in rows
    ]


def get_keywords_by_period(
    session: Session,
    period_type: str,
    period_start: datetime,
    asset_class: str | None = None,
    top_n: int = 10,
) -> list[Keyword]:
    """지정된 기간/자산군의 상위 키워드를 score 내림차순으로 조회한다.
    asset_class를 지정하지 않으면 모든 자산군의 키워드를 함께 반환한다."""
    stmt = select(Keyword).where(
        Keyword.period_type == period_type, Keyword.period_start == period_start
    )
    if asset_class:
        stmt = stmt.where(Keyword.asset_class == asset_class)
    stmt = stmt.order_by(Keyword.score.desc()).limit(top_n)

    return list(session.execute(stmt).scalars().all())
