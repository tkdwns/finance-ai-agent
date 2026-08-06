"""부동산 및 채권 금리 수집 Tool 단위 테스트."""

from unittest.mock import MagicMock, patch
from src.agent_tools.bond_tools import query_bond_yields
from src.agent_tools.real_estate_tools import query_real_estate_price
from src.collectors.bond_collector import BondCollector


def test_query_real_estate_price_tool():
    """query_real_estate_price Tool 호출을 검증한다."""
    res_gangnam = query_real_estate_price("강남구")
    assert "region_code" in res_gangnam
    assert "avg_price_manwon" in res_gangnam

    res_jongno = query_real_estate_price("종로구")
    assert "region_code" in res_jongno


def test_query_bond_yields_tool():
    """query_bond_yields Tool 호출을 검증한다."""
    res = query_bond_yields("국고채")
    assert "kr_treasury_3y" in res
    assert "us_treasury_10y" in res
    assert "credit_spread" in res


def test_bond_collector_fallback():
    """BondCollector 기본 리턴 구조를 검증한다."""
    collector = BondCollector()
    yields = collector.get_bond_yields()
    assert "kr_treasury_3y" in yields
    assert "us_treasury_10y" in yields
