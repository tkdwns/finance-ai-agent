"""scripts/collect_dart.py의 _parse_pblntf_types 헬퍼 함수 테스트."""

import pytest

from scripts.collect_dart import _parse_pblntf_types


def test_parse_returns_none_when_not_provided():
    assert _parse_pblntf_types(None) is None
    assert _parse_pblntf_types("") is None


def test_parse_expands_substantial_preset():
    assert _parse_pblntf_types("substantial") == ["A", "B", "C"]
    assert _parse_pblntf_types("Substantial") == ["A", "B", "C"]  # 대소문자 무관


def test_parse_splits_comma_separated_codes():
    assert _parse_pblntf_types("A,B,C") == ["A", "B", "C"]
    assert _parse_pblntf_types("a, d") == ["A", "D"]  # 소문자/공백 허용


def test_parse_raises_on_invalid_code():
    with pytest.raises(ValueError):
        _parse_pblntf_types("A,Z")
