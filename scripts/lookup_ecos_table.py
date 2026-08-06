"""
ECOS 통계표코드(stat_code) 검색 도우미.

주식시장(일)/주요국 통화의 대원화환율처럼 ECOS 웹사이트의 "통계코드검색"에서 내려받은
엑셀에는 항목코드(item_code1)만 있고 상위 통계표코드(stat_code)가 없다. 이 스크립트는
ECOS의 StatisticTableList API로 통계명에 코드를 직접 조회해 정확한 stat_code를 확인한다
(추측/하드코딩 없이 실제 API 응답으로 검증하기 위함).

이 스크립트는 실제 ECOS_API_KEY로 외부 네트워크 호출이 필요해 샌드박스에서는 실행할 수
없으므로, 사용자가 로컬 환경에서 직접 실행해야 한다.

사용법 (프로젝트 루트에서):
    python -m scripts.lookup_ecos_table "주식시장"
    python -m scripts.lookup_ecos_table "대원화환율"
"""

import sys

import requests

from config.settings import settings


def lookup(keyword: str) -> list[dict]:
    url = f"https://ecos.bok.or.kr/api/StatisticTableList/{settings.ecos_api_key}/json/kr/1/3000/"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    payload = response.json()

    if "StatisticTableList" not in payload:
        result = payload.get("RESULT", {})
        print(f"API 오류 ({result.get('CODE', 'UNKNOWN')}): {result.get('MESSAGE', payload)}")
        return []

    rows = payload["StatisticTableList"].get("row", [])
    return [r for r in rows if keyword in (r.get("STAT_NAME") or "")]


def main():
    if len(sys.argv) < 2:
        print('사용법: python -m scripts.lookup_ecos_table "검색어"')
        return
    keyword = sys.argv[1]
    matches = lookup(keyword)
    if not matches:
        print(f"'{keyword}'가 포함된 통계표를 찾지 못했습니다.")
        return
    for r in matches:
        print(f"{r['STAT_CODE']}\t주기={r.get('CYCLE')}\t{r['STAT_NAME']}")


if __name__ == "__main__":
    main()
