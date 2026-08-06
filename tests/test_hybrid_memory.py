"""BM25 + Vector 하이브리드 RAG 검색 단위 테스트."""

from src.memory import FinancialMemory


def test_hybrid_search_combines_keyword_and_vector():
    """키워드 정확 매칭(BM25)과 문맥 유사도(Vector) 융합을 검증한다."""
    memory = FinancialMemory()
    docs = [
        "2026-08-01 DART 기업 공시 접수번호 20260801000123",
        "한국은행 금융통화위원회 기준금리 동향 분석",
        "삼성전자 반도체 부문 실적 발표",
    ]
    memory.add_documents(docs)

    # 1. 고유 숫자로 정확 매칭 (BM25 강세)
    num_res = memory.hybrid_search("20260801000123", top_k=1, alpha=0.2)
    assert len(num_res) == 1
    assert "20260801000123" in num_res[0]["text"]
    assert num_res[0]["bm25_score"] > 0

    # 2. 문맥 의미로 검색 (Vector 강세)
    sem_res = memory.hybrid_search("기준금리 인하 동향", top_k=1, alpha=0.8)
    assert len(sem_res) == 1
    assert "한국은행" in sem_res[0]["text"]
