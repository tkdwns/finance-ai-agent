"""MolitCollector 단위 테스트 (실제 API 호출 없이 requests.get을 모킹)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.real_estate_collector import MolitApiError, MolitCollector


def _success_xml(items_xml: str, total_count: int, num_of_rows: int = 100, page_no: int = 1) -> str:
    return f"""
    <response>
        <header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>
        <body>
            <items>{items_xml}</items>
            <numOfRows>{num_of_rows}</numOfRows>
            <pageNo>{page_no}</pageNo>
            <totalCount>{total_count}</totalCount>
        </body>
    </response>
    """


def _item_xml(
    apt_nm="래미안아파트",
    deal_amount="115,000",
    year="2026",
    month="6",
    day="15",
    area="84.95",
    floor="12",
    umd_nm="역삼동",
) -> str:
    return f"""
    <item>
        <aptNm>{apt_nm}</aptNm>
        <dealAmount>{deal_amount}</dealAmount>
        <dealYear>{year}</dealYear>
        <dealMonth>{month}</dealMonth>
        <dealDay>{day}</dealDay>
        <excluUseAr>{area}</excluUseAr>
        <floor>{floor}</floor>
        <umdNm>{umd_nm}</umdNm>
    </item>
    """


def _mock_response(xml_text: str):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = xml_text
    return resp


def test_collect_raises_when_api_key_missing(monkeypatch):
    # EcosCollector 테스트와 동일한 이유: .env에 값이 들어있는 환경에서도
    # "키 없음" 케이스를 확실히 재현하려면 settings 자체를 비워야 한다.
    monkeypatch.setattr("src.collectors.real_estate_collector.settings.molit_api_key", "")
    collector = MolitCollector(api_key="")
    with pytest.raises(MolitApiError):
        collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30), region_codes=["11680"])


def test_collect_parses_valid_item():
    collector = MolitCollector(api_key="dummy-key")
    with patch("src.collectors.real_estate_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_success_xml(_item_xml(), total_count=1))
        result = collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30), region_codes=["11680"])

    assert len(result) == 1
    txn = result[0]
    assert txn.source == "MOLIT"
    assert txn.region == "역삼동"
    assert txn.complex_name == "래미안아파트"
    assert txn.transaction_price == 115000.0
    assert txn.area_m2 == 84.95
    assert txn.floor == 12
    assert txn.transaction_date == datetime(2026, 6, 15)


def test_collect_raises_on_auth_error_response():
    collector = MolitCollector(api_key="dummy-key")
    error_xml = """
    <OpenAPI_ServiceResponse>
        <cmmMsgHeader>
            <errMsg>SERVICE ERROR</errMsg>
            <returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>
            <returnReasonCode>30</returnReasonCode>
        </cmmMsgHeader>
    </OpenAPI_ServiceResponse>
    """
    with patch("src.collectors.real_estate_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(error_xml)
        with pytest.raises(MolitApiError):
            collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30), region_codes=["11680"])


def test_collect_raises_on_bad_result_code():
    collector = MolitCollector(api_key="dummy-key")
    bad_xml = """
    <response>
        <header><resultCode>99</resultCode><resultMsg>알 수 없는 오류</resultMsg></header>
        <body><items></items><numOfRows>10</numOfRows><pageNo>1</pageNo><totalCount>0</totalCount></body>
    </response>
    """
    with patch("src.collectors.real_estate_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(bad_xml)
        with pytest.raises(MolitApiError):
            collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30), region_codes=["11680"])


def test_collect_raises_on_malformed_xml():
    collector = MolitCollector(api_key="dummy-key")
    with patch("src.collectors.real_estate_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response("<not><valid</xml>")
        with pytest.raises(MolitApiError):
            collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30), region_codes=["11680"])


def test_collect_filters_out_of_range_dates():
    """월 단위로 조회하므로 같은 달 안에서도 요청 기간(일 단위) 밖의 거래는 제외돼야 한다."""
    collector = MolitCollector(api_key="dummy-key")
    items_xml = _item_xml(day="1") + _item_xml(day="20", apt_nm="다른아파트")
    with patch("src.collectors.real_estate_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_success_xml(items_xml, total_count=2))
        result = collector.collect(datetime(2026, 6, 10), datetime(2026, 6, 30), region_codes=["11680"])

    assert len(result) == 1
    assert result[0].complex_name == "다른아파트"


def test_collect_skips_items_with_unparsable_price():
    collector = MolitCollector(api_key="dummy-key")
    items_xml = _item_xml(deal_amount="") + _item_xml(deal_amount="not-a-number")
    with patch("src.collectors.real_estate_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_success_xml(items_xml, total_count=2))
        result = collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30), region_codes=["11680"])

    assert result == []


def test_collect_paginates_when_total_count_exceeds_page_size():
    collector = MolitCollector(api_key="dummy-key")
    page1 = _success_xml(_item_xml(apt_nm="1페이지"), total_count=2, num_of_rows=1, page_no=1)
    page2 = _success_xml(_item_xml(apt_nm="2페이지"), total_count=2, num_of_rows=1, page_no=2)

    with patch("src.collectors.real_estate_collector.requests.get") as mock_get:
        mock_get.side_effect = [_mock_response(page1), _mock_response(page2)]
        result = collector.collect(
            datetime(2026, 6, 1), datetime(2026, 6, 30), region_codes=["11680"], page_count=1
        )

    assert mock_get.call_count == 2
    assert {t.complex_name for t in result} == {"1페이지", "2페이지"}


def test_collect_loops_over_multiple_regions_and_months():
    collector = MolitCollector(api_key="dummy-key")
    with patch("src.collectors.real_estate_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_success_xml(_item_xml(), total_count=1))
        collector.collect(
            datetime(2026, 5, 15), datetime(2026, 6, 15), region_codes=["11680", "11650"]
        )

    # 2개 지역 x 2개월(5월,6월) = 4번 호출
    assert mock_get.call_count == 4
