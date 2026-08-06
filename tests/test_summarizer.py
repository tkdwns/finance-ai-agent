"""src/analysis/summarizer.py 테스트 (실제 LLM 호출은 모킹)."""

from unittest.mock import patch

from src.analysis.summarizer import summarize_documents, summarize_group


def test_summarize_documents_returns_empty_dict_for_empty_input():
    assert summarize_documents([]) == {}


def test_summarize_documents_parses_llm_json_response():
    # 프롬프트/응답 키는 원본 식별자(URL)가 아니라 인덱스("0","1",...)를 쓴다 —
    # 긴 URL을 응답 키로 그대로 요구하면 모델이 정확히 재현하지 못해 매칭이 깨지는
    # 문제를 피하기 위함.
    items = [("url1", "삼성전자가 유상증자를 결정했다는 공시 원문..."), ("url2", "은행법 개정 관련 원문...")]
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.return_value = '{"0": "삼성전자 유상증자 결정 요약", "1": "은행법 개정 요약"}'
        result = summarize_documents(items)

    assert result == {"url1": "삼성전자 유상증자 결정 요약", "url2": "은행법 개정 요약"}


def test_summarize_documents_strips_markdown_code_fence():
    items = [("url1", "원문")]
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.return_value = '```json\n{"0": "요약"}\n```'
        result = summarize_documents(items)

    assert result == {"url1": "요약"}


def test_summarize_documents_falls_back_to_truncated_text_on_llm_error():
    items = [("url1", "짧은 원문")]
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.side_effect = RuntimeError("API 키 없음")
        result = summarize_documents(items)

    assert result == {"url1": "짧은 원문"}


def test_summarize_documents_falls_back_to_truncated_text_on_invalid_json():
    items = [("url1", "원문 내용")]
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.return_value = "이건 JSON이 아닙니다"
        result = summarize_documents(items)

    assert result == {"url1": "원문 내용"}


def test_summarize_documents_fallback_truncates_long_text():
    long_text = "가" * 500
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.side_effect = RuntimeError("실패")
        result = summarize_documents([("url1", long_text)])

    assert len(result["url1"]) < 500
    assert result["url1"].endswith("...")


def test_summarize_documents_keeps_fallback_when_llm_omits_a_key():
    items = [("url1", "원문1"), ("url2", "원문2")]
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.return_value = '{"0": "요약1"}'  # url2(인덱스 1) 누락
        result = summarize_documents(items)

    assert result == {"url1": "요약1", "url2": "원문2"}


def test_summarize_documents_splits_large_batches_into_multiple_llm_calls():
    # 실사용 중 발견된 버그 재현: 문서 30건을 한 번의 LLM 호출로 요약하면 응답이
    # max_tokens에서 잘려 JSON 파싱이 통째로 실패하고 전부 원문 truncate로 대체됐다.
    # _BATCH_SIZE(6)개씩 나눠 여러 번 호출해야 한다.
    items = [(f"url{i}", f"원문{i}") for i in range(14)]  # 6+6+2 -> 3번 호출
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.side_effect = [
            '{"0": "요약0", "1": "요약1", "2": "요약2", "3": "요약3", "4": "요약4", "5": "요약5"}',
            '{"0": "요약6", "1": "요약7", "2": "요약8", "3": "요약9", "4": "요약10", "5": "요약11"}',
            '{"0": "요약12", "1": "요약13"}',
        ]
        result = summarize_documents(items)

    assert mock_call.call_count == 3
    assert result["url0"] == "요약0"
    assert result["url13"] == "요약13"
    assert len(result) == 14


def test_summarize_group_returns_empty_string_for_empty_input():
    assert summarize_group([]) == ""


def test_summarize_group_returns_single_combined_summary():
    texts = ["공시 원문 A...", "공시 원문 B...", "공시 원문 C..."]
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.return_value = "이번 기간 공시는 유상증자와 자기주식 취득이 주를 이뤘다."
        result = summarize_group(texts)

    assert result == "이번 기간 공시는 유상증자와 자기주식 취득이 주를 이뤘다."
    assert mock_call.call_count == 1


def test_summarize_group_returns_empty_string_on_llm_error():
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.side_effect = RuntimeError("API 키 없음")
        result = summarize_group(["원문"])

    assert result == ""


def test_summarize_group_strips_json_wrapper_from_response():
    # 순수 텍스트로 응답하라고 프롬프트에 명시해도 모델이 가끔 {"1": "..."} 같은
    # JSON으로 응답하는 경우가 실사용 중 발견됨 — 중괄호/따옴표/번호 없이 텍스트만 남겨야 한다.
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.return_value = '{ "1": "한국 금융 시장의 원활한 발전을 위해 새로운 제도를 도입한다." }'
        result = summarize_group(["원문"])

    assert result == "한국 금융 시장의 원활한 발전을 위해 새로운 제도를 도입한다."


def test_summarize_group_strips_leading_number_and_quotes_without_braces():
    # {"1": "..."} 뿐 아니라, 중괄호 없이 `1: "..."`만 붙이는 변형도 실사용 중 발견됨.
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.return_value = '1: "금융시장에서는 여러 기업들이 자본 조달에 나섰다."'
        result = summarize_group(["원문"])

    assert result == "금융시장에서는 여러 기업들이 자본 조달에 나섰다."


def test_summarize_group_caps_number_of_items_sent_to_llm():
    texts = [f"원문{i}" for i in range(30)]
    with patch("src.analysis.summarizer._call_llm") as mock_call:
        mock_call.return_value = "요약"
        summarize_group(texts)

    prompt = mock_call.call_args[0][0]
    assert "[20]" in prompt
    assert "[21]" not in prompt
