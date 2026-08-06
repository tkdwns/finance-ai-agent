"""
프로젝트 전역 설정 모듈.

.env 파일의 값을 읽어와 Settings 객체로 제공한다.
다른 모듈에서는 아래와 같이 사용한다:

    from config.settings import settings
    print(settings.dart_api_key)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트 기준으로 .env 로드
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    # --- LLM ---
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    # "anthropic", "openai", 또는 "gemini" (무료) 중 선택.
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini"))
    # 소유자 인증용 핀코드 (기본값: 1234)
    admin_pin_code: str = field(default_factory=lambda: os.getenv("ADMIN_PIN_CODE", "1234"))

    # --- 금융 데이터 API ---
    dart_api_key: str = field(default_factory=lambda: os.getenv("DART_API_KEY", ""))
    ecos_api_key: str = field(default_factory=lambda: os.getenv("ECOS_API_KEY", ""))
    molit_api_key: str = field(default_factory=lambda: os.getenv("MOLIT_API_KEY", ""))
    law_api_key: str = field(default_factory=lambda: os.getenv("LAW_API_KEY", ""))
    # 나스닥/S&P500 등 해외 지수용 (세인트루이스 연방준비은행 FRED Open API)
    fred_api_key: str = field(default_factory=lambda: os.getenv("FRED_API_KEY", ""))

    # --- 뉴스 RSS 피드 ---
    # 콤마로 구분한 RSS 피드 URL 목록. 어떤 언론사/카테고리를 쓸지는 각자 선정해야 한다
    # (크롤링 대상 사이트의 robots.txt·이용약관을 먼저 확인할 것 — PROJECT_GUIDELINE.md
    # 4장 법적·윤리적 체크리스트 참고). 비워두면 NewsCollector가 아무것도 수집하지 않는다.
    news_rss_urls: list[str] = field(
        default_factory=lambda: [
            url.strip() for url in os.getenv("NEWS_RSS_URLS", "").split(",") if url.strip()
        ]
    )

    # --- 부동산 실거래가 대상 지역 ---
    # 콤마로 구분한 법정동코드(5자리, LAWD_CD) 목록. 관심 지역을 직접 골라 넣는다.
    # 코드는 행정표준코드관리시스템(code.go.kr) 또는 공공데이터포털 API 문서에서 확인 가능.
    # 비워두면 real_estate_collector.py의 기본 프리셋(REGION_PRESETS)을 사용한다.
    real_estate_regions: list[str] = field(
        default_factory=lambda: [
            code.strip() for code in os.getenv("REAL_ESTATE_REGIONS", "").split(",") if code.strip()
        ]
    )

    # --- 한국어 형태소 분석 (konlpy/JVM) ---
    # 시스템 환경변수 JAVA_HOME이 터미널/IDE마다 다르게(또는 늦게) 반영되는 문제를
    # 피하기 위해, 프로젝트 차원에서 .env로 직접 지정할 수 있게 한다.
    # 비워두면 시스템 JAVA_HOME을 그대로 사용한다.
    java_home: str = field(default_factory=lambda: os.getenv("JAVA_HOME", ""))

    # --- 데이터베이스 ---
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/financial_agent.db")
    )

    # --- 배포: 이메일 자동발송 (선택) ---
    # SMTP_HOST가 비어있으면 이메일 발송 기능은 조용히 비활성 상태로 남는다(스케줄러 파이프라인이
    # 이 값으로 발송 여부를 판단 — src/scheduler/jobs.py 참고).
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    # 비워두면 SMTP_USER를 발신자로 사용한다.
    report_email_from: str = field(default_factory=lambda: os.getenv("REPORT_EMAIL_FROM", ""))
    # 콤마로 구분한 수신자 목록.
    report_email_to: list[str] = field(
        default_factory=lambda: [
            addr.strip() for addr in os.getenv("REPORT_EMAIL_TO", "").split(",") if addr.strip()
        ]
    )

    # --- 애플리케이션 ---
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    # --- 경로 ---
    base_dir: Path = BASE_DIR
    data_raw_dir: Path = BASE_DIR / "data" / "raw"
    data_processed_dir: Path = BASE_DIR / "data" / "processed"
    reports_output_dir: Path = BASE_DIR / "reports_output"

    def validate(self) -> list[str]:
        """필수 API 키가 비어있는지 확인하고, 누락된 항목 이름 목록을 반환한다.

        LLM 키는 llm_provider 설정에 따라 anthropic 또는 openai 중 하나만 있으면 된다.
        """
        missing = []
        required = {"DART_API_KEY": self.dart_api_key}
        for name, value in required.items():
            if not value:
                missing.append(name)

        if self.llm_provider == "gemini":
            llm_key = self.gemini_api_key
            llm_name = "GEMINI_API_KEY"
        elif self.llm_provider == "openai":
            llm_key = self.openai_api_key
            llm_name = "OPENAI_API_KEY"
        else:
            llm_key = self.anthropic_api_key
            llm_name = "ANTHROPIC_API_KEY"

        if not llm_key:
            missing.append(llm_name)

        return missing


settings = Settings()


if __name__ == "__main__":
    missing = settings.validate()
    if missing:
        print(f"[경고] 다음 환경변수가 설정되지 않았습니다: {', '.join(missing)}")
        print(".env 파일을 확인하세요 (.env.example 참고).")
    else:
        print("모든 필수 환경변수가 설정되었습니다.")
