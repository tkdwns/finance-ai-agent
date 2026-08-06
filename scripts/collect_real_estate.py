"""
MOLIT(국토교통부) 아파트 매매 실거래가 수집 실행 스크립트.

사용법 (프로젝트 루트에서):
    python -m scripts.collect_real_estate --days 30
    python -m scripts.collect_real_estate --days 30 --regions seoul_gangnam,seoul_songpa
    python -m scripts.collect_real_estate --days 30 --regions 11680,41135   # 법정동코드 직접 지정

사전 준비:
    .env 파일에 MOLIT_API_KEY가 설정되어 있어야 한다 (공공데이터포털에서 발급).
    REAL_ESTATE_REGIONS에 관심 지역의 법정동코드(5자리)를 미리 넣어두면 --regions
    생략 시 그 값을 기본으로 사용한다.

--regions 옵션 설명:
    콤마로 구분한 값. src/collectors/real_estate_collector.py의 REGION_PRESETS에 있는
    프리셋 이름(예: seoul_gangnam) 또는 법정동코드(5자리) 숫자를 섞어서 쓸 수 있다.
    생략하면 .env의 REAL_ESTATE_REGIONS, 그것도 없으면 REGION_PRESETS 전체를 사용한다.

주의:
    이 API는 "지역 1곳 x 연월 1개"당 한 번씩 호출해야 하고 일일 호출 한도가 낮은
    편이다(기본 1,000건/일). 지역·기간을 너무 넓게 잡으면 호출 수가 급격히 늘어난다.
"""

import argparse
from datetime import datetime, timedelta

from src.collectors.real_estate_collector import REGION_PRESETS, MolitApiError, MolitCollector
from src.storage.db import ensure_schema_up_to_date, get_session
from src.storage.models import Base
from src.storage.save import save_real_estate_transactions


def _parse_regions(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [REGION_PRESETS.get(token.strip(), token.strip()) for token in raw.split(",") if token.strip()]


def run_collect_real_estate(days: int, regions: list[str] | None = None) -> dict:
    """
    MOLIT 실거래가 수집의 핵심 로직. CLI(argparse)와 스케줄러 양쪽에서 재사용할 수
    있도록 인자를 명시적으로 받는 함수로 분리했다.

    Returns:
        {"collected": int, "saved": int, "skipped": int} 형태의 실행 결과 요약
    """
    ensure_schema_up_to_date(Base)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"[1/2] MOLIT 실거래가 수집 중: {start_date.date()} ~ {end_date.date()} | 지역: {regions or '기본값'}")

    collector = MolitCollector()
    try:
        raw_items = collector.collect(start_date, end_date, region_codes=regions)
    except MolitApiError as e:
        print(f"수집 실패: {e}")
        return {"collected": 0, "saved": 0, "skipped": 0, "error": str(e)}

    print(f"      수집된 거래 건수: {len(raw_items)}")

    print("[2/2] DB 저장 중")
    session = get_session()
    try:
        saved, skipped = save_real_estate_transactions(session, raw_items)
        print(f"      새로 저장된 건수: {saved} / 중복으로 건너뜀: {skipped}")
    finally:
        session.close()

    return {"collected": len(raw_items), "saved": saved, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(description="MOLIT 아파트 매매 실거래가 수집 및 저장")
    parser.add_argument("--days", type=int, default=30, help="오늘로부터 며칠 전까지 조회할지 (기본 30일)")
    parser.add_argument(
        "--regions",
        type=str,
        default=None,
        help=f"콤마로 구분한 프리셋 이름 또는 법정동코드. 생략 시 .env(REAL_ESTATE_REGIONS) 또는 "
        f"기본 프리셋 사용. 등록된 프리셋: {', '.join(REGION_PRESETS.keys())}",
    )
    args = parser.parse_args()

    regions = _parse_regions(args.regions)
    run_collect_real_estate(days=args.days, regions=regions)


if __name__ == "__main__":
    main()
