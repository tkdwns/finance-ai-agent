"""src/reports/charts.py 차트 생성 함수 테스트."""

from datetime import datetime

from src.reports.charts import generate_bond_charts, generate_real_estate_chart
from src.storage.queries import IndicatorPoint, TransactionPoint


def _indicator(date, value=3.0, code="722Y001", name="한국은행 기준금리", unit="%"):
    return IndicatorPoint(
        indicator_code=code, indicator_name=name, date=date, value=value, unit=unit, source="ECOS"
    )


def _transaction(date, region="역삼동", price=100000.0):
    return TransactionPoint(
        region=region, complex_name="A", transaction_price=price,
        area_m2=84.0, floor=5, transaction_date=date, source="MOLIT",
    )


def test_generate_bond_charts_returns_empty_list_when_no_points(tmp_path):
    assert generate_bond_charts([], str(tmp_path), "chart") == []


def test_generate_bond_charts_creates_one_file_per_indicator(tmp_path):
    # 단위(%, pt)가 서로 다른 지표를 한 그래프에 겹쳐 그리면 알아보기 어렵다는 피드백을
    # 반영해, 지표별로 독립된 PNG 파일을 만들어야 한다(격자 배치는 리포트 쪽에서 처리).
    points = [
        _indicator(datetime(2026, 1, 1), value=3.25, name="한국은행 기준금리", unit="%"),
        _indicator(datetime(2026, 2, 1), value=3.00, name="한국은행 기준금리", unit="%"),
        _indicator(datetime(2026, 1, 1), value=2500.0, code="802Y001_0001000", name="KOSPI지수", unit="pt"),
        _indicator(datetime(2026, 2, 1), value=2600.0, code="802Y001_0001000", name="KOSPI지수", unit="pt"),
    ]
    results = generate_bond_charts(points, str(tmp_path), "chart")

    assert [name for name, _ in results] == ["한국은행 기준금리", "KOSPI지수"]
    for _, filename in results:
        output_file = tmp_path / filename
        assert output_file.exists()
        assert output_file.stat().st_size > 0


def test_generate_bond_charts_includes_indicators_with_single_point(tmp_path):
    # 기준금리처럼 기간 내 값이 1건뿐인 지표도(월별 갱신이라 변동이 없으면 이렇게 됨)
    # 점 하나짜리 그래프로라도 표시해야 한다 — 예전에는 통째로 제외되던 문제가 있었음.
    points = [
        _indicator(datetime(2026, 1, 1), value=3.25, name="한국은행 기준금리"),
        _indicator(datetime(2026, 1, 1), value=2500.0, code="802Y001_0001000", name="KOSPI지수"),
        _indicator(datetime(2026, 2, 1), value=2600.0, code="802Y001_0001000", name="KOSPI지수"),
    ]
    results = generate_bond_charts(points, str(tmp_path), "chart")
    assert [name for name, _ in results] == ["한국은행 기준금리", "KOSPI지수"]
    for _, filename in results:
        assert (tmp_path / filename).exists()


def test_generate_bond_charts_handles_six_indicators(tmp_path):
    points = []
    for i in range(6):
        points.append(_indicator(datetime(2026, 1, 1), value=float(i), name=f"지표{i}"))
        points.append(_indicator(datetime(2026, 2, 1), value=float(i) + 1, name=f"지표{i}"))

    results = generate_bond_charts(points, str(tmp_path), "chart")
    assert len(results) == 6
    for _, filename in results:
        assert (tmp_path / filename).exists()


def test_generate_real_estate_chart_returns_none_when_single_month_region(tmp_path):
    points = [_transaction(datetime(2026, 6, 1)), _transaction(datetime(2026, 6, 15))]
    # 같은 지역·같은 연월이라 (region, year-month) 조합이 1개뿐 -> 추이 없음
    assert generate_real_estate_chart(points, str(tmp_path), "re.png") is None


def test_generate_real_estate_chart_creates_file_with_multiple_months(tmp_path):
    points = [_transaction(datetime(2026, 5, 1), price=90000.0), _transaction(datetime(2026, 6, 1), price=100000.0)]
    filename = generate_real_estate_chart(points, str(tmp_path), "re.png")

    assert filename == "re.png"
    output_file = tmp_path / "re.png"
    assert output_file.exists()
    assert output_file.stat().st_size > 0
