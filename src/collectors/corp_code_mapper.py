"""기업명 ↔ DART 고유코드(corp_code) 및 KRX 종목코드(stock_code) 매퍼 모듈."""

from typing import Any

# 주요 상장기업 즉시 매핑 사전 (초고속 제로 레이턴시 대응)
KNOWN_CORP_MAP: dict[str, dict[str, str]] = {
    "삼성전자": {"corp_code": "00126380", "stock_code": "005930"},
    "SK하이닉스": {"corp_code": "00164779", "stock_code": "000660"},
    "카카오": {"corp_code": "00258801", "stock_code": "035720"},
    "NAVER": {"corp_code": "00266961", "stock_code": "035420"},
    "네이버": {"corp_code": "00266961", "stock_code": "035420"},
    "LG에너지솔루션": {"corp_code": "01515325", "stock_code": "373220"},
    "현대차": {"corp_code": "00164742", "stock_code": "005380"},
    "현대자동차": {"corp_code": "00164742", "stock_code": "005380"},
    "POSCO홀딩스": {"corp_code": "00139150", "stock_code": "005490"},
    "포스코홀딩스": {"corp_code": "00139150", "stock_code": "005490"},
    "셀트리온": {"corp_code": "00401878", "stock_code": "068270"},
    "기아": {"corp_code": "00106641", "stock_code": "000270"},
    "KB금융": {"corp_code": "00689406", "stock_code": "105560"},
    "신한지주": {"corp_code": "00382199", "stock_code": "055550"},
}


class CorpCodeMapper:
    """기업명을 DART corp_code 및 KRX stock_code로 변환하는 클래스."""

    def __init__(self) -> None:
        self._map = dict(KNOWN_CORP_MAP)

    def get_info(self, corp_name: str) -> dict[str, str] | None:
        """기업 정보(corp_code, stock_code)를 조회한다."""
        name = corp_name.strip()
        # 정확히 매칭되거나 부분 포함 매칭 확인
        if name in self._map:
            return self._map[name]

        for key, val in self._map.items():
            if name in key or key in name:
                return val

        # 만약 8자리 숫자가 직접 입력되었다면 corp_code로 그대로 사용
        if len(name) == 8 and name.isdigit():
            return {"corp_code": name, "stock_code": ""}

        return None

    def get_corp_code(self, corp_name: str) -> str | None:
        """기업명에 해당하는 DART 8자리 corp_code를 반환한다."""
        info = self.get_info(corp_name)
        return info["corp_code"] if info else None

    def get_stock_code(self, corp_name: str) -> str | None:
        """기업명에 해당하는 KRX 6자리 stock_code를 반환한다."""
        info = self.get_info(corp_name)
        return info["stock_code"] if info else None


# 전역 기본 매퍼 인스턴스
global_corp_mapper = CorpCodeMapper()
