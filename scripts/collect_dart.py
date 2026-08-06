"""
DART 공시 수집 실행 스크립트.

사용법 (프로젝트 루트에서):
    python -m scripts.collect_dart --days 7
    python -m scripts.collect_dart --days 30 --corp-code 00126380     # 삼성전자만
    python -m scripts.collect_dart --days 7 --fetch-text              # 공시 원문까지 요약해서 저장
    python -m scripts.collect_dart --days 7 --fetch-text --max-text-fetches 5  # 원문 조회를 5건으로 제한
    python -m scripts.collect_dart --days 7 --pblntf-types A,B,C       # 정기공시+주요사항보고+발행공시만
    python -m scripts.collect_dart --days 7 --pblntf-types substantial # 위와 동일 (추천 프리셋)

사전 준비: .env 파일에 DART_API_KEY가 설정되어 있어야 한다.

--fetch-text 옵션 설명:
    list.json API는 공시 "제목"만 제공한다. --fetch-text를 켜면 공시마다
    document.xml API를 추가로 호출해 본문 텍스트를 가져와 summary 필드를
    채운다. 공시 건수만큼 API 호출이 늘어나므로(느려짐 + 요청 제한 위험),
    --max-text-fetches로 상한을 걸어두는 것을 권장한다 (기본 20건).

--pblntf-types 옵션 설명:
    필터링 없이 수집하면 "임원·주요주주 소유상황보고서" 같은 절차성 신고가
    대부분을 차지해 핵심 키워드 추출 시 노이즈가 된다. 콤마로 구분한 유형
    코드(A/B/C/D/E/F/G/H/I/J, 자세한 설명은 dart_collector.py의
    DART_DISCLOSURE_TYPES 참고)를 지정하면 해당 유형만 수집한다.
    "substantial"을 넣으면 추천 조합(A,B,C = 정기공시+주요사항보고+발행공시)을 사용한다.
"""

import argparse
from datetime import datetime, timedelta

from src.collectors.dart_collector import (
    DART_DISCLOSURE_TYPES,
    RECOMMENDED_SUBSTANTIAL_TYPES,
    DartApiError,
    DartCollector,
)
from src.collectors.dart_document_fetcher import DartDocumentError, DartDocumentFetcher
from src.preprocessing.pipeline import preprocess
from src.storage.db import ensure_schema_up_to_date, get_session
from src.storage.models import Base
from src.storage.save import save_stock_disclosures


