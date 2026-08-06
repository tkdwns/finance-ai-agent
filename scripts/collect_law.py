"""
법제처(국가법령정보센터) 법령 개정 이력 수집 실행 스크립트.

사용법 (프로젝트 루트에서):
    python -m scripts.collect_law --days 30

사전 준비: .env 파일에 LAW_API_KEY(OC 인증키)가 설정되어 있어야 한다.
(https://open.law.go.kr 에서 회원가입 후 "Open API 사용 신청"으로 발급)

주의: 이 API의 법령 목록 조회는 보통 "현재 시행중인 버전" 1건만 반환하므로,
이 수집기는 과거 개정 이력 전체가 아니라 "가장 최근 개정이 지정 기간 안에
있었는지"만 감지한다 (자세한 내용은 law_collector.py 상단 주석 참고).
"""

import argparse
from datetime import datetime, timedelta

from src.collectors.law_collector import TARGET_LAWS, LawApiError, LawCollector
from src.storage.db import ensure_schema_up_to_date, get_session
from src.storage.models import Base
from src.storage.save import save_law_amendments


def run_collect_law(days: int) -> dict:
    """
    법령 개정 이력 수집의 핵심 로직. CLI(argparse)와 스케줄러 양쪽에서 재사용할 수
    있도록 인자를 명시적으로 받는 함수로 분리했다.

    Returns:
        {"collected": int, "saved": int, "skipped": int} 형태의 실행 결과 요약
    """
    ensure_schema_up_to_date(Base)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"[1/2] 법령 개정 이력 수집 중: {start_date.date()} ~ {end_date.date()} | 대상: {TARGET_LAWS}")

    collector = LawCollector()
    try:
        raw_items = collector.collect(start_date, end_date)
    except LawApiError as e:
        print(f"수집 실패: {e}")
        return {"collected": 0, "saved": 0, "skipped": 0, "error": str(e)}

    print(f"      수집된 개정 건수: {len(raw_items)}")

    print("[2/2] DB 저장 중")
    session = get_session()
    try:
        saved, skipped = save_law_amendments(session, raw_items)
        print(f"      새로 저장된 건수: {saved} / 중복으로 건너뜀: {skipped}")
    finally:
        session.close()

    return {"collected": len(raw_items), "saved": saved, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(description="법령 개정 이력 수집 및 저장")
    parser.add_argument("--days", type=int, default=30, help="오늘로부터 며칠 전까지 조회할지 (기본 30일)")
    args = parser.parse_args()

    run_collect_law(days=args.days)


if __name__ == "__main__":
    main()
