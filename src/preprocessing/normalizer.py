"""
텍스트 정규화 모듈.

HTML 태그 제거, 공백/특수문자 정리, 한국어 형태소 분석(토큰화)을 담당한다.
"""

import os
import re

from bs4 import BeautifulSoup

_WHITESPACE_RE = re.compile(r"\s+")
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")

_okt_instance = None


def strip_html(text: str) -> str:
    """HTML 태그를 제거하고 순수 텍스트만 남긴다."""
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(separator=" ")


def normalize_whitespace(text: str) -> str:
    """제로폭 문자를 제거하고, 연속 공백/개행을 단일 공백으로 정리한다."""
    if not text:
        return ""
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_text(text: str) -> str:
    """HTML 제거 + 공백 정규화를 함께 수행하는 표준 진입점."""
    return normalize_whitespace(strip_html(text))


def _get_okt():
    """konlpy의 Okt 인스턴스를 지연 생성한다 (JVM 구동 비용이 크므로 1회만 생성).

    konlpy 패키지 자체는 설치돼 있어도 JDK/JAVA_HOME이 제대로 설정되지 않으면
    Okt() 생성 시점에 JVM 관련 예외(ImportError가 아닌 다양한 형태)가 날 수 있다.
    어떤 예외든 일관되게 RuntimeError로 감싸서, 호출부(tokenize_korean_nouns의
    사용처)가 예외 타입을 신경 쓰지 않고 안전하게 폴백할 수 있도록 한다.

    JAVA_HOME은 .env(config.settings.java_home)에 값이 있으면 그걸로 시스템
    환경변수를 덮어쓴다. VSCode 같은 IDE 터미널은 프로그램을 재시작하기 전까지
    옛 시스템 환경변수를 그대로 들고 있는 경우가 많아, 프로젝트 차원에서
    .env 값을 우선시켜 터미널/IDE 종류와 무관하게 동일하게 동작하도록 한다.
    """
    global _okt_instance
    if _okt_instance is None:
        from config.settings import settings

        if settings.java_home:
            os.environ["JAVA_HOME"] = settings.java_home

        try:
            from konlpy.tag import Okt

            _okt_instance = Okt()
        except Exception as e:
            raise RuntimeError(
                "konlpy를 사용할 수 없습니다 (패키지 미설치 또는 JDK/JVM 설정 문제). "
                "README의 '한국어 형태소 분석 설정'을 참고해 JDK를 설치하세요. "
                f"원본 오류: {type(e).__name__}: {e}"
            ) from e
    return _okt_instance


def tokenize_korean_nouns(text: str) -> list[str]:
    """한국어 텍스트에서 명사만 추출한다 (키워드 추출 단계의 전처리 입력으로 사용)."""
    if not text:
        return []
    return _get_okt().nouns(text)
