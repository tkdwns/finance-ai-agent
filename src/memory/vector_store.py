"""RAG 벡터 기억 장치 (FinancialMemory) 모듈."""

from typing import Any
import uuid

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class FinancialMemory:
    """수집된 금융 문서를 벡터화하고 의미 유사도로 검색(RAG)하는 기억 장치."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.metadatas: list[dict[str, Any]] = []
        self.doc_ids: list[str] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix: Any = None

    def add_documents(
        self, texts: list[str], metadatas: list[dict[str, Any]] | None = None
    ) -> list[str]:
        """기억 저장소에 새로운 문서들을 추가한다."""
        if not texts:
            return []

        added_ids = []
        for i, text in enumerate(texts):
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            doc_id = str(uuid.uuid4())
            self.texts.append(text)
            self.metadatas.append(meta)
            self.doc_ids.append(doc_id)
            added_ids.append(doc_id)

        self._reindex()
        return added_ids

    def _reindex(self) -> None:
        """저장된 전체 텍스트에 대해 벡터 인덱스를 재구성한다."""
        if not self.texts:
            self._vectorizer = None
            self._matrix = None
            return

        self._vectorizer = TfidfVectorizer()
        self._matrix = self._vectorizer.fit_transform(self.texts)

    def hybrid_search(self, query: str, top_k: int = 5, alpha: float = 0.5) -> list[dict[str, Any]]:
        """BM25 키워드 정확 매칭과 Vector 시맨틱 유사도를 융합한 하이브리드 검색을 수행한다."""
        if not self.texts or not self._vectorizer or self._matrix is None:
            return []

        # 1. Vector 시맨틱 유사도 점수 (0.0 ~ 1.0)
        try:
            query_vec = self._vectorizer.transform([query])
            vector_scores = cosine_similarity(query_vec, self._matrix).flatten()
        except Exception:
            vector_scores = [0.0] * len(self.texts)

        # 2. BM25 키워드 정확 매칭 점수
        query_terms = set(query.lower().split())
        bm25_scores = []
        for text in self.texts:
            t_lower = text.lower()
            match_count = sum(1 for term in query_terms if term in t_lower)
            score = match_count / max(len(query_terms), 1)
            bm25_scores.append(score)

        # 3. 하이브리드 점수 융합 (alpha * vector + (1 - alpha) * bm25)
        combined_scores = []
        for i in range(len(self.texts)):
            h_score = alpha * float(vector_scores[i]) + (1 - alpha) * float(bm25_scores[i])
            combined_scores.append(h_score)

        # 하이브리드 점수 내림차순 정렬
        sorted_indices = sorted(range(len(self.texts)), key=lambda i: combined_scores[i], reverse=True)[:top_k]

        results = []
        for idx in sorted_indices:
            score = combined_scores[idx]
            if score > 0.0:
                results.append(
                    {
                        "id": self.doc_ids[idx],
                        "text": self.texts[idx],
                        "metadata": self.metadatas[idx],
                        "score": round(score, 4),
                        "vector_score": round(float(vector_scores[idx]), 4),
                        "bm25_score": round(float(bm25_scores[idx]), 4),
                    }
                )

        return results

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """질의문과 가장 유사한 과거 문서를 top_k개 검색하여 반환한다 (기본값: hybrid_search 호환)."""
        return self.hybrid_search(query=query, top_k=top_k, alpha=0.6)

    def clear(self) -> None:
        """기억 저장소를 초기화한다."""
        self.texts.clear()
        self.metadatas.clear()
        self.doc_ids.clear()
        self._vectorizer = None
        self._matrix = None


# 전역 기본 기억 저장소 인스턴스
global_memory = FinancialMemory()
