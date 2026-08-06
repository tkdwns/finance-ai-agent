"""FinancialMemory 및 RAG 검색 도구 단위 테스트."""

from src.agent_tools import global_registry
from src.memory import FinancialMemory, global_memory


def test_financial_memory_add_and_search():
    """문서 등록 및 시맨틱 벡터 유사도 검색을 검증한다."""
    memory = FinancialMemory()
    docs = [
        "삼성전자 2026년 1분기 영업이익 10조원 달성 및 반도체 실적 개선",
        "한국은행 금융통화위원회 기준금리 0.25%p 인하 결정",
        "자본시장법 개정안 국회 본회의 통과 및 공매도 규제 강화",
    ]
    metas = [{"source": "DART"}, {"source": "ECOS"}, {"source": "LAW"}]

    added_ids = memory.add_documents(docs, metadatas=metas)
    assert len(added_ids) == 3

    # 검색 1: 금리 관련
    results_rate = memory.search("기준금리 인하", top_k=2)
    assert len(results_rate) > 0
    assert "기준금리" in results_rate[0]["text"]
    assert results_rate[0]["metadata"]["source"] == "ECOS"

    # 검색 2: 삼성전자 영업이익 관련
    results_samsung = memory.search("삼성전자 실적", top_k=1)
    assert len(results_samsung) == 1
    assert "삼성전자" in results_samsung[0]["text"]


def test_rag_agent_tool_integration():
    """search_financial_memory 도구가 레지스트리를 통해 정상 작동하는지 검증한다."""
    global_memory.clear()
    global_memory.add_documents(
        ["유상증자 결정 공시 제출"], metadatas=[{"corp": "A사"}]
    )

    # 레지스트리를 통해 RAG 메모리 검색 도구 실행
    tool_result = global_registry.execute("search_financial_memory", query="유상증자", top_k=1)
    assert isinstance(tool_result, list)
    assert len(tool_result) == 1
    assert tool_result[0]["metadata"]["corp"] == "A사"
