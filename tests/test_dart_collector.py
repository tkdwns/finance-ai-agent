"""DartCollector 단위 테스트 (실제 API 호출 없이 requests.get을 모킹)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.dart_collector import DartApiError, DartCollector


def _mock_response(status, list_data=None, total_page=1):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "status": status,
        "message": "정상" if status == "000" else "오류",
        "list": list_data or [],
        "total_page": total_page,
    }
    return resp


def test_collect_raises_when_api_key_missing():
    collector = DartCollector(api_key="")
    with pytest.raises(DartApiError):
        collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31))


def test_collect_returns_empty_list_when_no_data():
    collector = DartCollector(api_key="dummy-key")
    with patch("src.collectors.dart_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response("013")
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31))
    assert result == []


def test_collect_raises_on_error_status():
    collector = DartCollector(api_key="dummy-key")
    with patch("src.collectors.dart_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response("010")  # 등록되지 않은 키
        with pytest.raises(DartApiError):
            collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31))


def test_collect_parses_single_page_response():
    sample_entry = {
        "corp_name": "삼성전자",
        "corp_code": "00126380",
        "rcept_no": "20260120000123",
        "report_nm": "분기보고서 (2025.12)",
        "rcept_dt": "20260120",
    }
    collector = DartCollector(api_key="dummy-key")
    with patch("src.collectors.dart_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response("000", [sample_entry], total_page=1)
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31))

    assert len(result) == 1
    item = result[0]
    assert item.asset_class == "stock"
    assert item.title == "분기보고서 (2025.12)"
    assert item.published_at == datetime(2026, 1, 20)
    assert item.raw_meta["corp_name"] == "삼성전자"
    assert item.raw_meta["rcept_no"] == "20260120000123"
    assert "20260120000123" in item.url


def test_collect_paginates_across_multiple_pages():
    page1 = {"corp_name": "A사", "corp_code": "001", "rcept_no": "r1", "report_nm": "공시1", "rcept_dt": "20260101"}
    page2 = {"corp_name": "B사", "corp_code": "002", "rcept_no": "r2", "report_nm": "공시2", "rcept_dt": "20260102"}

    collector = DartCollector(api_key="dummy-key")
    responses = [
        _mock_response("000", [page1], total_page=2),
        _mock_response("000", [page2], total_page=2),
    ]
    with patch("src.collectors.dart_collector.requests.get", side_effect=responses):
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31))

    assert len(result) == 2
    assert {r.raw_meta["rcept_no"] for r in result} == {"r1", "r2"}


def test_collect_skips_entries_with_invalid_date():
    bad_entry = {"corp_name": "C사", "corp_code": "003", "rcept_no": "r3", "report_nm": "공시3", "rcept_dt": "invalid"}
    collector = DartCollector(api_key="dummy-key")
    with patch("src.collectors.dart_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response("000", [bad_entry], total_page=1)
        result = collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31))
    assert result == []


def test_collect_passes_pblntf_ty_param_when_provided():
    collector = DartCollector(api_key="dummy-key")
    with patch("src.collectors.dart_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response("000", [], total_page=1)
        collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31), pblntf_ty="B")

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["pblntf_ty"] == "B"


def test_collect_omits_pblntf_ty_param_when_not_provided():
    collector = DartCollector(api_key="dummy-key")
    with patch("src.collectors.dart_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response("000", [], total_page=1)
        collector.collect(datetime(2026, 1, 1), datetime(2026, 1, 31))

    called_params = mock_get.call_args.kwargs["params"]
    assert "pblntf_ty" not in called_params


def test_collect_by_types_merges_and_dedupes_across_types():
    entry_a = {"corp_name": "A사", "corp_code": "001", "rcept_no": "r1", "report_nm": "사업보고서", "rcept_dt": "20260101"}
    entry_b = {"corp_name": "B사", "corp_code": "002", "rcept_no": "r2", "report_nm": "주요사항보고서", "rcept_dt": "20260102"}

    collector = DartCollector(api_key="dummy-key")
    responses = [
        _mock_response("000", [entry_a], total_page=1),  # type A
        _mock_response("000", [entry_b], total_page=1),  # type B
    ]
    with patch("src.collectors.dart_collector.requests.get", side_effect=responses) as mock_get:
        result = collector.collect_by_types(
            datetime(2026, 1, 1), datetime(2026, 1, 31), pblntf_types=["A", "B"]
        )

    assert len(result) == 2
    assert {r.raw_meta["rcept_no"] for r in result} == {"r1", "r2"}
    # 유형별로 한 번씩 총 2번 호출됐는지 확인
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0].kwargs["params"]["pblntf_ty"] == "A"
    assert mock_get.call_args_list[1].kwargs["params"]["pblntf_ty"] == "B"


def test_collect_by_types_deduplicates_same_rcept_no_across_types():
    """같은 공시가 여러 유형에 걸쳐 중복으로 잡혀도 한 번만 남아야 한다."""
    entry = {"corp_name": "A사", "corp_code": "001", "rcept_no": "r1", "report_nm": "사업보고서", "rcept_dt": "20260101"}

    collector = DartCollector(api_key="dummy-key")
    responses = [
        _mock_response("000", [entry], total_page=1),
        _mock_response("000", [entry], total_page=1),
    ]
    with patch("src.collectors.dart_collector.requests.get", side_effect=responses):
        result = collector.collect_by_types(
            datetime(2026, 1, 1), datetime(2026, 1, 31), pblntf_types=["A", "B"]
        )

    assert len(result) == 1
