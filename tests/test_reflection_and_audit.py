"""AuditTrailLogger 및 CriticAgent Self-Reflection 단위 테스트."""

import os
from unittest.mock import MagicMock, patch

from src.multi_agent import CriticAgent, FinancialAgentTeam
from src.storage.audit_trail import AuditTrailLogger


def test_audit_trail_logger(tmp_path):
    """AuditTrailLogger 로그 기록 및 조회 기능을 검증한다."""
    log_file = tmp_path / "test_audit.jsonl"
    logger = AuditTrailLogger(log_path=str(log_file))

    logger.log_event("q123", "Researcher", "CollectData", {"count": 5})
    logger.log_event("q123", "Analyst", "AnalyzeData", {"status": "ok"})

    history = logger.get_history("q123")
    assert len(history) == 2
    assert history[0]["role"] == "Researcher"
    assert history[1]["role"] == "Analyst"


def test_critic_agent_evaluation():
    """CriticAgent 평가 및 자기 반성 피드백을 검증한다."""
    critic = CriticAgent()

    # 부실한 초안
    short_res = critic.evaluate_report("짧은 보고서")
    assert short_res["passed"] is False
    assert "너무 짧고" in short_res["feedback"]

    # 양호한 초안
    good_report = """# 금융 동향 보고서
## 1. 개요
삼성전자 주가 및 공시 동향을 분석한 결과입니다.
## 2. 결론
안정적인 추세입니다."""
    good_res = critic.evaluate_report(good_report)
    assert good_res["passed"] is True


@patch("src.agent.core.FinancialAgent.run")
def test_team_reflection_and_audit_integration(mock_run):
    """FinancialAgentTeam의 감사 로그 및 Reflection 통합 연동을 검증한다."""
    mock_state = MagicMock()
    mock_state.steps = []
    mock_state.final_answer = "# 자율 금융 분석 종합 보고서\n## 1. 개요 및 최근 주요 공시 동향 분석\n삼성전자 주가 및 DART 공시 분석 결과 이상 없음을 최종 승인합니다."
    mock_run.return_value = mock_state

    team = FinancialAgentTeam(provider="openai", api_key="dummy")
    result = team.run_team_analysis("테스트 질의")

    assert "query_id" in result
    assert "critic" in result
    assert result["critic"]["passed"] is True

    # 감사 로그가 적어도 4개 이상 기록되었는지 확인
    audit_history = team.audit_logger.get_history(result["query_id"])
    assert len(audit_history) >= 4
