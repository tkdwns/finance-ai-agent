"""금융 정보 분석 자율형 AI Agent 시스템 실행 진입점."""

import sys
from config.settings import settings
from src.agent import FinancialAgent
from src.multi_agent import FinancialAgentTeam


def main():
    """자율형 금융 AI Agent 실행 메인 함수."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    missing = settings.validate()
    if missing:
        print(f"[경고] 환경변수 누락: {', '.join(missing)}")
        print(".env 파일을 확인하세요 (.env.example 참고).")
        return

    print("============================================================")
    print("[시스템] 자율형 금융 정보 분석 AI Agent v1.0 가동")
    print(f"실행 환경: {settings.environment} | LLM 제공자: {settings.llm_provider}")
    print("============================================================")

    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
    else:
        user_query = "최근 DART 주요 공시와 한국은행 기준금리 동향을 종합 분석해줘."

    print(f"\n[질의 내용] {user_query}\n")
    print("[팀 가동] Multi-Agent 팀 (리서처 -> 분석가 -> 팩트체커 -> 리포터) 협업 프로세스 시작...")

    team = FinancialAgentTeam()
    result = team.run_team_analysis(user_query)

    report_text = result.get("final_report", "")
    query_id = result.get("query_id", "latest")

    # 산출물 파일 자동 저장
    from pathlib import Path
    out_dir = Path("reports_output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"agent_report_{query_id}.md"
    out_file.write_text(report_text, encoding="utf-8")

    print("\n================ [최종 리포트 분석 결과] ================\n")
    print(report_text or "분석 완료")
    print("\n============================================================")
    print(f"[저장 완료] 보고서 파일 저장 위치: {out_file.resolve()}")
    print("============================================================")


if __name__ == "__main__":
    main()
