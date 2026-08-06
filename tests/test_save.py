"""storage/save.py 저장 어댑터 테스트."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.collectors.base import RawItem
from src.collectors.ecos_collector import RawIndicator
from src.collectors.real_estate_collector import RawTransaction
from src.storage.models import (
    Base,
    BondIndicator,
    BondNews,
    LawAmendment,
    RealEstateTransaction,
    StockDisclosure,
    StockNews,
    law_amendment_asset_class,
)
from src.storage.save import (
    save_bond_indicators,
    save_law_amendments,
    save_news_items,
    save_real_estate_transactions,
    save_stock_disclosures,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_disclosure_item(rcept_no, corp_name="삼성전자", summary="분기보고서"):
    return RawItem(
        source="DART",
        asset_class="stock",
        title="분기보고서",
        url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
        published_at=datetime(2026, 1, 20),
        summary=summary,
        raw_meta={
            "corp_name": corp_name,
            "corp_code": "00126380",
            "rcept_no": rcept_no,
            "report_name": "분기보고서",
        },
    )


def test_save_stock_disclosures_inserts_new_rows(session):
    items = [_make_disclosure_item("r1"), _make_disclosure_item("r2")]
    saved, updated = save_stock_disclosures(session, items)

    assert (saved, updated) == (2, 0)
    rows = session.execute(select(StockDisclosure)).scalars().all()
    assert len(rows) == 2


def test_save_stock_disclosures_skips_existing_rcept_no_by_default(session):
    save_stock_disclosures(session, [_make_disclosure_item("r1")])
    saved, updated = save_stock_disclosures(session, [_make_disclosure_item("r1")])

    assert (saved, updated) == (0, 0)
    rows = session.execute(select(StockDisclosure)).scalars().all()
    assert len(rows) == 1


def test_save_stock_disclosures_updates_summary_when_richer_text_provided(session):
    save_stock_disclosures(session, [_make_disclosure_item("r1", summary="분기보고서")])

    richer_item = _make_disclosure_item("r1", summary="분기보고서 매출액이 전년 대비 크게 증가했다는 내용의 상세 원문 텍스트")
    saved, updated = save_stock_disclosures(session, [richer_item], update_existing=True)

    assert (saved, updated) == (0, 1)
    row = session.execute(
        select(StockDisclosure).where(StockDisclosure.rcept_no == "r1")
    ).scalar_one()
    assert "매출액이 전년 대비" in row.summary


def test_save_stock_disclosures_does_not_shrink_summary(session):
    save_stock_disclosures(
        session, [_make_disclosure_item("r1", summary="이미 긴 원문 요약 텍스트가 저장되어 있는 상태")]
    )

    shorter_item = _make_disclosure_item("r1", summary="짧은 제목")
    saved, updated = save_stock_disclosures(session, [shorter_item], update_existing=True)

    assert (saved, updated) == (0, 0)
    row = session.execute(
        select(StockDisclosure).where(StockDisclosure.rcept_no == "r1")
    ).scalar_one()
    assert row.summary == "이미 긴 원문 요약 텍스트가 저장되어 있는 상태"


def _make_indicator(date, value=3.25, indicator_code="722Y001"):
    return RawIndicator(
        source="ECOS",
        asset_class="bond",
        indicator_code=indicator_code,
        indicator_name="한국은행 기준금리",
        date=date,
        value=value,
        unit="%",
    )


def test_save_bond_indicators_inserts_new_rows(session):
    items = [_make_indicator(datetime(2026, 1, 1)), _make_indicator(datetime(2026, 2, 1))]
    saved, updated = save_bond_indicators(session, items)

    assert (saved, updated) == (2, 0)
    rows = session.execute(select(BondIndicator)).scalars().all()
    assert len(rows) == 2


def test_save_bond_indicators_skips_when_value_unchanged(session):
    save_bond_indicators(session, [_make_indicator(datetime(2026, 1, 1), value=3.25)])
    saved, updated = save_bond_indicators(session, [_make_indicator(datetime(2026, 1, 1), value=3.25)])

    assert (saved, updated) == (0, 0)
    rows = session.execute(select(BondIndicator)).scalars().all()
    assert len(rows) == 1


def test_save_bond_indicators_updates_when_value_revised(session):
    save_bond_indicators(session, [_make_indicator(datetime(2026, 1, 1), value=3.25)])
    saved, updated = save_bond_indicators(session, [_make_indicator(datetime(2026, 1, 1), value=3.00)])

    assert (saved, updated) == (0, 1)
    row = session.execute(select(BondIndicator)).scalar_one()
    assert row.value == 3.00


def test_save_bond_indicators_corrects_unit_on_recollection(session):
    # 실사용 중 발견된 버그 재현: 코스피/코스닥은 처음엔 ECOS가 내려주는 잘못된 단위
    # ("1980.01.04=100")로 저장됐었다. 이후 코드가 프리셋의 올바른 단위("pt")를 쓰도록
    # 고쳐졌으니, 재수집 시 값이 같아도 단위가 다르면 기존 행이 정정되어야 한다.
    stale = _make_indicator(datetime(2026, 7, 1), value=2600.0, indicator_code="802Y001_0001000")
    stale.unit = "1980.01.04=100"
    save_bond_indicators(session, [stale])

    fixed = _make_indicator(datetime(2026, 7, 1), value=2600.0, indicator_code="802Y001_0001000")
    fixed.unit = "pt"
    saved, updated = save_bond_indicators(session, [fixed])

    assert (saved, updated) == (0, 1)
    row = session.execute(select(BondIndicator)).scalar_one()
    assert row.unit == "pt"


def test_save_bond_indicators_does_not_collide_when_stat_code_shared(session):
    # 실사용 중 발견된 버그 재현: 코스피/코스닥은 같은 ECOS stat_code(802Y001)를 공유하고
    # item_code1만 다르다. indicator_code가 stat_code만 담으면 (indicator_code, date) 유니크
    # 제약에 걸려 IntegrityError가 났었다 (ecos_collector.py에서 stat_code_item_code1로 수정).
    same_date = datetime(2026, 7, 1)
    kospi = RawIndicator(
        source="ECOS", asset_class="stock", indicator_code="802Y001_0001000",
        indicator_name="코스피지수", date=same_date, value=2600.0, unit="pt",
    )
    kosdaq = RawIndicator(
        source="ECOS", asset_class="stock", indicator_code="802Y001_0089000",
        indicator_name="코스닥지수", date=same_date, value=900.0, unit="pt",
    )
    saved, updated = save_bond_indicators(session, [kospi, kosdaq])

    assert (saved, updated) == (2, 0)
    rows = session.execute(select(BondIndicator)).scalars().all()
    assert len(rows) == 2


def test_save_bond_indicators_persists_asset_class(session):
    # FRED 수집기가 asset_class="stock"으로 넘긴 RawIndicator도 그대로 저장되는지 확인
    # (채권/주식 지표가 같은 테이블에 섞이므로, 리포트 필터링이 이 값에 의존한다).
    item = RawIndicator(
        source="FRED", asset_class="stock", indicator_code="NASDAQCOM",
        indicator_name="나스닥종합지수", date=datetime(2026, 1, 1), value=15000.0, unit="pt",
    )
    save_bond_indicators(session, [item])

    row = session.execute(select(BondIndicator)).scalar_one()
    assert row.asset_class == "stock"


def _make_transaction(
    region="역삼동", complex_name="래미안아파트", price=115000.0,
    area=84.95, floor=12, date=datetime(2026, 6, 15),
):
    return RawTransaction(
        source="MOLIT", region=region, complex_name=complex_name,
        transaction_price=price, area_m2=area, floor=floor, transaction_date=date,
    )


def test_save_real_estate_transactions_inserts_new_rows(session):
    items = [_make_transaction(), _make_transaction(complex_name="다른아파트")]
    saved, skipped = save_real_estate_transactions(session, items)

    assert (saved, skipped) == (2, 0)
    rows = session.execute(select(RealEstateTransaction)).scalars().all()
    assert len(rows) == 2


def test_save_real_estate_transactions_skips_exact_duplicates(session):
    save_real_estate_transactions(session, [_make_transaction()])
    saved, skipped = save_real_estate_transactions(session, [_make_transaction()])

    assert (saved, skipped) == (0, 1)
    rows = session.execute(select(RealEstateTransaction)).scalars().all()
    assert len(rows) == 1


def test_save_real_estate_transactions_treats_different_price_as_new_row(session):
    save_real_estate_transactions(session, [_make_transaction(price=115000.0)])
    saved, skipped = save_real_estate_transactions(session, [_make_transaction(price=120000.0)])

    assert (saved, skipped) == (1, 0)
    rows = session.execute(select(RealEstateTransaction)).scalars().all()
    assert len(rows) == 2


def _make_news_item(url, asset_class="stock", title="뉴스 제목", source="테스트언론사"):
    return RawItem(
        source=source,
        asset_class=asset_class,
        title=title,
        url=url,
        published_at=datetime(2026, 7, 20, 9, 0),
        summary="요약",
    )


def test_save_news_items_routes_by_asset_class(session):
    items = [
        _make_news_item("http://a.com/1", asset_class="stock"),
        _make_news_item("http://a.com/2", asset_class="bond"),
    ]
    result = save_news_items(session, items)

    assert result["stock"] == 1
    assert result["bond"] == 1
    assert session.execute(select(StockNews)).scalars().all().__len__() == 1
    assert session.execute(select(BondNews)).scalars().all().__len__() == 1


def test_save_news_items_skips_unmapped_asset_classes(session):
    items = [
        _make_news_item("http://a.com/3", asset_class="real_estate"),
        _make_news_item("http://a.com/4", asset_class="unknown"),
        _make_news_item("http://a.com/5", asset_class=""),
    ]
    result = save_news_items(session, items)

    assert result["skipped_unmapped"] == 3
    assert result["stock"] == 0
    assert result["bond"] == 0


def test_save_news_items_skips_duplicate_urls(session):
    save_news_items(session, [_make_news_item("http://a.com/6", asset_class="stock")])
    result = save_news_items(session, [_make_news_item("http://a.com/6", asset_class="stock")])

    assert result["skipped_duplicate"] == 1
    assert result["stock"] == 0
    rows = session.execute(select(StockNews)).scalars().all()
    assert len(rows) == 1


def _make_law_item(url, law_name="자본시장과 금융투자업에 관한 법률"):
    return RawItem(
        source="법제처", asset_class="law", title=f"{law_name} 일부개정", url=url,
        published_at=datetime(2026, 6, 15), summary="요약", raw_meta={"law_name": law_name},
    )


def test_save_law_amendments_inserts_and_maps_asset_classes(session):
    saved, skipped = save_law_amendments(session, [_make_law_item("http://law.go.kr/1")])

    assert (saved, skipped) == (1, 0)
    amendment = session.execute(select(LawAmendment)).scalar_one()
    links = session.execute(
        select(law_amendment_asset_class.c.asset_class).where(
            law_amendment_asset_class.c.law_amendment_id == amendment.id
        )
    ).scalars().all()
    assert set(links) == {"stock", "bond"}


def test_save_law_amendments_skips_duplicate_urls(session):
    save_law_amendments(session, [_make_law_item("http://law.go.kr/2")])
    saved, skipped = save_law_amendments(session, [_make_law_item("http://law.go.kr/2")])

    assert (saved, skipped) == (0, 1)
    rows = session.execute(select(LawAmendment)).scalars().all()
    assert len(rows) == 1


def test_save_law_amendments_uses_reason_text_when_present(session):
    item = RawItem(
        source="법제처", asset_class="law", title="은행법 일부개정", url="http://law.go.kr/3",
        published_at=datetime(2026, 6, 15), summary="메타 정보 문자열",
        raw_meta={"law_name": "은행법", "reason_text": "실제 개정 이유 발췌문"},
    )
    save_law_amendments(session, [item])

    row = session.execute(select(LawAmendment)).scalar_one()
    assert row.amendment_reason_summary == "실제 개정 이유 발췌문"


def test_save_law_amendments_falls_back_to_meta_summary_when_reason_text_missing(session):
    item = RawItem(
        source="법제처", asset_class="law", title="은행법 일부개정", url="http://law.go.kr/4",
        published_at=datetime(2026, 6, 15), summary="메타 정보 문자열",
        raw_meta={"law_name": "은행법", "reason_text": None},
    )
    save_law_amendments(session, [item])

    row = session.execute(select(LawAmendment)).scalar_one()
    assert row.amendment_reason_summary == "메타 정보 문자열"
