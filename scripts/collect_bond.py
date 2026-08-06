"""
ECOS 채권 지표(기준금리 등) 수집 실행 스크립트.

사용법 (프로젝트 루트에서):
    python -m scripts.collect_bond --days 30
    python -m scripts.collect_bond --days 365 --indicators base_rate

사전 준비: .env 파일에 ECOS_API_KEY가 설정되어 있어야 한다.
(https://ecos.bok.or.kr 에서 회원가입 후 발급, 승인까지 다소 시간이 걸릴 수 있음)

--indicators 옵션 설명:
    콤마로 구분한 지표 키를 지정한다 (src/collectors/ecos_collector.py의
    INDICATOR_PRESETS 참고). 생략하면 등록된 전체 지표를 수집한다.
"""

import argparse
from datetime import datetime, timedelta

from src.collectors.ecos_collector import INDICATOR_PRESETS, EcosApiError, EcosCollector
from src.storage.db import ensure_schema_up_to_date, get_session
from src.storage.models import Base
from src.storage.save import save_bond_indicators


def _parse_indicators(raw: str | None) -> list[str] | None:
    if not raw:
        return None

    keys = [k.strip() for k in raw.split(",") if k.strip()]
    invalid = [k for k in keys if k not in INDICATOR_PRESETS]
    if invalid:
        valid_list = ", ".join(INDICATOR_PRESETS.keys())
        raise ValueError(f"알 수 없는 지표 키: {invalid}. 사용 가능한 키: {valid_list}")
    return keys


def run_collect_bond(days: int, indicators: list[str] | None = None) -> dict:
    """
    ECOS 채권 지표 수집의 핵심 로직. CLI(argparse)와 스케줄러 양쪽에서 재사용할 수
    있도록 인자를 명시적으로 받는 함수로 분리했다.

    Returns:
        {"collected": int, "saved": int, "updated": int} 형태의 실행 결과 요약
    """
    ensure_schema_up_to_date(Base)  # 테이블이 없으면 생성, 있으면 스키마 보강

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    target = indicators or list(INDICATOR_PRESETS.keys())

    print(f"[1/2] ECOS 지표 수집 중: {start_date.date()} ~ {end_date.date()} | 지표: {target}")

    collector = EcosCollector()
    try:
        raw_items = collector.collect(start_date, end_date, indicators=indicators)
    except EcosApiError as e:
        print(f"수집 실패: {e}")
        return {"collected": 0, "saved": 0, "updated": 0, "error": str(e)}

    print(f"      수집된 데이터 포인트: {len(raw_items)}")

    print("[2/2] DB 저장 중")
    session = get_session()
    try:
        saved, updated = save_bond_indicators(session, raw_items)
        skipped = len(raw_items) - saved - updated
        print(f"      새로 저장된 건수: {saved} / 갱신된 건수: {updated} / 변경 없음: {skipped}")
    finally:
        session.close()

    return {"collected": len(raw_items), "saved": saved, "updated": updated}


def main():
    parser = argparse.ArgumentParser(description="ECOS 채권 지표 수집 및 저장")
    parser.add_argument("--days", type=int, default=30, help="오늘로부터 며칠 전까지 조회할지 (기본 30일)")
    parser.add_argument(
        "--indicators",
        type=str,
        default=None,
        help=f"콤마로 구분한 지표 키. 생략 시 전체. 사용 가능한 키: {', '.join(INDICATOR_PRESETS.keys())}",
    )
    args = parser.parse_args()

    try:
        indicators = _parse_indicators(args.indicators)
    except ValueError as e:
        print(f"옵션 오류: {e}")
        return

    run_collect_bond(days=args.days, indicators=indicators)


if __name__ == "__main__":
    main()
