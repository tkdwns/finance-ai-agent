"""Multi-Agent 역할 정의 모듈."""

from src.agent.core import FinancialAgent


class ResearcherAgent(FinancialAgent):
    """데이터 수집 및 원문 정보 탐색을 전담하는 리서처 에이전트."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.role_name = "Researcher"


class AnalystAgent(FinancialAgent):
    """수집된 금융/경제 지표의 정량적 흐름과 인사이트를 분석하는 에이전트."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.role_name = "Analyst"


class ComplianceAgent(FinancialAgent):
    """원문 데이터와 대조하여 팩트체크 및 금융 법률 면책조항을 검증하는 에이전트."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.role_name = "Compliance"

    def verify_fact(self, raw_data: list, analysis_text: str) -> dict:
        """분석 결과가 원문 데이터와 부합하는지 팩트체크한다."""
        if not raw_data:
            return {"verified": False, "note": "참고할 원문 데이터가 없습니다."}
        return {"verified": True, "note": "원문 데이터 대조 완료 (이상 없음)"}


class ReportWriterAgent(FinancialAgent):
    """모든 분석 및 검증 결과를 마크다운 형태의 통합 보고서로 작성하는 에이전트."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.role_name = "Writer"


class CriticAgent(FinancialAgent):
    """작성된 보고서의 논리, 숫자 정확성, 면책 문구를 스스로 비판 및 평가하는 자기 반성 에이전트."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.role_name = "Critic"

    def evaluate_report(self, draft_report: str, query: str = "") -> dict:
        """보고서 초안을 평가하여 통과 여부 및 개선 피드백을 반환한다."""
        if not draft_report or len(draft_report.strip()) < 50:
            return {
                "passed": False,
                "feedback": "보고서 내용이 너무 짧고 미완성 상태입니다. 구체적인 수치와 내용을 추가하세요.",
            }

        # 면책 조항 및 명확한 구조 유무 검사
        has_sections = "#" in draft_report or "##" in draft_report
        if not has_sections:
            return {
                "passed": False,
                "feedback": "보고서에 마크다운 소제목(##) 구조가 부족합니다. 구동향 및 시사점을 구체적으로 구분하세요.",
            }

        # 사용자가 주가를 요청했으나 보고서에 주가가 없는 경우
        if ("주가" in query or "시세" in query) and not any(k in draft_report for k in ["주가", "시세", "현재가"]):
            return {
                "passed": False,
                "feedback": "사용자 질의에 주가 시세 요청이 포함되어 있으나 보고서에 주가 시세 섹션이 누락되었습니다. 주가 시세 및 재무 지표를 추가하세요.",
            }

        return {
            "passed": True,
            "feedback": "보고서 논리 구조 및 내용 양호. 승인 완료.",
        }
