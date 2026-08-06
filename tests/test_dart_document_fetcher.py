"""DartDocumentFetcher 단위 테스트 (실제 API 호출 없이 requests.get을 모킹)."""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.dart_document_fetcher import DartDocumentError, DartDocumentFetcher


def _make_zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _mock_zip_response(zip_bytes: bytes):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"Content-Type": "application/zip"}
    resp.content = zip_bytes
    return resp


def _mock_error_response(message="등록되지 않은 키입니다"):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"Content-Type": "application/json;charset=UTF-8"}
    resp.json.return_value = {"status": "010", "message": message}
    return resp


def test_fetch_text_raises_when_api_key_missing():
    fetcher = DartDocumentFetcher(api_key="")
    with pytest.raises(DartDocumentError):
        fetcher.fetch_text("r1")


def test_fetch_text_extracts_and_cleans_xml_text():
    xml_content = "<DOCUMENT><TITLE>분기보고서</TITLE><BODY>매출액이   전년 대비 \n\n 증가했다.</BODY></DOCUMENT>"
    zip_bytes = _make_zip_bytes({"body.xml": xml_content.encode("utf-8")})

    fetcher = DartDocumentFetcher(api_key="dummy-key")
    with patch("src.collectors.dart_document_fetcher.requests.get") as mock_get:
        mock_get.return_value = _mock_zip_response(zip_bytes)
        result = fetcher.fetch_text("r1")

    assert "<" not in result
    assert "분기보고서" in result
    assert "매출액이 전년 대비 증가했다." in result


def test_fetch_text_truncates_to_max_length():
    long_text = "가" * 5000
    xml_content = f"<BODY>{long_text}</BODY>"
    zip_bytes = _make_zip_bytes({"body.xml": xml_content.encode("utf-8")})

    fetcher = DartDocumentFetcher(api_key="dummy-key")
    with patch("src.collectors.dart_document_fetcher.requests.get") as mock_get:
        mock_get.return_value = _mock_zip_response(zip_bytes)
        result = fetcher.fetch_text("r1", max_length=100)

    assert len(result) == 100


def test_fetch_text_handles_cp949_encoded_content():
    xml_content = "<BODY>한글 인코딩 테스트</BODY>"
    zip_bytes = _make_zip_bytes({"body.xml": xml_content.encode("cp949")})

    fetcher = DartDocumentFetcher(api_key="dummy-key")
    with patch("src.collectors.dart_document_fetcher.requests.get") as mock_get:
        mock_get.return_value = _mock_zip_response(zip_bytes)
        result = fetcher.fetch_text("r1")

    assert "한글 인코딩 테스트" in result


def test_fetch_text_raises_on_error_json_response():
    fetcher = DartDocumentFetcher(api_key="dummy-key")
    with patch("src.collectors.dart_document_fetcher.requests.get") as mock_get:
        mock_get.return_value = _mock_error_response()
        with pytest.raises(DartDocumentError):
            fetcher.fetch_text("r1")


def test_fetch_text_raises_on_invalid_zip():
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"Content-Type": "application/zip"}
    resp.content = b"not a zip file"

    fetcher = DartDocumentFetcher(api_key="dummy-key")
    with patch("src.collectors.dart_document_fetcher.requests.get", return_value=resp):
        with pytest.raises(DartDocumentError):
            fetcher.fetch_text("r1")
