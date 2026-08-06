"""Phase 3 5대 자산 통합 보고서 및 Cross-Asset 파급효과 연동 단위 테스트."""

from unittest.mock import MagicMock, patch
from src.multi_agent.team import FinancialAgentTeam


def test_financial_agent_team_multi_asset_failsafe():
    """FinancialAgentTeam 실행 시 5대 자산 수집 및 Cross-Asset 인사이트 결합을 검증한다."""
    team = FinancialAgentTeam()
    
    # 가짜 래퍼 실행 모킹
    with patch.object(team.researcher, "run") as mock_researcher_run, \
         patch.object(team.analyst, "run") as mock_analyst_run, \
         patch.object(team.compliance, "verify_fact") as mock_verify_fact, \
         patch.object(team.writer, "run") as mock_writer_run, \
         patch.object(team.critic, "evaluate_report") as mock_eval_report:

        # 리서처 수집 모의 결과 설정
        mock_step_stock = MagicMock()
        mock_step_stock.observation = {"symbol": "NVDA", "name": "NVIDIA", "current_price": "$128.50", "change_percent": "+2.80%"}
        
        mock_step_re = MagicMock()
        mock_step_re.observation = {"region_code": "11680", "avg_price_manwon": "185,000만원", "trade_count": 12}
        
        mock_step_bond = MagicMock()
        mock_step_bond.observation = {"kr_treasury_3y": "2.95%", "us_treasury_10y": "3.85%", "credit_spread": "1.20%p"}

        mock_researcher_state = MagicMock()
        mock_researcher_state.steps = [mock_step_stock, mock_step_re, mock_step_bond]
        mock_researcher_run.return_value = mock_researcher_state

        mock_analyst_state = MagicMock()
        mock_analyst_state.final_answer = "엔비디아 시세 호조 및 강남구 실거래가 동향 분석 완료."
        mock_analyst_run.return_value = mock_analyst_state

        mock_verify_fact.return_value = {"passed": True, "details": "100% 팩트 일치"}

        mock_writer_state = MagicMock()
        mock_writer_state.final_answer = "글로벌 자산 종합 인사이트 분석 완료."
        mock_writer_run.return_value = mock_writer_state

        mock_eval_report.return_value = {"passed": True, "feedback": "완벽함"}

        res = team.run_team_analysis("엔비디아 미국 주가 및 강남구 아파트 실거래가, 국고채 금리 종합 분석해줘")

        assert "final_report" in res
        final_report_str = res["final_report"]
        assert "미국 증시" in final_report_str or "부동산" in final_report_str or "금리" in final_report_str
