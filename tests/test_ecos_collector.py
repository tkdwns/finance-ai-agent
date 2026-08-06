"""EcosCollector 단위 테스트 (실제 API 호출 없이 requests.get을 모킹)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.ecos_collector import EcosApiError, EcosCollector


def _mock_response(rows=None, error_code=None, error_message="오류"):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    if error_code is not None:
        resp.json.return_value = {"RESULT": {"CODE": error_code, "MESSAGE": error_message}}
    else:
        resp.json.return_value = {"StatisticSearch": {"row": rows or []}}
    return resp


def test_collect_raises_when_api_key_missing(monkeypatch):
    # api_key=""를 넘겨도 settings.ecos_api_key로 폴백하므로, .env에 값이 들어있는
    # 환경(placeholder 포함)에서도 "키 없음" 케이스를 확실히 재현하려면 settings 자체를
    # 비워야 한다.
    monkeypatch.setattr("src.collectors.ecos_collector.settings.ecos_api_key", "")
    collector = EcosCollector(api_key="")
    with pytest.raises(EcosApiError):
        collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 1))


def test_collect_returns_empty_list_when_no_data():
    collector = EcosCollector(api_key="dummy-key")
    with patch("src.collectors.ecos_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(error_code="INFO-200")
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 1))
    assert result == []


def test_collect_raises_on_error_status():
    collector = EcosCollector(api_key="dummy-key")
    with patch("src.collectors.ecos_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(error_code="ERROR-100", error_message="필수 값 누락")
        with pytest.raises(EcosApiError):
            collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 1))


def test_collect_parses_monthly_rows_for_base_rate():
    rows = [
        {
            "STAT_CODE": "722Y001",
            "ITEM_CODE1": "0101000",
            "ITEM_NAME1": "한국은행 기준금리",
            "TIME": "202601",
            "DATA_VALUE": "3.25",
            "UNIT_NAME": "%",
        },
        {
            "STAT_CODE": "722Y001",
            "ITEM_CODE1": "0101000",
            "ITEM_NAME1": "한국은행 기준금리",
            "TIME": "202606",
            "DATA_VALUE": "3.00",
            "UNIT_NAME": "%",
        },
    ]
    collector = EcosCollector(api_key="dummy-key")
    with patch("src.collectors.ecos_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(rows)
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 30), indicators=["base_rate"])

    assert len(result) == 2
    assert result[0].asset_class == "bond"
    assert result[0].indicator_code == "722Y001_0101000"
    assert result[0].indicator_name == "한국은행 기준금리"
    assert result[0].date == datetime(2026, 1, 1)
    assert result[0].value == 3.25
    assert result[1].date == datetime(2026, 6, 1)
    assert result[1].value == 3.00


def test_collect_skips_rows_with_invalid_time_or_value():
    rows = [
        {"ITEM_NAME1": "한국은행 기준금리", "TIME": "invalid", "DATA_VALUE": "3.25", "UNIT_NAME": "%"},
        {"ITEM_NAME1": "한국은행 기준금리", "TIME": "202601", "DATA_VALUE": "n/a", "UNIT_NAME": "%"},
    ]
    collector = EcosCollector(api_key="dummy-key")
    with patch("src.collectors.ecos_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(rows)
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 30), indicators=["base_rate"])
    assert result == []


def test_collect_rejects_unknown_indicator_key():
    collector = EcosCollector(api_key="dummy-key")
    with pytest.raises(ValueError):
        collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 30), indicators=["not_a_real_key"])


def test_collect_parses_kospi_and_kosdaq_daily_rows():
    # 실제 ECOS 응답의 UNIT_NAME은 "1980.01.04=100" 같은 기준시점 설명이라(실사용 중 확인),
    # 리포트에 그대로 쓰면 값과 뒤섞여 깨져 보인다. 프리셋에 지정한 "pt"를 항상 써야 한다.
    rows = [
        {"ITEM_NAME1": "코스피", "TIME": "20260102", "DATA_VALUE": "2600.12", "UNIT_NAME": "1980.01.04=100"},
    ]
    collector = EcosCollector(api_key="dummy-key")
    with patch("src.collectors.ecos_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(rows)
        kospi = collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31), indicators=["kospi"])
        kosdaq = collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31), indicators=["kosdaq"])

    assert kospi[0].asset_class == "stock"
    assert kospi[0].indicator_code == "802Y001_0001000"
    assert kospi[0].unit == "pt"
    assert kosdaq[0].asset_class == "stock"
    assert kosdaq[0].indicator_code == "802Y001_0089000"
    assert kosdaq[0].unit == "pt"
    # 같은 stat_code(802Y001)를 공유하지만 indicator_code에 item_code1까지 포함해
    # DB 유니크 제약(indicator_code, date)에서 서로 충돌하지 않아야 한다
    called_urls = [c.args[0] for c in mock_get.call_args_list]
    assert called_urls[0].endswith("0001000")
    assert called_urls[1].endswith("0089000")


def test_collect_parses_usd_krw_daily_rows():
    rows = [{"ITEM_NAME1": "원/미국달러(매매기준율)", "TIME": "20260102", "DATA_VALUE": "1350.5", "UNIT_NAME": "원"}]
    collector = EcosCollector(api_key="dummy-key")
    with patch("src.collectors.ecos_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(rows)
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31), indicators=["usd_krw"])

    assert result[0].asset_class == "bond"
    assert result[0].indicator_code == "731Y001_0000001"
    assert result[0].value == 1350.5


def test_collect_builds_url_with_monthly_cycle_dates():
    collector = EcosCollector(api_key="dummy-key")
    with patch("src.collectors.ecos_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response([])
        collector.collect(datetime(2026, 1, 15), datetime(2026, 6, 20), indicators=["base_rate"])

    called_url = mock_get.call_args.args[0]
    assert "dummy-key" in called_url
    assert "722Y001" in called_url
    assert "/M/202601/202606/" in called_url
    assert called_url.endswith("0101000")
