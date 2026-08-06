"""설정 모듈 기본 동작 확인용 테스트."""

from config.settings import Settings


def test_settings_defaults():
    s = Settings()
    assert s.database_url.startswith("sqlite:///") or s.database_url.startswith("postgresql://")
    assert s.log_level in ("DEBUG", "INFO", "WARNING", "ERROR")
