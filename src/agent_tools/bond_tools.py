"""국고채 및 채권 금리 조회 Tool 등록 모듈."""

from typing import Any
from src.agent_tools.registry import global_registry
from src.collectors.bond_collector import BondCollector

bond_collector = BondCollector()


@global_registry.register(
    name="query_bond_yields",
    description="한국 국고채 3년/10년 금리, 미 국채 10년물 금리 및 회사채 신용 스프레드 지표를 조회한다.",
    parameters={
        "type": "object",
        "properties": {
            "bond_type": {
                "type": "string",
                "description": "채권 종류 키워드 (국고채, 미국채, 회사채, 금리)",
            }
        },
        "required": [],
    },
)
def query_bond_yields(bond_type: str = "국고채") -> dict[str, Any]:
    """국내외 주요 채권 금리 및 스프레드 지표를 반환한다."""
    return bond_collector.get_bond_yields(bond_type=bond_type or "국고채")
