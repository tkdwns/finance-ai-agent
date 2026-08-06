"""normalizer.py의 한국어 형태소 분석 폴백 처리 테스트."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

import src.preprocessing.normalizer as normalizer_module


@pytest.fixture(autouse=True)
def _reset_okt_singleton():
    """테스트 간 _okt_instance 전역 캐시가 서로 영향을 주지 않도록 초기화한다."""
    normalizer_module._okt_instance = None
    yield
    normalizer_module._okt_instance = None


def test_get_okt_wraps_import_error_as_runtime_error():
    with patch.dict(sys.modules, {"konlpy": None, "konlpy.tag": None}):
        with pytest.raises(RuntimeError):
            normalizer_module._get_okt()


def test_get_okt_wraps_non_import_error_during_construction():
    """konlpy 패키지는 임포트되지만, JVM 문제 등으로 Okt() 생성 자체가 실패하는 경우
    (ImportError가 아닌 임의의 예외)도 RuntimeError로 일관되게 변환되어야 한다."""
    fake_konlpy_tag = MagicMock()
    fake_konlpy_tag.Okt.side_effect = OSError("JVM DLL을 찾을 수 없습니다")

    with patch.dict(sys.modules, {"konlpy.tag": fake_konlpy_tag}):
        with pytest.raises(RuntimeError, match="JVM DLL을 찾을 수 없습니다"):
            normalizer_module._get_okt()


def test_get_okt_caches_instance_after_success():
    fake_konlpy_tag = MagicMock()
    fake_instance = MagicMock()
    fake_konlpy_tag.Okt.return_value = fake_instance

    with patch.dict(sys.modules, {"konlpy.tag": fake_konlpy_tag}):
        first = normalizer_module._get_okt()
        second = normalizer_module._get_okt()

    assert first is fake_instance
    assert second is fake_instance
    fake_konlpy_tag.Okt.assert_called_once()  # 두 번째 호출은 캐시된 인스턴스를 반환해야 함


def test_get_okt_overrides_java_home_from_settings():
    """.env(config.settings.java_home)에 값이 있으면 시스템 환경변수보다 우선해야 한다
    (VSCode 등 IDE 터미널이 옛 시스템 환경변수를 들고 있는 문제를 피하기 위함)."""
    fake_konlpy_tag = MagicMock()
    fake_konlpy_tag.Okt.return_value = MagicMock()
    fake_settings = MagicMock(java_home="C:\\fake\\jdk-path")

    original_java_home = os.environ.get("JAVA_HOME")
    os.environ["JAVA_HOME"] = "C:\\old\\stale\\path"
    try:
        with patch.dict(sys.modules, {"konlpy.tag": fake_konlpy_tag}):
            with patch("config.settings.settings", fake_settings):
                normalizer_module._get_okt()
        assert os.environ["JAVA_HOME"] == "C:\\fake\\jdk-path"
    finally:
        if original_java_home is None:
            os.environ.pop("JAVA_HOME", None)
        else:
            os.environ["JAVA_HOME"] = original_java_home
