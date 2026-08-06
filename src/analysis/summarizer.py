"""
리포트에 표시할 문서/법령 원문을 짧게 요약하는 모듈.

원칙(docs/PROJECT_GUIDELINE.md 참고): 숫자·날짜 등 사실 정보는 LLM이 새로 만들지
않는다. 여기서 LLM은 "이미 수집된 원문을 몇 줄로 압축"하는 역할로만 쓴다.

키워드 추출(keyword_extractor.py)과 별도 모듈로 둔 이유: 이 기능은 리포트 표시를
위한 보조 기능이라 실패해도(키 미설정, API 오류 등) 리포트 생성 전체가 멈추면 안
된다 — 그래서 예외를 던지는 대신 원문을 잘라낸 값으로 조용히 대체한다.
"""

import json
import re

_MAX_INPUT_CHARS_PER_ITEM = 1500  # 항목당 LLM에 보낼 원문 길이 제한 (토큰/비용 절약)

# 순수 텍스트를 요청해도 모델이 가끔 `1: "..."` 처럼 중괄호 없이 번호+콜론으로 시작하는
# 응답을 주는 경우가 실사용 중 발견됨 (JSON도 아니라서 json.loads로는 못 잡음).
_LEADING_INDEX_RE = re.compile(r'^\s*\d+\s*[:.]\s*')

# 한 번의 LLM 호출에 담을 최대 항목 수. 너무 크면(예: 리포트에 표시되는 문서 30건을
# 한 번에 요약) 응답이 max_tokens에서 잘려 JSON 파싱이 통째로 실패하고 전부 원문
# truncate로 대체되는 문제가 실사용 중 발견됨 — 작은 배치로 나눠 호출한다.
_BATCH_SIZE = 6


def _truncate(text: str, limit: int = 200) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    # 공백 기준으로 자연스럽게 자르되, 공백이 없으면(예: 한글이 죽 이어진 텍스트)
    # limit 위치에서 그대로 자른다. rfind()는 못 찾으면 -1을 반환하는데, "-1 or limit"
    # 식으로 쓰면 -1이 참으로 취급돼 버그가 나므로 명시적으로 분기한다.
    cutoff = text.rfind(" ", 0, limit)
    if cutoff <= 0:
        cutoff = limit
    return text[:cutoff] + "..."


