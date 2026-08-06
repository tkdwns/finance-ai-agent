"""
뉴스 RSS 수집 실행 스크립트.

사용법 (프로젝트 루트에서):
    python -m scripts.collect_news --days 7

사전 준비: .env 파일의 NEWS_RSS_URLS에 RSS 피드 URL을 콤마로 구분해 채워 넣어야 한다.
어떤 언론사/카테고리를 쓸지는 직접 선정해야 하며, 크롤링 대상 사이트의 robots.txt와
이용약관을 사전에 확인할 것 (docs/PROJECT_GUIDELINE.md 4장 법적·윤리적 체크리스트 참고).

이 스크립트는 주식/채권 뉴스를 함께 수집한다. RSS 피드 자체에는 자산군 구분이 없고,
전처리 단계(src/preprocessing/tagger.py)가 기사 제목/요약의 키워드를 보고 자동으로
stock/bond/real_estate/crypto 중 하나로 분류한다. stock/bond로 분류된 기사만 현재
저장 대상이며(save.py 참고), 나머지는 건수만 집계되고 저장되지 않는다.
"""

import argparse
from datetime import datetime, timedelta

from src.collectors.news_collector import NewsCollector
from src.preprocessing.pipeline import preprocess
from src.storage.db import ensure_schema_up_to_date, get_session
from src.storage.models import Base
from src.storage.save import save_news_items


def run_collect_news(days: int) -> dict:
    """
    뉴스 RSS 수집의 핵심 로직. CLI(argparse)와 스케줄러 양쪽에서 재사용할 수 있도록
    인자를 명시적으로 받는 함수로 분리했다.

    Returns:
        {"collected": int, "stock": int, "bond": int,
         "skipped_duplicate": int, "skipped_unmapped": int} 형태의 실행 결과 요약
    """
    ensure_schema_up_to_date(Base)

    collector = NewsCollector()
    if not collector.rss_urls:
        print("[알림] NEWS_RSS_URLS가 비어 있어 뉴스 수집을 건너뜁니다. .env를 확인하세요.")
        return {"collected": 0, "stock": 0, "bond": 0, "skipped_duplicate": 0, "skipped_unmapped": 0}

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    print(f"[1/3] 뉴스 RSS 수집 중: {start_date.date()} ~ {end_date.date()} | 피드 {len(collector.rss_urls)}개")
    raw_items = collector.collect(start_date, end_date)
    print(f"      수집된 기사 건수: {len(raw_items)}")

    print("[2/3] 전처리 중 (정규화 + 자산군 태깅 + 제목/URL 유사도 기준 중복 제거)")
    cleaned_items = preprocess(raw_items)
    removed = len(raw_items) - len(cleaned_items)
    print(f"      전처리 후 건수: {len(cleaned_items)} (중복 {removed}건 제거)")

    print("[3/3] DB 저장 중 (stock/bond로 분류된 기사만 저장)")
    session = get_session()
    try:
        result = save_news_items(session, cleaned_items)
        print(
            f"      주식: {result['stock']}건 / 채권: {result['bond']}건 / "
            f"중복 건너뜀: {result['skipped_duplicate']}건 / "
            f"미분류(부동산·암호화폐 등) 건너뜀: {result['skipped_unmapped']}건"
        )
    finally:
        session.close()

    return {"collected": len(raw_items), **result}


def main():
    parser = argparse.ArgumentParser(description="뉴스 RSS 수집 및 저장 (주식/채권)")
    parser.add_argument("--days", type=int, default=7, help="오늘로부터 며칠 전까지 조회할지 (기본 7일)")
    args = parser.parse_args()

    run_collect_news(days=args.days)


if __name__ == "__main__":
    main()
