"""
DART 공시 원문 조회 모듈.

공시 목록 API(list.json)는 제목만 제공하고 본문은 주지 않는다.
실제 공시 원문은 document.xml API로 접수번호(rcept_no)마다 별도 요청해야 하며,
응답은 ZIP으로 압축된 XML(페이지별) 파일들이다. 이 모듈은 그 ZIP을 받아
텍스트만 추출하고 정제한다.

주의:
- 공시 원문은 상장기업이 법적 의무에 따라 제출하는 공식 문서이지만, 이 프로젝트는
  저장 원칙(원문 전체 저장 금지)을 일관되게 지키기 위해 추출한 텍스트를 일정
  길이로 잘라 "요약"으로만 저장한다. 전체 원문은 이미 저장된 DART 뷰어 링크(url)로
  언제든 확인할 수 있다.
"""

import io
import re
import zipfile

import requests

from config.settings import settings

_XML_TAG_RE = re.compile(r"<[^>]+>")
_MAX_SUMMARY_LENGTH = 3000


class DartDocumentError(RuntimeError):
    """공시 원문을 가져오거나 파싱하는 데 실패했을 때 발생시키는 예외."""


class DartDocumentFetcher:
    def __init__(self, api_key: str | None = None, timeout: int = 15):
        self.api_key = api_key or settings.dart_api_key
        self.base_url = "https://opendart.fss.or.kr/api/document.xml"
        self.timeout = timeout

    def fetch_text(self, rcept_no: str, max_length: int = _MAX_SUMMARY_LENGTH) -> str:
        """
        접수번호(rcept_no)에 해당하는 공시 원문을 받아 텍스트만 추출한다.
        결과는 max_length 길이로 잘라서 반환한다 (원문 전체 저장 금지 원칙).
        """
        if not self.api_key:
            raise DartDocumentError("DART_API_KEY가 설정되지 않았습니다.")

        content = self._download_zip(rcept_no)
        text = self._extract_text_from_zip(content)
        text = self._clean(text)
        return text[:max_length]

    def _download_zip(self, rcept_no: str) -> bytes:
        params = {"crtfc_key": self.api_key, "rcept_no": rcept_no}
        response = requests.get(self.base_url, params=params, timeout=self.timeout)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            # 정상 응답은 zip이지만, 에러 시에는 json으로 status/message가 온다.
            payload = response.json()
            raise DartDocumentError(
                f"공시 원문 요청 실패 (rcept_no={rcept_no}): {payload.get('message', payload)}"
            )
        return response.content

    def _extract_text_from_zip(self, content: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                texts = [self._decode(zf.read(name)) for name in zf.namelist()]
                return "\n".join(texts)
        except zipfile.BadZipFile as e:
            raise DartDocumentError("공시 원문 응답이 올바른 ZIP 형식이 아닙니다.") from e

    @staticmethod
    def _decode(raw: bytes) -> str:
        for encoding in ("utf-8", "cp949", "euc-kr"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")

    @staticmethod
    def _clean(text: str) -> str:
        text = _XML_TAG_RE.sub(" ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
