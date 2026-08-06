"""
기간(period) 경계를 자정 기준으로 정규화하는 유틸리티.

여러 스크립트(키워드 추출, 보고서 생성)가 서로 다른 시각에 실행되어도 같은 "N일간"을
가리키면 period_start가 정확히 일치해야 한다 (Keyword 테이블 조회/upsert가 period_start
동등 비교를 사용하기 때문). datetime.now()를 그대로 쓰면 실행 시각의 초/마이크로초
차이 때문에 절대 일치하지 않으므로, 자정(00:00:00) 기준으로 정규화해서 사용한다.
"""

from datetime import datetime, timedelta


def get_period_bounds(days: int) -> tuple[datetime, datetime]:
    """오늘 자정을 기준으로 (days일 전 자정, 오늘 자정) 튜플을 반환한다.

    예: get_period_bounds(7) -> (2026-07-21 00:00:00, 2026-07-28 00:00:00)
    실행 시각과 무관하게 같은 날 여러 번 호출하면 항상 동일한 값을 반환한다.
    """
    today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today_midnight - timedelta(days=days)
    return start, today_midnight