def _parse_pblntf_types(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    if raw.strip().lower() == "substantial":
        return RECOMMENDED_SUBSTANTIAL_TYPES

    types = [t.strip().upper() for t in raw.split(",") if t.strip()]
    invalid = [t for t in types if t not in DART_DISCLOSURE_TYPES]
    if invalid:
        valid_list = ", ".join(f"{k}({v})" for k, v in DART_DISCLOSURE_TYPES.items())
        raise ValueError(f"알 수 없는 공시 유형 코드: {invalid}. 사용 가능한 코드: {valid_list}")
    return types


def _enrich_with_document_text(items, max_fetches: int) -> None:
    """상위 max_fetches건에 한해 공시 원문을 가져와 summary를 교체한다.
    실패한 건은 기존 summary(보고서명)를 그대로 유지하고 다음 건으로 넘어간다."""
    fetcher = DartDocumentFetcher()
    target_items = items[:max_fetches]

    for idx, item in enumerate(target_items, start=1):
        rcept_no = item.raw_meta.get("rcept_no", "")
        print(f"      [{idx}/{len(target_items)}] 원문 조회 중: {item.raw_meta.get('corp_name')} - {rcept_no}")
        try:
            item.summary = fetcher.fetch_text(rcept_no)
        except DartDocumentError as e:
            print(f"      경고: 원문 조회 실패 ({rcept_no}), 제목으로 대체합니다. ({e})")


def run_collect_dart(
    days: int,
    corp_code: str | None = None,
    pblntf_types: list[str] | None = None,
    fetch_text: bool = False,
    max_text_fetches: int = 20,
) -> dict:
    """
    DART 공시 수집의 핵심 로직. CLI(argparse)와 스케줄러 양쪽에서 재사용할 수 있도록
    인자를 명시적으로 받는 함수로 분리했다.

    Returns:
        {"collected": int, "saved": int, "updated": int} 형태의 실행 결과 요약
    """
    ensure_schema_up_to_date(Base)  # 테이블이 없으면 생성, 있으면 스키마 보강

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    steps_total = 4 if fetch_text else 3

    if pblntf_types:
        labels = ", ".join(f"{t}({DART_DISCLOSURE_TYPES[t]})" for t in pblntf_types)
        print(f"[1/{steps_total}] DART 공시 수집 중: {start_date.date()} ~ {end_date.date()} | 유형: {labels}")
    else:
        print(f"[1/{steps_total}] DART 공시 수집 중: {start_date.date()} ~ {end_date.date()} | 유형: 전체")

    collector = DartCollector()
    try:
        if pblntf_types:
            raw_items = collector.collect_by_types(
                start_date, end_date, pblntf_types, corp_code=corp_code
            )
        else:
            raw_items = collector.collect(start_date, end_date, corp_code=corp_code)
    except DartApiError as e:
        print(f"수집 실패: {e}")
        return {"collected": 0, "saved": 0, "updated": 0, "error": str(e)}

    print(f"      수집된 공시 건수: {len(raw_items)}")

    # 공시는 rcept_no로 이미 고유하므로 제목 유사도 dedup은 끈다 (title_similarity_threshold=None)
    print(f"[2/{steps_total}] 전처리 중 (정규화 + URL 기준 중복 제거)")
    cleaned_items = preprocess(raw_items, title_similarity_threshold=None)
    removed = len(raw_items) - len(cleaned_items)
    print(f"      전처리 후 건수: {len(cleaned_items)} (중복 {removed}건 제거)")

    if fetch_text:
        print(f"[3/{steps_total}] 공시 원문 조회 중 (최대 {max_text_fetches}건)")
        _enrich_with_document_text(cleaned_items, max_text_fetches)

    print(f"[{steps_total}/{steps_total}] DB 저장 중")
    session = get_session()
    try:
        saved, updated = save_stock_disclosures(session, cleaned_items, update_existing=fetch_text)
        skipped = len(cleaned_items) - saved - updated
        print(f"      새로 저장된 건수: {saved} / 갱신된 건수: {updated} / 변경 없음: {skipped}")
    finally:
        session.close()

    return {"collected": len(raw_items), "saved": saved, "updated": updated}


def main():
    parser = argparse.ArgumentParser(description="DART 공시 수집 및 저장")
    parser.add_argument("--days", type=int, default=7, help="오늘로부터 며칠 전까지 조회할지 (기본 7일)")
    parser.add_argument("--corp-code", type=str, default=None, help="특정 기업의 DART 고유번호")
    parser.add_argument(
        "--pblntf-types",
        type=str,
        default=None,
        help="콤마로 구분한 공시 유형 코드 (예: A,B,C) 또는 'substantial'(추천 프리셋). 생략 시 전체 유형",
    )
    parser.add_argument(
        "--fetch-text", action="store_true", help="공시 원문을 조회해 요약 텍스트로 저장 (API 호출 늘어남)"
    )
    parser.add_argument(
        "--max-text-fetches", type=int, default=20, help="--fetch-text 사용 시 원문을 가져올 최대 건수 (기본 20)"
    )
    args = parser.parse_args()

    try:
        pblntf_types = _parse_pblntf_types(args.pblntf_types)
    except ValueError as e:
        print(f"옵션 오류: {e}")
        return

    run_collect_dart(
        days=args.days,
        corp_code=args.corp_code,
        pblntf_types=pblntf_types,
        fetch_text=args.fetch_text,
        max_text_fetches=args.max_text_fetches,
    )


if __name__ == "__main__":
    main()
