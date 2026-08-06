"""FredCollector 단위 테스트 (실제 API 호출 없이 requests.get을 모킹)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.fred_collector import FredApiError, FredCollector


def _mock_response(observations=None, error_message=None):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    if error_message is not None:
        resp.json.return_value = {"error_message": error_message}
    else:
        resp.json.return_value = {"observations": observations or []}
    return resp


def test_collect_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr("src.collectors.fred_collector.settings.fred_api_key", "")
    collector = FredCollector(api_key="")
    with pytest.raises(FredApiError):
        collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 1))


def test_collect_raises_on_error_message():
    collector = FredCollector(api_key="dummy-key")
    with patch("src.collectors.fred_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(error_message="Bad Request")
        with pytest.raises(FredApiError):
            collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 1), indicators=["nasdaq"])


def test_collect_parses_observations_for_nasdaq():
    observations = [
        {"date": "2026-01-02", "value": "15000.5"},
        {"date": "2026-06-01", "value": "16000.0"},
    ]
    collector = FredCollector(api_key="dummy-key")
    with patch("src.collectors.fred_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(observations)
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 30), indicators=["nasdaq"])

    assert len(result) == 2
    assert result[0].asset_class == "stock"
    assert result[0].indicator_code == "NASDAQCOM"
    assert result[0].indicator_name == "나스닥종합지수"
    assert result[0].date == datetime(2026, 1, 2)
    assert result[0].value == 15000.5
    assert result[0].unit == "pt"


def test_collect_skips_dot_values_for_holidays():
    observations = [
        {"date": "2026-01-01", "value": "."},
        {"date": "2026-01-02", "value": "15000.5"},
    ]
    collector = FredCollector(api_key="dummy-key")
    with patch("src.collectors.fred_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(observations)
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31), indicators=["nasdaq"])

    assert len(result) == 1
    assert result[0].date == datetime(2026, 1, 2)


def test_collect_rejects_unknown_indicator_key():
    collector = FredCollector(api_key="dummy-key")
    with pytest.raises(ValueError):
        collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 30), indicators=["not_a_real_key"])


def test_collect_defaults_to_all_presets_when_unspecified():
    collector = FredCollector(api_key="dummy-key")
    with patch("src.collectors.fred_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response([])
        collector.collect(datetime(2026, 1, 1), datetime(2026, 6, 30))

    called_series_ids = {call.kwargs["params"]["series_id"] for call in mock_get.call_args_list}
    assert called_series_ids == {"NASDAQCOM", "SP500"}
