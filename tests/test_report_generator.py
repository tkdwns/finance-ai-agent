"""보고서 생성 모듈(src/reports/report_generator.py) 테스트."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from src.reports.report_generator import generate_report
from src.storage.models import (
    AssetClass,
    Base,
    BondIndicator,
    Keyword,
    LawAmendment,
    PeriodType,
    RealEstateTransaction,
    StockDisclosure,
    law_amendment_asset_class,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(autouse=True)
def _stub_summarizer(monkeypatch):
    """LLM 요약(summarize_documents)을 원문 그대로 돌려주는 스텁으로 교체한다.

    실제 LLM을 호출하면(키 설정 여부와 무관하게) 테스트가 네트워크에 의존하게 되고
    느려지므로, 리포트 조립 로직만 검증하도록 항상 패스스루로 대체한다."""

    def _passthrough(items, max_lines=3, api_key=None, provider=None):
        return {key: text for key, text in items}

    def _group_passthrough(texts, max_lines=6, api_key=None, provider=None):
        return " / ".join(texts)

    monkeypatch.setattr("src.reports.report_generator.summarize_documents", _passthrough)
    monkeypatch.setattr("src.reports.report_generator.summarize_group", _group_passthrough)


def test_generate_report_includes_keywords_and_documents(session):
    now = datetime(2026, 7, 27, 9, 0)
    period_start = datetime(2026, 7, 21)
    period_end = datetime(2026, 7, 28)

    session.add(
        StockDisclosure(
            source="DART", title="주요사항보고서(회사합병결정)", url="https://dart.fss.or.kr/x1",
            summary="이사회는 합병을 결정했다", published_at=now,
            corp_name="삼성전자", corp_code="001", rcept_no="r1", report_name="주요사항보고서",
        )
    )
    session.add(
        Keyword(
            asset_class=AssetClass.STOCK, period_type=PeriodType.WEEKLY,
            period_start=period_start, period_end=period_end,
            keyword="합병", score=8.5, explanation="여러 건의 합병 이슈가 있었다.",
        )
    )
    session.commit()

    report = generate_report(session, PeriodType.WEEKLY, period_start, period_end)

    assert "주간 금융 리포트" in report
    assert "합병" in report
    assert "여러 건의 합병 이슈가 있었다." in report
    assert "공시 (1건)" in report  # 개별 문서 대신 content_type별 그룹 종합요약으로 표시
    assert "이사회는 합병을 결정했다" in report  # 그룹 요약(스텁이라 원문 그대로) 표시 확인
    # 그룹 요약과는 별도로, 접힌 원문 목록에 개별 문서 제목·링크도 함께 표시된다 (절충안).
    assert "주요사항보고서(회사합병결정)" in report
    assert "https://dart.fss.or.kr/x1" in report
    assert "삼성전자" in report
    assert "투자 권유가 아닙니다" in report


def test_generate_report_handles_empty_period(session):
    period_start = datetime(2026, 1, 1)
    period_end = datetime(2026, 1, 8)

    report = generate_report(session, PeriodType.WEEKLY, period_start, period_end)

    assert "추출된 키워드가 없습니다" in report
    assert "수집된 문서가 없습니다" in report


def test_generate_report_filters_by_asset_class(session):
    now = datetime(2026, 7, 27)
    period_start = datetime(2026, 7, 21)
    period_end = datetime(2026, 7, 28)

    session.add(
        StockDisclosure(
            source="DART", title="주식 공시", url="https://dart.fss.or.kr/x2",
            summary="주식 공시 원문 요약", published_at=now,
            corp_name="A사", corp_code="001", rcept_no="r2", report_name="주식 공시",
        )
    )
    session.add(
        Keyword(
            asset_class=AssetClass.CRYPTO, period_type=PeriodType.WEEKLY,
            period_start=period_start, period_end=period_end,
            keyword="비트코인", score=5.0, explanation="암호화폐 이슈",
        )
    )
    session.commit()

    report = generate_report(
        session, PeriodType.WEEKLY, period_start, period_end, asset_class=AssetClass.STOCK
    )

    assert "주식" in report
    assert "주식 공시 원문 요약" in report  # 그룹 요약(스텁이라 원문 그대로)
    assert "비트코인" not in report  # 다른 자산군 키워드는 제외되어야 함


def test_generate_report_limits_document_count(session):
    now = datetime(2026, 7, 27)
    period_start = datetime(2026, 7, 21)
    period_end = datetime(2026, 7, 28)

    for i in range(5):
        session.add(
            StockDisclosure(
                source="DART", title=f"공시 {i}", url=f"https://dart.fss.or.kr/x{i}",
                summary="요약", published_at=now - timedelta(hours=i),
                corp_name="A사", corp_code="001", rcept_no=f"r{i}", report_name=f"공시 {i}",
            )
        )
    session.commit()

    report = generate_report(session, PeriodType.WEEKLY, period_start, period_end, max_documents=2)

    assert "전체 5건 중 최신 2건 표시" in report
    # max_documents=2로 제한된 뒤 그룹 요약에 들어가므로, 그룹 표시 건수도 2건이어야 함
    assert "공시 (2건)" in report


def test_generate_report_applies_exclude_pattern(session):
    now = datetime(2026, 7, 27)
    period_start = datetime(2026, 7, 21)
    period_end = datetime(2026, 7, 28)

    session.add_all(
        [
            StockDisclosure(
                source="DART", title="주가연계증권(ELS) 발행실적보고서", url="https://dart.fss.or.kr/e1",
                summary="ELS 발행 실적", published_at=now,
                corp_name="A사", corp_code="001", rcept_no="r1", report_name="ELS",
            ),
            StockDisclosure(
                source="DART", title="주요사항보고서(회사합병결정)", url="https://dart.fss.or.kr/e2",
                summary="합병 결정", published_at=now,
                corp_name="B사", corp_code="002", rcept_no="r2", report_name="합병",
            ),
        ]
    )
    session.commit()

    report = generate_report(
        session, PeriodType.WEEKLY, period_start, period_end, exclude_pattern="structured"
    )

    assert "전체 1건 중 최신 1건 표시" in report
    assert "합병 결정" in report
    assert "ELS 발행 실적" not in report


def test_generate_report_applies_only_enriched(session):
    now = datetime(2026, 7, 27)
    period_start = datetime(2026, 7, 21)
    period_end = datetime(2026, 7, 28)

    session.add_all(
        [
            # summary가 title(report_name)과 동일 -> "제목만 있는 건"으로 간주되어 제외됨
            StockDisclosure(
                source="DART", title="제목만 있는 공시", url="https://dart.fss.or.kr/p1",
                summary="제목만 있는 공시", published_at=now,
                corp_name="A사", corp_code="001", rcept_no="r1", report_name="제목만 있는 공시",
            ),
            StockDisclosure(
                source="DART", title="원문 채워진 공시", url="https://dart.fss.or.kr/p2",
                summary="실제 원문 내용이 채워진 요약", published_at=now,
                corp_name="B사", corp_code="002", rcept_no="r2", report_name="원문 채워진 공시",
            ),
        ]
    )
    session.commit()

    report = generate_report(
        session, PeriodType.WEEKLY, period_start, period_end, only_enriched=True
    )

    assert "전체 1건 중 최신 1건 표시" in report
    assert "실제 원문 내용이 채워진 요약" in report


def test_generate_report_includes_bond_indicator_summary(session):
    period_start = datetime(2026, 1, 1)
    period_end = datetime(2026, 6, 30)

    session.add_all(
        [
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 1, 1), value=3.25, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 6, 1), value=3.00, unit="%", source="ECOS",
            ),
        ]
    )
    session.commit()

    report = generate_report(session, PeriodType.WEEKLY, period_start, period_end)

    assert "주요 금리·지수 지표" in report
    assert "한국은행 기준금리" in report
    assert "3.00%" in report  # 최근 값
    assert "-0.25%" in report  # 기간 중 변화 (3.00 - 3.25)


def test_generate_report_excludes_bond_indicators_for_other_asset_class(session):
    period_start = datetime(2026, 1, 1)
    period_end = datetime(2026, 6, 30)

    session.add(
        BondIndicator(
            indicator_code="722Y001", indicator_name="한국은행 기준금리",
            date=datetime(2026, 1, 1), value=3.25, unit="%", source="ECOS",
        )
    )
    session.commit()

    report = generate_report(
        session, PeriodType.WEEKLY, period_start, period_end, asset_class=AssetClass.STOCK
    )

    assert "주요 금리·지수 지표" not in report


def test_generate_report_separates_bond_and_stock_indicators(session):
    # bond_indicators 테이블은 ECOS(채권)/FRED(주식지수)가 함께 저장되므로, asset_class별
    # 리포트에서 서로 섞여 노출되면 안 된다 (예: 채권 리포트에 나스닥이 나오는 등).
    period_start = datetime(2026, 1, 1)
    period_end = datetime(2026, 6, 30)

    session.add_all(
        [
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리", asset_class="bond",
                date=datetime(2026, 1, 1), value=3.25, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리", asset_class="bond",
                date=datetime(2026, 6, 1), value=3.00, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="NASDAQCOM", indicator_name="나스닥종합지수", asset_class="stock",
                date=datetime(2026, 1, 1), value=15000.0, unit="pt", source="FRED",
            ),
            BondIndicator(
                indicator_code="NASDAQCOM", indicator_name="나스닥종합지수", asset_class="stock",
                date=datetime(2026, 6, 1), value=16000.0, unit="pt", source="FRED",
            ),
        ]
    )
    session.commit()

    stock_report = generate_report(
        session, PeriodType.WEEKLY, period_start, period_end, asset_class=AssetClass.STOCK
    )
    assert "나스닥종합지수" in stock_report
    assert "한국은행 기준금리" not in stock_report

    bond_report = generate_report(
        session, PeriodType.WEEKLY, period_start, period_end, asset_class=AssetClass.BOND
    )
    assert "한국은행 기준금리" in bond_report
    assert "나스닥종합지수" not in bond_report


def test_generate_report_includes_real_estate_transaction_summary(session):
    period_start = datetime(2026, 6, 1)
    period_end = datetime(2026, 6, 30)

    session.add_all(
        [
            RealEstateTransaction(
                region="역삼동", complex_name="래미안", transaction_price=100000.0,
                area_m2=84.0, floor=5, transaction_date=datetime(2026, 6, 10), source="MOLIT",
            ),
            RealEstateTransaction(
                region="역삼동", complex_name="래미안", transaction_price=120000.0,
                area_m2=84.0, floor=8, transaction_date=datetime(2026, 6, 20), source="MOLIT",
            ),
        ]
    )
    session.commit()

    report = generate_report(session, PeriodType.MONTHLY, period_start, period_end)

    assert "부동산 실거래가" in report
    assert "역삼동" in report
    assert "2건" in report
    assert "110,000만원" in report  # 평균가 (100,000 + 120,000) / 2


def test_generate_report_excludes_real_estate_transactions_for_other_asset_class(session):
    period_start = datetime(2026, 6, 1)
    period_end = datetime(2026, 6, 30)

    session.add(
        RealEstateTransaction(
            region="역삼동", complex_name="래미안", transaction_price=100000.0,
            area_m2=84.0, floor=5, transaction_date=datetime(2026, 6, 10), source="MOLIT",
        )
    )
    session.commit()

    report = generate_report(
        session, PeriodType.MONTHLY, period_start, period_end, asset_class=AssetClass.STOCK
    )

    assert "부동산 실거래가" not in report


def test_generate_report_includes_law_amendments(session):
    period_start = datetime(2026, 5, 1)
    period_end = datetime(2026, 7, 30)

    amendment = LawAmendment(
        source="법제처", title="은행법 일부개정", url="https://www.law.go.kr/x1",
        summary="금융위원회 · 공포일자 20260616 · 시행일자 20260701",
        amendment_reason_summary="금융소비자 보호 강화를 위해 관련 조항을 개정함.",
        published_at=datetime(2026, 7, 1), law_name="은행법",
        amendment_date=datetime(2026, 7, 1),
    )
    session.add(amendment)
    session.commit()
    session.execute(
        insert(law_amendment_asset_class).values(law_amendment_id=amendment.id, asset_class=AssetClass.BOND)
    )
    session.commit()

    report = generate_report(session, PeriodType.MONTHLY, period_start, period_end)

    assert "법령·규제 개정" in report
    assert "은행법 일부개정" in report
    assert "금융소비자 보호 강화를 위해 관련 조항을 개정함." in report  # 요약(스텁이라 원문 그대로)
    assert "https://www.law.go.kr/x1" not in report  # 링크는 더 이상 표시하지 않음


def test_generate_report_excludes_law_amendments_for_other_asset_class(session):
    period_start = datetime(2026, 5, 1)
    period_end = datetime(2026, 7, 30)

    amendment = LawAmendment(
        source="법제처", title="은행법 일부개정", url="https://www.law.go.kr/x2",
        summary="요약", published_at=datetime(2026, 7, 1), law_name="은행법",
        amendment_date=datetime(2026, 7, 1),
    )
    session.add(amendment)
    session.commit()
    session.execute(
        insert(law_amendment_asset_class).values(law_amendment_id=amendment.id, asset_class=AssetClass.BOND)
    )
    session.commit()

    report = generate_report(
        session, PeriodType.MONTHLY, period_start, period_end, asset_class=AssetClass.STOCK
    )

    assert "법령·규제 개정" not in report


def test_generate_report_embeds_bond_chart_when_chart_dir_given(session, tmp_path):
    period_start = datetime(2026, 1, 1)
    period_end = datetime(2026, 6, 30)

    session.add_all(
        [
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 1, 1), value=3.25, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 6, 1), value=3.00, unit="%", source="ECOS",
            ),
        ]
    )
    session.commit()

    chart_dir = tmp_path / "charts"
    report = generate_report(
        session, PeriodType.MONTHLY, period_start, period_end, chart_dir=str(chart_dir)
    )

    # 지표별로 개별 PNG가 생성되고, 리포트에는 3열 격자 표(HTML table)로 삽입된다.
    assert '<img src="charts/' in report
    assert any(chart_dir.iterdir())


def test_generate_report_has_no_chart_reference_without_chart_dir(session):
    period_start = datetime(2026, 1, 1)
    period_end = datetime(2026, 6, 30)

    session.add_all(
        [
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 1, 1), value=3.25, unit="%", source="ECOS",
            ),
            BondIndicator(
                indicator_code="722Y001", indicator_name="한국은행 기준금리",
                date=datetime(2026, 6, 1), value=3.00, unit="%", source="ECOS",
            ),
        ]
    )
    session.commit()

    report = generate_report(session, PeriodType.MONTHLY, period_start, period_end)

    assert "<img src=" not in report
