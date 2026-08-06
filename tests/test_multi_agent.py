"""Multi-Agent 팀 오케스트레이션 단위 테스트."""

from unittest.mock import MagicMock, patch

from src.multi_agent import (
    AnalystAgent,
    ComplianceAgent,
    FinancialAgentTeam,
    ReportWriterAgent,
    ResearcherAgent,
)


def test_agent_roles_initialization():
    """전문 에이전트 역할 클래스 생성을 검증한다."""
    researcher = ResearcherAgent(provider="openai", api_key="dummy")
    analyst = AnalystAgent(provider="openai", api_key="dummy")
    compliance = ComplianceAgent(provider="openai", api_key="dummy")
    writer = ReportWriterAgent(provider="openai", api_key="dummy")

    assert researcher.role_name == "Researcher"
    assert analyst.role_name == "Analyst"
    assert compliance.role_name == "Compliance"
    assert writer.role_name == "Writer"


def test_compliance_agent_verify_fact():
    """ComplianceAgent 팩트체크 기능을 검증한다."""
    compliance = ComplianceAgent(provider="openai", api_key="dummy")
    res_empty = compliance.verify_fact([], "분석 텍스트")
    assert res_empty["verified"] is False

    res_valid = compliance.verify_fact([{"title": "공시"}], "분석 텍스트")
    assert res_valid["verified"] is True


@patch("src.agent.core.FinancialAgent.run")
def test_financial_agent_team_run_analysis(mock_run):
    """FinancialAgentTeam 팀 협업 분석 실행을 검증한다."""
    mock_state = MagicMock()
    mock_state.steps = []
    mock_state.final_answer = "팀 분석 완료 보고서"
    mock_run.return_value = mock_state

    team = FinancialAgentTeam(provider="openai", api_key="dummy")
    result = team.run_team_analysis("삼성전자 2026년 실적 분석")

    assert "query" in result
    assert result["query"] == "삼성전자 2026년 실적 분석"
    assert "compliance" in result
    assert "팀 분석 완료 보고서" in result["final_report"]
    assert mock_run.call_count >= 3  # 리서처, 분석가, 리포터, 비판가 순차 호출
