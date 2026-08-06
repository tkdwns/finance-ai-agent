"""키워드 추출 모듈(src/analysis/keyword_extractor.py) 테스트."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.analysis.keyword_extractor import (
    extract_keywords,
    extract_keywords_statistical,
    refine_keywords_with_llm,
)

SAMPLE_TEXTS = [
    "주요사항보고서(회사합병결정) 이사회는 회사합병을 결정했다. 합병 비율은 추후 공시한다.",
    "주요사항보고서(유상증자결정) 유상증자를 통해 시설자금을 조달할 예정이다. 유상증자 규모는 100억원이다.",
    "주요사항보고서(회사합병결정) 양사 이사회는 합병 계약을 체결했다고 공시했다.",
    "기타시장안내(관리종목지정우려종목) 시가총액 200억원 미달로 관리종목 지정 우려가 있다.",
]


def test_extract_keywords_statistical_returns_ranked_tuples():
    result = extract_keywords_statistical(SAMPLE_TEXTS, top_n=5)

    assert len(result) > 0
    assert all(isinstance(item, tuple) and len(item) == 2 for item in result)
    # 점수 내림차순 정렬 확인
    scores = [score for _, score in result]
    assert scores == sorted(scores, reverse=True)


def test_extract_keywords_statistical_surfaces_meaningful_business_terms():
    result = extract_keywords_statistical(SAMPLE_TEXTS, top_n=10)
    keywords = [w for w, _ in result]

    # "합병"이 2개 문서에 등장하므로 상위권에 들어야 한다
    assert "합병" in keywords


def test_extract_keywords_statistical_excludes_stopwords():
    result = extract_keywords_statistical(SAMPLE_TEXTS, top_n=20)
    keywords = {w for w, _ in result}

    assert "보고서" not in keywords
    assert "결정" not in keywords
    assert "사항" not in keywords


def test_extract_keywords_statistical_handles_empty_input():
    assert extract_keywords_statistical([], top_n=5) == []
    assert extract_keywords_statistical(["", "   "], top_n=5) == []


def test_extract_keywords_statistical_filters_boilerplate_with_max_df():
    """거의 모든 문서에 등장하는 상투적 문구(공시 유형명 등)는 max_df로 자동 제외되어야 한다."""
    boilerplate_texts = [
        f"증권발행실적보고서 펀드{i}호 관련 내용입니다 합병 이슈도 있었다"
        for i in range(10)
    ]
    # "증권발행실적보고서"는 10개 문서 전부(100%)에 등장, "합병"은 전부에 등장(일부러 동일 비중 테스트는 아래 별도)
    result_default = extract_keywords_statistical(boilerplate_texts, top_n=10, max_df=0.5)
    keywords_default = {w for w, _ in result_default}
    # 전체 문서의 100%에 등장하는 단어는 max_df=0.5 기준을 넘으므로 제외되어야 한다
    assert "증권발행실적보고서" not in keywords_default


def test_extract_keywords_statistical_small_batch_ignores_max_df():
    """문서가 5건 미만이면 max_df 필터링을 자동으로 끈다 (전체 어휘가 지워지는 것 방지)."""
    tiny_texts = ["합병 계약을 체결했다", "유상증자를 결정했다"]
    result = extract_keywords_statistical(tiny_texts, top_n=5, max_df=0.5)
    # max_df를 그대로 적용했다면 df=1인 모든 단어가 threshold(0.5*2=1.0)를 넘어 전부 제외됐을 것
    assert len(result) > 0


def _make_llm_response(json_text: str):
    resp = MagicMock()
    resp.content = [SimpleNamespace(type="text", text=json_text)]
    return resp


def test_refine_keywords_with_llm_parses_json_response():
    candidates = [("합병", 1.2), ("유상증자", 0.9)]
    fake_json = '[{"keyword": "합병", "explanation": "여러 건의 회사 합병 결정이 있었다."}]'

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_llm_response(fake_json)
        mock_anthropic_cls.return_value = mock_client

        result = refine_keywords_with_llm(candidates, context="테스트 문맥", api_key="dummy-key", provider="anthropic")

    assert len(result) == 1
    assert result[0]["keyword"] == "합병"
    assert result[0]["score"] == 1.2
    assert "합병" in result[0]["explanation"]


def test_refine_keywords_with_llm_strips_markdown_code_fence():
    candidates = [("합병", 1.2)]
    fenced_json = '```json\n[{"keyword": "합병", "explanation": "설명"}]\n```'

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_llm_response(fenced_json)
        mock_anthropic_cls.return_value = mock_client

        result = refine_keywords_with_llm(candidates, context="", api_key="dummy-key", provider="anthropic")

    assert result[0]["keyword"] == "합병"


def test_extract_keywords_without_llm_returns_statistical_only():
    result = extract_keywords(SAMPLE_TEXTS, top_n=3, use_llm=False)

    assert len(result) <= 3
    assert all(item["explanation"] == "" for item in result)
    assert all("keyword" in item and "score" in item for item in result)


def test_extract_keywords_with_llm_calls_refine_step():
    fake_json = '[{"keyword": "합병", "explanation": "합병 이슈가 두드러졌다."}]'

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_llm_response(fake_json)
        mock_anthropic_cls.return_value = mock_client

        result = extract_keywords(SAMPLE_TEXTS, top_n=5, use_llm=True, api_key="dummy-key", provider="anthropic")

    assert len(result) == 1
    assert result[0]["keyword"] == "합병"
    assert result[0]["explanation"] == "합병 이슈가 두드러졌다."


def test_extract_keywords_returns_empty_when_no_candidates():
    result = extract_keywords(["", ""], top_n=5, use_llm=True)
    assert result == []


def _make_openai_response(content: str):
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    return resp


def test_refine_keywords_with_llm_supports_openai_provider():
    candidates = [("합병", 1.2)]
    fake_json = '[{"keyword": "합병", "explanation": "여러 건의 합병 결정이 있었다."}]'

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(fake_json)
        mock_openai_cls.return_value = mock_client

        result = refine_keywords_with_llm(
            candidates, context="테스트 문맥", api_key="dummy-key", provider="openai"
        )

    assert len(result) == 1
    assert result[0]["keyword"] == "합병"
    mock_client.chat.completions.create.assert_called_once()
    assert mock_client.chat.completions.create.call_args.kwargs["model"] == "gpt-4o-mini"


def test_refine_keywords_with_llm_raises_on_unknown_provider():
    import pytest

    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        refine_keywords_with_llm([("합병", 1.0)], context="", api_key="x", provider="unknown")


def test_extract_keywords_uses_provider_argument_over_default():
    fake_json = '[{"keyword": "합병", "explanation": "설명"}]'

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(fake_json)
        mock_openai_cls.return_value = mock_client

        result = extract_keywords(
            SAMPLE_TEXTS, top_n=5, use_llm=True, api_key="dummy-key", provider="openai"
        )

    assert result[0]["keyword"] == "합병"
