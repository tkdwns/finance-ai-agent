"""FinancialAgent ReAct 대뇌 엔진 단위 테스트."""

from unittest.mock import MagicMock, patch

from src.agent import AgentState, AgentStep, FinancialAgent
from src.agent_tools.registry import ToolRegistry


def test_agent_state_and_step():
    """AgentState 및 AgentStep 데이터 구조 작성을 검증한다."""
    state = AgentState(query="삼성전자 공시 분석해줘")
    assert state.query == "삼성전자 공시 분석해줘"
    assert len(state.steps) == 0

    step = AgentStep(thought="DART 도구를 검색해야겠어", tool_name="search_dart_disclosures", tool_input={"days": 7})
    state.add_step(step)
    assert len(state.steps) == 1
    assert state.steps[0].tool_name == "search_dart_disclosures"


@patch("openai.OpenAI")
def test_financial_agent_openai_react_loop(mock_openai):
    """OpenAI 모델 기반 ReAct 추론 루프 동작을 검증한다."""
    registry = ToolRegistry()

    @registry.register(name="dummy_tool", description="테스트용 도구")
    def dummy_tool(query: str):
        return {"result": f"수집완료: {query}"}

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # 1번째 호출: dummy_tool 실행 요청
    mock_msg_1 = MagicMock()
    mock_msg_1.content = "도구를 실행합니다."
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "dummy_tool"
    mock_tool_call.function.arguments = '{"query": "테스트"}'
    mock_msg_1.tool_calls = [mock_tool_call]
    mock_resp_1 = MagicMock()
    mock_resp_1.choices = [MagicMock(message=mock_msg_1)]

    # 2번째 호출: 최종 답변 완료
    mock_msg_2 = MagicMock()
    mock_msg_2.content = "최종 분석 결과입니다."
    mock_msg_2.tool_calls = None
    mock_resp_2 = MagicMock()
    mock_resp_2.choices = [MagicMock(message=mock_msg_2)]

    mock_client.chat.completions.create.side_effect = [mock_resp_1, mock_resp_2]

    agent = FinancialAgent(provider="openai", api_key="dummy_key", registry=registry)
    state = agent.run("테스트 질문", max_steps=3)

    assert len(state.steps) == 2
    assert state.steps[0].tool_name == "dummy_tool"
    assert state.steps[0].observation == {"result": "수집완료: 테스트"}
    assert state.final_answer == "최종 분석 결과입니다."


@patch("anthropic.Anthropic")
def test_financial_agent_anthropic_react_loop(mock_anthropic):
    """Anthropic 모델 기반 ReAct 추론 루프 동작을 검증한다."""
    registry = ToolRegistry()

    @registry.register(name="dummy_tool", description="테스트용 도구")
    def dummy_tool(query: str):
        return {"result": f"수집완료: {query}"}

    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client

    # 1번째 호출: tool_use 반환
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "dummy_tool"
    tool_block.input = {"query": "테스트"}
    mock_resp_1 = MagicMock()
    mock_resp_1.content = [tool_block]

    # 2번째 호출: text 반환 (최종 답변)
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "클로드 분석 결과입니다."
    mock_resp_2 = MagicMock()
    mock_resp_2.content = [text_block]

    mock_client.messages.create.side_effect = [mock_resp_1, mock_resp_2]

    agent = FinancialAgent(provider="anthropic", api_key="dummy_key", registry=registry)
    state = agent.run("테스트 질문", max_steps=3)

    assert len(state.steps) == 2
    assert state.steps[0].tool_name == "dummy_tool"
    assert state.final_answer == "클로드 분석 결과입니다."
