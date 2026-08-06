"""src/common/period.py 테스트."""

from datetime import datetime
from unittest.mock import patch

from src.common.period import get_period_bounds


def test_get_period_bounds_truncates_to_midnight():
    fixed_now = datetime(2026, 7, 28, 15, 42, 33, 123456)
    with patch("src.common.period.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        start, end = get_period_bounds(7)

    assert end == datetime(2026, 7, 28, 0, 0, 0)
    assert start == datetime(2026, 7, 21, 0, 0, 0)


def test_get_period_bounds_is_stable_across_multiple_calls_same_day():
    """실행 시각이 몇 초 달라도 같은 날이면 항상 동일한 경계를 반환해야 한다
    (extract_keywords와 generate_report가 다른 시각에 실행돼도 매칭되도록)."""
    first_start, first_end = get_period_bounds(7)
    second_start, second_end = get_period_bounds(7)

    assert first_start == second_start
    assert first_end == second_end
    assert first_start.hour == 0 and first_start.minute == 0 and first_start.second == 0
