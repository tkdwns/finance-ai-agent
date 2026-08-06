"""
키워드 추출 모듈.

1차: TF-IDF로 통계적 후보 키워드 추출 (빠르고 저렴, API 키 없이도 동작)
2차: 상위 후보만 Claude API로 정제 (의미 없는 후보 제거 + 트렌드 한 줄 설명)

원칙 (docs/PROJECT_GUIDELINE.md 참고):
- 숫자/법 조항 등 팩트성 정보는 LLM이 새로 만들어내지 않는다. LLM은 이미
  통계적으로 뽑힌 후보 중 의미 없는 것을 걸러내고, 짧은 트렌드 설명만 붙이는
  역할로 한정한다 (환각 방지 원칙).
"""

import json
import re

from sklearn.feature_extraction.text import TfidfVectorizer

from src.preprocessing.normalizer import tokenize_korean_nouns

# konlpy(JDK)가 없는 환경에서도 파이프라인이 완전히 막히지 않도록 쓰는 대체 토크나이저.
# 한글 2글자 이상 연속 구간을 하나의 토큰으로 본다 (형태소 분석만큼 정교하지는 않음).
_FALLBACK_TOKEN_RE = re.compile(r"[가-힣]{2,}")

# TF-IDF 상위 후보에서도 걸러내고 싶은 공시 관용구 (불용어)
STOPWORDS: set[str] = {
    "보고서", "공시", "관련", "사항", "결정", "내용", "당사", "회사", "귀중",
    "제출", "기재", "정정", "신고", "안내", "해당", "경우", "이상", "이하",
    "기타", "사유", "확인", "진행", "예정", "완료",
    # 여러 공시 유형(자기주식취득, 유상증자, 전환사채 등)에 공통으로 반복되는
    # 법률/회계 상투어. 형태소 분석기가 없는 폴백 토크나이저 환경에서 특히
    # 조사/어미가 붙은 채로 뽑히는 경우가 많아 통계적으로는 이렇게 명시적으로 제외한다.
    "기타주식", "보통주식", "자기주식", "가중산술평균주가", "상기",
    "신주의", "사채의", "바랍니다", "비율",
}


# konlpy 폴백이 발생했을 때 콘솔에 한 번만 경고를 띄우기 위한 플래그
_fallback_warned = False


def _tokenize(text: str) -> list[str]:
    """konlpy가 사용 가능하면 명사 추출을, 아니면 정규식 기반 대체 토크나이저를 쓴다."""
    global _fallback_warned
    try:
        tokens = tokenize_korean_nouns(text)
    except RuntimeError as e:
        if not _fallback_warned:
            print(f"[경고] 한국어 형태소 분석기를 사용할 수 없어 대체 토크나이저로 전환합니다: {e}")
            _fallback_warned = True
        tokens = _FALLBACK_TOKEN_RE.findall(text)
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def extract_keywords_statistical(
    texts: list[str], top_n: int = 10, max_df: float = 0.5
) -> list[tuple[str, float]]:
    """
    문서 집합(texts)에서 TF-IDF 기반으로 상위 키워드 후보를 추출한다.

    개별 문서의 TF-IDF 점수가 아니라, 전체 texts에서 각 단어의 TF-IDF 점수 합을
    구해 "이 기간 전체에서 중요한 단어"를 뽑는 방식이다.

    Args:
        max_df: 이 비율 이상의 문서에 등장하는 단어는 제외한다 (기본 0.5 = 전체 문서의
            50% 이상에 나오면 제외). "주요사항보고서"처럼 거의 모든 공시에 반복되는
            상투적 문구를 하나하나 불용어로 등록하지 않아도 자동으로 걸러내기 위함.

    Returns:
        (키워드, 점수) 튜플 리스트, 점수 내림차순 정렬
    """
    non_empty_texts = [t for t in texts if t and t.strip()]
    if not non_empty_texts:
        return []

    # 문서가 너무 적으면(예: 5건 미만) max_df 필터링이 전체 어휘를 지워버릴 수 있다
    # (예: 문서 1건이면 모든 단어의 df=1로 max_df=0.5 기준을 항상 넘겨 전부 제외됨).
    # 상투적 문구 필터링은 문서가 충분히 많을 때만 의미가 있으므로 소규모 배치에서는 끈다.
    effective_max_df = max_df if len(non_empty_texts) >= 5 else 1.0

    vectorizer = TfidfVectorizer(
        tokenizer=_tokenize, lowercase=False, token_pattern=None, max_df=effective_max_df
    )
    try:
        matrix = vectorizer.fit_transform(non_empty_texts)
    except ValueError as e:
        print(f"[경고] TF-IDF 벡터화 실패 (문서 {len(non_empty_texts)}건): {e}")
        print(f"       입력 텍스트 예시: {non_empty_texts[0][:100]!r}")
        return []

    if matrix.shape[1] == 0:
        print(f"[경고] 토큰화 결과 어휘가 비어있습니다 (문서 {len(non_empty_texts)}건 처리했지만 유효 토큰 0개).")
        print(f"       입력 텍스트 예시: {non_empty_texts[0][:100]!r}")
        return []

    scores = matrix.sum(axis=0).A1  # 각 단어의 전체 문서 합산 점수
    feature_names = vectorizer.get_feature_names_out()

    ranked = sorted(zip(feature_names, scores), key=lambda x: x[1], reverse=True)
    return [(word, float(score)) for word, score in ranked[:top_n]]


