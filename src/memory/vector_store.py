"""RAG 벡터 기억 장치 (FinancialMemory) 모듈."""

import math
from typing import Any
import uuid

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class FinancialMemory:
    """수집된 금융 문서를 벡터화하고 Okapi BM25 및 의미 유사도로 하이브리드 검색(RAG)하는 기억 장치."""

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

    def _calculate_bm25_scores(self, query: str, k1: float = 1.5, b: float = 0.75) -> list[float]:
        """Okapi BM25 (TF-IDF 기반 가중치 및 문서 길이 정규화 알고리즘) 점수를 계산한다."""
        if not self.texts:
            return []

        tokenized_docs = [text.lower().split() for text in self.texts]
        N = len(tokenized_docs)
        if N == 0:
            return []

        doc_lens = [len(doc) for doc in tokenized_docs]
        avgdl = sum(doc_lens) / N if N > 0 else 1.0

        query_terms = query.lower().split()
        if not query_terms:
            return [0.0] * N

        # IDF 계산
        idf = {}
        for term in set(query_terms):
            n_q = sum(1 for doc in tokenized_docs if term in doc)
            idf[term] = math.log((N - n_q + 0.5) / (n_q + 0.5) + 1.0)

        # BM25 문서 점수 계산
        bm25_raw_scores = []
        for i, doc in enumerate(tokenized_docs):
            doc_len = doc_lens[i]
            score = 0.0
            for term in query_terms:
                if term not in idf:
                    continue
                tf = doc.count(term)
                if tf == 0:
                    continue
                num = tf * (k1 + 1.0)
                den = tf + k1 * (1.0 - b + b * (doc_len / (avgdl or 1.0)))
                score += idf[term] * (num / den)
            bm25_raw_scores.append(score)

        # Min-Max 0.0 ~ 1.0 정규화
        max_score = max(bm25_raw_scores) if bm25_raw_scores else 0.0
        if max_score > 0:
            return [s / max_score for s in bm25_raw_scores]
        return [0.0] * N

    def hybrid_search(self, query: str, top_k: int = 5, alpha: float = 0.5) -> list[dict[str, Any]]:
        """Okapi BM25 정밀 키워드 매칭과 Vector 시맨틱 유사도를 융합한 하이브리드 검색을 수행한다."""
        if not self.texts or not self._vectorizer or self._matrix is None:
            return []

        # 1. Vector 시맨틱 유사도 점수 (0.0 ~ 1.0)
        try:
            query_vec = self._vectorizer.transform([query])
            vector_scores = cosine_similarity(query_vec, self._matrix).flatten()
        except Exception:
            vector_scores = [0.0] * len(self.texts)

        # 2. Okapi BM25 정량 점수 계산
        bm25_scores = self._calculate_bm25_scores(query)

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
        """질의문과 가장 유사한 과거 문서를 top_k개 검색하여 반환한다."""
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
