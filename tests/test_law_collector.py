"""LawCollector 단위 테스트 (실제 API 호출 없이 requests.get을 모킹)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.law_collector import LawApiError, LawCollector


def _law_xml(
    eff_date="20260615", pub_date="20260601", org="금융위원회", gubun="일부개정",
    law_name_hangul="자본시장과 금융투자업에 관한 법률",
) -> str:
    return f"""
    <LawSearch>
        <law>
            <법령명한글>{law_name_hangul}</법령명한글>
            <제개정구분명>{gubun}</제개정구분명>
            <소관부처명>{org}</소관부처명>
            <공포일자>{pub_date}</공포일자>
            <시행일자>{eff_date}</시행일자>
            <법령상세링크>/DRF/lawService.do?OC=test&amp;target=law&amp;MST=1234</법령상세링크>
        </law>
    </LawSearch>
    """


def _mock_response(xml_text: str):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = xml_text
    return resp


def test_collect_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setattr("src.collectors.law_collector.settings.law_api_key", "")
    collector = LawCollector(api_key="")
    with pytest.raises(LawApiError):
        collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30))


def test_collect_parses_item_within_date_range():
    collector = LawCollector(api_key="dummy-key")
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_law_xml())
        result = collector.collect(
            datetime(2026, 6, 1), datetime(2026, 6, 30), laws=["자본시장과 금융투자업에 관한 법률"]
        )

    assert len(result) == 1
    item = result[0]
    assert item.asset_class == "law"
    assert "자본시장과 금융투자업에 관한 법률" in item.title
    assert item.published_at == datetime(2026, 6, 15)
    assert item.url == "https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&MST=1234"
    assert item.raw_meta["law_name"] == "자본시장과 금융투자업에 관한 법률"


def test_collect_filters_out_amendments_outside_date_range():
    collector = LawCollector(api_key="dummy-key")
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_law_xml(eff_date="20250101", pub_date="20250101"))
        result = collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30), laws=["은행법"])

    assert result == []


def test_collect_raises_on_error_response():
    collector = LawCollector(api_key="dummy-key")
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response("<OpenAPI_Error><msg>인증 실패</msg></OpenAPI_Error>")
        with pytest.raises(LawApiError):
            collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30), laws=["은행법"])


def test_collect_uses_actual_returned_law_name_in_title():
    """"은행법"으로 검색해도 은행법 시행령/시행규칙 등 연관 법령이 함께 반환될 수 있으므로,
    제목은 검색어가 아니라 응답의 실제 법령명한글 필드를 써야 한다."""
    collector = LawCollector(api_key="dummy-key")
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_law_xml(law_name_hangul="은행법 시행령"))
        result = collector.collect(datetime(2026, 6, 1), datetime(2026, 6, 30), laws=["은행법"])

    assert len(result) == 1
    assert result[0].title.startswith("은행법 시행령")
    # 자산군 매핑에 쓰이는 raw_meta는 검색어(대상 법령) 기준을 유지해야 한다.
    assert result[0].raw_meta["law_name"] == "은행법"


def test_collect_queries_each_target_law_separately():
    collector = LawCollector(api_key="dummy-key")
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.return_value = _mock_response(_law_xml(eff_date="20250101", pub_date="20250101"))
        collector.collect(
            datetime(2026, 6, 1), datetime(2026, 6, 30),
            laws=["자본시장과 금융투자업에 관한 법률", "은행법", "금융소비자 보호에 관한 법률"],
        )

    assert mock_get.call_count == 3


def _html_response(html_text: str):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = html_text
    return resp


def _wrapper_html(lsi_seq="1234", chr_cls_cd="010202") -> str:
    """법령상세링크가 실제로 반환하는 iframe 래퍼 페이지를 흉내낸다.

    실제 개정이유 본문은 이 페이지가 아니라, 여기 담긴 lsiSeq/chrClsCd로 다시 요청하는
    lsRvsDocInfoR.do 페이지에만 있다(law_collector.py 모듈 docstring 참고)."""
    return (
        f'<html><body><iframe src="https://www.law.go.kr/LSW/lsInfoP.do?'
        f'lsiSeq={lsi_seq}&chrClsCd={chr_cls_cd}&urlMode=lsInfoP"></iframe></body></html>'
    )


def test_fetch_reason_excerpt_extracts_text_after_heading():
    collector = LawCollector(api_key="dummy-key")
    reason_html = (
        "<html><body><h3>제·개정이유</h3><p>" + "금융소비자 보호를 강화하기 위해 개정함. " * 5 + "</p></body></html>"
    )
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.side_effect = [_html_response(_wrapper_html()), _html_response(reason_html)]
        excerpt = collector._fetch_reason_excerpt("https://www.law.go.kr/dummy")

    assert excerpt is not None
    assert "금융소비자 보호를 강화" in excerpt
    assert mock_get.call_count == 2
    second_call_url = mock_get.call_args_list[1].args[0]
    assert "lsRvsDocInfoR.do" in second_call_url
    assert "lsiSeq=1234" in second_call_url
    assert "chrClsCd=010202" in second_call_url


def test_fetch_reason_excerpt_returns_none_when_heading_missing():
    collector = LawCollector(api_key="dummy-key")
    reason_html = "<html><body><p>관련 없는 내용의 페이지입니다.</p></body></html>"
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.side_effect = [_html_response(_wrapper_html()), _html_response(reason_html)]
        assert collector._fetch_reason_excerpt("https://www.law.go.kr/dummy") is None


def test_fetch_reason_excerpt_returns_none_when_wrapper_has_no_iframe():
    # 래퍼 페이지 구조가 예상과 다르면(사이트 개편 등) 두 번째 요청을 시도하지 않고 None
    collector = LawCollector(api_key="dummy-key")
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.return_value = _html_response("<html><body>예상과 다른 페이지</body></html>")
        assert collector._fetch_reason_excerpt("https://www.law.go.kr/dummy") is None
    assert mock_get.call_count == 1


def test_fetch_reason_excerpt_returns_none_on_request_failure():
    import requests

    collector = LawCollector(api_key="dummy-key")
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.side_effect = requests.RequestException("연결 실패")
        assert collector._fetch_reason_excerpt("https://www.law.go.kr/dummy") is None


def test_collect_includes_reason_excerpt_in_raw_meta_when_found():
    collector = LawCollector(api_key="dummy-key")
    reason_html = "<html><body><h3>개정이유</h3><p>" + "자본시장 투명성 제고를 위한 개정. " * 5 + "</p></body></html>"
    with patch("src.collectors.law_collector.requests.get") as mock_get:
        mock_get.side_effect = [
            _mock_response(_law_xml()),
            _html_response(_wrapper_html()),
            _html_response(reason_html),
        ]
        result = collector.collect(
            datetime(2026, 6, 1), datetime(2026, 6, 30), laws=["자본시장과 금융투자업에 관한 법률"]
        )

    assert len(result) == 1
    assert "자본시장 투명성 제고" in result[0].raw_meta["reason_text"]
