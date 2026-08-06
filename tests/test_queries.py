"""자산군 통합 조회 헬퍼 함수(src/storage/queries.py) 테스트."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from src.storage.models import (
    AssetClass,
    Base,
    BondIndicator,
    BondNews,
    CryptoNotice,
    Keyword,
    LawAmendment,
    PeriodType,
    RealEstatePolicy,
    RealEstateTransaction,
    StockNews,
    law_amendment_asset_class,
)
from src.storage.queries import (
    get_bond_indicators_by_period,
    get_documents_by_period,
    get_keywords_by_period,
    get_law_amendments_by_period,
    get_real_estate_transactions_by_period,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_get_documents_by_period_merges_across_asset_classes(session):
    now = datetime(2026, 7, 20, 9, 0)
    session.add_all(
        [
            StockNews(
                source="한국경제", title="코스피 상승", url="http://a.com/1",
                summary="요약1", published_at=now,
            ),
            BondNews(
                source="연합인포맥스", title="국고채 금리 하락", url="http://b.com/1",
                summary="요약2", published_at=now - timedelta(hours=1),
            ),
            RealEstatePolicy(
                source="국토부", title="대출규제 강화 발표", url="http://c.com/1",
                summary="요약3", published_at=now - timedelta(hours=2), policy_type="대출규제",
            ),
            CryptoNotice(
                source="업비트", title="A코인 유의종목 지정", url="http://d.com/1",
                summary="요약4", published_at=now - timedelta(hours=3),
                exchange_name="업비트", notice_type="유의종목",
            ),
        ]
    )
    session.commit()

    start = now - timedelta(days=1)
    end = now + timedelta(hours=1)
    docs = get_documents_by_period(session, start, end)

    assert len(docs) == 4
    # published_at 내림차순 정렬 확인
    assert docs[0].title == "코스피 상승"
    assert docs[-1].title == "A코인 유의종목 지정"
    # 자산군이 섞여서 반환되는지 확인
    returned_asset_classes = {d.asset_class for d in docs}
    assert returned_asset_classes == {"stock", "bond", "real_estate", "crypto"}


def test_get_documents_by_period_filters_by_asset_class(session):
    now = datetime(2026, 7, 20, 9, 0)
    session.add_all(
        [
            StockNews(source="A", title="주식 뉴스", url="http://a.com/2", summary="", published_at=now),
            BondNews(source="B", title="채권 뉴스", url="http://b.com/2", summary="", published_at=now),
        ]
    )
    session.commit()

    docs = get_documents_by_period(
        session, now - timedelta(hours=1), now + timedelta(hours=1), asset_classes=["stock"]
    )
    assert len(docs) == 1
    assert docs[0].asset_class == "stock"


def test_get_law_amendments_by_period_filters_by_asset_class(session):
    now = datetime(2026, 7, 20, 9, 0)
    amendment = LawAmendment(
        source="금융위", title="자본시장법 개정", url="http://law.com/1",
        summary="개정 요약", published_at=now, law_name="자본시장법",
    )
    session.add(amendment)
    session.commit()

    # stock, bond 두 자산군에 태깅
    session.execute(
        insert(law_amendment_asset_class),
        [
            {"law_amendment_id": amendment.id, "asset_class": AssetClass.STOCK},
            {"law_amendment_id": amendment.id, "asset_class": AssetClass.BOND},
        ],
    )
    session.commit()

    start, end = now - timedelta(days=1), now + timedelta(days=1)

    stock_results = get_law_amendments_by_period(session, start, end, asset_class="stock")
    crypto_results = get_law_amendments_by_period(session, start, end, asset_class="crypto")
    all_results = get_law_amendments_by_period(session, start, end)

    assert len(stock_results) == 1
    assert len(crypto_results) == 0
    assert len(all_results) == 1


def test_get_keywords_by_period_orders_by_score_and_limits(session):
    period_start = datetime(2026, 7, 20)
    period_end = datetime(2026, 7, 21)
    session.add_all(
        [
            Keyword(
                asset_class=AssetClass.STOCK, period_type=PeriodType.DAILY,
                period_start=period_start, period_end=period_end,
                keyword="금리인하", score=0.9,
            ),
            Keyword(
                asset_class=AssetClass.STOCK, period_type=PeriodType.DAILY,
                period_start=period_start, period_end=period_end,
                keyword="실적발표", score=0.5,
            ),
            Keyword(
                asset_class=AssetClass.CRYPTO, period_type=PeriodType.DAILY,
                period_start=period_start, period_end=period_end,
                keyword="비트코인ETF", score=0.99,
            ),
        ]
    )
    session.commit()

    stock_keywords = get_keywords_by_period(
        session, PeriodType.DAILY, period_start, asset_class="stock", top_n=10
    )
    assert [k.keyword for k in stock_keywords] == ["금리인하", "실적발표"]

    all_keywords = get_keywords_by_period(session, PeriodType.DAILY, period_start, top_n=1)
    assert len(all_keywords) == 1
    assert all_keywords[0].keyword == "비트코인ETF"  # score 가장 높은 항목


def test_get_bond_indicators_by_period_orders_by_date_and_filters_by_code(session):
    session.add_all(
        [
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 6, 1), value=3.00, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 1, 1), value=3.25, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="999Z999", indicator_name="다른 지표",
                date=datetime(2026, 3, 1), value=1.0, unit="%", source="ECOS",
            ),
        ]
    )
    session.commit()

    start, end = datetime(2026, 1, 1), datetime(2026, 12, 31)
    result = get_bond_indicators_by_period(session, start, end, indicator_codes=["722Y001"])

    assert len(result) == 2
    # date 오름차순 정렬 확인
    assert result[0].date == datetime(2026, 1, 1)
    assert result[1].date == datetime(2026, 6, 1)
    assert all(r.indicator_code == "722Y001" for r in result)


def test_get_bond_indicators_by_period_returns_all_codes_when_not_filtered(session):
    session.add_all(
        [
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 6, 1), value=3.00, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="999Z999", indicator_name="다른 지표",
                date=datetime(2026, 6, 1), value=1.0, unit="%", source="ECOS",
            ),
        ]
    )
    session.commit()

    result = get_bond_indicators_by_period(session, datetime(2026, 1, 1), datetime(2026, 12, 31))
    assert {r.indicator_code for r in result} == {"722Y001", "999Z999"}


def test_get_bond_indicators_by_period_filters_by_asset_class(session):
    # bond_indicators 테이블은 ECOS(채권)와 FRED(주식지수)가 함께 저장되므로,
    # asset_classes로 걸러야 리포트에서 서로 섞이지 않는다. 레거시 행(asset_class=NULL)은
    # "bond"로 취급되어야 한다.
    session.add_all(
        [
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리", asset_class="bond",
                date=datetime(2026, 1, 1), value=3.25, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="NASDAQCOM", indicator_name="나스닥종합지수", asset_class="stock",
                date=datetime(2026, 1, 1), value=15000.0, unit="pt", source="FRED",
            ),
            BondIndicator(
                indicator_code="LEGACY001", indicator_name="레거시 지표", asset_class=None,
                date=datetime(2026, 1, 1), value=1.0, unit="%", source="ECOS",
            ),
        ]
    )
    session.commit()

    start, end = datetime(2026, 1, 1), datetime(2026, 12, 31)

    stock_only = get_bond_indicators_by_period(session, start, end, asset_classes=["stock"])
    assert {r.indicator_code for r in stock_only} == {"NASDAQCOM"}

    bond_only = get_bond_indicators_by_period(session, start, end, asset_classes=["bond"])
    assert {r.indicator_code for r in bond_only} == {"722Y001", "LEGACY001"}  # NULL은 bond로 취급

    unfiltered = get_bond_indicators_by_period(session, start, end)
    assert len(unfiltered) == 3


def test_get_bond_indicators_by_period_backfills_latest_value_when_none_in_window(session):
    # 실사용 중 발견된 문제: 기준금리처럼 월별로만 갱신되는 지표는 정확히 이번 달에
    # 새 값이 없으면(금리가 그대로라 ECOS가 갱신 안 함) 리포트 기간 안에 데이터가
    # 하나도 없어 지표 자체가 리포트에서 통째로 빠졌다. 기간 이전의 최신 값을 하나
    # 보충해서라도 표시되어야 한다.
    session.add_all(
        [
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 5, 1), value=3.25, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="999Z999", indicator_name="다른 지표",
                date=datetime(2026, 7, 15), value=1.0, unit="%", source="ECOS",
            ),
        ]
    )
    session.commit()

    # 7월 한 달만 조회 -> 기준금리(5월 값)는 기간 밖이지만, 최신값으로 보충되어야 함
    result = get_bond_indicators_by_period(session, datetime(2026, 7, 1), datetime(2026, 7, 31))

    codes = {r.indicator_code for r in result}
    assert codes == {"722Y001", "999Z999"}
    base_rate = next(r for r in result if r.indicator_code == "722Y001")
    assert base_rate.value == 3.25
    assert base_rate.date == datetime(2026, 5, 1)


def test_get_real_estate_transactions_by_period_orders_by_date_and_filters_by_region(session):
    session.add_all(
        [
            RealEstateTransaction(
                region="역삼동", complex_name="A", transaction_price=100000.0,
                area_m2=84.0, floor=5, transaction_date=datetime(2026, 6, 20), source="MOLIT",
            ),
            RealEstateTransaction(
                region="역삼동", complex_name="B", transaction_price=90000.0,
                area_m2=59.0, floor=3, transaction_date=datetime(2026, 6, 1), source="MOLIT",
            ),
            RealEstateTransaction(
                region="종로동", complex_name="C", transaction_price=80000.0,
                area_m2=59.0, floor=2, transaction_date=datetime(2026, 6, 10), source="MOLIT",
            ),
        ]
    )
    session.commit()

    start, end = datetime(2026, 6, 1), datetime(2026, 6, 30)
    result = get_real_estate_transactions_by_period(session, start, end, regions=["역삼동"])

    assert len(result) == 2
    # transaction_date 오름차순 정렬 확인
    assert result[0].transaction_date == datetime(2026, 6, 1)
    assert result[1].transaction_date == datetime(2026, 6, 20)
    assert all(r.region == "역삼동" for r in result)


def test_get_real_estate_transactions_by_period_returns_all_regions_when_not_filtered(session):
    session.add_all(
        [
            RealEstateTransaction(
                region="역삼동", complex_name="A", transaction_price=100000.0,
                area_m2=84.0, floor=5, transaction_date=datetime(2026, 6, 1), source="MOLIT",
            ),
            RealEstateTransaction(
                region="종로동", complex_name="C", transaction_price=80000.0,
                area_m2=59.0, floor=2, transaction_date=datetime(2026, 6, 1), source="MOLIT",
            ),
        ]
    )
    session.commit()

    result = get_real_estate_transactions_by_period(session, datetime(2026, 1, 1), datetime(2026, 12, 31))
    assert {r.region for r in result} == {"역삼동", "종로동"}