def _call_llm(prompt: str, api_key: str | None, provider: str | None) -> str:
    from config.settings import settings

    resolved_provider = provider or settings.llm_provider
    if resolved_provider == "openai":
        import openai

        client = openai.OpenAI(api_key=api_key or settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
    elif resolved_provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=api_key or settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
    else:
        raise ValueError(f"알 수 없는 LLM_PROVIDER: {resolved_provider!r} ('anthropic' 또는 'openai'만 지원)")


def _parse_summary_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json"):].strip()
    return json.loads(text)


def _strip_json_wrapper(text: str) -> str:
    """summarize_group()이 순수 텍스트를 요청해도 모델이 가끔 `{"1": "..."}` 같은
    JSON으로 응답하는 경우가 실사용 중 발견됨 — 그대로 리포트에 노출되지 않도록
    JSON이면 값만 꺼내 이어붙인다. JSON이 아니면 원문을 그대로 반환한다.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json"):].strip()
    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            return " ".join(str(v) for v in parsed.values()).strip()
        if isinstance(parsed, list):
            return " ".join(str(v) for v in parsed).strip()

    # 중괄호 없는 `1: "..."` / `1. "..."` 형태 — 앞의 번호를 떼고, 전체가 따옴표로
    # 감싸져 있으면 그 따옴표도 벗긴다.
    text = _LEADING_INDEX_RE.sub("", text).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def _summarize_batch(
    items: list[tuple[str, str]], max_lines: int, api_key: str | None, provider: str | None
) -> dict[str, str]:
    """items(<= _BATCH_SIZE개)를 LLM 한 번의 호출로 요약한다.

    프롬프트/응답 키로 원본 식별자(URL 등)를 그대로 쓰면 응답 토큰이 커지고, 모델이
    긴 URL을 정확히 그대로 되돌려주지 못해 매칭에 실패하는 경우가 있어 짧은 인덱스
    키("0", "1", ...)를 대신 쓰고 내부적으로 원래 키에 매핑한다.
    """
    fallback = {key: _truncate(text) for key, text in items}
    index_to_key = {str(i): key for i, (key, _) in enumerate(items)}

    body = "\n\n".join(f"[{i}]\n{text[:_MAX_INPUT_CHARS_PER_ITEM]}" for i, (_, text) in enumerate(items))
    prompt = f"""다음은 금융 뉴스/공시/법령 원문 목록입니다. 각 항목을 {max_lines}줄 이내의
한국어 핵심 요약으로 압축하세요. 원문에 없는 숫자·사실을 새로 만들어내지 말고,
원문에 실제로 있는 내용만 요약하세요. 원문이 비어있거나 의미 있는 내용이 없으면
빈 문자열로 응답하세요.

{body}

반드시 아래 JSON 객체 형식으로만 응답하세요 (키는 대괄호 안의 번호와 동일하게):
{{"0": "요약문", "1": "요약문", ...}}
"""

    try:
        raw = _call_llm(prompt, api_key, provider)
        parsed = _parse_summary_response(raw)
    except Exception as e:
        print(f"[경고] 리포트 요약용 LLM 호출 실패, 원문 일부로 대체합니다: {e}")
        return fallback

    result = dict(fallback)
    for idx, summary in parsed.items():
        key = index_to_key.get(str(idx))
        if key and key in result and summary:
            result[key] = summary
    return result


_GROUP_MAX_ITEMS = 20  # 그룹 전체요약 시 입력에 포함할 최대 항목 수 (max_tokens 초과 방지)


def summarize_group(
    texts: list[str],
    max_lines: int = 6,
    api_key: str | None = None,
    provider: str | None = None,
) -> str:
    """여러 원문(예: 공시 30건, 뉴스 20건)을 하나로 묶어 종합 요약 한 편을 만든다.

    개별 항목마다 요약을 나열하지 말고 그룹 전체를 관통하는 핵심 흐름만 max_lines줄
    이내로 정리해달라는 피드백에 따른 함수. 실패 시(키 미설정, API 오류 등) 예외를
    던지지 않고 빈 문자열을 반환한다 — 호출부에서 대체 문구를 붙인다.
    """
    if not texts:
        return ""

    body = "\n\n".join(
        f"[{i + 1}] {t[:_MAX_INPUT_CHARS_PER_ITEM]}" for i, t in enumerate(texts[:_GROUP_MAX_ITEMS])
    )
    prompt = f"""다음은 금융 뉴스/공시 원문 {len(texts[:_GROUP_MAX_ITEMS])}건입니다. 이 항목들을
개별적으로 나열하지 말고, 전체를 관통하는 핵심 내용만 묶어 {max_lines}줄 이내의
한국어 종합 요약 하나로 작성하세요. 원문에 없는 숫자·사실을 새로 만들어내지 마세요.

{body}

요약문만 출력하세요 (JSON, 번호, 따옴표 없이 순수 텍스트로).
"""
    try:
        raw = _call_llm(prompt, api_key, provider)
        return _strip_json_wrapper(raw)
    except Exception as e:
        print(f"[경고] 그룹 종합 요약용 LLM 호출 실패: {e}")
        return ""


def summarize_documents(
    items: list[tuple[str, str]],
    max_lines: int = 3,
    api_key: str | None = None,
    provider: str | None = None,
) -> dict[str, str]:
    """
    (식별자, 원문) 목록을 받아 각각 max_lines줄 이내 요약을 만든다.

    한 번의 LLM 호출에 너무 많은 항목을 담으면 응답이 max_tokens에서 잘려 JSON 파싱이
    통째로 실패하는 문제가 있어(실사용 중 발견 — 리포트 문서 30건 요약이 전부 원문
    truncate로 대체됨), _BATCH_SIZE개씩 나눠 여러 번 호출한다. 한 배치가 실패해도
    그 배치만 원문 일부로 대체되고 나머지 배치는 정상적으로 요약된다.

    items가 비어 있으면 빈 dict를 반환한다.

    Returns:
        {식별자: 요약문} 딕셔너리 (모든 입력 키에 대해 값이 채워짐 — 성공하면 LLM 요약,
        실패하면 원문 일부)
    """
    if not items:
        return {}

    result: dict[str, str] = {}
    for i in range(0, len(items), _BATCH_SIZE):
        batch = items[i : i + _BATCH_SIZE]
        result.update(_summarize_batch(batch, max_lines, api_key, provider))
    return result
