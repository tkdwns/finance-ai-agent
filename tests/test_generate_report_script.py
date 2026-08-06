"""scripts/generate_report.py의 CLI 보조 로직(_resolve_days) 테스트."""

from scripts.generate_report import _resolve_days


def test_resolve_days_uses_canonical_value_when_omitted():
    assert _resolve_days(None, "daily") == 1
    assert _resolve_days(None, "weekly") == 7
    assert _resolve_days(None, "monthly") == 30
    assert _resolve_days(None, "yearly") == 365


def test_resolve_days_keeps_explicit_value_when_matching_canonical():
    assert _resolve_days(7, "weekly") == 7


def test_resolve_days_keeps_explicit_value_even_when_mismatched(capsys):
    # --days 90 --period-type weekly 처럼 명시적으로 다르게 줬다면 사용자 의도를
    # 존중해 그대로 쓰되, 라벨과 실제 기간이 다르다는 안내를 출력해야 한다.
    result = _resolve_days(90, "weekly")

    assert result == 90
    captured = capsys.readouterr()
    assert "weekly" in captured.out
    assert "90" in captured.out