def _build_refine_prompt(candidates: list[tuple[str, float]], context: str) -> str:
    candidate_list = "\n".join(f"- {word} (점수: {score:.2f})" for word, score in candidates)
    return f"""다음은 국내 상장기업 공시 텍스트에서 TF-IDF로 추출한 후보 키워드 목록입니다.
이 텍스트는 형태소 분석 없이 기계적으로 추출되어, 조사가 붙었거나 불완전한 단어,
문법적 기능어가 섞여 있을 수 있습니다.

{candidate_list}

참고 문맥 (이 기간 공시 요약 일부):
{context[:2000]}

작업:
1. 다음에 해당하는 후보는 반드시 제외하세요 (제외 기준을 관대하게 적용하지 말고 엄격하게):
   - 조사/어미가 붙어 완전한 명사가 아닌 것 (예: "회사의", "신주를", "사채의")
   - "여부", "직전", "이후", "상기"처럼 그 자체로는 구체적 의미가 없는 지시어/기능어
   - "취득", "결정", "변경"처럼 너무 일반적이어서 어떤 공시에도 붙을 수 있는 범용 동작 명사
     (단, "타법인주식취득", "자기주식취득"처럼 구체적 대상과 결합된 복합어는 유지)
   - 특정 기업명 단독
   각 후보가 "이 기간에 실제로 어떤 구체적 사건/이슈를 가리키는가"를 스스로 자문해보고,
   답이 애매하면 억지로 설명을 만들어내지 말고 제외하세요. 남기는 것보다 제외하는 쪽으로
   판단이 애매할 때는 기울이세요.
2. 남은 키워드마다 이 기간 공시에서 왜 중요해 보이는지 한 문장으로 설명하세요.
3. 모든 후보가 기준에 미달하면 빈 배열 []을 반환해도 됩니다.
4. 반드시 아래 JSON 배열 형식으로만 응답하세요. 다른 텍스트를 추가하지 마세요.

[{{"keyword": "...", "explanation": "..."}}]
"""


def _parse_refine_response(text: str, candidates: list[tuple[str, float]]) -> list[dict]:
    """LLM 응답(마크다운 코드펜스 포함 가능)을 파싱해 표준 결과 형태로 변환한다."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json"):].strip()

    refined = json.loads(text)

    score_map = dict(candidates)
    result = []
    for item in refined:
        keyword = item.get("keyword", "")
        result.append(
            {
                "keyword": keyword,
                "score": score_map.get(keyword, 0.0),
                "explanation": item.get("explanation", ""),
            }
        )
    return result


def _refine_with_anthropic(prompt: str, api_key: str | None) -> str:
    import anthropic

    from config.settings import settings

    client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _refine_with_openai(prompt: str, api_key: str | None) -> str:
    import openai

    from config.settings import settings

    client = openai.OpenAI(api_key=api_key or settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def refine_keywords_with_llm(
    candidates: list[tuple[str, float]],
    context: str,
    api_key: str | None = None,
    provider: str | None = None,
) -> list[dict]:
    """
    TF-IDF 후보 키워드를 LLM으로 정제한다 (Anthropic 또는 OpenAI 중 선택).

    - 의미 없는 후보(불용어 잔재, 지나치게 일반적인 단어)를 제거한다.
    - 남은 키워드마다 이 기간의 트렌드를 설명하는 한 문장을 붙인다.

    Args:
        provider: "anthropic" 또는 "openai". None이면 config.settings.llm_provider를 따른다.
            결제 등록이 되는 쪽을 .env의 LLM_PROVIDER에 지정해두면 코드 변경 없이 전환 가능.

    주의: 숫자/고유명사/법 조항 등 사실 관계는 LLM이 새로 만들어내지 않는다.
    LLM은 "이미 통계적으로 뽑힌 후보를 정리하고 설명을 붙이는" 역할로 한정한다.

    Returns:
        [{"keyword": str, "score": float, "explanation": str}, ...]
    """
    from config.settings import settings

    resolved_provider = provider or settings.llm_provider
    prompt = _build_refine_prompt(candidates, context)

    if resolved_provider == "openai":
        text = _refine_with_openai(prompt, api_key)
    elif resolved_provider == "anthropic":
        text = _refine_with_anthropic(prompt, api_key)
    else:
        raise ValueError(f"알 수 없는 LLM_PROVIDER: {resolved_provider!r} ('anthropic' 또는 'openai'만 지원)")

    return _parse_refine_response(text, candidates)


def extract_keywords(
    texts: list[str],
    top_n: int = 10,
    use_llm: bool = True,
    api_key: str | None = None,
    max_df: float = 0.5,
    provider: str | None = None,
) -> list[dict]:
    """
    통계 기반 1차 추출 -> (옵션) LLM 정제까지 묶은 진입점.

    use_llm=False면 통계 결과만 {"keyword", "score", "explanation": ""} 형태로 반환한다
    (API 키가 없거나 빠르게 결과만 확인하고 싶을 때 사용).
    """
    candidates = extract_keywords_statistical(texts, top_n=top_n * 2, max_df=max_df)  # LLM이 걸러낼 여유를 두고 더 뽑음
    if not candidates:
        return []

    if not use_llm:
        return [{"keyword": w, "score": s, "explanation": ""} for w, s in candidates[:top_n]]

    context = " ".join(texts)[:3000]
    refined = refine_keywords_with_llm(candidates, context, api_key=api_key, provider=provider)
    return refined[:top_n]
