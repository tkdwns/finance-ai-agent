"""
수집된 RawItem을 DB 모델로 변환해 저장하는 어댑터.

수집기(Collector)는 소스에 종속되지 않는 RawItem을 반환하고,
이 모듈이 RawItem을 각 자산군/콘텐츠유형에 맞는 ORM 테이블로 변환해 저장한다.
"""

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from src.collectors.base import RawItem
from src.collectors.ecos_collector import RawIndicator
from src.collectors.real_estate_collector import RawTransaction
from src.storage.models import (
    BondIndicator,
    BondNews,
    LawAmendment,
    RealEstateTransaction,
    StockDisclosure,
    StockNews,
    law_amendment_asset_class,
)

# 법령명 -> 영향받는 자산군 매핑 (개인용 프로젝트 기준 단순화한 규칙).
LAW_ASSET_CLASS_MAP: dict[str, list[str]] = {
    "자본시장과 금융투자업에 관한 법률": ["stock", "bond"],
    "은행법": ["bond"],
    "금융소비자 보호에 관한 법률": ["stock", "bond", "real_estate", "crypto"],
}


def raw_item_to_stock_disclosure(item: RawItem) -> StockDisclosure:
    """DartCollector가 반환한 RawItem을 StockDisclosure ORM 객체로 변환한다."""
    meta = item.raw_meta
    return StockDisclosure(
        source=item.source,
        title=item.title,
        url=item.url,
        summary=item.summary,
        published_at=item.published_at,
        corp_name=meta.get("corp_name", ""),
        corp_code=meta.get("corp_code", ""),
        rcept_no=meta.get("rcept_no", ""),
        report_name=meta.get("report_name", item.title),
    )


def save_stock_disclosures(
    session: Session, items: list[RawItem], update_existing: bool = False
) -> tuple[int, int]:
    """
    RawItem 리스트를 stock_disclosures 테이블에 저장한다.
    rcept_no(공시 접수번호) 기준으로 이미 존재하는 건은 기본적으로 건너뛴다.

    update_existing=True로 호출하면, 이미 존재하는 건이라도 새 summary가 기존보다
    길면(더 풍부한 정보) summary를 갱신한다. --fetch-text로 원문을 나중에 추가
    조회했을 때, 이전에 제목만 저장해둔 기존 행을 갱신하는 용도로 사용한다.

    Returns:
        (새로 저장된 건수, 갱신된 건수) 튜플
    """
    saved = 0
    updated = 0
    for item in items:
        rcept_no = item.raw_meta.get("rcept_no")
        existing = session.execute(
            select(StockDisclosure).where(StockDisclosure.rcept_no == rcept_no)
        ).scalar_one_or_none()

        if existing is None:
            session.add(raw_item_to_stock_disclosure(item))
            saved += 1
            continue

        if update_existing and len(item.summary) > len(existing.summary):
            existing.summary = item.summary
            updated += 1

    session.commit()
    return saved, updated


def raw_indicator_to_bond_indicator(item: RawIndicator) -> BondIndicator:
    """EcosCollector가 반환한 RawIndicator를 BondIndicator ORM 객체로 변환한다."""
    return BondIndicator(
        indicator_code=item.indicator_code,
        indicator_name=item.indicator_name,
        asset_class=item.asset_class,
        date=item.date,
        value=item.value,
        unit=item.unit,
        source=item.source,
    )


def save_bond_indicators(session: Session, items: list[RawIndicator]) -> tuple[int, int]:
    """
    RawIndicator 리스트를 bond_indicators 테이블에 저장한다.
    (indicator_code, date) 기준으로 이미 존재하는 건은 값이 달라졌을 때만 갱신한다.
    (ECOS는 최근 시점 데이터가 잠정치로 나중에 확정치로 바뀔 수 있어, 값이 같으면
    갱신 없이 건너뛴다.)

    Returns:
        (새로 저장된 건수, 갱신된 건수) 튜플
    """
    saved = 0
    updated = 0
    for item in items:
        existing = session.execute(
            select(BondIndicator).where(
                BondIndicator.indicator_code == item.indicator_code,
                BondIndicator.date == item.date,
            )
        ).scalar_one_or_none()

        if existing is None:
            session.add(raw_indicator_to_bond_indicator(item))
            saved += 1
            continue

        # unit도 비교 대상에 포함 — 프리셋의 단위 정의가 나중에 수정되면(예: ECOS가 내려주는
        # "1980.01.04=100" 같은 기준시점 문자열 대신 "pt"를 쓰도록 바꾼 경우) 다음 수집 때
        # 기존 행도 자동으로 정정되도록 한다.
        if existing.value != item.value or existing.unit != item.unit:
            existing.value = item.value
            existing.unit = item.unit
            updated += 1

    session.commit()
    return saved, updated


def raw_item_to_stock_news(item: RawItem) -> StockNews:
    return StockNews(
        source=item.source,
        title=item.title,
        url=item.url,
        summary=item.summary,
        published_at=item.published_at,
        related_ticker=item.raw_meta.get("related_ticker"),
    )


def raw_item_to_bond_news(item: RawItem) -> BondNews:
    return BondNews(
        source=item.source,
        title=item.title,
        url=item.url,
        summary=item.summary,
        published_at=item.published_at,
    )


