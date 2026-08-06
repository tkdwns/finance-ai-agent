"""
저장된 데이터를 터미널에서 간단히 확인하는 스크립트.

사용법 (프로젝트 루트에서):
    python -m scripts.view_data                  # 최근 20건 미리보기
    python -m scripts.view_data --limit 50        # 최근 50건 미리보기
    python -m scripts.view_data --export out.csv  # 전체 데이터를 CSV로 내보내기 (엑셀로 열람 가능)
"""

import argparse
import csv

from src.storage.db import get_session
from src.storage.models import StockDisclosure


def main():
    parser = argparse.ArgumentParser(description="저장된 DART 공시 데이터 확인")
    parser.add_argument("--limit", type=int, default=20, help="미리보기로 출력할 최근 건수 (기본 20)")
    parser.add_argument("--export", type=str, default=None, help="전체 데이터를 저장할 CSV 파일 경로")
    args = parser.parse_args()

    session = get_session()
    try:
        total = session.query(StockDisclosure).count()
        print(f"stock_disclosures 테이블 총 {total}건 저장됨")

        if total == 0:
            print("저장된 데이터가 없습니다. 먼저 다음을 실행하세요:")
            print("  python -m scripts.collect_dart --days 7")
            return

        all_rows = session.query(StockDisclosure).all()
        enriched = sum(1 for r in all_rows if r.summary != r.report_name)
        print(
            f"  -> 원문 요약이 채워진 건: {enriched}건 / 제목만 있는 건: {total - enriched}건\n"
            f"     (--fetch-text의 --max-text-fetches 기본값이 20이라, 전체 중 일부만 원문이 채워지는 게 정상입니다)\n"
        )

        if args.export:
            rows = session.query(StockDisclosure).order_by(StockDisclosure.published_at.desc()).all()
            with open(args.export, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["공시일", "기업명", "보고서명", "요약(summary)", "접수번호", "출처", "링크"])
                for row in rows:
                    writer.writerow([
                        row.published_at.strftime("%Y-%m-%d"),
                        row.corp_name,
                        row.report_name,
                        row.summary,
                        row.rcept_no,
                        row.source,
                        row.url,
                    ])
            print(f"전체 {len(rows)}건을 {args.export} 로 내보냈습니다. 엑셀로 열어보세요.")
            return

        rows = (
            session.query(StockDisclosure)
            .order_by(StockDisclosure.published_at.desc())
            .limit(args.limit)
            .all()
        )
        print(f"최근 {len(rows)}건:\n")
        print("공시일       | 기업명          | 보고서명                       | 접수번호")
        print("-" * 90)
        for row in rows:
            published = row.published_at.strftime("%Y-%m-%d")
            print(f"{published} | {row.corp_name:<14} | {row.report_name[:28]:<28} | {row.rcept_no}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
