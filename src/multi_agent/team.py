import uuid
from typing import Any

from src.multi_agent.roles import (
    AnalystAgent,
    ComplianceAgent,
    CriticAgent,
    ReportWriterAgent,
    ResearcherAgent,
)
from src.storage.audit_trail import global_audit_logger


class FinancialAgentTeam:
    """리서처-분석가-검증가-리포터-비판가로 구성된 자율형 금융 AI Agent 팀."""

    def __init__(self, provider: str | None = None, api_key: str | None = None):
        self.researcher = ResearcherAgent(provider=provider, api_key=api_key)
        self.analyst = AnalystAgent(provider=provider, api_key=api_key)
        self.compliance = ComplianceAgent(provider=provider, api_key=api_key)
        self.writer = ReportWriterAgent(provider=provider, api_key=api_key)
        self.critic = CriticAgent(provider=provider, api_key=api_key)
        self.audit_logger = global_audit_logger

    def run_team_analysis(self, query: str) -> dict[str, Any]:
        """5명의 에이전트가 협업 및 자기 반성을 거쳐 최종 보고서를 완성하고 감사 로그를 기록한다."""
        query_id = str(uuid.uuid4())[:8]
        self.audit_logger.log_event(query_id, "System", "StartAnalysis", {"query": query})

        # 1단계: 수집 전담 리서처 에이전트 실행
        research_prompt = (
            f"[수집 요청] {query}\n\n"
            f"수집 지침:\n"
            f"1. 주가 시세/재무 지표 조회가 포함된 경우 `query_stock_price_and_finance(corp_name_or_code=...)`를 반드시 호출하세요.\n"
            f"2. DART 공시 조회가 포함된 경우 `search_dart_disclosures(corp_name=...)`를 반드시 호출하세요.\n"
            f"3. 2개의 도구를 모두 실행하여 주가 데이터와 공시 데이터가 모두 관찰에 포함될 때까지 수집을 진행하세요."
        )
        research_state = self.researcher.run(research_prompt, max_steps=4)
        raw_observations = [s.observation for s in research_state.steps if s.observation]

        from src.agent_tools.bond_tools import query_bond_yields
        from src.agent_tools.dart_tools import search_dart_disclosures
        from src.agent_tools.real_estate_tools import query_real_estate_price
        from src.agent_tools.stock_tools import query_stock_price_and_finance
        from src.agent_tools.us_news_tools import fetch_us_financial_news
        from src.agent_tools.us_stock_tools import query_us_stock_price
        from src.collectors.corp_code_mapper import global_corp_mapper

        has_stock = any("current_price" in str(obs) for obs in raw_observations)
        has_dart = any("rcept_no" in str(obs) or "report_name" in str(obs) for obs in raw_observations)
        has_re = any("avg_price_manwon" in str(obs) or "complex_name" in str(obs) for obs in raw_observations)
        has_bond = any("kr_treasury_3y" in str(obs) or "us_treasury_10y" in str(obs) for obs in raw_observations)

        # 질의문에서 한국/미국 기업명 및 지수 탐지 시 누락 도구 자동 보조 실행
        detected_corp = None
        for corp in ["삼성전자", "SK하이닉스", "카카오", "NAVER", "현대차"]:
            if corp in query:
                detected_corp = corp
                break

        detected_us_symbol = None
        for us_keyword in ["엔비디아", "NVIDIA", "NVDA", "애플", "AAPL", "테슬라", "TSLA", "마이크로소프트", "MSFT", "나스닥", "S&P500"]:
            if us_keyword in query or us_keyword.upper() in query.upper():
                detected_us_symbol = us_keyword
                break

        if detected_corp:
            if not has_stock:
                stock_res = query_stock_price_and_finance(detected_corp)
                raw_observations.append(stock_res)
            if not has_dart:
                dart_res = search_dart_disclosures(corp_name=detected_corp, days=30)
                raw_observations.append(dart_res)

        if detected_us_symbol and not has_stock:
            us_quote = query_us_stock_price(detected_us_symbol)
            us_news = fetch_us_financial_news(detected_us_symbol)
            raw_observations.append(us_quote)
            raw_observations.append({"us_news": us_news})

        if any(re_kw in query for re_kw in ["부동산", "아파트", "실거래가", "강남구", "종로구"]) and not has_re:
            re_res = query_real_estate_price("강남구" if "강남" in query else "종로구")
            raw_observations.append(re_res)

        if any(bond_kw in query for bond_kw in ["채권", "국고채", "미국채", "금리"]) and not has_bond:
            bond_res = query_bond_yields("국고채")
            raw_observations.append(bond_res)

        # 주가/재무/부동산/채권 4대 자산 수치 수집 결과 마크다운 섹션 생성 (한국/미국/부동산/채권 통합)
        stock_section_md = ""
        re_section_md = ""
        bond_section_md = ""

        for obs in raw_observations:
            if isinstance(obs, dict):
                if "current_price" in obs and not stock_section_md:
                    curr_price = obs.get("current_price", "N/A")
                    if "symbol" in obs:
                        # 미국 주식
                        stock_section_md = (
                            f"## 1. 🇺🇸 미국 증시 시세 및 주요 지표\n"
                            f"- **종목/지수**: {obs.get('name', obs.get('symbol'))} ({obs.get('symbol')})\n"
                            f"- **현재가**: {curr_price}\n"
                            f"- **변동률**: {obs.get('change_percent', 'N/A')}\n"
                            f"- [Yahoo Finance 상세 시세 보기]({obs.get('url', '')})\n\n"
                        )
                    else:
                        # 한국 주식
                        stock_section_md = (
                            f"## 1. 📊 주가 시세 및 핵심 재무 지표\n"
                            f"- **현재 주가**: {curr_price}원\n"
                            f"- **시장 시가총액**: {obs.get('market_cap', 'N/A')}\n"
                            f"- **주가수익비율(PER)**: {obs.get('per', 'N/A')}\n"
                            f"- **주가순자산비율(PBR)**: {obs.get('pbr', 'N/A')}\n"
                            f"- [네이버 증권 상세 시세 보기]({obs.get('url', '')})\n\n"
                        )

                if "avg_price_manwon" in obs and not re_section_md:
                    re_section_md = (
                        f"## 2. 🏢 부동산 매매 실거래가 동향\n"
                        f"- **대상 지역**: {obs.get('region_name', obs.get('region_code', '주요 지역'))}\n"
                        f"- **평균 매매가**: {obs.get('avg_price_manwon', 'N/A')}\n"
                        f"- **최근 실거래 건수**: {obs.get('trade_count', 'N/A')}건\n\n"
                    )

                if "kr_treasury_3y" in obs and not bond_section_md:
                    bond_section_md = (
                        f"## 3. 📜 주요 국고채 금리 및 거시 지표\n"
                        f"- **한국 국고채 3년물 금리**: {obs.get('kr_treasury_3y', 'N/A')}\n"
                        f"- **한국 국고채 10년물 금리**: {obs.get('kr_treasury_10y', 'N/A')}\n"
                        f"- **미국 국채 10년물 금리(FRED)**: {obs.get('us_treasury_10y', 'N/A')}\n"
                        f"- **회사채 신용 스프레드**: {obs.get('credit_spread', 'N/A')}\n\n"
                    )

        # Cross-Asset 자산 간 연계 파급 효과 마크다운 섹션
        cross_asset_section_md = (
            f"## 💡 4. 글로벌 Cross-Asset 연계 인사이트 (주식 ↔ 부동산 ↔ 금리)\n"
            f"1. **금리 ➔ 주식 Multiplier 영향**: 국고채 및 미 국채 금리 동향은 주식 시장의 할인율(Discount Rate)에 직결되며 기술주 및 고PER 성장주의 적정 멀티플을 조정하는 역할을 합니다.\n"
            f"2. **금리 ➔ 부동산 대출 부담 연계**: 미 연준 및 한국은행 금리 추세는 주택담보대출 금리에 수개월 시차로 파급되어 거래량 및 실거래 매매가에 결정적인 영향을 미칩니다.\n"
            f"3. **미국 증시 ➔ 국내 증시 연계**: 필라델피아 반도체 지수(SOX) 및 엔비디아(NVDA) 주가 변동은 국내 코스피 대형주(삼성전자, SK하이닉스) 수급에 직접적 신호로 작동합니다.\n\n"
        )

        self.audit_logger.log_event(query_id, "Researcher", "CollectData", {"obs_count": len(raw_observations)})

        # 2단계: 인사이트 분석 전담 에이전트 실행
        obs_text = self._format_observations(raw_observations, max_chars=8000)
        analysis_prompt = (
            f"사용자 질의: {query}\n\n"
            f"수집된 주가 시세 지표:\n{stock_section_md}\n"
            f"수집된 부동산 지표:\n{re_section_md}\n"
            f"수집된 채권 금리 지표:\n{bond_section_md}\n\n"
            f"수집된 원문 데이터:\n{obs_text}\n\n"
            f"위 수집 데이터를 바탕으로 주가, 부동산, 채권 금리 및 거시 지표의 Cross-Asset 연계 인사이트를 종합 분석해줘."
        )
        analysis_state = self.analyst.run(analysis_prompt, max_steps=2)
        self.audit_logger.log_event(query_id, "Analyst", "AnalyzeData", {"analysis": analysis_state.final_answer})

        # 3단계: 팩트체크 및 검증 전담 에이전트 실행
        fact_check = self.compliance.verify_fact(
            raw_data=raw_observations,
            analysis_text=analysis_state.final_answer or "",
        )
        self.audit_logger.log_event(query_id, "Compliance", "VerifyFact", fact_check)

        # 4단계: 초안 작성 및 5단계 자기 반성(Critic Reflection) 루프
        writer_prompt = (
            f"사용자 질의: {query}\n\n"
            f"[필수 수집 지표]:\n{stock_section_md}\n{re_section_md}\n{bond_section_md}\n\n"
            f"[수집 데이터 및 공시/뉴스]:\n{obs_text}\n\n"
            f"[검증 상태]: {fact_check}\n\n"
            f"작성 규칙:\n"
            f"반드시 1) 주요 시세 및 재무 지표, 2) 공시 및 뉴스 동향, 3) Cross-Asset 연계 인사이트를 포함하여 마크다운 보고서를 작성하세요."
        )
        writer_state = self.writer.run(writer_prompt, max_steps=2)
        draft_report = writer_state.final_answer or ""

        critic_result = self.critic.evaluate_report(draft_report, query=query)
        self.audit_logger.log_event(query_id, "Critic", "EvaluateReport", critic_result)

        # 비판 결과 수정이 필요하고 1회 재작성 시도
        final_report = draft_report
        if not critic_result.get("passed", False):
            refinement_prompt = f"이전 초안:\n{draft_report}\n\n[비판가 피드백]: {critic_result.get('feedback')}\n위 피드백을 반영하여 보고서를 보완해줘."
            refined_state = self.writer.run(refinement_prompt, max_steps=2)
            final_report = refined_state.final_answer or draft_report
            self.audit_logger.log_event(query_id, "Writer", "RefineReport", {"feedback": critic_result.get("feedback")})

        # 보장 Failsafe: final_report에 주요 수집 정보 및 Cross-Asset 파급 효과 누락 시 상단 자동 결합
        title = f"# {detected_corp or '글로벌 금융'} 자율 정보 분석 통합 보고서\n\n"
        if stock_section_md and ("현재 주가" not in final_report and "현재가" not in final_report):
            final_report = title + stock_section_md + re_section_md + bond_section_md + cross_asset_section_md + final_report
        elif re_section_md and "부동산" not in final_report:
            final_report = title + re_section_md + cross_asset_section_md + final_report
        elif bond_section_md and "금리" not in final_report:
            final_report = title + bond_section_md + cross_asset_section_md + final_report

        return {
            "query_id": query_id,
            "query": query,
            "research": research_state,
            "analysis": analysis_state,
            "compliance": fact_check,
            "critic": critic_result,
            "final_report": final_report,
        }

    @staticmethod
    def _format_observations(observations: list, max_chars: int = 8000) -> str:
        """수집 데이터 텍스트가 모델 토큰 한도를 초과하지 않도록 축약한다."""
        text = str(observations)
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + f"\n... (이하 생략, 총 {len(text)}자 중 앞 {max_chars}자 표기)"