# asset_class(전처리 단계의 tagger.py가 채운 값) -> (ORM 모델, 변환 함수) 매핑.
# real_estate/crypto는 아직 news 테이블 저장 로직이 연결되지 않아(2순위 확장 대상)
# 여기 등록되지 않은 asset_class는 skipped_unmapped로 집계된다.
_NEWS_SAVERS: dict[str, tuple] = {
    "stock": (StockNews, raw_item_to_stock_news),
    "bond": (BondNews, raw_item_to_bond_news),
}


def raw_transaction_to_real_estate_transaction(item: RawTransaction) -> RealEstateTransaction:
    return RealEstateTransaction(
        region=item.region,
        complex_name=item.complex_name,
        transaction_price=item.transaction_price,
        area_m2=item.area_m2,
        floor=item.floor,
        transaction_date=item.transaction_date,
        source=item.source,
    )


def save_real_estate_transactions(session: Session, items: list[RawTransaction]) -> tuple[int, int]:
    """
    RawTransaction 리스트를 real_estate_transactions 테이블에 저장한다.

    MOLIT 응답에는 거래를 유일하게 식별할 수 있는 접수번호 같은 값이 없어서, DB에도
    별도 unique 제약을 걸지 않았다(models.py 참고). 대신 이 함수에서 (지역, 단지명,
    면적, 층, 거래일, 거래가) 조합이 완전히 같은 행이 이미 있으면 중복으로 보고
    건너뛴다. 아주 드물게 같은 날 같은 단지·같은 층에서 우연히 같은 가격으로 서로
    다른 거래가 발생하면 하나로 합쳐질 수 있으나, 개인용 정보 수집 목적에는
    허용 가능한 수준의 근사치로 판단했다.

    Returns:
        (새로 저장된 건수, 중복으로 건너뛴 건수) 튜플
    """
    saved = 0
    skipped = 0
    for item in items:
        existing = session.execute(
            select(RealEstateTransaction).where(
                RealEstateTransaction.region == item.region,
                RealEstateTransaction.complex_name == item.complex_name,
                RealEstateTransaction.area_m2 == item.area_m2,
                RealEstateTransaction.floor == item.floor,
                RealEstateTransaction.transaction_date == item.transaction_date,
                RealEstateTransaction.transaction_price == item.transaction_price,
            )
        ).scalar_one_or_none()

        if existing is not None:
            skipped += 1
            continue

        session.add(raw_transaction_to_real_estate_transaction(item))
        saved += 1

    session.commit()
    return saved, skipped


def raw_item_to_law_amendment(item: RawItem) -> LawAmendment:
    # reason_text: 법령상세링크 페이지에서 발췌한 개정 이유 원문(최선 노력, 없을 수 있음).
    # 못 찾았으면 메타 정보 문자열(item.summary)로 대체 — 리포트에서 요약할 원문이
    # 항상 존재하도록 보장한다.
    return LawAmendment(
        source=item.source,
        title=item.title,
        url=item.url,
        summary=item.summary,
        published_at=item.published_at,
        law_name=item.raw_meta.get("law_name", ""),
        amendment_date=item.published_at,
        amendment_reason_summary=item.raw_meta.get("reason_text") or item.summary,
    )


def save_law_amendments(session: Session, items: list[RawItem]) -> tuple[int, int]:
    """
    RawItem 리스트를 law_amendments 테이블에 저장하고, LAW_ASSET_CLASS_MAP 기준으로
    law_amendment_asset_class 연결 테이블도 채운다. url 기준 중복은 건너뛴다.

    Returns:
        (새로 저장된 건수, 중복으로 건너뛴 건수) 튜플
    """
    saved = 0
    skipped = 0
    for item in items:
        existing = session.execute(
            select(LawAmendment).where(LawAmendment.url == item.url)
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        amendment = raw_item_to_law_amendment(item)
        session.add(amendment)
        session.flush()  # amendment.id 확보

        law_name = item.raw_meta.get("law_name", "")
        for asset_class in LAW_ASSET_CLASS_MAP.get(law_name, []):
            session.execute(
                insert(law_amendment_asset_class).values(
                    law_amendment_id=amendment.id, asset_class=asset_class
                )
            )
        saved += 1

    session.commit()
    return saved, skipped


def save_news_items(session: Session, items: list[RawItem]) -> dict:
    """
    NewsCollector가 반환한(전처리에서 태깅된) RawItem 리스트를 asset_class에 따라
    stock_news/bond_news 테이블로 나눠 저장한다.

    url(unique 제약) 기준으로 이미 저장된 기사는 건너뛴다. stock/bond로 태깅되지
    않은 항목(real_estate/crypto/unknown)은 아직 연결된 테이블이 없어 건너뛰고
    skipped_unmapped로 집계만 한다.

    Returns:
        {"stock": int, "bond": int, "skipped_duplicate": int, "skipped_unmapped": int}
    """
    result = {"stock": 0, "bond": 0, "skipped_duplicate": 0, "skipped_unmapped": 0}

    for item in items:
        mapping = _NEWS_SAVERS.get(item.asset_class)
        if mapping is None:
            result["skipped_unmapped"] += 1
            continue

        model, converter = mapping
        existing = session.execute(select(model).where(model.url == item.url)).scalar_one_or_none()
        if existing is not None:
            result["skipped_duplicate"] += 1
            continue

        session.add(converter(item))
        result[item.asset_class] += 1

    session.commit()
    return result
